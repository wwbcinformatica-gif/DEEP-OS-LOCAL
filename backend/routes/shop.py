"""
Rota pública de produtos digitais (Downloads) + Planos públicos
"""
import json
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from core.auth import get_current_tenant_id
from database.connection import get_conn

router = APIRouter(tags=["Shop"])


# ─── Planos públicos ──────────────────────────────────────────────
PLANS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "plans.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "system_config.json")


def _load_plans():
    """Carrega planos: overrides do arquivo + DEFAULT_PLANS."""
    from models.plan import PlanType, DEFAULT_PLANS
    
    saved = {}
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
    except Exception:
        pass
    
    plans = []
    for pt in PlanType:
        if pt in DEFAULT_PLANS:
            base = DEFAULT_PLANS[pt]
            plan_info = {
                "id": pt.value,
                "name": base["name"],
                "price": base["price"],
                "interval": base["interval"],
                "description": base["description"],
                "features": base["features"].model_dump(),
                "discount_percent": base.get("discount_percent"),
                "includes_jarvis_lifetime": base.get("includes_jarvis_lifetime", False),
                "is_active": True,
            }
            if pt.value in saved:
                plan_info.update({k: v for k, v in saved[pt.value].items() if v is not None})
            # Só exibe na loja se estiver ativo
            if plan_info.get("is_active", True):
                plans.append(plan_info)
    
    # Adiciona planos customizados salvos no arquivo
    for plan_id, plan_data in saved.items():
        if plan_id not in [pt.value for pt in PlanType]:
            plan_data = {
                "id": plan_id,
                "is_active": True,
                **plan_data,
            }
            if plan_data.get("is_active"):
                plans.append(plan_data)
    return plans


def _load_system_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_system_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


@router.get("/plans/public")
async def get_public_plans():
    """Retorna planos atuais (publico, sem autenticacao)."""
    return {"plans": _load_plans()}


# ─── Produtos públicos ────────────────────────────────────────────

@router.get("/shop/products")
async def get_shop_products():
    """Retorna produtos publicos para a loja."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM products WHERE status = 'available' ORDER BY sort_order ASC, created_at DESC"
        ).fetchall()
        products = []
        for r in rows:
            p = dict(r)
            p["features"] = json.loads(p.get("features", "[]"))
            products.append(p)
        return {"products": products}
    finally:
        conn.close()


@router.get("/shop/products/{product_id}")
async def get_shop_product(product_id: str):
    """Retorna um produto especifico."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Produto nao encontrado")
        p = dict(r)
        p["features"] = json.loads(p.get("features", "[]"))
        return p
    finally:
        conn.close()


# ─── Assinatura de plano ──────────────────────────────────────────

class SubscribeRequest(BaseModel):
    plan_id: str


@router.post("/plans/subscribe")
async def subscribe_plan(req: SubscribeRequest, tenant_id: str = Depends(get_current_tenant_id)):
    """Assina um plano. Planos gratuitos (price=0) ativam imediatamente."""
    from database.connection import get_conn

    plans = _load_plans()
    plan = next((p for p in plans if p["id"] == req.plan_id), None)
    if not plan:
        raise HTTPException(404, "Plano nao encontrado")

    if plan["price"] > 0:
        raise HTTPException(402, "Integracao de pagamento ainda nao disponivel")

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE tenants SET plan = ?, updated_at = datetime('now') WHERE id = ?",
            (req.plan_id, tenant_id)
        )
        conn.commit()
        return {
            "message": f"Plano {plan['name']} ativado com sucesso!",
            "plan": req.plan_id,
            "tenant_id": tenant_id
        }
    finally:
        conn.close()


# ─── Solicitacao de pagamento via PIX ─────────────────────────────

class PaymentRequestModel(BaseModel):
    plan_id: str
    amount: float
    notes: Optional[str] = None


@router.post("/plans/request-payment")
async def request_payment(req: PaymentRequestModel, tenant_id: str = Depends(get_current_tenant_id)):
    """Envia solicitacao de pagamento para o admin confirmar."""
    from datetime import datetime

    conn = get_conn()
    try:
        tenant = conn.execute("SELECT id, name, email FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        if not tenant:
            raise HTTPException(404, "Usuario nao encontrado")
        
        # Verifica se ja existe solicitacao pendente no banco para este plano
        existing = conn.execute(
            "SELECT id FROM payments WHERE tenant_id = ? AND plan_id = ? AND status = 'pending'",
            (tenant_id, req.plan_id)
        ).fetchone()
        if existing:
            return {"message": "Solicitacao ja enviada. Aguardando confirmacao do admin.", "status": "pending"}
        
        # Salva no banco de dados para historico
        conn.execute("""
            INSERT INTO payments (tenant_id, amount, currency, method, source, status, plan_id, subscription_months, created_at, updated_at)
            VALUES (?, ?, 'BRL', 'pix', 'pix', 'pending', ?, 3, datetime('now'), datetime('now'))
        """, (tenant_id, req.amount, req.plan_id))
        conn.commit()
    finally:
        conn.close()

    # Mantem compatibilidade com sistema antigo de pending_payments em JSON
    config = _load_system_config()
    pending = config.get("pending_payments", [])

    existing_json = next((p for p in pending if p.get("tenant_id") == tenant_id and p.get("plan_id") == req.plan_id), None)
    if not existing_json:
        pending.append({
            "tenant_id": tenant_id,
            "tenant_name": tenant["name"],
            "tenant_email": tenant["email"],
            "plan_id": req.plan_id,
            "amount": req.amount,
            "notes": req.notes or "",
            "requested_at": datetime.utcnow().isoformat(),
            "status": "pending",
        })
        config["pending_payments"] = pending
        _save_system_config(config)

    return {"message": "Solicitacao de pagamento enviada! Aguarde confirmacao do admin.", "status": "pending"}


# ─── Meus Downloads (tenant logado) ─────────────────────────────

@router.get("/shop/my-products")
async def get_my_products(tenant_id: str = Depends(get_current_tenant_id)):
    """Lista produtos liberados para o tenant autenticado."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT p.* FROM products p
            INNER JOIN tenant_products tp ON p.id = tp.product_id
            WHERE tp.tenant_id = ?
            ORDER BY p.sort_order ASC
        """, (tenant_id,)).fetchall()
        products = []
        for r in rows:
            p = dict(r)
            p["features"] = json.loads(p.get("features", "[]"))
            products.append(p)
        return {"products": products}
    finally:
        conn.close()


# ─── Meus Pagamentos (tenant logado) ─────────────────────────────

@router.get("/shop/my-payments")
async def get_my_payments(tenant_id: str = Depends(get_current_tenant_id)):
    """Lista historico de pagamentos do tenant autenticado."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, amount, method, status, plan_id, created_at, updated_at
            FROM payments
            WHERE tenant_id = ?
            ORDER BY created_at DESC
        """, (tenant_id,)).fetchall()
        payments = [dict(r) for r in rows]
        return {"payments": payments}
    finally:
        conn.close()
