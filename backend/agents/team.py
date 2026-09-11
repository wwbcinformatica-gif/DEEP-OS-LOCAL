"""Agent team coordination system."""
import time
import uuid

_teams: dict[str, dict] = {}
_messages: list[dict] = []

async def team_create(name: str, members: list | None = None) -> dict:
    team_id = str(uuid.uuid4())[:8]
    _teams[team_id] = {
        "id": team_id,
        "name": name,
        "members": members or [],
        "created_at": time.time(),
    }
    return {"team_id": team_id, "name": name, "members": members or []}

async def team_delete(team_id: str) -> dict:
    removed = _teams.pop(team_id, None)
    return {"deleted": removed is not None, "team_id": team_id}

async def send_message(recipient: str, message: str) -> dict:
    msg_id = str(uuid.uuid4())[:8]
    msg = {
        "id": msg_id,
        "recipient": recipient,
        "message": message,
        "timestamp": time.time(),
    }
    _messages.append(msg)
    return {"message_id": msg_id, "sent": True}

async def get_messages(agent_id: str = "") -> dict:
    filtered = [m for m in _messages if not agent_id or m.get("recipient") == agent_id]
    return {"messages": filtered, "count": len(filtered)}
