"""
Secrets Management — gerencia variaveis de ambiente e chaves de API de forma segura.
"""
import logging
import os
import re
import time
from pathlib import Path

_log = logging.getLogger("wbc.secrets")

_env_path: Path | None = None
_env_backup: dict[str, str] = {}


def init_secrets(env_path: Path | None = None):
    """Inicializa o sistema de secrets com o caminho do .env."""
    global _env_path
    if env_path:
        _env_path = env_path
    elif _env_path is None:
        _env_path = Path(__file__).parent.parent / ".env"
    _load_env_file()


def _load_env_file() -> dict[str, str]:
    """Le o arquivo .env e retorna dict de variaveis."""
    if not _env_path or not _env_path.exists():
        return {}
    env = {}
    with open(_env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env[key] = value
    return env


def _save_env_file(env: dict[str, str]):
    """Salva dict de variaveis no arquivo .env."""
    if not _env_path:
        raise RuntimeError("Caminho .env nao configurado")
    lines = []
    for key, value in sorted(env.items()):
        if " " in value or "'" in value or '"' in value:
            lines.append(f'{key}="{value}"')
        else:
            lines.append(f"{key}={value}")
    with open(_env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _mask_value(value: str) -> str:
    """Mascara valor sensivel para exibicao."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


async def secrets_list(hide_values: bool = True) -> dict:
    """Lista todas as variaveis de ambiente do .env."""
    init_secrets()
    env = _load_env_file()
    secrets = []
    for key, value in env.items():
        secrets.append({
            "key": key,
            "value": _mask_value(value) if hide_values else value,
            "is_masked": hide_values,
        })
    return {"secrets": secrets, "count": len(secrets), "file": str(_env_path)}


async def secrets_get(key: str, reveal: bool = False) -> dict:
    """Obtem valor de uma variavel especifica."""
    init_secrets()
    env = _load_env_file()
    if key not in env:
        raise KeyError(f"Secret '{key}' nao encontrado")
    value = env[key]
    return {
        "key": key,
        "value": value if reveal else _mask_value(value),
        "is_masked": not reveal,
    }


async def secrets_set(key: str, value: str, overwrite: bool = True) -> dict:
    """Define ou atualiza uma variavel de ambiente."""
    init_secrets()
    env = _load_env_file()

    if key in env and not overwrite:
        raise ValueError(f"Secret '{key}' ja existe. Use overwrite=True para atualizar")

    old_value = env.get(key)
    env[key] = value
    _save_env_file(env)

    # Atualiza variavel de ambiente atual tambem
    os.environ[key] = value

    _log.info("Secret definido: %s", key)
    return {
        "key": key,
        "created": old_value is None,
        "updated": old_value is not None,
    }


async def secrets_delete(key: str) -> dict:
    """Remove uma variavel de ambiente."""
    init_secrets()
    env = _load_env_file()

    if key not in env:
        raise KeyError(f"Secret '{key}' nao encontrado")

    del env[key]
    _save_env_file(env)

    # Remove do ambiente atual
    os.environ.pop(key, None)

    _log.info("Secret removido: %s", key)
    return {"deleted": True, "key": key}


async def secrets_bulk_set(secrets: dict[str, str]) -> dict:
    """Define multiplas variaveis de uma vez."""
    init_secrets()
    env = _load_env_file()
    results = []
    for key, value in secrets.items():
        old = env.get(key)
        env[key] = value
        os.environ[key] = value
        results.append({"key": key, "created": old is None, "updated": old is not None})

    _save_env_file(env)
    _log.info("Bulk secrets: %d atualizados", len(secrets))
    return {"results": results, "count": len(results)}


async def secrets_validate() -> dict:
    """Valida quais secrets estao configurados vs necessarios."""
    init_secrets()
    env = _load_env_file()

    required = {
        "GROQ_API_KEY": "Groq (Llama 3.3)",
        "OPENAI_API_KEY": "OpenAI (GPT-4)",
        "GEMINI_API_KEY": "Google Gemini",
        "MIMO_API_KEY": "MiMo V2.5",
        "OPENROUTER_API_KEY": "OpenRouter",
    }

    status = []
    for key, provider in required.items():
        value = env.get(key, "")
        is_set = bool(value) and not value.startswith("YOUR_") and not value.startswith("sk-placeholder")
        status.append({
            "key": key,
            "provider": provider,
            "configured": is_set,
            "masked_value": _mask_value(value) if is_set else None,
        })

    configured_count = sum(1 for s in status if s["configured"])
    return {
        "status": status,
        "configured": configured_count,
        "total": len(status),
    }
