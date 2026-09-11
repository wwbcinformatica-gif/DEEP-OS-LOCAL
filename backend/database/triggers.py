"""
Database Triggers — monitora tabelas SQLite e dispara acoes quando dados mudam.
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from pathlib import Path

from database.connection import get_conn

_log = logging.getLogger("wbc.triggers")

_triggers: dict[str, dict] = {}
_watching = False
_watch_task: asyncio.Task | None = None
_table_hashes: dict[str, str] = {}


def _compute_table_hash(table_name: str) -> str:
    """Computa hash do conteudo atual de uma tabela."""
    try:
        conn = get_conn()
        with conn:
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
            data = json.dumps([dict(r) for r in rows], default=str, sort_keys=True)
            return hashlib.md5(data.encode()).hexdigest()
    except Exception:
        return ""


def _detect_changes(table_name: str) -> dict | None:
    """Detecta mudancas em uma tabela comparando com hash anterior."""
    current_hash = _compute_table_hash(table_name)
    if not current_hash:
        return None

    old_hash = _table_hashes.get(table_name)
    _table_hashes[table_name] = current_hash

    if old_hash is None:
        return None  # Primeira vez, sem mudanca

    if old_hash != current_hash:
        return {
            "table": table_name,
            "old_hash": old_hash,
            "new_hash": current_hash,
            "detected_at": time.time(),
        }
    return None


async def _execute_trigger(trigger: dict, change: dict):
    """Executa a acao de um trigger quando mudanca detectada."""
    trigger_id = trigger["id"]
    _log.info("Trigger %s disparado para tabela %s", trigger_id, change["table"])

    trigger["last_fired"] = time.time()
    trigger["fire_count"] = trigger.get("fire_count", 0) + 1
    trigger["status"] = "firing"

    try:
        # Monta mensagem para o agente
        action = trigger.get("action", "notify")
        message = trigger.get("message", f"Mudanca detectada na tabela {change['table']}")

        if action == "execute":
            # Executa tarefa do agente
            from agents.loop import run_agent_task
            result = await run_agent_task(
                user_message=f"[Database Trigger] {message}",
                provider=trigger.get("provider", "opencode"),
                model=trigger.get("model", "deepseek-v4-flash-free"),
                source="trigger",
            )
            trigger["last_result"] = str(result)[:500]
        elif action == "webhook":
            # Envia webhook
            import httpx
            url = trigger.get("webhook_url", "")
            if url:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json={
                        "trigger": trigger_id,
                        "table": change["table"],
                        "event": "changed",
                        "timestamp": time.time(),
                    })
                    trigger["last_result"] = f"HTTP {resp.status_code}"

        trigger["status"] = "idle"
        _log.info("Trigger %s executado com sucesso", trigger_id)
    except Exception as e:
        trigger["status"] = "error"
        trigger["last_result"] = str(e)[:500]
        _log.error("Trigger %s falhou: %s", trigger_id, e)


async def _watch_loop():
    """Loop principal — verifica tabelas a cada 15 segundos."""
    global _watching
    _watching = True
    _log.info("Database trigger watcher iniciado")

    while _watching:
        # Coleta tabelas unicas dos triggers
        tables = set()
        for t in _triggers.values():
            if t.get("enabled", True):
                tables.add(t["table"])

        # Detecta mudancas
        for table in tables:
            change = _detect_changes(table)
            if change:
                # Dispara todos os triggers dessa tabela
                for trigger in _triggers.values():
                    if trigger["table"] == table and trigger.get("enabled", True):
                        asyncio.create_task(_execute_trigger(trigger, change))

        await asyncio.sleep(15)


def _ensure_watcher():
    """Garante que o watcher esta rodando."""
    global _watch_task
    if _watch_task is None or _watch_task.done():
        _watch_task = asyncio.create_task(_watch_loop())


async def trigger_create(
    table: str,
    action: str = "notify",
    message: str = "",
    webhook_url: str = "",
    provider: str = "opencode",
    model: str = "deepseek-v4-flash-free",
) -> dict:
    """Cria um trigger em uma tabela."""
    # Verifica se tabela existe
    try:
        conn = get_conn()
        with conn:
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
    except Exception:
        raise ValueError(f"Tabela '{table}' nao existe no banco de dados")

    trigger_id = str(uuid.uuid4())[:8]
    trigger = {
        "id": trigger_id,
        "table": table,
        "action": action,
        "message": message,
        "webhook_url": webhook_url,
        "provider": provider,
        "model": model,
        "enabled": True,
        "created_at": time.time(),
        "last_fired": None,
        "fire_count": 0,
        "status": "idle",
    }
    _triggers[trigger_id] = trigger
    _ensure_watcher()

    # Inicializa hash da tabela
    _compute_table_hash(table)

    _log.info("Trigger criado: %s na tabela %s", trigger_id, table)
    return {"trigger_id": trigger_id, "table": table, "action": action}


async def trigger_delete(trigger_id: str) -> bool:
    """Remove um trigger."""
    removed = _triggers.pop(trigger_id, None)
    return removed is not None


async def trigger_list() -> dict:
    """Lista todos os triggers."""
    return {"triggers": list(_triggers.values()), "count": len(_triggers)}


async def trigger_enable(trigger_id: str) -> bool:
    """Ativa um trigger."""
    t = _triggers.get(trigger_id)
    if not t:
        return False
    t["enabled"] = True
    return True


async def trigger_disable(trigger_id: str) -> bool:
    """Desativa um trigger."""
    t = _triggers.get(trigger_id)
    if not t:
        return False
    t["enabled"] = False
    return True


async def trigger_list_tables() -> dict:
    """Lista tabelas disponiveis no banco."""
    try:
        conn = get_conn()
        with conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            tables = [r["name"] for r in rows]
        return {"tables": tables}
    except Exception as e:
        return {"tables": [], "error": str(e)}
