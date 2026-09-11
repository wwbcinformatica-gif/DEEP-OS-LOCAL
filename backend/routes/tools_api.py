import re
import subprocess
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import ALLOWED_BASH, get_base_dir
from core.models import ToolBash, ToolRead, ToolWrite
from core.security import validate_message_length
from tools.system_tools import tool_read, tool_write

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

def _check_sandbox(command: str):
    """Verifica se o modo restrito do sandbox está ativo e bloqueia comandos que acessam outros drives."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if not config_path.exists():
        return  # Sem config, permite
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and data.get("security", {}).get("sandbox_enabled", False):
            # Modo restrito ativo — inspeciona o comando
            cmd_lower = command.strip().lower()
            drives_blocked = [r"d:", r"d:\\", r"i:", r"i:\\", r"e:", r"e:\\",
                              r"f:", r"f:\\", r"g:", r"g:\\", r"h:", r"h:\\",
                              r"j:", r"j:\\", r"k:", r"k:\\", r"l:", r"l:\\",
                              r"m:", r"m:\\", r"n:", r"n:\\", r"o:", r"o:\\",
                              r"p:", r"p:\\", r"q:", r"q:\\", r"r:", r"r:\\",
                              r"s:", r"s:\\", r"t:", r"t:\\", r"u:", r"u:\\",
                              r"v:", r"v:\\", r"x:", r"x:\\", r"y:", r"y:\\",
                              r"z:", r"z:\\"]
            # Verifica caminhos absolutos fora do projeto
            project_root = str(get_base_dir()).lower()
            for blocked in drives_blocked:
                if blocked in cmd_lower:
                    # Permite apenas se for exatamente o drive do projeto
                    if not cmd_lower.startswith(project_root[:2]):
                        raise HTTPException(
                            status_code=403,
                            detail="Acesso Negado: O terminal está bloqueado pelo Modo Restrito."
                        )
            # Verifica caminhos absolutos com \ que fogem do projeto
            if "\\" in cmd_lower:
                import re
                abs_paths = re.findall(r'[a-zA-Z]:\\\\[^\\\s]+', cmd_lower)
                for p in abs_paths:
                    if not p.lower().startswith(project_root[:2]):
                        raise HTTPException(
                            status_code=403,
                            detail="Acesso Negado: O terminal está bloqueado pelo Modo Restrito."
                        )
    except HTTPException:
        raise
    except Exception:
        pass  # Se erro ao ler config, permite execução normal

@router.post("/tool/read")
@limiter.limit("60/minute")
async def api_tool_read(request: Request, payload: ToolRead):
    try:
        return await tool_read(payload.path, payload.root)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tool/write")
@limiter.limit("30/minute")
async def api_tool_write(request: Request, payload: ToolWrite):
    if not validate_message_length(payload.content):
        raise HTTPException(400, "Conteúdo muito longo")
    try:
        return await tool_write(payload.path, payload.content, payload.root)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tool/bash")
@limiter.limit("30/minute")
async def api_tool_bash(request: Request, payload: ToolBash):
    cmd_name = payload.command.strip().split()[0].lower() if payload.command.strip() else ""
    if cmd_name not in ALLOWED_BASH:
        raise HTTPException(status_code=403, detail=f"Comando '{cmd_name}' não permitido")
    # ── Verifica Modo Restrito (Sandbox) ──────────────────────────────
    _check_sandbox(payload.command)
    # ───────────────────────────────────────────────────────────────────
    try:
        wd = payload.workdir or str(get_base_dir())
        r = subprocess.run(
            payload.command, shell=True, capture_output=True,
            text=True, timeout=30, cwd=wd
        )
        return {
            "status": "ok" if r.returncode == 0 else "error",
            "stdout": strip_ansi(r.stdout[-5000:]),
            "stderr": strip_ansi(r.stderr[-2000:]),
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Timeout 30s")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tool/list")
async def tool_list():
    from tools.executor import TOOL_METADATA
    return {"tools": TOOL_METADATA}
