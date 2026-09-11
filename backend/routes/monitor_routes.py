"""Rota REST para o dashboard de monitoramento."""
from fastapi import APIRouter

from tools.monitor import coletar_dashboard

router = APIRouter()

@router.get("/monitor")
async def get_monitor():
    return coletar_dashboard()
