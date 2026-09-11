"""
Database Triggers Routes — API para gerenciamento de triggers de banco.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.triggers import (
    trigger_create,
    trigger_delete,
    trigger_disable,
    trigger_enable,
    trigger_list,
    trigger_list_tables,
)

router = APIRouter()


class TriggerCreateRequest(BaseModel):
    table: str
    action: str = "notify"
    message: str = ""
    webhook_url: str = ""
    provider: str = "opencode"
    model: str = "deepseek-v4-flash-free"


@router.post("/triggers")
async def api_create_trigger(req: TriggerCreateRequest):
    """Cria um trigger em uma tabela do banco."""
    try:
        return await trigger_create(
            table=req.table,
            action=req.action,
            message=req.message,
            webhook_url=req.webhook_url,
            provider=req.provider,
            model=req.model,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar trigger: {e}")


@router.delete("/triggers/{trigger_id}")
async def api_delete_trigger(trigger_id: str):
    """Remove um trigger."""
    ok = await trigger_delete(trigger_id)
    if not ok:
        raise HTTPException(404, "Trigger nao encontrado")
    return {"status": "deleted", "trigger_id": trigger_id}


@router.get("/triggers")
async def api_list_triggers():
    """Lista todos os triggers ativos."""
    return await trigger_list()


@router.get("/triggers/tables")
async def api_list_tables():
    """Lista tabelas disponiveis no banco de dados."""
    return await trigger_list_tables()


@router.post("/triggers/{trigger_id}/enable")
async def api_enable_trigger(trigger_id: str):
    """Ativa um trigger."""
    ok = await trigger_enable(trigger_id)
    if not ok:
        raise HTTPException(404, "Trigger nao encontrado")
    return {"status": "enabled", "trigger_id": trigger_id}


@router.post("/triggers/{trigger_id}/disable")
async def api_disable_trigger(trigger_id: str):
    """Desativa um trigger."""
    ok = await trigger_disable(trigger_id)
    if not ok:
        raise HTTPException(404, "Trigger nao encontrado")
    return {"status": "disabled", "trigger_id": trigger_id}
