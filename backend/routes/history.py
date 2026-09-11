from fastapi import APIRouter, HTTPException

from database.connection import get_conn

router = APIRouter()

@router.get("/history")
async def get_history():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, question, answer, created_at FROM history ORDER BY id DESC LIMIT 50"
    )
    rows = cur.fetchall()
    conn.close()
    return {
        "history": [
            {"id": r[0], "question": r[1], "answer": r[2], "created_at": r[3]}
            for r in rows
        ]
    }

@router.delete("/history/{item_id}")
async def delete_history(item_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM history WHERE id = ?", (item_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    return {"status": "ok"}

@router.delete("/history")
async def clear_history():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM history")
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Histórico limpo"}
