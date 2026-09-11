"""
Logs Routes — API para visualizacao e analise de logs.
"""
from fastapi import APIRouter, Query

from core.log_viewer import logs_clear, logs_read, logs_stats

router = APIRouter()


@router.get("/logs")
async def api_read_logs(
    lines: int = Query(100, ge=1, le=5000),
    level: str | None = Query(None),
    search: str | None = Query(None),
    since: str | None = Query(None),
    logger: str | None = Query(None),
):
    """Le e filtra logs do backend."""
    return await logs_read(lines=lines, level=level, search=search, since=since, logger_filter=logger)


@router.get("/logs/stats")
async def api_log_stats():
    """Retorna estatisticas dos logs (por nivel, erros recentes)."""
    return await logs_stats()


@router.delete("/logs")
async def api_clear_logs():
    """Limpa o arquivo de log."""
    return await logs_clear()
