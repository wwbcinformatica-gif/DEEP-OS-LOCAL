"""
Workspace Routes — GET/POST /api/workspace
Gerencia o workspace ativo em runtime.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


class SetWorkspaceRequest(BaseModel):
    path: str


@router.get("")
async def get_workspace():
    from core.workspace_manager import WorkspaceManager
    wm = WorkspaceManager.get_instance()
    ws = wm.get_workspace()
    return {
        "workspace": str(ws),
        "name": wm.get_workspace_name(),
        "valid": True,
    }


@router.post("")
async def set_workspace(req: SetWorkspaceRequest):
    from core.workspace_manager import WorkspaceManager
    wm = WorkspaceManager.get_instance()
    result = wm.set_workspace(req.path)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Limpa historico ao trocar de workspace para evitar que o modelo
    # confunda contexto do projeto anterior com o novo
    try:
        from database.connection import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM history")
        conn.commit()
        conn.close()
    except Exception:
        pass

    return result


@router.get("/validate")
async def validate_workspace(path: str = ""):
    from core.workspace_manager import WorkspaceManager
    wm = WorkspaceManager.get_instance()
    return wm.validate_workspace(path)


@router.get("/list")
async def list_workspaces():
    from core.workspace_manager import WorkspaceManager
    wm = WorkspaceManager.get_instance()
    workspaces = wm.list_workspaces()
    return {"workspaces": [w.to_dict() for w in workspaces]}
