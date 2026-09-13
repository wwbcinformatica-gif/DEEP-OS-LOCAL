"""
Instancias do DEEP-OS — modelos salvos com nome proprio pelo assinante.

⚠️ POR QUE ESTE ARQUIVO FOI REESCRITO (VAZAMENTO ENTRE ASSINANTES)

O tenant vinha de um PARAMETRO DA REQUISICAO, nao do token:

    @router.get("")
    async def list_instances(tenant_id: str = ""):
        if tenant_id:
            ... WHERE tenant_id = ?
        else:
            cur.execute("SELECT * FROM instances ORDER BY created_at DESC")   # <-- TODOS

E o frontend (JarvisPage) chama `/api/instances` SEM passar `tenant_id`. Resultado:
o `SELECT` caia no ramo SEM FILTRO e devolvia as instancias de **todos os
assinantes** — nome, modelo, provedor, `system_prompt` e `temperature`. Como a
tela usa esses campos, uma instancia de outro cliente podia ate ser adotada e
usada na conversa.

Pior ainda em `PUT` e `DELETE`, que nao olhavam tenant NENHUM: qualquer usuario
autenticado podia ALTERAR ou APAGAR a instancia de outro so sabendo o id.

Este e exatamente o risco que o usuario levantou por conta propria:
"se for um usuario esperto como o programa e de aluguel ele poderia ter acesso a
outras conversas e pesquisas de outros usuarios".

A CORRECAO segue o padrao que o resto do projeto ja usa (`routes/shop.py`,
`routes/auth.py`): o tenant vem do JWT, via `Depends(get_current_tenant_id)`, e
e conferido em toda operacao que mexe em UMA instancia.

Nao volte a aceitar `tenant_id` como parametro: e o mesmo defeito da rota
catch-all que ja vazou identidade neste projeto, em outra roupa.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_tenant_id
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
async def list_instances(tenant_id: str = Depends(get_current_tenant_id)):
    """
    Lista SOMENTE as instancias do assinante do token.

    O `tenant_id` NAO e parametro: vem do JWT. Antes, sem o parametro, a rota
    devolvia as instancias de todos os assinantes.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM instances WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
        return {"instances": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("")
async def create_instance(inst: InstanceCreate, tenant_id: str = Depends(get_current_tenant_id)):
    """Cria uma instancia PARA O ASSINANTE DO TOKEN (nunca para um id recebido)."""
    iid = str(uuid.uuid4())[:12]
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO instances (id, tenant_id, name, model, provider) VALUES (?, ?, ?, ?, ?)",
            (iid, tenant_id, inst.name, inst.model, inst.provider),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM instances WHERE id = ?", (iid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def _exigir_dono(conn, instance_id: str, tenant_id: str) -> dict:
    """
    Devolve a instancia se ela for DO ASSINANTE; 404 se nao for dele.

    Responde 404 (e nao 403) de proposito: 403 confirmaria que aquele id existe e
    e de outra pessoa — informacao que nao precisa ser dada a quem tentou.
    """
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    if not row or dict(row).get("tenant_id") != tenant_id:
        raise HTTPException(404, "Instancia nao encontrada")
    return dict(row)


@router.put("/{instance_id}")
async def update_instance(
    instance_id: str,
    inst: InstanceUpdate,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Altera uma instancia — so se ela pertencer ao assinante do token."""
    conn = get_conn()
    try:
        _exigir_dono(conn, instance_id, tenant_id)
        updates = {k: v for k, v in inst.model_dump().items() if v is not None}
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [datetime.utcnow().isoformat(), instance_id]
            conn.execute(f"UPDATE instances SET {set_clause}, updated_at = ? WHERE id = ?", values)
            conn.commit()
        row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.delete("/{instance_id}")
async def delete_instance(instance_id: str, tenant_id: str = Depends(get_current_tenant_id)):
    """Apaga uma instancia — so se ela pertencer ao assinante do token."""
    conn = get_conn()
    try:
        _exigir_dono(conn, instance_id, tenant_id)
        cur = conn.execute(
            "DELETE FROM instances WHERE id = ? AND tenant_id = ?", (instance_id, tenant_id)
        )
        conn.commit()
        if not cur.rowcount:
            raise HTTPException(404, "Instancia nao encontrada")
        return {"status": "deleted", "id": instance_id}
    finally:
        conn.close()
