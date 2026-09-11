"""
MiMo Executor - Intercepta ações conhecidas (igual Charon) e executa diretamente.
Para o resto, delega ao mimo.exe.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional
from urllib.parse import quote_plus

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIONS_DIR = str(_PROJECT_ROOT / "actions")
BACKEND_DIR = str(_PROJECT_ROOT / "backend")
MIMO_EXE = str(_PROJECT_ROOT / ".mimocode" / "bin" / "mimo.exe")

for d in [str(_PROJECT_ROOT), ACTIONS_DIR, BACKEND_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

# ── Importa actions do Charon ──────────────────────────────────────────────
_ACTIONS = {}
try:
    from youtube_video import youtube_video as _yt
    from open_app import open_app as _open_app
    from weather_report import weather_action as _weather
    from computer_settings import computer_settings as _comp_settings
    from browser_control import browser_control as _browser
    from computer_control import computer_control as _comp_control
    from desktop import desktop_control as _desktop
    from reminder import reminder as _reminder
    from system_monitor import get_system_status as _sys_status
    from calorie_counter import run as _calorie_counter
    from pushup_counter import run as _pushup_counter
    from upload_video import run as _upload_video
    _ACTIONS = {
        "youtube": _yt, "open_app": _open_app, "weather": _weather,
        "computer_settings": _comp_settings, "browser": _browser,
        "computer_control": _comp_control, "desktop": _desktop,
        "reminder": _reminder, "calorie_counter": _calorie_counter,
        "pushup_counter": _pushup_counter, "upload_video": _upload_video,
    }
    _SYS_STATUS = _sys_status
except ImportError as e:
    print(f"[MiMoExecutor] Aviso: nem todas as actions foram importadas: {e}")
    _SYS_STATUS = None

import subprocess


def _detect_action(message: str) -> Optional[Dict[str, Any]]:
    """Detecta se a mensagem pede uma ação conhecida (YouTube, abrir app, etc.)"""
    q = message.lower().strip()

    # ── YouTube ──────────────────────────────────────────────────────────
    yt_match = re.search(
        r'(?:abra|abrir|toque|tocar|reproduza|reproduzir|playing|play|coloque|colocar|assistir|veja|video|musica|música|canal)\b.*(?:no\s+)?(?:youtube|yt)',
        q
    )
    if not yt_match:
        yt_match = re.search(
            r'(?:youtube|yt)\b.*(?:abra|abrir|toque|tocar|reproduza|reproduzir|play|pesquis|busca|procure)',
            q
        )
    if yt_match:
        # Remove palavras-chave e artefatos para extrair só a query
        query = q
        for pattern in [
            r'(?:no\s+)?(?:youtube|yt)\s*',
            r'(?:abra|abrir|toque|tocar|reproduza|reproduzir|playing|play|coloque|colocar|assistir|veja|video|videos|musica|música|canal|pesquise|pesquisar|busca|procure)\s*',
            r'(?:e\s+)?(?:pesquis|busca|procure)\s*(?:videos?|musicas?|por\s+)?\s*',
            r'(?:por\s+favor|please|pra\s+mim|pra\s+eu)\s*$',
            r'(?:uma\s+)?(?:musica|music)\s+(?:do|da|de)\s+',
            r'\b(?:o|a|e|de|do|da|no|na)\b\s+',
        ]:
            query = re.sub(pattern, ' ', query, count=1)
        query = ' '.join(query.split()).strip().strip('"\'').strip()
        if query:
            return {"type": "youtube_play", "query": query}

    # ── Abrir aplicação ──────────────────────────────────────────────────
    app_match = re.search(
        r'(?:abra|abrir|inicie|iniciar|abre|execute|executar|launch|open)\s+(.+?)(?:\s+por\s+favor|\s+please|\s+pra\s+mim|\s+pra\s+eu|$)',
        q
    )
    if app_match:
        app_name = app_match.group(1).strip()
        app_name = re.sub(r'\s*(o|a|os|as|no|na|no\s+youtube)\s*$', '', app_name).strip()
        # Remove artigo inicial
        app_name = re.sub(r'^(o|a|os|as)\s+', '', app_name).strip()
        if app_name and len(app_name) < 50 and app_name not in ('youtube', 'yt'):
            return {"type": "open_app", "app_name": app_name}

    # ── Clima/Weather ────────────────────────────────────────────────────
    weather_match = re.search(
        r'(?:clima|tempo|temperatura|temp\s+em|weather)\s+(?:em|de|na|no)\s+(.+?)(?:\s+hoje|\s+agora|\s+por\s+favor|$)',
        q
    )
    if weather_match:
        city = weather_match.group(1).strip()
        return {"type": "weather", "city": city}

    # ── Calorias / Nutricao ──────────────────────────────────────────────
    calorie_match = re.search(
        r'(?:calori|caloria|calorias|calories|nutri[çc][aã]o|nutri[cç]ao|quantas?\s+calorias?|quanto\s+(?:tem|tem\s+de)\s+caloria)',
        q
    )
    if calorie_match:
        return {"type": "calorie_counter", "query": message}

    # ── Flexao / Pushup ──────────────────────────────────────────────────
    pushup_match = re.search(
        r'(?:flex[aã]o|flex[aõ]es|pushup|push-ups?|pushup|count\s+my\s+pushup)',
        q
    )
    if pushup_match:
        target = 0
        target_match = re.search(r'(\d+)\s*(?:flex|pushup|rep)', q)
        if target_match:
            target = int(target_match.group(1))
        return {"type": "pushup_counter", "query": message, "target": target}

    # ── Upload TikTok ────────────────────────────────────────────────────
    upload_match = re.search(
        r'(?:upload|postar|post|enviar|compartilhar|subir).*(?:tiktok|tik\s*tok)',
        q
    )
    if upload_match:
        return {"type": "upload_video", "description": message}

    return None


def _execute_action(action: Dict[str, Any]) -> str:
    """Executa uma ação detectada e retorna o resultado como texto."""
    try:
        atype = action["type"]

        if atype == "youtube_play":
            r = _ACTIONS["youtube"](
                parameters={"action": "play", "query": action["query"]},
                response=None, player=None
            )
            return r or "Video aberto."

        elif atype == "open_app":
            r = _ACTIONS["open_app"](
                parameters={"app_name": action["app_name"]},
                response=None, player=None
            )
            return r or f"{action['app_name']} aberto."

        elif atype == "weather":
            r = _ACTIONS["weather"](
                parameters={"city": action["city"]},
                player=None
            )
            return r or "Clima obtido."

        elif atype == "calorie_counter":
            r = _ACTIONS["calorie_counter"](
                parameters={"query": action["query"]},
                player=None
            )
            return r or "Analise de calorias concluida."

        elif atype == "pushup_counter":
            r = _ACTIONS["pushup_counter"](
                parameters={"query": action["query"], "target": action.get("target", 0)},
                player=None
            )
            return r or "Sessao de flexoes concluida."

        elif atype == "upload_video":
            r = _ACTIONS["upload_video"](
                parameters={"description": action["description"]},
                player=None
            )
            return r or "Upload iniciado."

    except Exception as e:
        return f"Erro ao executar ação: {e}"

    return ""


async def stream_mimo_task(
    message: str,
    model: str = "xiaomi/mimo-v2.5",
    root: str = "",
    timeout: int = 300,
    history: list = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Intercepta ações conhecidas e executa diretamente (igual Charon).
    Para o resto, delega ao mimo.exe.
    """
    # ── 1. Detecta e executa ação conhecida ─────────────────────────────
    action = _detect_action(message)
    if action:
        yield {"type": "tool_start", "tool": action["type"], "params": action}
        result_text = await asyncio.to_thread(_execute_action, action)
        yield {"type": "tool_end", "tool": action["type"], "result": {"output": result_text}}
        yield {"type": "content", "data": result_text}
        yield {"type": "done", "content": result_text, "tool_calls": [{"tool": action["type"], "params": action, "result": {"output": result_text}}]}
        return

    # ── 2. Sem ação detectada: delega ao mimo.exe ───────────────────────
    full_message = message
    if history:
        context_parts = []
        for msg in history[-15:]:
            role = "Usuario" if msg["role"] == "user" else "Assistente"
            context_parts.append(f"{role}: {msg['content'][:500]}")
        context_str = "\n".join(context_parts)
        full_message = f"[CONTEXTO DA CONVERSA]\n{context_str}\n[FIM DO CONTEXTO]\n\nMensagem atual: {message}"

    cmd = [
        MIMO_EXE, "run", full_message,
        "--format", "json",
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    if root:
        cmd.extend(["--dir", root])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        full_content = ""
        full_reasoning = ""
        tool_events = []

        while True:
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                yield {"type": "error", "message": f"Timeout apos {timeout}s"}
                break

            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")
            part = event.get("part", {})

            if event_type == "text":
                text = part.get("text", "")
                if text:
                    full_content += text
                    yield {"type": "content", "data": text}

            elif event_type == "reasoning":
                text = part.get("text", "") or part.get("content", "")
                if text:
                    full_reasoning += text
                    yield {"type": "content", "data": text}

            elif event_type == "tool_use":
                tool_name = part.get("tool", "")
                state = part.get("state", {})
                tool_input = state.get("input", {})
                tool_output = state.get("output", "")
                tool_status = state.get("status", "")

                if tool_name and tool_status == "completed":
                    yield {"type": "tool_start", "tool": tool_name, "params": tool_input}
                    result = {"output": tool_output} if tool_output else {"status": "ok"}
                    if isinstance(tool_output, dict):
                        result = tool_output
                    yield {"type": "tool_end", "tool": tool_name, "result": result}
                    tool_events.append({
                        "tool": tool_name,
                        "params": tool_input,
                        "result": result,
                    })

            elif event_type == "error":
                err = event.get("error", {})
                err_data = err.get("data", {})
                err_msg = err_data.get("message", "") or str(err)
                yield {"type": "error", "message": err_msg}

        await process.wait()

        if process.returncode != 0:
            stderr_data = await process.stderr.read()
            stderr_str = stderr_data.decode("utf-8", errors="replace")
            if stderr_str and not full_content:
                yield {"type": "error", "message": f"mimo.exe erro: {stderr_str[:500]}"}

        yield {
            "type": "done",
            "content": full_content,
            "reasoning": full_reasoning,
            "tool_calls": tool_events,
        }

    except FileNotFoundError:
        yield {"type": "error", "message": f"mimo.exe nao encontrado em {MIMO_EXE}"}
    except Exception as e:
        yield {"type": "error", "message": f"Erro ao executar mimo.exe: {str(e)}"}


async def run_mimo_task(
    message: str,
    model: str = "xiaomi/mimo-v2.5",
    root: str = "",
    timeout: int = 300,
) -> Dict[str, Any]:
    result = {"content": "", "tool_calls": [], "reasoning": "", "error": None}
    async for event in stream_mimo_task(message, model, root, timeout):
        if event["type"] == "content":
            result["content"] += event.get("data", "")
        elif event["type"] == "error":
            result["error"] = event.get("message", "")
        elif event["type"] == "done":
            result["content"] = event.get("content", result["content"])
            result["tool_calls"] = event.get("tool_calls", [])
            result["reasoning"] = event.get("reasoning", "")
    return result
