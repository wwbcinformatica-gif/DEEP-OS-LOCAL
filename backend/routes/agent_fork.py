"""
Agent Forking Routes — REST API for subagent management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.fork import fork_subagent, get_subagent_result

router = APIRouter()


class ForkRequest(BaseModel):
    task: str
    system_prompt: str = ""
    tools: list[str] | None = None


@router.post("/agent/fork")
async def api_fork_subagent(req: ForkRequest):
    result = await fork_subagent(req.task, req.system_prompt, req.tools)
    return result


@router.get("/agent/fork/{subagent_id}")
async def api_get_subagent(subagent_id: str):
    result = await get_subagent_result(subagent_id)
    if not result:
        raise HTTPException(404, "Subagente não encontrado")
    return result
