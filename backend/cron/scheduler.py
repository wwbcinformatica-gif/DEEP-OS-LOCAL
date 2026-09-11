"""
Cron scheduler — executa tarefas agendadas usando asyncio.
Suporta expressoes cron simples: * * * * * (minuto hora dia mes dia_da_semana)
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Callable, Awaitable

_log = logging.getLogger("wbc.cron")

_jobs: dict[str, dict] = {}
_running = False
_task: asyncio.Task | None = None


def _parse_cron_field(field: str, min_val: int, max_val: int) -> list[int]:
    """Parseia um campo cron em lista de valores validos."""
    if field == "*":
        return list(range(min_val, max_val + 1))
    values = set()
    for part in field.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            values.update(range(int(start), int(end) + 1))
        elif "/" in part:
            start, step = part.split("/", 1)
            base = int(start) if start != "*" else min_val
            values.update(range(base, max_val + 1, int(step)))
        else:
            values.add(int(part))
    return sorted(v for v in values if min_val <= v <= max_val)


def _matches_cron(expr: str, dt: datetime) -> bool:
    """Verifica se datetime corresponde a expressao cron."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, day, month, weekday = parts
    return (
        dt.minute in _parse_cron_field(minute, 0, 59)
        and dt.hour in _parse_cron_field(hour, 0, 23)
        and dt.day in _parse_cron_field(day, 1, 31)
        and dt.month in _parse_cron_field(month, 1, 12)
        and dt.weekday() in _parse_cron_field(weekday, 0, 6)
    )


def _next_run(expr: str, after: datetime | None = None) -> datetime:
    """Calcula proxima execucao apos o momento dado."""
    after = after or datetime.now()
    candidate = after + timedelta(minutes=1)
    candidate = candidate.replace(second=0, microsecond=0)
    for _ in range(60 * 24 * 365):  # max 1 ano lookahead
        if _matches_cron(expr, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    return after + timedelta(hours=1)


async def _execute_job(job: dict):
    """Executa um job cron."""
    job_id = job["id"]
    task_text = job["task"]
    _log.info("Cron executando job %s: %s", job_id, task_text[:80])

    job["last_run"] = time.time()
    job["run_count"] = job.get("run_count", 0) + 1
    job["status"] = "running"

    try:
        # Chama o agent loop para executar a tarefa
        from agents.loop import run_agent_task

        result = await run_agent_task(
            user_message=task_text,
            provider=job.get("provider", "opencode"),
            model=job.get("model", "deepseek-v4-flash-free"),
            source="cron",
        )
        job["status"] = "done"
        job["last_result"] = str(result)[:500]
        _log.info("Cron job %s concluido com sucesso", job_id)
    except Exception as e:
        job["status"] = "error"
        job["last_result"] = str(e)[:500]
        _log.error("Cron job %s falhou: %s", job_id, e)


async def _scheduler_loop():
    """Loop principal do scheduler — verifica jobs a cada 30 segundos."""
    global _running
    _running = True
    _log.info("Cron scheduler iniciado")

    while _running:
        now = datetime.now()
        for job in list(_jobs.values()):
            if job.get("status") == "running":
                continue
            if job.get("next_run") and now >= job["next_run"]:
                asyncio.create_task(_execute_job(job))
                job["next_run"] = _next_run(job["expression"], now)

        await asyncio.sleep(30)


def _ensure_scheduler():
    """Garante que o loop do scheduler esta rodando."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_scheduler_loop())


async def cron_create(
    expression: str,
    task: str,
    task_id: str | None = None,
    provider: str = "opencode",
    model: str = "deepseek-v4-flash-free",
) -> dict:
    """Cria um novo job cron."""
    job_id = str(uuid.uuid4())[:8]
    next_run = _next_run(expression)

    job = {
        "id": job_id,
        "expression": expression,
        "task": task,
        "task_id": task_id,
        "provider": provider,
        "model": model,
        "created_at": time.time(),
        "next_run": next_run,
        "last_run": None,
        "last_result": None,
        "run_count": 0,
        "status": "idle",
    }
    _jobs[job_id] = job
    _ensure_scheduler()

    _log.info("Cron job criado: %s [%s] -> %s", job_id, expression, task[:60])
    return {
        "job_id": job_id,
        "expression": expression,
        "task": task,
        "next_run": next_run.isoformat(),
    }


async def cron_delete(job_id: str) -> bool:
    """Remove um job cron."""
    removed = _jobs.pop(job_id, None)
    if removed:
        _log.info("Cron job removido: %s", job_id)
    return removed is not None


async def cron_list() -> dict:
    """Lista todos os jobs cron."""
    jobs = []
    for j in _jobs.values():
        jobs.append({
            **j,
            "next_run": j["next_run"].isoformat() if j.get("next_run") else None,
        })
    return {"jobs": jobs, "count": len(jobs), "scheduler_running": _running}


async def cron_pause(job_id: str) -> bool:
    """Pausa um job cron."""
    job = _jobs.get(job_id)
    if not job:
        return False
    job["paused"] = True
    job["next_run"] = None
    return True


async def cron_resume(job_id: str) -> bool:
    """Retoma um job cron pausado."""
    job = _jobs.get(job_id)
    if not job or not job.get("paused"):
        return False
    job["paused"] = False
    job["next_run"] = _next_run(job["expression"])
    return True


async def cron_run_now(job_id: str) -> bool:
    """Executa um job imediatamente."""
    job = _jobs.get(job_id)
    if not job:
        return False
    asyncio.create_task(_execute_job(job))
    return True
