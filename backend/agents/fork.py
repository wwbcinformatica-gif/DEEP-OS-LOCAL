"""Agent fork/subagent system."""
import uuid

_subagents: dict[str, dict] = {}

async def fork_subagent(task: str, system_prompt: str = "", tools: list | None = None) -> dict:
    subagent_id = str(uuid.uuid4())[:8]
    _subagents[subagent_id] = {
        "id": subagent_id,
        "task": task,
        "system_prompt": system_prompt,
        "status": "running",
        "result": None,
    }
    return {"subagent_id": subagent_id, "status": "running"}

async def get_subagent_result(subagent_id: str) -> dict:
    agent = _subagents.get(subagent_id)
    if not agent:
        return {"error": f"Subagent {subagent_id} not found"}
    return agent
