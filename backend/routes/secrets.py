"""
Secrets Routes — API para gerenciamento de variaveis de ambiente.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.secrets import secrets_bulk_set, secrets_delete, secrets_get, secrets_list, secrets_set, secrets_validate

router = APIRouter()


class SecretSetRequest(BaseModel):
    key: str
    value: str
    overwrite: bool = True


class SecretBulkRequest(BaseModel):
    secrets: dict[str, str]


@router.get("/secrets")
async def api_list_secrets(hide_values: bool = True):
    """Lista todas as variaveis de ambiente do .env."""
    return await secrets_list(hide_values=hide_values)


@router.get("/secrets/validate")
async def api_validate_secrets():
    """Valida quais secrets estao configurados."""
    return await secrets_validate()


@router.get("/secrets/{key}")
async def api_get_secret(key: str, reveal: bool = False):
    """Obtem valor de uma variavel especifica."""
    try:
        return await secrets_get(key, reveal=reveal)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/secrets")
async def api_set_secret(req: SecretSetRequest):
    """Define ou atualiza uma variavel de ambiente."""
    try:
        return await secrets_set(req.key, req.value, req.overwrite)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/secrets/bulk")
async def api_bulk_set_secrets(req: SecretBulkRequest):
    """Define multiplas variaveis de uma vez."""
    return await secrets_bulk_set(req.secrets)


@router.delete("/secrets/{key}")
async def api_delete_secret(key: str):
    """Remove uma variavel de ambiente."""
    try:
        return await secrets_delete(key)
    except KeyError as e:
        raise HTTPException(404, str(e))
