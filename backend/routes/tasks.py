"""
Task Management REST API — mirrors OpenClaude's task system.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tasks.task_manager import create_task, delete_task, get_task, list_tasks, stop_task, update_task

router = APIRouter()


class TaskCreateRequest(BaseModel):
    subject: str
    description: str = ""
    active_form: str = ""
    metadata: dict = {}


class TaskUpdateRequest(BaseModel):
    status: str | None = None
    output: str | None = None
    active_form: str | None = None
    metadata: dict | None = None


@router.post("/tasks")
async def api_create_task(req: TaskCreateRequest):
    task = await create_task(req.subject, req.description, req.active_form, req.metadata)
    return task.to_dict()


@router.get("/tasks")
async def api_list_tasks(status: str = None):
    tasks = await list_tasks(status)
    return {"tasks": [t.to_dict() for t in tasks]}


@router.get("/tasks/{task_id}")
async def api_get_task(task_id: str):
    task = await get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.to_dict()


@router.put("/tasks/{task_id}")
async def api_update_task(task_id: str, req: TaskUpdateRequest):
    fields = {k: v for k, v in req.dict(exclude_none=True).items() if v is not None}
    task = await update_task(task_id, **fields)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.to_dict()


@router.post("/tasks/{task_id}/stop")
async def api_stop_task(task_id: str):
    ok = await stop_task(task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"status": "stopped"}


@router.delete("/tasks/{task_id}")
async def api_delete_task(task_id: str):
    ok = await delete_task(task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"status": "deleted"}
