"""
Servico de lembretes — persistencia + disparo.

Por que existe
--------------
A action `reminder` agendava via `schtasks` (Windows), `launchctl` (macOS),
`systemd-run --user` ou `at` (Linux). Num VPS headless NENHUMA funciona:

- `systemd-run --user` exige session bus do D-Bus (nao existe em servico root)
- `at` nao vem instalado no Ubuntu por padrao
- `notify-send` nao tem desktop para notificar

Resultado pratico: o Charon respondia "Nao consegui registrar o lembrete
no agendador do sistema."

Agora o lembrete vai para o SQLite e um loop asyncio dentro do proprio
backend dispara na hora certa. Vantagens:
- funciona headless no VPS
- sobrevive a restart do backend e reboot do servidor
- isolado por tenant
- reaproveita o WebSocket do Charon para avisar em voz
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

_log = logging.getLogger("reminders")

_POLL_INTERVAL = 20  # segundos
_task: Optional[asyncio.Task] = None
_running = False

# Formato unico de data no banco (ordenavel como texto em SQLite)
_FMT = "%Y-%m-%d %H:%M:%S"


def _conn():
    from database.connection import get_conn

    return get_conn()


def add_reminder(
    fire_at: datetime,
    message: str,
    tenant_id: Optional[str] = None,
    channel: str = "voice",
    tz: Optional[str] = None,
) -> int:
    """
    Grava um lembrete.

    CONVENCAO DE FUSO (importante):
    - `fire_at` e a hora LOCAL do usuario (naive), como ele pediu ("14:30").
    - `tz` e o fuso do usuario (IANA). Se omitido, usa o do contexto.
    - Internamente converte para UTC antes de gravar, e guarda o fuso na
      coluna `tz` para conseguir exibir de volta na hora local certa.
      O servidor roda em UTC; sem essa conversao, um lembrete das 14:30 em
      Brasilia parecia estar no passado.
    """
    from core.tenant_identity import get_current_timezone, safe_zoneinfo

    tz_name = tz or get_current_timezone()

    # Converte a hora local pedida pelo usuario para UTC
    fire_utc = fire_at
    zone = safe_zoneinfo(tz_name)
    if zone is not None:
        if fire_at.tzinfo is None:
            fire_utc = fire_at.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
        else:
            fire_utc = fire_at.astimezone(timezone.utc).replace(tzinfo=None)

    conn = _conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO reminders (tenant_id, message, fire_at, status, channel, tz)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (tenant_id, message, fire_utc.strftime(_FMT), channel, tz_name),
        )
        conn.commit()
        rid = cur.lastrowid
        _log.info(
            "Lembrete %s agendado para %s UTC (= %s em %s) (tenant=%s)",
            rid, fire_utc, fire_at, tz_name, tenant_id or "global",
        )
        return rid
    finally:
        conn.close()


def list_reminders(tenant_id: Optional[str] = None, include_fired: bool = False) -> list[dict]:
    """Lista lembretes. Sem tenant_id, retorna os globais."""
    conn = _conn()
    try:
        sql = "SELECT * FROM reminders WHERE "
        params: list = []

        if tenant_id:
            sql += "tenant_id = ? "
            params.append(tenant_id)
        else:
            sql += "tenant_id IS NULL "

        if not include_fired:
            sql += "AND status = 'pending' "

        sql += "ORDER BY fire_at ASC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cancel_reminder(reminder_id: int) -> bool:
    """Cancela um lembrete pendente."""
    conn = _conn()
    try:
        cur = conn.execute(
            "UPDATE reminders SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (reminder_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def due_reminders(now: Optional[datetime] = None) -> list[dict]:
    """
    Lembretes pendentes cujo horario ja passou.

    `fire_at` esta gravado em UTC. Compara com datetime.utcnow() por padrao —
    usar hora local do servidor aqui causaria disparo adiantado ou atrasado.

    Marca como 'pending' ainda; o chamador confirma com `mark_fired`
    depois de entregar — assim um erro de entrega nao perde o lembrete.
    """
    now = now or datetime.utcnow()
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT * FROM reminders
             WHERE status = 'pending' AND fire_at <= ?
             ORDER BY fire_at ASC
            """,
            (now.strftime(_FMT),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_fired(reminder_id: int) -> None:
    """Marca o lembrete como entregue."""
    conn = _conn()
    try:
        conn.execute(
            "UPDATE reminders SET status = 'fired', fired_at = datetime('now') WHERE id = ?",
            (reminder_id,),
        )
        conn.commit()
    finally:
        conn.close()


async def _deliver(reminder: dict) -> bool:
    """
    Entrega o lembrete ao assinante pelo WebSocket do Charon.

    Retorna True se entregou (ou se nao ha como entregar e nao vale retentar).
    """
    from routes.voice_ws import deliver_reminder

    try:
        return await deliver_reminder(
            reminder.get("tenant_id"), reminder["message"], reminder=reminder
        )
    except Exception as e:
        _log.warning("Falha ao entregar lembrete %s: %s", reminder["id"], e)
        return False


async def _reminder_loop() -> None:
    global _running

    _running = True
    _log.info("Servico de lembretes iniciado (intervalo %ss)", _POLL_INTERVAL)

    while _running:
        try:
            for reminder in due_reminders():
                # Define o fuso do lembrete no contexto, para a entrega
                # formatar o horario na hora local correta do usuario.
                try:
                    from core.tenant_identity import set_current_timezone
                    if reminder.get("tz"):
                        set_current_timezone(reminder["tz"])
                except Exception:
                    pass

                entregue = await _deliver(reminder)
                if entregue:
                    mark_fired(reminder["id"])
                else:
                    # Sem conexao ativa: tenta de novo no proximo ciclo.
                    # Nao marca como fired para nao perder o lembrete.
                    _log.info(
                        "Lembrete %s vencido, mas sem sessao ativa — tentando de novo", reminder["id"]
                    )
        except Exception as e:
            _log.error("Erro no loop de lembretes: %s", e)

        await asyncio.sleep(_POLL_INTERVAL)


def ensure_reminder_loop() -> None:
    """Inicia o loop de lembretes se ainda nao estiver rodando."""
    global _task

    if _task is None or _task.done():
        try:
            _task = asyncio.create_task(_reminder_loop())
        except RuntimeError:
            # Sem event loop rodando (ex: import em script) — ignora
            pass
