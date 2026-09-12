from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.agent_config import reset_config_cache
from core.auth import get_current_tenant_optional

router = APIRouter(prefix="/api/config", tags=["Config"])

def _get_config_path() -> str:
    from pathlib import Path
    return str(Path(__file__).resolve().parent.parent.parent / "config.yaml")

def _read_config() -> dict:
    path = _get_config_path()
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading config: {e}")

def _write_config(data: dict):
    path = _get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing config: {e}")

def _deep_set(data: dict, key_path: str, value: Any):
    keys = key_path.split(".")
    d = data
    for k in keys[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value

def _deep_get(data: dict, key_path: str, default: Any = None) -> Any:
    keys = key_path.split(".")
    d = data
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
            if d is None:
                return default
        else:
            return default
    return d

class IdentityConfig(BaseModel):
    assistant_name: str = "DEEP-OS"
    user_name: str = ""
    custom_color: str = ""
    voice: str = "Charon"

class SandboxConfig(BaseModel):
    enabled: bool

class AccentThemeConfig(BaseModel):
    theme: str

class VoiceConfig(BaseModel):
    auto_send: bool | None = None
    mic_active_on_start: bool | None = None
    deep_mode_active: bool | None = None
    voice_preset: str | None = None
    voice_rate: str | None = None
    voice_pitch: str | None = None
    jarvis_rate: str | None = None
    jarvis_pitch: str | None = None
    tts_enabled: bool | None = None
    elevenlabs_voices: bool | None = None
    auto_send_delay: int | None = None
    hybrid_mode: bool | None = None
    hybrid_voice: str | None = None

class ConfigUpdatePayload(BaseModel):
    section: str
    values: dict

@router.get("")
async def get_full_config():
    data = _read_config()
    return data

@router.put("")
async def update_config(payload: ConfigUpdatePayload):
    data = _read_config()
    data[payload.section] = payload.values
    _write_config(data)
    reset_config_cache()
    return {"status": "success", "section": payload.section}

@router.post("/sandbox")
async def update_sandbox_config(config: SandboxConfig):
    data = _read_config()
    if "security" not in data:
        data["security"] = {}
    data["security"]["sandbox_enabled"] = config.enabled
    _write_config(data)
    
    # Atualizar permissoes do agente baseado no modo
    from core.permissions import set_full_access, load_perms, save_perms
    from core.permissions import ALL_CATEGORIES, _SENSITIVE
    
    if not config.enabled:
        # Modo Desenvolvedor: acesso total
        set_full_access(True)
    else:
        # Modo Restrito: permissoes padrao
        perms = load_perms()
        perms["full_access"] = False
        for c in ALL_CATEGORIES:
            perms["categories"][c] = "ask" if c in _SENSITIVE else "allow"
        save_perms(perms)
    
    return {"status": "success", "sandbox_enabled": config.enabled}

@router.post("/accent-theme")
async def update_accent_theme(config: AccentThemeConfig):
    data = _read_config()
    if "display" not in data:
        data["display"] = {}
    data["display"]["accent_theme"] = config.theme
    _write_config(data)
    return {"status": "success", "accent_theme": config.theme}

@router.get("/identity")
async def get_identity(tenant_id: str | None = Depends(get_current_tenant_optional)):
    """
    Identidade (nome do assistente/usuario/voz).

    Com JWT valido -> identidade daquele tenant (isolada por assinante).
    Sem JWT         -> identidade global de config.yaml (app desktop).

    NOTA: esta rota precisa vir ANTES do catch-all `/{section}` (que fica no
    fim do arquivo). Enquanto ele vinha primeiro, este path casava com o
    catch-all e devolvia a identidade GLOBAL — o isolamento por tenant nunca
    funcionava e a voz/nome de um usuario aparecia em todos os outros.
    """
    from core.tenant_identity import get_identity as _get_tenant_identity

    identity = _get_tenant_identity(tenant_id)
    data = _read_config()
    global_identity = data.get("identity", {})
    return {
        "assistant_name": identity["assistant_name"],
        "user_name": identity["user_name"],
        "custom_color": global_identity.get("custom_color", ""),
        # A voz vem do tenant (preferencia pessoal).
        "voice": identity.get("voice") or global_identity.get("voice", "Charon"),
    }

@router.put("/identity")
async def update_identity(
    config: IdentityConfig,
    tenant_id: str | None = Depends(get_current_tenant_optional),
):
    """
    Salva a identidade (nome do assistente, nome do usuario e voz).

    Com JWT valido -> grava SO no tenant; config.yaml global fica intocado,
    entao a escolha de um assinante nao afeta os outros.
    Sem JWT         -> grava no config.yaml global (app desktop).
    """
    from core.tenant_identity import set_identity as _set_tenant_identity

    # ─── Caminho SaaS: persiste por tenant, nao vaza para os outros ───
    if tenant_id:
        saved = _set_tenant_identity(
            tenant_id,
            config.assistant_name,
            config.user_name,
            voice=config.voice,
        )
        if saved:
            # custom_color segue global: e aparencia da interface, nao
            # identidade do assistente.
            data = _read_config()
            identity_global = data.get("identity", {})
            identity_global["custom_color"] = config.custom_color
            data["identity"] = identity_global
            _write_config(data)
            reset_config_cache()
            return {
                "status": "success",
                "scope": "tenant",
                "identity": {
                    "assistant_name": config.assistant_name.strip() or "DEEP-OS",
                    "user_name": config.user_name.strip(),
                    "custom_color": config.custom_color,
                    "voice": config.voice,
                },
            }
        # Tenant nao encontrado no banco -> cai para o caminho global
        # (evita perder a configuracao caso o token seja de um admin)

    # ─── Caminho global: app desktop / sem login ───
    data = _read_config()
    data["identity"] = config.model_dump()
    _write_config(data)
    # Mantem api_keys.json sincronizado (usado por config_manager.py / morning brief)
    try:
        from memory.config_manager import save_assistant_config
        save_assistant_config(config.assistant_name, config.user_name)
    except Exception:
        pass
    reset_config_cache()
    return {"status": "success", "scope": "global", "identity": data["identity"]}

@router.get("/accent-theme")
async def get_accent_theme():
    data = _read_config()
    theme = _deep_get(data, "display.accent_theme", "azul-claro")
    return {"accent_theme": theme}

@router.get("/voice")
async def get_voice_config():
    data = _read_config()
    voice = data.get("voice", {})
    return voice

@router.post("/voice")
async def update_voice_config(config: VoiceConfig):
    data = _read_config()
    if "voice" not in data:
        data["voice"] = {}
    update_data = config.model_dump(exclude_none=True)
    data["voice"].update(update_data)
    _write_config(data)
    reset_config_cache()
    return {"status": "success", "voice": data["voice"]}

class AgentModelsConfig(BaseModel):
    jarvis: str | None = None
    architect: str | None = None
    debugger: str | None = None
    planner: str | None = None
    coder: str | None = None

DEFAULT_AGENT_MODELS = {
    "jarvis": "qwen2.5-coder:14b",
    "architect": "qwen3:14b",
    "debugger": "qwen2.5-coder:14b",
    "planner": "qwen3.5:9b",
    "coder": "qwen2.5-coder:14b",
}

@router.get("/agent-models")
async def get_agent_models():
    data = _read_config()
    models = data.get("agent_models", {})
    result = {}
    for agent, default in DEFAULT_AGENT_MODELS.items():
        result[agent] = models.get(agent, default)
    return result

@router.put("/agent-models")
async def update_agent_models(config: AgentModelsConfig):
    data = _read_config()
    if "agent_models" not in data:
        data["agent_models"] = {}
    update_data = config.model_dump(exclude_none=True)
    data["agent_models"].update(update_data)
    _write_config(data)
    return {"status": "success", "agent_models": data["agent_models"]}

@router.post("/agent-models/reset")
async def reset_agent_models():
    data = _read_config()
    data["agent_models"] = DEFAULT_AGENT_MODELS.copy()
    _write_config(data)
    return {"status": "success", "agent_models": data["agent_models"]}

# ─── MCP Server CRUD ─────────────────────────────────────────────

class McpServerConfig(BaseModel):
    type: str = "local"
    command: list[str] | None = None
    url: str | None = None
    enabled: bool = True
    environment: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    timeout: int | None = 5000

@router.get("/mcp-servers")
async def list_mcp_servers_config():
    data = _read_config()
    servers = data.get("mcp", {})
    return {"servers": servers}

@router.put("/mcp-servers/{name}")
async def upsert_mcp_server(name: str, config: McpServerConfig):
    data = _read_config()
    if "mcp" not in data:
        data["mcp"] = {}
    entry = {"type": config.type, "enabled": config.enabled}
    if config.type == "local" and config.command:
        entry["command"] = config.command
    if config.type == "remote" and config.url:
        entry["url"] = config.url
    if config.environment:
        entry["environment"] = config.environment
    if config.headers:
        entry["headers"] = config.headers
    if config.timeout:
        entry["timeout"] = config.timeout
    data["mcp"][name] = entry
    _write_config(data)
    return {"status": "success", "server": name}

@router.delete("/mcp-servers/{name}")
async def delete_mcp_server(name: str):
    data = _read_config()
    mcp = data.get("mcp", {})
    if name not in mcp:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    del mcp[name]
    data["mcp"] = mcp
    _write_config(data)
    return {"status": "success", "removed": name}

class ApiKeyConfig(BaseModel):
    gemini_api_key: str = ""

@router.get("/api-key")
async def get_api_key():
    try:
        import json
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            key = data.get("gemini_api_key", "")
            masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "(vazia)"
            return {"has_key": bool(key), "masked": masked}
    except Exception:
        pass
    return {"has_key": False, "masked": "(vazia)"}

@router.put("/api-key")
async def update_api_key(config: ApiKeyConfig):
    try:
        import json
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data["gemini_api_key"] = config.gemini_api_key
        cfg_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        return {"status": "success", "message": "Chave API salva no servidor"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar chave: {e}")

@router.put("/api-keys")
async def update_api_keys(request: dict):
    try:
        import json
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            data = {}
        key_map = {
            "GEMINI_API_KEY": "gemini_api_key",
            "OPENROUTER_API_KEY": "openrouter_api_key",
            "OPENAI_API_KEY": "openai_api_key",
            "GROQ_API_KEY": "groq_api_key",
            "NVIDIA_API_KEY": "nvidia_api_key",
            "MIMO_API_KEY": "mimo_api_key",
            "OPENCLAUDE_API_KEY": "openclaude_api_key",
            "OPENCODE_API_KEY": "opencode_api_key",
            "ZHIPU_API_KEY": "zhipu_api_key",
        }
        updated = []
        for env_key, json_key in key_map.items():
            if env_key in request and request[env_key]:
                data[json_key] = request[env_key]
                updated.append(json_key)
        cfg_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        return {"status": "success", "updated": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar chaves: {e}")

@router.get("/api-keys")
async def get_api_keys():
    try:
        import json
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            data = {}
        result = {}
        key_map = {
            "gemini_api_key": "gemini",
            "openrouter_api_key": "openrouter",
            "openai_api_key": "openai",
            "groq_api_key": "groq",
            "nvidia_api_key": "nvidia",
            "mimo_api_key": "mimo",
            "openclaude_api_key": "openclaude",
            "opencode_api_key": "opencode",
            "zhipu_api_key": "zhipu",
        }
        for json_key, name in key_map.items():
            val = data.get(json_key, "")
            if val and len(val) > 10:
                result[name] = {"has_key": True, "masked": val[:6] + "..." + val[-4:]}
            elif val:
                result[name] = {"has_key": True, "masked": "(curta)"}
            else:
                result[name] = {"has_key": False, "masked": "(vazia)"}
        return result
    except Exception:
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# CATCH-ALL — SEMPRE NO FIM DO ARQUIVO
#
# O FastAPI resolve rotas na ordem de registro. Qualquer rota literal
# (/identity, /voice, /accent-theme, ...) PRECISA ser registrada antes desta,
# senao o path literal casa aqui e a rota especifica nunca executa.
#
# Historico: enquanto esta rota vinha antes de /identity, o frontend lia a
# identidade GLOBAL do config.yaml em vez da identidade do tenant — a voz e o
# nome de um usuario apareciam para todos os outros.
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{section}")
async def get_config_section(section: str):
    """
    ATENCAO: esta rota e um CATCH-ALL e DEVE ficar por ULTIMO no arquivo.

    O FastAPI casa as rotas na ordem de registro. Enquanto ela estava antes de
    `/identity`, aquele path casava com `/{section}` e caia aqui — devolvendo a
    identidade GLOBAL do config.yaml. Efeito pratico: o isolamento por tenant
    nunca funcionava, e a voz/nome de um usuario aparecia em todos os outros.
    """
    data = _read_config()
    return data.get(section, {})
