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


# ─────────────────────────────────────────────────────────────────────────────
# Mesma operação sob /api/ — POR QUE EXISTE
#
# O nginx de producao encaminha ao backend apenas os prefixos:
#     /api/  /auth/  /chat/  /voice/  /admin/  /ws/
# Qualquer outro caminho cai no `location /`, que devolve o HTML do frontend.
#
# Entao um `DELETE /history` vindo do NAVEGADOR nao chega no backend: recebe o
# index.html com HTTP 200. O frontend veria "sucesso" sem nada ter sido apagado —
# um falso positivo silencioso, do mesmo tipo que ja custou tempo neste projeto.
#
# (Localmente funciona, porque o Vite faz proxy e o middleware libera o Host
# local — ou seja, o bug SO apareceria em producao. Por isso a rota duplicada.)
# ─────────────────────────────────────────────────────────────────────────────
@router.delete("/api/history")
async def clear_history_api():
    """Limpa o historico do tenant atual (rota alcancavel via nginx)."""
    return await clear_history()
