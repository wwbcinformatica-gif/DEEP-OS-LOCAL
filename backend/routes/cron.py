"""
Cron Routes — API completa para gerenciamento de jobs agendados.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cron.scheduler import (
    cron_create,
    cron_delete,
    cron_list,
    cron_pause,
    cron_resume,
    cron_run_now,
)

router = APIRouter()


class CronCreateRequest(BaseModel):
    expression: str
    task: str
    task_id: str | None = None
    provider: str = "opencode"
    model: str = "deepseek-v4-flash-free"


@router.post("/cron")
async def api_create_cron(req: CronCreateRequest):
    """Cria um novo job cron com expressao e tarefa."""
    try:
        return await cron_create(
            expression=req.expression,
            task=req.task,
            task_id=req.task_id,
            provider=req.provider,
            model=req.model,
        )
    except Exception as e:
        raise HTTPException(400, f"Erro ao criar cron: {e}")


@router.delete("/cron/{job_id}")
async def api_delete_cron(job_id: str):
    """Remove um job cron."""
    ok = await cron_delete(job_id)
    if not ok:
        raise HTTPException(404, "Job nao encontrado")
    return {"status": "deleted", "job_id": job_id}


@router.get("/cron")
async def api_list_cron():
    """Lista todos os jobs cron ativos."""
    return await cron_list()


@router.post("/cron/{job_id}/pause")
async def api_pause_cron(job_id: str):
    """Pausa um job cron."""
    ok = await cron_pause(job_id)
    if not ok:
        raise HTTPException(404, "Job nao encontrado")
    return {"status": "paused", "job_id": job_id}


@router.post("/cron/{job_id}/resume")
async def api_resume_cron(job_id: str):
    """Retoma um job cron pausado."""
    ok = await cron_resume(job_id)
    if not ok:
        raise HTTPException(404, "Job nao encontrado ou nao pausado")
    return {"status": "resumed", "job_id": job_id}


@router.post("/cron/{job_id}/run")
async def api_run_cron(job_id: str):
    """Executa um job cron imediatamente."""
    ok = await cron_run_now(job_id)
    if not ok:
        raise HTTPException(404, "Job nao encontrado")
    return {"status": "executing", "job_id": job_id}
