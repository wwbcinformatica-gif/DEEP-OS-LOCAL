"""
Sistema de Licenciamento DEEP-OS
===================================
Valida chaves de licença via API remota ou arquivo local.
"""
import hashlib
import json
import os
import platform
from datetime import datetime, timedelta
from pathlib import Path

import httpx

LICENSE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "license.json"
LICENSE_API_URL = os.environ.get("LICENSE_API_URL", "https://api.DEEP-OS.com/validate")
TIMEOUT_DAYS = int(os.environ.get("LICENSE_TIMEOUT_DAYS", "30"))


def _get_machine_id() -> str:
    """Gera um ID único da máquina baseado em hardware."""
    info = f"{platform.node()}-{platform.processor()}-{platform.machine()}"
    return hashlib.sha256(info.encode()).hexdigest()[:16]


def _load_local_license() -> dict:
    """Carrega licença do arquivo local."""
    if LICENSE_FILE.exists():
        try:
            return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_local_license(data: dict):
    """Salva licença no arquivo local."""
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def validate_license(license_key: str) -> dict:
    """
    Valida a chave de licença.
    
    Retorna:
        {"valid": bool, "error": str | None, "expires": str | None, "features": list}
    """
    if not license_key or license_key == "cole_sua_chave_aqui":
        return {"valid": False, "error": "Chave de licença não configurada", "expires": None, "features": []}

    machine_id = _get_machine_id()

    # Tenta validar via API remota primeiro
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                LICENSE_API_URL,
                json={"key": license_key, "machine_id": machine_id},
            )
            if response.status_code == 200:
                data = response.json()
                _save_local_license(data)
                return data
    except Exception:
        pass

    # Fallback: valida offline (cache local)
    local = _load_local_license()
    if local and local.get("key") == license_key:
        expires = local.get("expires", "")
        if expires:
            try:
                exp_date = datetime.fromisoformat(expires)
                if exp_date > datetime.now():
                    return local
                else:
                    return {"valid": False, "error": "Licença expirada", "expires": expires, "features": []}
            except Exception:
                pass

    return {"valid": False, "error": "Licença inválida", "expires": None, "features": []}


def generate_license_key(customer_id: str, days: int = 30) -> str:
    """Gera uma chave de licença (usado no painel administrativo)."""
    expiry = datetime.now() + timedelta(days=days)
    raw = f"{customer_id}-{expiry.isoformat()}-DEEP-OS-secret"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def check_license() -> dict:
    """Verifica se a instância atual está licenciada."""
    license_key = os.environ.get("DEEP_AUREA_LICENSE", "")
    if not license_key:
        local = _load_local_license()
        license_key = local.get("key", "")
    
    return await validate_license(license_key)
