import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.connection import get_conn

router = APIRouter(prefix="/api/instances", tags=["Instances"])


class InstanceCreate(BaseModel):
    name: str
    model: str = "gemini-2.5-flash"
    provider: str = "gemini"


class InstanceUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    provider: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None


@router.get("")
async def list_instances(tenant_id: str = ""):
    conn = get_conn()
    cur = conn.cursor()
    if tenant_id:
        cur.execute("SELECT * FROM instances WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,))
    else:
        cur.execute("SELECT * FROM instances ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"instances": rows}


@router.post("")
async def create_instance(inst: InstanceCreate, tenant_id: str = "default"):
    iid = str(uuid.uuid4())[:12]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO instances (id, tenant_id, name, model, provider) VALUES (?, ?, ?, ?, ?)",
        (iid, tenant_id, inst.name, inst.model, inst.provider)
    )
    conn.commit()
    row = cur.execute("SELECT * FROM instances WHERE id = ?", (iid,)).fetchone()
    conn.close()
    return dict(row)


@router.put("/{instance_id}")
async def update_instance(instance_id: str, inst: InstanceUpdate):
    conn = get_conn()
    cur = conn.cursor()
    existing = cur.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Instancia nao encontrada")
    updates = {k: v for k, v in inst.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [datetime.utcnow().isoformat(), instance_id]
        cur.execute(f"UPDATE instances SET {set_clause}, updated_at = ? WHERE id = ?", values)
        conn.commit()
    row = cur.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    return dict(row)


@router.delete("/{instance_id}")
async def delete_instance(instance_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(404, "Instancia nao encontrada")
    return {"status": "deleted", "id": instance_id}