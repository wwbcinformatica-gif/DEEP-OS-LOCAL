from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.agent_config import reset_config_cache
from core.auth import get_current_tenant_optional

router = APIRouter(prefix="/api/config", tags=["Config"])

# Valores que NUNCA devem ser gravados como chave de API.
#
# BUG CORRIGIDO: o frontend marcava as chaves ja salvas no estado/localStorage
# com '***saved***' e enviava TODOS os providers ao salvar um deles. O backend
# aceitava esse texto como chave valida (e truthy) e gravava no `.env`,
# SOBRESCREVENDO a chave verdadeira do usuario — que parava de funcionar, mesmo
# "estando salva".
#
# O frontend foi corrigido (nao envia mais o marcador nem os outros providers),
# mas o backend tambem recusa, como defesa em profundidade.
_PLACEHOLDERS_INVALIDOS = {
    "***saved***", "***salvo***", "***", "saved", "salvo", "(vazia)", "(empty)",
    "undefined", "null", "none", "changeme", "your-api-key", "cole_sua_chave_aqui",
}


def _chave_valida(valor) -> bool:
    """False para vazio, nao-string e para os marcadores de placeholder."""
    if not valor or not isinstance(valor, str):
        return False
    v = valor.strip()
    if not v:
        return False
    if v.lower() in _PLACEHOLDERS_INVALIDOS:
        return False
    # Marcadores mascarados do tipo "sk-...abcd" ou "***...abcd"
    if v.startswith("***") or ("..." in v and len(v) < 20):
        return False
    return True


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
    # Qual assistente esta salvando ("charon" | "jarvis").
    #
    # O NOME DO ASSISTENTE e um so para os dois (decisao do usuario), mas o NOME
    # DO USUARIO e separado por assistente. Sem este campo, salvar num mudaria o
    # nome usado pelo outro — foi o defeito relatado ("trocado para wilson e o
    # jarvis recebeu yuri").
    assistente: str = ""

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
async def get_identity(
    tenant_id: str | None = Depends(get_current_tenant_optional),
    assistente: str = "",
):
    """
    Identidade (nome do assistente/usuario/voz).

    Com JWT valido -> identidade daquele tenant (isolada por assinante).
    Sem JWT         -> identidade global de config.yaml (app desktop).

    `assistente` ("charon" | "jarvis") escolhe de qual coluna vem o NOME DO
    USUARIO: cada assistente tem o seu (ver core/tenant_identity.get_identity).
    O nome do ASSISTENTE e o mesmo para os dois.

    NOTA: esta rota precisa vir ANTES do catch-all `/{section}` (que fica no
    fim do arquivo). Enquanto ele vinha primeiro, este path casava com o
    catch-all e devolvia a identidade GLOBAL — o isolamento por tenant nunca
    funcionava e a voz/nome de um usuario aparecia em todos os outros.
    """
    from core.tenant_identity import get_identity as _get_tenant_identity

    identity = _get_tenant_identity(tenant_id, assistente or None)
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
            assistente=config.assistente or None,
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
        import json, os
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        env_path = Path(__file__).resolve().parent.parent / ".env"

        # Nao gravar placeholder (evita destruir a chave real; ver _chave_valida)
        if not _chave_valida(config.gemini_api_key):
            raise HTTPException(
                status_code=400,
                detail="Valor invalido para a chave. Digite a chave real (o marcador "
                       "'***saved***' indica que ja existe uma salva).",
            )

        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data["gemini_api_key"] = config.gemini_api_key.strip()
        cfg_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

        # Write to .env AND update os.environ
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines = []
        for line in env_lines:
            stripped = line.strip()
            if stripped.startswith("GEMINI_API_KEY="):
                new_lines.append(f"GEMINI_API_KEY={config.gemini_api_key}")
                found = True
            else:
                new_lines.append(line)
        if not found and config.gemini_api_key:
            new_lines.append(f"GEMINI_API_KEY={config.gemini_api_key}")
        env_path.write_text('\n'.join(new_lines) + '\n', encoding="utf-8")
        os.environ["GEMINI_API_KEY"] = config.gemini_api_key

        return {"status": "success", "message": "Chave API salva no servidor"}
    except HTTPException:
        # Sem isto o 400 acima seria capturado pelo except generico e viraria 500,
        # escondendo do frontend que o valor foi recusado.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar chave: {e}")

@router.put("/api-keys")
async def update_api_keys(request: dict):
    try:
        import json, os
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        env_path = Path(__file__).resolve().parent.parent / ".env"
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

        # Provedores COMUNS que foram adicionados ao registro e ainda nao estao
        # no mapa fixo acima. Sem isto, a chave do DeepSeek (por exemplo) seria
        # silenciosamente ignorada no salvamento — exatamente a classe de bug do
        # `openai` sem campo na interface.
        try:
            from core.provedores import PRESETS

            for pid, meta in PRESETS.items():
                env = meta.get("key_env")
                if env and env not in key_map:
                    key_map[env] = f"{pid}_api_key"
        except Exception:
            pass

        # Provedores PERSONALIZADOS criados pelo usuario pela interface.
        # O nome da variavel segue o padrao `<ID>_API_KEY`, entao nao precisa de
        # alteracao de codigo para um provedor novo ser salvo.
        try:
            from core.provedores import ids_personalizados

            for pid in ids_personalizados():
                env = f"{pid.upper()}_API_KEY"
                key_map.setdefault(env, f"{pid}_api_key")
        except Exception:
            pass

        updated = []
        recusados = []
        for env_key, json_key in key_map.items():
            if env_key not in request or not request[env_key]:
                continue
            if not _chave_valida(request[env_key]):
                # Placeholder/mascarado: NAO gravar (destruiria a chave real)
                recusados.append(env_key)
                continue
            data[json_key] = request[env_key].strip()
            updated.append(env_key)
        cfg_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

        # Write to .env AND update os.environ
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        env_keys_written = set()
        new_lines = []
        for line in env_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key_name = stripped.split('=', 1)[0].strip()
                if key_name in key_map and _chave_valida(request.get(key_name)):
                    new_lines.append(f"{key_name}={request[key_name].strip()}")
                    env_keys_written.add(key_name)
                    os.environ[key_name] = request[key_name].strip()
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        for env_key in key_map:
            if _chave_valida(request.get(env_key)) and env_key not in env_keys_written:
                new_lines.append(f"{env_key}={request[env_key].strip()}")
                os.environ[env_key] = request[env_key].strip()
        env_path.write_text('\n'.join(new_lines) + '\n', encoding="utf-8")

        resposta = {"status": "success", "updated": updated}
        if recusados:
            resposta["recusados"] = recusados
            resposta["aviso"] = (
                "Alguns valores foram recusados por parecerem mascarados/placeholder "
                "(ex: '***saved***'). Nenhuma chave existente foi alterada por eles."
            )
        return resposta
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar chaves: {e}")


# Modelo usado para testar cada provedor (barato e rapido).
# Usado so quando o frontend nao manda um modelo.
_MODELO_DE_TESTE = {
    "gemini": "gemini-2.5-flash",
    "groq": "openai/gpt-oss-20b",
    "openrouter": "openai/gpt-4o-mini",
    "openai": "gpt-4o-mini",
    "nvidia": "nvidia/nemotron-3-super-120b-a12b",
    "zhipu": "glm-4.6",
    "mimo": "mimo-v2.5",
    "opencode": "deepseek-v4-flash-free",
    "openclaude": "claude-sonnet-4-6",
    "ollama": "qwen2.5-coder:7b",
}


class TestarChavePayload(BaseModel):
    provider: str
    model: str = ""


@router.post("/testar-chave")
async def testar_chave(payload: TestarChavePayload):
    """
    Testa a chave de um provedor com uma chamada de chat REAL.

    POR QUE ISTO EXISTE
    O usuario perdeu bastante tempo com chaves que "pareciam salvas" e nao
    funcionavam: a tela dizia "salvo" e o erro real ficava escondido. Este
    endpoint responde a pergunta que importa — "esta chave funciona?" — usando
    o MESMO caminho de codigo que o chat usa (`core.llm_native.complete_chat`),
    entao o veredito reflete a realidade e nao uma verificacao paralela.

    Nao usa `/models` de proposito: descobrimos que esse endpoint mente (o do
    OpenRouter e publico e responde com chave falsa; o da NVIDIA lista modelos
    que a conta nao tem). So a chamada de chat prova.
    """
    import asyncio

    provider = (payload.provider or "").strip().lower()
    if not provider:
        raise HTTPException(status_code=400, detail="Informe o provedor.")

    model = (payload.model or "").strip() or _MODELO_DE_TESTE.get(provider, "")
    if not model:
        raise HTTPException(
            status_code=400,
            detail=f"Nao sei qual modelo usar para testar '{provider}'. Informe o modelo.",
        )

    try:
        from core.llm_native import complete_chat

        texto = await asyncio.wait_for(
            complete_chat(
                provider,
                model,
                [{"role": "user", "content": "Responda apenas: OK"}],
                0.0,
            ),
            timeout=25,
        )
        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "resposta": (texto or "").strip()[:120],
            "mensagem": f"Chave valida — {model} respondeu.",
        }

    except asyncio.TimeoutError:
        return {
            "ok": False,
            "provider": provider,
            "model": model,
            "mensagem": "Tempo esgotado (25s). O provedor nao respondeu — verifique a conexao do servidor.",
        }
    except Exception as e:
        bruto = str(e)
        baixo = bruto.lower()

        # Traduz o erro tecnico para algo acionavel. Cada caso aqui ja apareceu
        # de verdade nas chaves deste projeto.
        if "401" in bruto or "unauthorized" in baixo or "incorrect api key" in baixo or "no auth" in baixo or "user not found" in baixo:
            dica = "Chave INVALIDA ou revogada. Gere uma nova no painel do provedor e salve de novo."
        elif "402" in bruto or "insufficient" in baixo or "balance" in baixo or "quota" in baixo or "余额不足" in bruto:
            dica = "Conta SEM SALDO/limite atingido. Recarregue a conta do provedor (nao e erro da chave)."
        elif "429" in bruto or "rate limit" in baixo:
            dica = "Limite de uso atingido (429). Espere um pouco ou recarregue a conta."
        elif "404" in bruto or "not found" in baixo or "does not exist" in baixo:
            dica = f"Modelo '{model}' nao existe mais neste provedor. Escolha outro modelo na lista."
        elif "connect" in baixo or "refused" in baixo or "timeout" in baixo or "getaddrinfo" in baixo:
            dica = (
                "Nao consegui conectar. Se for 'openclaude', ele aponta para um servidor "
                "LOCAL (localhost:4000) que precisa estar rodando."
            )
        else:
            dica = "Falha ao testar. Veja a mensagem tecnica abaixo."

        return {
            "ok": False,
            "provider": provider,
            "model": model,
            "mensagem": dica,
            "erro": bruto[:400],
        }


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

        # Provedores comuns novos e personalizados tambem reportam `has_key`.
        #
        # Sem isto, a interface mostraria "(vazia)" para uma chave que JA esta
        # salva — e o usuario salvaria de novo achando que perdeu. O padrao do
        # nome vem de `provedores.env_key_do_id()` (uma fonte so).
        try:
            from core.provedores import PRESETS, ids_personalizados

            for pid in PRESETS:
                key_map.setdefault(f"{pid}_api_key", pid)
            for pid in ids_personalizados():
                key_map.setdefault(f"{pid}_api_key", pid)
        except Exception:
            pass

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
# PROVEDORES — comuns + personalizados (criados pelo usuario)
#
# POR QUE EXISTE
# O usuario pediu: "pode inserir outros provedores ou uma opcao para que eu crie
# provedores novos, pois sempre tem provedores novos; ja deixa no projeto os
# mais comuns incluso".
#
# Motivo concreto: `openai`, `opencode` e `openclaude` eram suportados pelo
# backend mas NAO tinham campo na interface — nao havia onde colar a chave.
# Com um registro, adicionar provedor deixa de exigir mexer em codigo.
#
# ATENCAO: estas rotas precisam vir ANTES do catch-all `/{section}` no fim do
# arquivo (o FastAPI resolve por ordem de registro).
# ─────────────────────────────────────────────────────────────────────────────

class ProvedorPayload(BaseModel):
    id: str = ""
    label: str = ""
    base_url: str = ""
    models: list = []
    aviso: str = ""
    local: bool = False


class BuscarModelosPayload(BaseModel):
    provider: str = ""
    base_url: str = ""
    api_key: str = ""


@router.get("/provedores")
async def listar_provedores():
    """
    Lista os provedores comuns (presets) e os personalizados do usuario.

    A interface usa isto para montar o seletor e os campos de chave — assim um
    provedor novo deixa de precisar de alteracao no frontend.
    """
    from core import provedores

    dados = provedores.listar()
    dados["total"] = len(dados["comuns"]) + len(dados["personalizados"])
    return dados


@router.post("/provedores")
async def salvar_provedor(payload: ProvedorPayload):
    """
    Cria ou atualiza um provedor personalizado.

    Nao testa a conexao aqui de proposito: salvar e testar sao coisas separadas
    (uma rede instavel faria "salvar" falhar sem necessidade). Para testar
    existe POST /api/config/testar-chave.
    """
    from core import provedores

    try:
        registro = provedores.salvar({
            "id": payload.id,
            "label": payload.label,
            "base_url": payload.base_url,
            "models": payload.models,
            "aviso": payload.aviso,
            "local": payload.local,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar provedor: {e}")

    return {
        "status": "success",
        "provedor": registro,
        "mensagem": (
            f"Provedor '{registro['label']}' salvo. Agora cole a chave em "
            f"{registro['key_env']} e clique em Testar."
        ),
    }


@router.delete("/provedores/{pid}")
async def remover_provedor(pid: str):
    """
    Remove um provedor personalizado.

    A chave permanece no .env: remover por engano e recriar com o mesmo nome
    volta a funcionar sem redigitar nada.
    """
    from core import provedores

    if provedores.remover(pid):
        return {"status": "success", "mensagem": f"Provedor '{pid}' removido."}
    raise HTTPException(status_code=404, detail=f"Provedor personalizado '{pid}' nao encontrado.")


@router.post("/provedores/modelos")
async def buscar_modelos_do_provedor(payload: BuscarModelosPayload):
    """
    Busca a lista de modelos no endpoint /models do provedor.

    Serve para preencher o formulario de provedor novo sem digitar modelo por
    modelo. Aceita `provider` (usa a chave ja salva) OU `base_url` + `api_key`
    (para testar antes de salvar).

    AVISO HONESTO sobre o resultado: `/models` mente em varios provedores.
      - O do OpenRouter e PUBLICO: devolve modelos mesmo com chave falsa.
      - O da NVIDIA lista modelos que a conta NAO tem habilitados.
    Por isso o retorno traz `confiavel: False` nesses casos, e a interface avisa
    que a lista e uma sugestao — o que prova o modelo e o botao Testar.
    """
    import httpx

    provider = (payload.provider or "").strip().lower()
    base_url = (payload.base_url or "").strip().rstrip("/")
    chave = (payload.api_key or "").strip()

    # Descobre a URL base e a chave
    if provider:
        from core.provedores import resolver

        meta = resolver(provider)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Provedor '{provider}' nao registrado.")
        base_url = base_url or (meta.get("base_url") or "").rstrip("/")
        if not chave:
            import os

            chave = os.environ.get(meta.get("key_env") or "", "")
            if not chave:
                try:
                    import json
                    from pathlib import Path

                    cfg = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
                    if cfg.exists():
                        dados = json.loads(cfg.read_text(encoding="utf-8"))
                        chave = dados.get(f"{provider}_api_key", "") or dados.get("gemini_api_key", "")
                except Exception:
                    chave = ""

    if not base_url:
        raise HTTPException(status_code=400, detail="Informe a URL base do provedor.")

    url = base_url + "/models"
    cabecalhos = {"Accept": "application/json"}
    if chave:
        cabecalhos["Authorization"] = f"Bearer {chave}"

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(url, headers=cabecalhos)
    except Exception as e:
        return {
            "ok": False,
            "modelos": [],
            "mensagem": f"Nao consegui acessar {url}: {e}",
        }

    if resp.status_code != 200:
        return {
            "ok": False,
            "modelos": [],
            "mensagem": (
                f"O provedor respondeu HTTP {resp.status_code} em {url}. "
                "Confira a URL base e a chave (a URL costuma terminar em /v1)."
            ),
        }

    try:
        dados = resp.json()
    except Exception:
        return {"ok": False, "modelos": [], "mensagem": f"{url} nao devolveu JSON."}

    brutos = dados.get("data") or dados.get("models") or []
    modelos = []
    for m in brutos:
        if isinstance(m, str):
            modelos.append({"id": m, "label": m})
            continue
        mid = m.get("id") or m.get("name") or m.get("model")
        if not mid:
            continue
        # Gemini devolve "models/gemini-3.6-flash"; o SDK espera sem o prefixo
        mid = str(mid).replace("models/", "")
        modelos.append({"id": mid, "label": mid})

    # Ordena e remove repetidos
    vistos = set()
    unicos = []
    for m in sorted(modelos, key=lambda x: x["id"]):
        if m["id"] not in vistos:
            vistos.add(m["id"])
            unicos.append(m)

    # Provedores cujo /models nao serve para validar nada (ver docstring)
    NAO_CONFIAVEIS = {"openrouter", "nvidia"}
    confiavel = provider not in NAO_CONFIAVEIS

    return {
        "ok": True,
        "provider": provider,
        "base_url": base_url,
        "total": len(unicos),
        "modelos": unicos,
        "confiavel": confiavel,
        "mensagem": (
            f"{len(unicos)} modelos encontrados."
            + ("" if confiavel else
               " ATENCAO: neste provedor o /models nao e confiavel — ele lista "
               "modelos que a sua conta pode nao ter. Use o botao Testar para "
               "confirmar os que voce for usar.")
        ),
    }


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
