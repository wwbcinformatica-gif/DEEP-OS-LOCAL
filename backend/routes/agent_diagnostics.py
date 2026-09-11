"""
DEEP-OS — Agent Diagnostics & Run Routes
=================================================
Endpoints para monitoramento e execução do agente:
  GET  /agent/diagnostics   — Histórico de falhas, ferramentas, taxa de circuit breaker
  GET  /memory/anti-patterns — Lista de lições de falha (is_failure: True)
  POST /agent/run            — Executa tarefa e retorna resultado ou graça diagnóstica
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import MEMORY_DIR

router = APIRouter()


# ─── Models ─────────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    task: str
    provider: str = "groq"
    model: str = "llama-3.1-70b-versatile"
    temperature: float = 0.3
    max_steps: int = 0
    personality: str = "Voce e um engenheiro de software eficiente e objetivo."


# ─── In-memory diagnostics store (reseta com o servidor) ────────────────

_diagnostics_log: list[dict] = []
_circuit_breaker_activations: int = 0
_total_runs: int = 0


def _record_diagnostic(event: dict):
    _diagnostics_log.append({
        **event,
        "timestamp": datetime.now().isoformat(),
    })
    # Mantém apenas últimos 100
    if len(_diagnostics_log) > 100:
        _diagnostics_log.pop(0)


# ─── GET /agent/diagnostics ─────────────────────────────────────────────

@router.get("/agent/diagnostics")
async def api_agent_diagnostics():
    """
    Retorna histórico das últimas falhas, ferramentas mais utilizadas
    e taxa de ativação do circuit breaker.
    """
    # Lê falhas do index.json
    index_file = MEMORY_DIR / "long_term" / "index.json"
    failure_count = 0
    success_count = 0
    tools_frequency: dict[str, int] = {}

    if index_file.exists():
        try:
            with open(index_file, encoding="utf-8") as f:
                entries = json.load(f)
            for e in entries:
                if e.get("is_failure"):
                    failure_count += 1
                else:
                    success_count += 1
                for t in e.get("tools_used", []):
                    tools_frequency[t] = tools_frequency.get(t, 0) + 1
        except (json.JSONDecodeError, Exception):
            pass

    # Ordena ferramentas por frequência
    top_tools = sorted(tools_frequency.items(), key=lambda x: x[1], reverse=True)[:10]

    cb_rate = (
        _circuit_breaker_activations / _total_runs * 100
        if _total_runs > 0
        else 0
    )

    return {
        "summary": {
            "total_runs": _total_runs,
            "circuit_breaker_activations": _circuit_breaker_activations,
            "circuit_breaker_rate_pct": round(cb_rate, 1),
            "total_memories": success_count + failure_count,
            "success_memories": success_count,
            "failure_memories": failure_count,
        },
        "top_tools": [{"tool": t, "count": c} for t, c in top_tools],
        "recent_events": _diagnostics_log[-20:],
    }


# ─── GET /memory/anti-patterns ──────────────────────────────────────────

@router.get("/memory/anti-patterns")
async def api_memory_anti_patterns():
    """
    Retorna especificamente a lista de lições de falhas
    (is_failure: True) registradas no index.json.
    """
    index_file = MEMORY_DIR / "long_term" / "index.json"
    if not index_file.exists():
        return {"anti_patterns": [], "count": 0}

    try:
        with open(index_file, encoding="utf-8") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, Exception):
        return {"anti_patterns": [], "count": 0}

    failures = []
    for e in entries:
        if e.get("is_failure"):
            failures.append({
                "hash": e.get("hash", ""),
                "task": e.get("task", ""),
                "failure_reason": e.get("solution_summary", "")[:500],
                "tools_attempted": e.get("tools_used", []),
                "error_summary": e.get("lessons_learned", "")[:500],
                "timestamp": e.get("timestamp", ""),
            })

    # Mais recentes primeiro
    failures.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "anti_patterns": failures,
        "count": len(failures),
    }


# ─── POST /agent/run ────────────────────────────────────────────────────

@router.post("/agent/run")
async def api_agent_run(req: AgentRunRequest):
    """
    Executa uma tarefa completa via agente e retorna:
    - Em caso de sucesso: { status, result, steps }
    - Em caso de falha: { status, result (graceful message), diagnostics }
    """
    global _total_runs, _circuit_breaker_activations
    _total_runs += 1

    from agents.loop import run_agent

    start = time.time()
    try:
        result = await run_agent(
            task=req.task,
            provider=req.provider,
            model=req.model,
            temperature=req.temperature,
            max_steps=req.max_steps if req.max_steps > 0 else None,
            personality=req.personality,
        )
    except Exception as e:
        _record_diagnostic({
            "event": "run_error",
            "task": req.task[:200],
            "error": str(e)[:300],
        })
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - start
    status = result.get("status", "unknown")

    # Registra diagnóstico
    event = {
        "event": "run_complete",
        "task": req.task[:200],
        "status": status,
        "steps": result.get("steps", 0),
        "elapsed_s": round(elapsed, 2),
    }

    if status in ("circuit_breaker", "failed", "max_steps"):
        _circuit_breaker_activations += 1
        event["diagnostics"] = result.get("diagnostics", {})

    _record_diagnostic(event)

    return {
        "status": status,
        "result": result.get("result", ""),
        "steps": result.get("steps", 0),
        "elapsed_s": round(elapsed, 2),
        "diagnostics": result.get("diagnostics", {}),
    }
