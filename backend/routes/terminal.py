"""
WBC Terminal - WebSocket-based real terminal with persistent shell sessions
Suporta powershell.exe e cmd.exe com sessao persistente.
"""
import asyncio
import logging
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.config import get_base_dir

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)

logger = logging.getLogger(__name__)
router = APIRouter()

# -- Sess�es Shell Persistentes ------------------------------------------
# _sessions[session_id] = { "process": asyncio.subprocess.Process,
#                            "last_active": float,
#                            "workdir": str }

_sessions: dict[str, dict] = {}
_SESSION_TIMEOUT = 300  # 5 min de inatividade

class TerminalCommand(BaseModel):
    command: str
    workdir: str = ""
    session_id: str = ""


async def _cleanup_stale_sessions():
    """Remove sess�es inativas a cada minuto"""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        stale = [sid for sid, s in _sessions.items()
                 if now - s.get("last_active", now) > _SESSION_TIMEOUT]
        for sid in stale:
            session = _sessions.pop(sid, None)
            if session:
                try:
                    session["process"].kill()
                    await session["process"].wait()
                except Exception:
                    pass
                logger.info(f"Session {sid[:8]} cleaned up (timeout)")


async def _create_session(session_id: str, workdir: str) -> dict:
    """Cria uma nova sessao shell (bash no Linux, cmd.exe no Windows)"""
    import platform
    cwd = workdir if workdir and Path(workdir).exists() else str(get_base_dir())
    if platform.system() == "Windows":
        process = await asyncio.create_subprocess_exec(
            "cmd.exe",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
    else:
        process = await asyncio.create_subprocess_exec(
            "bash",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
    session = {
        "process": process,
        "last_active": time.time(),
        "workdir": cwd,
    }
    _sessions[session_id] = session
    logger.info(f"Session {session_id[:8]} created (cwd={cwd})")
    return session


async def _ensure_session(session_id: str, workdir: str = "") -> dict:
    """Recupera ou cria uma sess�o"""
    if session_id in _sessions:
        session = _sessions[session_id]
        proc = session["process"]
        if proc.returncode is not None:
            # Sess�o morta, recria
            del _sessions[session_id]
            return await _create_session(session_id, workdir)
        session["last_active"] = time.time()
        return session
    return await _create_session(session_id, workdir)


# -- HTTP endpoints (legacy, manter compatibilidade) ---------------------

BUILTINS = {
    "help": (
        "Comandos dispon�veis:\n"
        "  help          � mostra esta ajuda\n"
        "  clear         � limpa o terminal (frontend)\n"
        "  status        � status do projeto\n"
        "  pwd           � diret�rio atual\n"
        "  (qualquer comando do sistema)"
    ),
    "status": (
        "DEEP-OS\n"
        "Backend: FastAPI + WebSocket Terminal\n"
        "Frontend: React + xterm.js\n"
        f"Raiz do projeto: {get_base_dir()}"
    ),
}


@router.post("/terminal")
async def run_terminal(body: TerminalCommand):
    """Endpoint HTTP legado para compatibilidade"""
    cmd = body.command.strip()
    if not cmd:
        return {"stdout": "", "stderr": "", "returncode": 0}

    cmd_lower = cmd.lower().split()[0]
    if cmd_lower in BUILTINS:
        return {"stdout": BUILTINS[cmd_lower], "stderr": "", "returncode": 0}
    if cmd_lower == "clear":
        return {"stdout": "", "stderr": "", "returncode": 0}

    # Usa sess�o persistente para comandos HTTP tamb�m
    sid = body.session_id or "http_default"
    try:
        session = await _ensure_session(sid, body.workdir)
        proc = session["process"]
        proc.stdin.write(f"{cmd}\r\n".encode())
        proc.stdin.write(b"echo __WBC_CMD_DONE__\r\n")
        await proc.stdin.drain()
        session["last_active"] = time.time()

        # L� at� o marcador
        output = ""
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
            decoded = line.decode("utf-8", errors="replace")
            if "__WBC_CMD_DONE__" in decoded:
                break
            output += decoded

        # Captura o diret�rio atual ap�s o comando
        cwd = ""
        try:
            proc.stdin.write(b"cd\r\n")
            proc.stdin.write(b"echo __WBC_CWD_DONE__\r\n")
            await proc.stdin.drain()
            cwd_output = ""
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
                decoded = line.decode("utf-8", errors="replace")
                if "__WBC_CWD_DONE__" in decoded:
                    break
                cwd_output += decoded
            cwd = cwd_output.strip().split("\n")[-1].strip() if cwd_output.strip() else ""
        except Exception:
            cwd = os.getcwd()

        return {"stdout": strip_ansi(output), "stderr": "", "returncode": 0, "cwd": cwd}
    except asyncio.TimeoutError:
        return {"stdout": "", "stderr": "Timeout", "returncode": 124}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": 1}


# -- WebSocket Terminal (real-time) --------------------------------------

@router.websocket("/terminal/ws")
async def terminal_websocket(websocket: WebSocket, session_id: str = ""):
    await websocket.accept()
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())[:12]

    await websocket.send_json({"type": "session", "session_id": session_id})

    try:
        session = await _ensure_session(session_id)
        proc = session["process"]
        session["last_active"] = time.time()

        # Envia prompt inicial e mostra diretorio
        proc.stdin.write(b"@echo off\r\n")
        await proc.stdin.drain()
        await asyncio.sleep(0.1)
        proc.stdin.write(b"echo WBC_TERMINAL_READY && cd\r\n")
        await proc.stdin.drain()

        # Task: ler stdout continuamente
        async def read_stdout():
            while True:
                try:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=1.0
                    )
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace")
                    # Suppress echo of @echo off command itself
                    if text.strip() == "@echo off":
                        continue
                    # -- Detecta marcador de diret�rio atual --
                    if "__WBC_CWD__" in text:
                        import re as _re
                        m = _re.search(r"__WBC_CWD__(.*?)__WBC_CWD__", text)
                        if m:
                            cwd = m.group(1).strip()
                            try:
                                await websocket.send_json({"type": "cwd", "path": cwd})
                            except Exception:
                                pass
                        continue
                    try:
                        await websocket.send_json({
                            "type": "output",
                            "data": text,
                        })
                    except Exception:
                        break
                    session["last_active"] = time.time()
                except asyncio.TimeoutError:
                    continue  # Keep reading � not an error

        # Task: receber input do cliente
        async def write_stdin():
            try:
                while True:
                    data = await websocket.receive_json()
                    if data.get("type") == "input":
                        raw = data.get("data", "")
                        if raw.strip().lower() == "clear":
                            await websocket.send_json({"type": "clear"})
                            continue
                        # Windows pipe: send \r\n for Enter, raw chars otherwise
                        payload = raw.replace("\r", "\r\n")
                        proc.stdin.write(payload.encode("utf-8"))
                        await proc.stdin.drain()
                        session["last_active"] = time.time()

                        # -- Ap�s Enter, captura o diret�rio atual --
                        if "\r" in raw:
                            await asyncio.sleep(0.05)
                            cwd_query = b"\r\necho __WBC_CWD__%cd%__WBC_CWD__\r\n"
                            proc.stdin.write(cwd_query)
                            await proc.stdin.drain()
            except Exception:
                pass

        read_task = asyncio.create_task(read_stdout())
        write_task = asyncio.create_task(write_stdin())

        done, pending = await asyncio.wait(
            [read_task, write_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        logger.info(f"Session {session_id[:8]} websocket disconnected")
    except Exception as e:
        logger.error(f"Session {session_id[:8]} error: {e}")
    finally:
        pass


# -- Session Management --------------------------------------------------

@router.get("/terminal/sessions")
async def list_sessions():
    """Lista sess�es ativas"""
    return {
        "sessions": [
            {
                "id": sid,
                "active_seconds": int(time.time() - s["last_active"]),
                "workdir": s.get("workdir", ""),
            }
            for sid, s in _sessions.items()
            if s["process"].returncode is None
        ]
    }


@router.post("/terminal/session/{session_id}/kill")
async def kill_session(session_id: str):
    """Mata uma sess�o espec�fica"""
    session = _sessions.pop(session_id, None)
    if session:
        try:
            session["process"].kill()
            await session["process"].wait()
        except Exception:
            pass
        return {"status": "killed"}
    return {"status": "not_found"}


# Cleanup � iniciado via startup event no main.py
# start_cleanup() � chamado por app.add_event_handler("startup", ...)
