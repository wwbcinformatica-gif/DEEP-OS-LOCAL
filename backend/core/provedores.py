"""
DEEP-OS — Registro de provedores de LLM (comuns + personalizados).

POR QUE ESTE MODULO EXISTE
--------------------------
Duas necessidades que o codigo antigo nao atendia:

1. PROVEDORES NOVOS APARECEM O TEMPO TODO. Antes, cada provedor exigia editar
   codigo em varios lugares (frontend, key_map, get_client) — e, como ficou
   provado nesta sessao, e facil esquecer um deles: `openai`, `opencode` e
   `openclaude` eram suportados pelo backend mas NAO tinham campo na interface,
   entao o usuario simplesmente nao tinha onde colar a chave.

2. O USUARIO QUER CRIAR OS PROPRIOS. Muitos servicos (e servidores locais como
   LM Studio, vLLM, text-generation-webui) expoem a MESMA API do OpenAI. Para
   esses, a unica coisa que muda e a `base_url`, a chave e a lista de modelos.
   Nao faz sentido exigir alteracao de codigo.

ARQUITETURA
-----------
- `PRESETS`: provedores comuns, so com os metadados (base_url, env da chave,
  se e local, se e compativel com a API do OpenAI). Ficam no codigo porque sao
  estaveis e servem de "receita pronta".
- `provedores_custom.json`: provedores criados pelo usuario. Ficam em arquivo
  (fora do git) porque mudam sem deploy.
- A uniao dos dois e o que a interface mostra.

SEGURANCA: a chave NUNCA entra no `provedores_custom.json`. Ela vai para o
`.env` e `api_keys.json`, como as demais — o registro guarda so o NOME da
variavel de ambiente.
"""
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

ARQUIVO = Path(__file__).resolve().parent.parent / "config" / "provedores_custom.json"


# ── Provedores comuns (presets) ──────────────────────────────────────────────
#
# `compativel_openai`: True quando o servico aceita o SDK do OpenAI
# (`/chat/completions`). O DEEP-OS usa `AsyncOpenAI` para todos, entao um
# provedor com False nao pode ser usado por aqui.
#
# `local`: True quando aponta para a propria maquina (nao precisa de chave e nao
# funciona no VPS, que e headless e nao tem o servico rodando).
PRESETS: dict[str, dict[str, Any]] = {
    # --- ja existiam e continuam iguais ---
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "openrouter": {
        "label": "OpenRouter (gratis/variados)",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "groq": {
        "label": "Groq (gratis/rapido)",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "zhipu": {
        "label": "Zhipu AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "key_env": "ZHIPU_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "mimo": {
        "label": "MiMo (Xiaomi)",
        "base_url": "https://api.xiaomimimo.com/v1",
        "key_env": "MIMO_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "opencode": {
        "label": "OpenCode (zen)",
        "base_url": "https://opencode.ai/zen/v1",
        "key_env": "OPENCODE_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "openclaude": {
        "label": "OpenClaude (servidor local)",
        "base_url": "http://localhost:4000/api/v1",
        "key_env": "OPENCLAUDE_API_KEY",
        "compativel_openai": True,
        "local": True,
    },
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "key_env": "",
        "compativel_openai": True,
        "local": True,
    },
    "llamacpp": {
        "label": "llama.cpp (GGUF local)",
        "base_url": "http://localhost:8080/v1",
        "key_env": "",
        "compativel_openai": True,
        "local": True,
    },

    # --- provedores comuns que FALTAVAM ---
    # Todos falam o dialeto do OpenAI (`/chat/completions`), entao entram no
    # mesmo caminho de codigo. As chaves sao salvas como os demais.
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "xai": {
        "label": "xAI (Grok)",
        "base_url": "https://api.x.ai/v1",
        "key_env": "XAI_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "mistral": {
        "label": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "key_env": "MISTRAL_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1/",
        "key_env": "ANTHROPIC_API_KEY",
        "compativel_openai": True,
        "local": False,
        "aviso": (
            "A Anthropic tem API propria; esta entrada usa a camada compativel "
            "com o SDK do OpenAI. Se nao funcionar, use Claude via OpenRouter."
        ),
    },
    "together": {
        "label": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "fireworks": {
        "label": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "key_env": "FIREWORKS_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "cerebras": {
        "label": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "perplexity": {
        "label": "Perplexity",
        "base_url": "https://api.perplexity.ai",
        "key_env": "PERPLEXITY_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "deepinfra": {
        "label": "DeepInfra",
        "base_url": "https://api.deepinfra.com/v1/openai",
        "key_env": "DEEPINFRA_API_KEY",
        "compativel_openai": True,
        "local": False,
    },
    "hyperbolic": {
        "label": "Hyperbolic",
        "base_url": "https://api.hyperbolic.xyz/v1",
        "key_env": "HYPERBOLIC_API_KEY",
        "compativel_openai": True,
        "local": False,
    },

    # --- servidores locais compativeis com OpenAI ---
    # Uteis no PC com GPU. No VPS (headless, sem GPU) nao ha o que servir.
    "lmstudio": {
        "label": "LM Studio (local)",
        "base_url": "http://localhost:1234/v1",
        "key_env": "",
        "compativel_openai": True,
        "local": True,
    },
    "vllm": {
        "label": "vLLM (local)",
        "base_url": "http://localhost:8000/v1",
        "key_env": "",
        "compativel_openai": True,
        "local": True,
    },
    "textgenwebui": {
        "label": "text-generation-webui (local)",
        "base_url": "http://localhost:5000/v1",
        "key_env": "",
        "compativel_openai": True,
        "local": True,
    },
    "jan": {
        "label": "Jan (local)",
        "base_url": "http://localhost:1337/v1",
        "key_env": "",
        "compativel_openai": True,
        "local": True,
    },
}

# Nomes que um provedor personalizado NAO pode usar (colidiria com o codigo).
RESERVADOS = set(PRESETS) | {"llm", "llamacpp", "none", "default"}


def slug(nome: str) -> str:
    """
    Converte o nome digitado pelo usuario em um id seguro.

    O id vai virar NOME DE VARIAVEL DE AMBIENTE (`<ID>_API_KEY`) e chave no JSON,
    entao so pode ter letra, numero e `_`. Acentuacao e removida em vez de
    virar `_` para "Configuração" virar "configuracao" e nao "configura_o".
    """
    if not nome:
        return ""
    # Remove acentos: "Configuração" -> "Configuracao"
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c)
    )
    # Tudo que nao for letra/numero vira "_"
    limpo = re.sub(r"[^A-Za-z0-9]+", "_", sem_acento).strip("_").lower()
    # Nao pode comecar com numero (nome de variavel de ambiente)
    if limpo and limpo[0].isdigit():
        limpo = "p_" + limpo
    return limpo


def env_key_do_id(pid: str) -> str:
    """`meu_provedor` -> `MEU_PROVEDOR_API_KEY`."""
    return pid.upper() + "_API_KEY"


def _ler_arquivo() -> list[dict]:
    if not ARQUIVO.exists():
        return []
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(dados, dict):
        dados = dados.get("provedores", [])
    return dados if isinstance(dados, list) else []


def _escrever_arquivo(lista: list[dict]) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(
        json.dumps({"provedores": lista}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def listar_custom() -> list[dict]:
    return _ler_arquivo()


def resolver(pid: str) -> dict | None:
    """
    Devolve os metadados de um provedor: preset OU personalizado.

    E o que `get_client` usa para aceitar qualquer provedor registrado sem
    precisar de um `elif` novo no codigo.
    """
    if not pid:
        return None
    pid = pid.strip().lower()

    if pid in PRESETS:
        meta = dict(PRESETS[pid])
        meta["id"] = pid
        meta["tipo"] = "comum"
        return meta

    for p in _ler_arquivo():
        if str(p.get("id", "")).lower() == pid:
            return {
                "id": pid,
                "label": p.get("label", pid),
                "base_url": p.get("base_url", ""),
                "key_env": p.get("key_env", env_key_do_id(pid)),
                "compativel_openai": True,
                "local": bool(p.get("local", False)),
                "models": p.get("models", []),
                "tipo": "personalizado",
                "aviso": p.get("aviso", ""),
            }
    return None


def listar() -> dict:
    """Tudo o que a interface precisa: comuns + personalizados."""
    comuns = []
    for pid, meta in PRESETS.items():
        comuns.append({
            "id": pid,
            "label": meta["label"],
            "base_url": meta["base_url"],
            "key_env": meta["key_env"],
            "precisa_chave": bool(meta["key_env"]),
            "local": meta["local"],
            "aviso": meta.get("aviso", ""),
            "tipo": "comum",
        })
    custom = []
    for p in _ler_arquivo():
        if not p.get("id"):
            continue
        custom.append({
            "id": p["id"],
            "label": p.get("label", p["id"]),
            "base_url": p.get("base_url", ""),
            "key_env": p.get("key_env", env_key_do_id(p["id"])),
            "precisa_chave": True,
            "local": bool(p.get("local", False)),
            "models": p.get("models", []),
            "aviso": p.get("aviso", ""),
            "tipo": "personalizado",
        })
    return {"comuns": comuns, "personalizados": custom}


def salvar(dados: dict) -> dict:
    """
    Cria ou atualiza um provedor personalizado.

    Valida o essencial: base_url plausivel e id que nao colida com o codigo.
    Nao testa a conexao aqui — para isso existe /api/config/testar-chave, e
    misturar as duas coisas faria "salvar" falhar por rede instavel.
    """
    rotulo = (dados.get("label") or "").strip()
    if not rotulo:
        raise ValueError("Informe um nome para o provedor.")

    pid = slug(dados.get("id") or rotulo)
    if not pid:
        raise ValueError("Nao consegui gerar um identificador a partir do nome.")
    if pid in RESERVADOS and pid not in {p.get("id") for p in _ler_arquivo()}:
        raise ValueError(
            f"'{pid}' e um provedor que ja existe no DEEP-OS. Escolha outro nome."
        )

    base_url = (dados.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("Informe a URL base do provedor (ex: https://api.exemplo.com/v1).")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("A URL base precisa comecar com http:// ou https://")

    modelos = dados.get("models") or []
    modelos_limpos = []
    for m in modelos:
        if isinstance(m, str):
            m = {"id": m, "label": m}
        mid = str(m.get("id", "")).strip()
        if mid:
            modelos_limpos.append({"id": mid, "label": str(m.get("label") or mid)})

    registro = {
        "id": pid,
        "label": rotulo,
        "base_url": base_url,
        "key_env": env_key_do_id(pid),
        "local": bool(dados.get("local", False)) or "localhost" in base_url or "127.0.0.1" in base_url,
        "models": modelos_limpos,
        "aviso": (dados.get("aviso") or "").strip(),
    }

    lista = _ler_arquivo()
    for i, p in enumerate(lista):
        if p.get("id") == pid:
            # Preserva modelos anteriores se o novo vem vazio (nao apagar por engano)
            if not modelos_limpos and p.get("models"):
                registro["models"] = p["models"]
            lista[i] = registro
            break
    else:
        lista.append(registro)

    _escrever_arquivo(lista)
    return registro


def remover(pid: str) -> bool:
    """
    Remove um provedor personalizado.

    A chave NAO e apagada do .env de proposito: se o usuario remover por engano,
    recriar o provedor com o mesmo nome volta a funcionar.
    """
    pid = (pid or "").strip().lower()
    lista = _ler_arquivo()
    nova = [p for p in lista if p.get("id") != pid]
    if len(nova) == len(lista):
        return False
    _escrever_arquivo(nova)
    return True


def eh_personalizado(pid: str) -> bool:
    return any(p.get("id") == (pid or "").strip().lower() for p in _ler_arquivo())


def ids_personalizados() -> list[str]:
    return [p["id"] for p in _ler_arquivo() if p.get("id")]
