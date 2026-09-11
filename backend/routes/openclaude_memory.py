from fastapi import APIRouter
from pydantic import BaseModel

from memory.openclaude_bridge import (
    export_to_openclaude_memory,
    import_openclaude_history,
    import_openclaude_sessions,
)

router = APIRouter()

class ExportPayload(BaseModel):
    conversation_text: str
    session_id: str = ""

@router.post("/openclaude/import/history")
async def api_import_history():
    result = await import_openclaude_history()
    return result

@router.post("/openclaude/import/sessions")
async def api_import_sessions():
    result = await import_openclaude_sessions()
    return result

@router.post("/openclaude/export")
async def api_export_memory(payload: ExportPayload):
    result = await export_to_openclaude_memory(payload.conversation_text, payload.session_id)
    return result
