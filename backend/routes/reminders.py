"""
Rotas de lembretes.

Expoe o servico `core.reminders` para o frontend: listar, criar, cancelar.
Isolado por tenant via JWT (require_plan(1) = a partir do plano mensal).
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from core.auth import require_plan
from core.tenant_identity import DEFAULT_TZ, get_tzinfo, safe_zoneinfo

logger = logging.getLogger("reminders.api")
router = APIRouter(prefix="/api/reminders", tags=["Reminders"])


class ReminderCreate(BaseModel):
    message: str
    fire_at: str  # "YYYY-MM-DD HH:MM" na hora LOCAL do usuario
    timezone: Optional[str] = None  # IANA, ex "America/Sao_Paulo"


class ReminderOut(BaseModel):
    id: int
    message: str
    fire_at: str
    status: str


def _parse_fire_at(raw: str, tz: Optional[str] = None) -> datetime:
    """
    Aceita 'YYYY-MM-DD HH:MM' ou ISO, interpretando na hora LOCAL do usuario.

    Retorna um datetime AWARE no fuso informado, para o core converter para
    UTC sem ambiguidade (o servidor roda em UTC; Brasilia e UTC-3).
    """
    candidatos = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )
    texto = (raw or "").strip().replace("Z", "")
    if "." in texto:
        texto = texto.split(".")[0]

    for fmt in candidatos:
        # NAO cortar a string por posicao: 'YYYY-MM-DD HH:MM' tem 16 chars e
        # seria truncado de forma errada. Deixa o strptime validar o formato —
        # ele exige o tamanho exato, entao tentar em ordem resolve.
        try:
            naive = datetime.strptime(texto, fmt)
        except ValueError:
            continue

        zone = safe_zoneinfo(tz) or get_tzinfo()
        # Se o usuario mandou algo com offset explicito, respeita.
        if naive.tzinfo is None:
            return naive.replace(tzinfo=zone)
        return naive

    raise HTTPException(400, f"Data invalida: {raw!r}. Use o formato YYYY-MM-DD HH:MM")


def _resolver_tz(x_timezone: Optional[str], body_tz: Optional[str]) -> str:
    """Fuso do usuario: corpo > header X-Timezone > padrao do projeto."""
    for candidato in (body_tz, x_timezone):
        if candidato and safe_zoneinfo(candidato):
            return candidato
    return DEFAULT_TZ


@router.get("")
async def list_my_reminders(
    include_fired: bool = False,
    tenant_id: str = Depends(require_plan(1)),
):
    """Lista os lembretes do tenant autenticado."""
    from core.reminders import list_reminders

    return {"reminders": list_reminders(tenant_id, include_fired=include_fired)}


@router.post("")
async def create_my_reminder(
    payload: ReminderCreate,
    tenant_id: str = Depends(require_plan(1)),
    x_timezone: Optional[str] = Header(default=None, alias="X-Timezone"),
):
    """Cria um lembrete para o tenant autenticado."""
    from core.reminders import add_reminder

    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(400, "A mensagem do lembrete e obrigatoria")

    tz = _resolver_tz(x_timezone, payload.timezone)
    fire_at = _parse_fire_at(payload.fire_at, tz)

    # Compara em UTC (o servidor roda em UTC; a entrada veio em hora local)
    from datetime import timezone as _tzmod
    if fire_at.astimezone(_tzmod.utc) <= datetime.now(_tzmod.utc):
        raise HTTPException(400, "O horario do lembrete precisa ser no futuro")

    reminder_id = add_reminder(
        fire_at=fire_at,
        message=message,
        tenant_id=tenant_id,
        channel="voice",
        tz=tz,
    )
    logger.info("Lembrete %s criado para o tenant %s (fuso %s)", reminder_id, tenant_id, tz)
    return {
        "status": "success",
        "id": reminder_id,
        "fire_at": fire_at.strftime("%Y-%m-%d %H:%M"),
        "timezone": tz,
    }


@router.get("/summary")
async def reminders_summary(
    tenant_id: str = Depends(require_plan(1)),
):
    """
    Resumo em texto dos lembretes (curto, para ser lido em voz).
    Serve tambem como endpoint leve para o frontend.
    """
    from core.reminders import list_reminders
    from core.reminder_doc import build_spoken_summary

    meus = list_reminders(tenant_id)
    return {
        "summary": build_spoken_summary(meus),
        "count": len(meus),
        "reminders": meus,
    }


@router.get("/export")
async def export_reminders_document(
    include_fired: bool = False,
    tenant_id: str = Depends(require_plan(1)),
):
    """
    Gera um documento com os lembretes e devolve o link de download.

    Mesmo caminho usado pelos resumos que ja funcionam: grava em downloads/
    e devolve /api/download?path=...
    """
    from core.reminders import list_reminders
    from core.reminder_doc import save_summary_document

    meus = list_reminders(tenant_id, include_fired=include_fired)
    doc = save_summary_document(meus, titulo="Meus Lembretes")

    if not doc:
        raise HTTPException(500, "Nao consegui gerar o documento de lembretes")

    logger.info("Documento de lembretes gerado: %s (%s itens)", doc["filename"], doc["count"])
    return {"status": "success", **doc}


# ─────────────────────────────────────────────────────────────────────────────
# ATENCAO: rota com parametro de caminho DEVE ficar por ultimo.
#
# O FastAPI resolve rotas na ordem de registro. Enquanto este DELETE vinha
# antes de `/summary` e `/export`, aqueles paths casavam com `/{reminder_id}`
# (que tenta converter "summary" para int e falha com 422) e as rotas
# literais ficavam inalcancaveis.
#
# Detectado por tests-manual/test_all_routes.py (parte 1, offline).
# ─────────────────────────────────────────────────────────────────────────────
@router.delete("/{reminder_id}")
async def cancel_my_reminder(
    reminder_id: int,
    tenant_id: str = Depends(require_plan(1)),
):
    """Cancela um lembrete pendente do tenant autenticado."""
    from core.reminders import list_reminders, cancel_reminder

    # Confirma que o lembrete pertence a este tenant antes de cancelar
    meus = {r["id"] for r in list_reminders(tenant_id, include_fired=True)}
    if reminder_id not in meus:
        raise HTTPException(404, "Lembrete nao encontrado")

    if not cancel_reminder(reminder_id):
        raise HTTPException(400, "Lembrete nao esta pendente")

    return {"status": "success", "id": reminder_id}
