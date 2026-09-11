"""Task management system."""
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    subject: str = ""
    description: str = ""
    status: str = "pending"
    active_form: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "active_form": self.active_form,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

_tasks: dict[str, Task] = {}

async def create_task(subject: str, description: str = "", active_form: str = "") -> Task:
    task = Task(subject=subject, description=description, active_form=active_form)
    _tasks[task.id] = task
    return task

async def get_task(task_id: str) -> Task | None:
    return _tasks.get(task_id)

async def update_task(task_id: str, **fields) -> Task | None:
    task = _tasks.get(task_id)
    if not task:
        return None
    for k, v in fields.items():
        if hasattr(task, k) and v is not None:
            setattr(task, k, v)
    task.updated_at = time.time()
    return task

async def list_tasks(status: str | None = None) -> list[Task]:
    if status:
        return [t for t in _tasks.values() if t.status == status]
    return list(_tasks.values())

async def stop_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if not task:
        return False
    task.status = "killed"
    task.updated_at = time.time()
    return True

async def delete_task(task_id: str) -> bool:
    return _tasks.pop(task_id, None) is not None
