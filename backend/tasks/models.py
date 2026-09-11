from datetime import datetime

from pydantic import BaseModel


class Task(BaseModel):
    id: str
    subject: str
    description: str = ""
    status: str = "pending"  # pending | running | completed | failed | killed
    active_form: str = ""
    metadata: dict = {}
    output: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __init__(self, **data):
        now = datetime.now().isoformat()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("updated_at"):
            data["updated_at"] = now
        if not data.get("id"):
            import uuid
            data["id"] = uuid.uuid4().hex[:12]
        super().__init__(**data)

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "active_form": self.active_form,
            "metadata": self.metadata,
            "output": self.output,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
