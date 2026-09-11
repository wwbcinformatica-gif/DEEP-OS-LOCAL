"""
DEEP-OS WebSocket Terminal — endpoint /ws/terminal
Shell: powershell.exe com sessão persistente.
"""

import asyncio
import logging
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.config import get_base_dir

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)

logger = logging.getLogger(__name__)
router = APIRouter()

_sessions: dict[str, dict] = {}
_SESSION_TIMEOUT = 300  # 5 min


async def _create_session(session_id: str, root: str = "") -> dict:
    import platform
    cwd = root if root and Path(root).exists() else str(get_base_dir())
    if platform.system() == "Windows":
        proc = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        shell_name = "powershell"
    else:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        shell_name = "bash"
    session = {
        "process": proc,
        "last_active": time.time(),
        "bootstrapped": False,
    }
    _sessions[session_id] = session
    logger.info(f"[WS] Session {session_id[:8]} created ({shell_name}, cwd={cwd})")
    return session


async def _ensure_session(session_id: str, root: str = "") -> dict:
    if session_id in _sessions:
        session = _sessions[session_id]
        proc = session["process"]
        if proc.returncode is not None:
            del _sessions[session_id]
            return await _create_session(session_id, root)
        session["last_active"] = time.time()
        return session
    return await _create_session(session_id, root)


@router.websocket("/ws/terminal")
async def ws_terminal(websocket: WebSocket, session_id: str = "", root: str = ""):
    await websocket.accept()
    if not session_id:
        session_id = str(uuid.uuid4())[:12]

    await websocket.send_json({"type": "session", "session_id": session_id})

    # Resolve workspace root
    workspace_root = root if root and Path(root).exists() else str(get_base_dir())

    try:
        session = await _ensure_session(session_id, workspace_root)
        proc = session["process"]
        session["last_active"] = time.time()

        # Bootstrap apenas na primeira conex�o desta sess�o
        if not session.get("bootstrapped"):
            import platform
            if platform.system() == "Windows":
                proc.stdin.write(b"$function:prompt = { 'WBC:' ++ (Get-Location).Path + '> ' }\r\n")
                proc.stdin.write(b"cd '" + workspace_root.encode("utf-8") + b"'\r\n")
                proc.stdin.write(b"Write-Host 'WBC_TERMINAL_READY'\r\n")
                await proc.stdin.drain()
                await asyncio.sleep(0.3)
                session["bootstrapped"] = True
                await websocket.send_json({"type": "cwd", "path": workspace_root})
                await websocket.send_json({"type": "output", "data": f"WBC:{workspace_root}> "})
            else:
                proc.stdin.write(b"cd '" + workspace_root.encode("utf-8") + b"'\n")
                proc.stdin.write(b"echo 'WBC_TERMINAL_READY'\n")
                await proc.stdin.drain()
                await asyncio.sleep(0.2)
                session["bootstrapped"] = True
                await websocket.send_json({"type": "cwd", "path": workspace_root})
                await websocket.send_json({"type": "output", "data": f"WBC:{workspace_root}$ "})

        async def read_stdout():
            while True:
                try:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=1.0
                    )
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace")
                    # Pular linhas de bootstrap/defini��o de prompt
                    if "WBC_TERMINAL_READY" in text or "$function:prompt" in text or "function prompt" in text:
                        continue
                    # Detecta cwd a partir do prompt: "WBC:C:\path>"
                    m = re.match(r"WBC:\s*$", text.strip())
                    if m:
                        cwd = m.group(1).strip()
                        try:
                            await websocket.send_json({"type": "cwd", "path": cwd})
                        except Exception:
                            break
                    try:
                        await websocket.send_json({"type": "output", "data": strip_ansi(text)})
                    except Exception:
                        break
                    session["last_active"] = time.time()
                except asyncio.TimeoutError:
                    continue
                except RuntimeError:
                    # Another coroutine is already reading � wait and retry
                    await asyncio.sleep(0.1)
                    continue

        async def write_stdin():
            try:
                while True:
                    data = await websocket.receive_json()
                    if data.get("type") == "input":
                        raw = data.get("data", "")
                        if raw.strip().lower() == "clear":
                            await websocket.send_json({"type": "clear"})
                            continue
                        # Envia para o PowerShell
                        payload = raw.replace("\r", "\r\n")
                        proc.stdin.write(payload.encode("utf-8"))
                        await proc.stdin.drain()
                        session["last_active"] = time.time()
                        # Local echo � PowerShell n�o retorna chars individuais via pipe
                        for ch in raw:
                            if ch == "\r":
                                await websocket.send_json({"type": "output", "data": "\r\n"})
                            elif ch == "\x7f":
                                await websocket.send_json({"type": "output", "data": "\b \b"})
                            elif ch == "\t":
                                pass  # tab completion � tratado pelo PowerShell
                            elif ch == "\x03":
                                await websocket.send_json({"type": "output", "data": "^C\r\n"})
                            elif ord(ch) >= 0x20:
                                await websocket.send_json({"type": "output", "data": ch})
            except Exception:
                pass

        async def keepalive():
            while True:
                await asyncio.sleep(25)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

        read_task = asyncio.create_task(read_stdout())
        write_task = asyncio.create_task(write_stdin())
        keep_task = asyncio.create_task(keepalive())

        done, pending = await asyncio.wait(
            [read_task, write_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        keep_task.cancel()
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        logger.info(f"[WS] Session {session_id[:8]} websocket disconnected")
    except Exception as e:
        logger.error(f"[WS] Session {session_id[:8]} error: {e}")
