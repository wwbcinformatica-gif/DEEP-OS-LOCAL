"""
Team Routes — REST API for agent team coordination.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.team import get_messages, send_message, team_create, team_delete

router = APIRouter()


class TeamCreateRequest(BaseModel):
    name: str
    members: list[str] | None = None


class SendMessageRequest(BaseModel):
    recipient: str
    message: str


@router.post("/teams")
async def api_create_team(req: TeamCreateRequest):
    return await team_create(req.name, req.members)


@router.delete("/teams/{team_id}")
async def api_delete_team(team_id: str):
    result = await team_delete(team_id)
    if not result["deleted"]:
        raise HTTPException(404, "Time não encontrado")
    return {"status": "deleted"}


@router.post("/teams/message")
async def api_send_message(req: SendMessageRequest):
    return await send_message(req.recipient, req.message)


@router.get("/teams/messages/{agent_id}")
async def api_get_messages(agent_id: str):
    return {"messages": await get_messages(agent_id)}
