"""
Rotas do Painel Administrativo
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel

from core.auth import require_admin, AuthManager
from models.tenant import TenantCreate, TenantUpdate, TenantResponse
from models.plan import PlanType, DEFAULT_PLANS, PlanFeatures

router = APIRouter(prefix="/admin", tags=["Admin"])

# ─── Planos persistidos em JSON ──────────────────────────────────
PLANS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "plans.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "system_config.json")

def _load_plans_from_file():
    """Carrega planos salvos do arquivo JSON."""
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_plans_to_file(plans_data: dict):
    """Salva planos no arquivo JSON."""
    os.makedirs(os.path.dirname(PLANS_FILE), exist_ok=True)
    with open(PLANS_FILE, "w", encoding="utf-8") as f:
        json.dump(plans_data, f, ensure_ascii=False, indent=2)

def _get_plan_data(plan_id: str):
    """Retorna dados de um plano (arquivo > DEFAULT_PLANS)."""
    saved = _load_plans_from_file()
    if plan_id in saved:
        return saved[plan_id]
    # Busca no DEFAULT_PLANS
    for pt in PlanType:
        if pt.value == plan_id and pt in DEFAULT_PLANS:
            p = DEFAULT_PLANS[pt]
            return {
                "name": p["name"],
                "price": p["price"],
                "description": p["description"],
                "interval": p["interval"],
                "features": p["features"].model_dump(),
                "discount_percent": p.get("discount_percent"),
                "includes_jarvis_lifetime": p.get("includes_jarvis_lifetime", False),
            }
    return None

def _save_plan_override(plan_id: str, updates: dict):
    """Salva override de um plano no arquivo."""
    saved = _load_plans_from_file()
    if plan_id not in saved:
        # Carrega dados base do DEFAULT_PLANS
        base = _get_plan_data(plan_id)
        if not base:
            return False
        saved[plan_id] = base
    saved[plan_id].update(updates)
    _save_plans_to_file(saved)
    return True

# ─── Configuracao do Sistema ─────────────────────────────────────

def _load_system_config():
    """Carrega configuracoes do sistema."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_system_config(config: dict):
    """Salva configuracoes do sistema."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ─── PIX (Admin) ─────────────────────────────────────────────────

class PIXConfigRequest(BaseModel):
    pix_key: str
    pix_type: str = "random"  # random, cpf, cnpj, email, phone
    owner_name: Optional[str] = None
    instructions: Optional[str] = None
    pix_qr: Optional[str] = None  # base64 do QR code image
    pix_qr_base64: Optional[str] = None  # alias compat

@router.get("/pix")
async def get_pix_config(admin: str = Depends(require_admin)):
    """Retorna configuracao PIX do sistema (admin)."""
    config = _load_system_config()
    pix_qr_url = ""
    if config.get("pix_qr_file"):
        pix_qr_url = f"/admin/pix/qr"
    return {
        "pix_key": config.get("pix_key", ""),
        "pix_type": config.get("pix_type", "random"),
        "owner_name": config.get("owner_name", ""),
        "instructions": config.get("instructions", ""),
        "pix_qr_url": pix_qr_url,
        "updated_at": config.get("updated_at", ""),
    }

@router.put("/pix")
async def update_pix_config(
    req: PIXConfigRequest,
    admin: str = Depends(require_admin)
):
    """Atualiza configuracao PIX do sistema (admin)."""
    config = _load_system_config()
    config["pix_key"] = req.pix_key
    config["pix_type"] = req.pix_type
    config["owner_name"] = req.owner_name or ""
    config["instructions"] = req.instructions or ""
    
    # Salvar QR code como arquivo
    qr_data = req.pix_qr or req.pix_qr_base64
    if qr_data:
        import base64
        qr_dir = os.path.join(os.path.dirname(CONFIG_FILE))
        os.makedirs(qr_dir, exist_ok=True)
        qr_path = os.path.join(qr_dir, "pix_qr.png")
        with open(qr_path, "wb") as f:
            f.write(base64.b64decode(qr_data))
        config["pix_qr_file"] = "pix_qr.png"
        config.pop("pix_qr", None)  # Remove base64 antigo se existir
    
    config["updated_at"] = datetime.utcnow().isoformat()
    config["updated_by"] = admin
    _save_system_config(config)
    return {"message": "PIX configurado com sucesso", "pix_key": req.pix_key}

@router.get("/pix/qr")
async def get_pix_qr():
    """Retorna imagem do QR Code PIX."""
    config = _load_system_config()
    qr_file = config.get("pix_qr_file", "")
    if not qr_file:
        raise HTTPException(404, "QR Code nao configurado")
    qr_path = os.path.join(os.path.dirname(CONFIG_FILE), qr_file)
    if not os.path.exists(qr_path):
        raise HTTPException(404, "QR Code nao encontrado")
    from fastapi.responses import FileResponse
    return FileResponse(qr_path, media_type="image/png")

# ─── PIX (Publico) ───────────────────────────────────────────────

@router.get("/pix/public")
async def get_pix_public():
    """Retorna chave PIX publica para pagamento (sem autenticacao)."""
    config = _load_system_config()
    pix_key = config.get("pix_key", "")
    pix_qr_url = ""
    if config.get("pix_qr_file"):
        pix_qr_url = "/admin/pix/qr"
    if not pix_key:
        return {
            "pix_key": "",
            "pix_type": "",
            "owner_name": "",
            "instructions": "",
            "pix_qr_url": "",
        }
    return {
        "pix_key": pix_key,
        "pix_type": config.get("pix_type", "random"),
        "owner_name": config.get("owner_name", ""),
        "instructions": config.get("instructions", ""),
        "pix_qr_url": pix_qr_url,
    }

# ─── Pagamentos Pendentes ────────────────────────────────────────

class PaymentConfirmRequest(BaseModel):
    tenant_id: str
    plan_id: str
    amount: float
    notes: Optional[str] = None

@router.get("/payments/pending")
async def list_pending_payments(admin: str = Depends(require_admin)):
    """Lista pagamentos pendentes de confirmacao."""
    config = _load_system_config()
    pending = config.get("pending_payments", [])
    return {"payments": pending}

@router.post("/payments/confirm")
async def confirm_payment(
    req: PaymentConfirmRequest,
    admin: str = Depends(require_admin)
):
    """Confirma pagamento e ativa plano do usuario."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        # Verifica se tenant existe
        tenant = conn.execute("SELECT id, name, email FROM tenants WHERE id = ?", (req.tenant_id,)).fetchone()
        if not tenant:
            raise HTTPException(404, "Usuario nao encontrado")
        
        # Ativa plano
        conn.execute(
            "UPDATE tenants SET plan = ?, updated_at = datetime('now') WHERE id = ?",
            (req.plan_id, req.tenant_id)
        )
        
        # Atualiza pagamento no banco para confirmado
        conn.execute("""
            UPDATE payments 
            SET status = 'confirmed', updated_at = datetime('now'), paid_at = datetime('now')
            WHERE tenant_id = ? AND plan_id = ? AND status = 'pending'
        """, (req.tenant_id, req.plan_id))
        conn.commit()
        
        # Remove dos pendentes em JSON (compatibilidade)
        config = _load_system_config()
        pending = config.get("pending_payments", [])
        config["pending_payments"] = [p for p in pending if p.get("tenant_id") != req.tenant_id]
        _save_system_config(config)
        
        return {
            "message": f"Plano {req.plan_id} ativado para {tenant['name']}",
            "tenant_id": req.tenant_id,
            "plan": req.plan_id,
        }
    finally:
        conn.close()



@router.post("/payments/reject")
async def reject_payment(
    tenant_id: str = Query(...),
    admin: str = Depends(require_admin)
):
    """Rejeita solicitacao de pagamento."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        # Atualiza pagamento no banco para rejeitado
        conn.execute(
            "UPDATE payments SET status = 'rejected', updated_at = datetime('now') WHERE tenant_id = ? AND status = 'pending'",
            (tenant_id,)
        )
        conn.commit()
        
        # Remove dos pendentes em JSON
        config = _load_system_config()
        pending = config.get("pending_payments", [])
        config["pending_payments"] = [p for p in pending if p.get("tenant_id") != tenant_id]
        _save_system_config(config)
        
        return {"message": "Solicitacao de pagamento rejeitada"}
    finally:
        conn.close()


async def list_payment_history(admin: str = Depends(require_admin)):
    """Historico de pagamentos confirmados."""
    config = _load_system_config()
    history = config.get("payment_history", [])
    return {"payments": history}


# ─── Modelos de Request/Response ───────────────────────────────────

class DashboardStats(BaseModel):
    total_tenants: int
    active_tenants: int
    tenants_by_plan: dict
    mrr: float  # Monthly Recurring Revenue
    new_this_month: int


class TenantListItem(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    status: str
    created_at: str
    last_login: Optional[str]


# ─── Dashboard ─────────────────────────────────────────────────────

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(admin: str = Depends(require_admin)):
    """Retorna estatísticas do dashboard administrativo."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        # Total de tenants
        total = conn.execute("SELECT COUNT(*) as count FROM tenants").fetchone()["count"]
        
        # Tenants ativos
        active = conn.execute(
            "SELECT COUNT(*) as count FROM tenants WHERE status = 'active'"
        ).fetchone()["count"]
        
        # Tenants por plano
        by_plan = {}
        for plan in PlanType:
            count = conn.execute(
                "SELECT COUNT(*) as count FROM tenants WHERE plan = ?",
                (plan.value,)
            ).fetchone()["count"]
            by_plan[plan.value] = count
        
        # MRR (Monthly Recurring Revenue) - usa planos persistidos
        mrr = 0.0
        for plan_type in PlanType:
            count = by_plan.get(plan_type.value, 0)
            plan_data = _get_plan_data(plan_type.value)
            if plan_data:
                price = plan_data.get("price", 0)
                interval = plan_data.get("interval", "month")
                if interval == "year":
                    mrr += count * (price / 12)
                elif interval == "quarter":
                    mrr += count * (price / 3)
                else:
                    mrr += count * price
        
        # Novos este mês
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
        new_this_month = conn.execute(
            "SELECT COUNT(*) as count FROM tenants WHERE created_at >= ?",
            (month_start,)
        ).fetchone()["count"]
        
        return DashboardStats(
            total_tenants=total,
            active_tenants=active,
            tenants_by_plan=by_plan,
            mrr=round(mrr, 2),
            new_this_month=new_this_month
        )
    finally:
        conn.close()


# ─── Tenants CRUD ──────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    plan_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: str = Depends(require_admin)
):
    """Lista todos os tenants com paginação e filtros."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        query = "SELECT * FROM tenants WHERE 1=1"
        params = []
        
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        
        if plan_filter:
            query += " AND plan = ?"
            params.append(plan_filter)
        
        if search:
            query += " AND (name LIKE ? OR email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
        total = conn.execute(count_query, params).fetchone()["count"]
        
        # Paginação
        offset = (page - 1) * limit
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        results = conn.execute(query, params).fetchall()
        
        tenants = [
            TenantListItem(
                id=r["id"],
                name=r["name"],
                email=r["email"],
                plan=r["plan"],
                status=r["status"],
                created_at=r["created_at"],
                last_login=dict(r).get("last_login")
            )
            for r in results
        ]
        
        return {
            "tenants": tenants,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    finally:
        conn.close()


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    admin: str = Depends(require_admin)
):
    """Retorna detalhes de um tenant específico."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        result = conn.execute(
            "SELECT * FROM tenants WHERE id = ?",
            (tenant_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant não encontrado"
            )
        
        return dict(result)
    finally:
        conn.close()


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    update: TenantUpdate,
    admin: str = Depends(require_admin)
):
    """Atualiza um tenant."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        # Verifica se existe
        existing = conn.execute(
            "SELECT id FROM tenants WHERE id = ?",
            (tenant_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant não encontrado"
            )
        
        # Monta update dinâmico
        updates = []
        params = []
        
        for field, value in update.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(tenant_id)
            
            query = f"UPDATE tenants SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
        
        return {"message": "Tenant atualizado com sucesso"}
    finally:
        conn.close()


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: str,
    admin: str = Depends(require_admin)
):
    """Suspende um tenant."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE tenants SET status = 'suspended', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), tenant_id)
        )
        conn.commit()
        return {"message": "Tenant suspenso com sucesso"}
    finally:
        conn.close()


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    tenant_id: str,
    admin: str = Depends(require_admin)
):
    """Reativa um tenant."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE tenants SET status = 'active', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), tenant_id)
        )
        conn.commit()
        return {"message": "Tenant reativado com sucesso"}
    finally:
        conn.close()


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    admin: str = Depends(require_admin)
):
    """Deleta um tenant (soft delete)."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE tenants SET status = 'deleted', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), tenant_id)
        )
        conn.commit()
        return {"message": "Tenant removido com sucesso"}
    finally:
        conn.close()


# ─── Planos ────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(admin: str = Depends(require_admin)):
    """Lista todos os planos disponíveis (com overrides salvos)."""
    saved = _load_plans_from_file()
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
            }
            # Aplica overrides salvos
            if pt.value in saved:
                plan_info.update({k: v for k, v in saved[pt.value].items() if v is not None})
            plans.append(plan_info)
    return {"plans": plans}


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    interval: Optional[str] = None
    is_active: Optional[bool] = None
    discount_percent: Optional[int] = None
    features: Optional[dict] = None

@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    update: PlanUpdateRequest,
    admin: str = Depends(require_admin)
):
    """Atualiza plano existente (persistido em JSON)."""
    from models.plan import PlanType
    plan_type = None
    for pt in PlanType:
        if pt.value == plan_id:
            plan_type = pt
            break
    if not plan_type or plan_type not in DEFAULT_PLANS:
        raise HTTPException(404, "Plano nao encontrado")
    
    updates = {}
    for field in ["name", "price", "description", "interval", "is_active", "discount_percent", "features"]:
        value = getattr(update, field, None)
        if value is not None:
            updates[field] = value
    
    if updates:
        _save_plan_override(plan_id, updates)
    
    plan_data = _get_plan_data(plan_id)
    return {"message": "Plano atualizado", "plan": plan_data}



class CustomPlanCreate(BaseModel):
    id: str
    name: str
    price: float
    interval: str = "month"
    description: str = ""
    discount_percent: Optional[int] = None
    features: Optional[dict] = None
    is_active: bool = True

@router.post("/plans")
async def create_plan(
    req: CustomPlanCreate,
    admin: str = Depends(require_admin)
):
    """Cria um novo plano customizado."""
    saved = _load_plans_from_file()
    if req.id in saved:
        raise HTTPException(409, "Ja existe um plano com este ID")
    
    plan_data = {
        "id": req.id,
        "name": req.name,
        "price": req.price,
        "interval": req.interval,
        "description": req.description,
        "discount_percent": req.discount_percent,
        "is_active": req.is_active,
    }
    if req.features:
        plan_data["features"] = req.features
    
    saved[req.id] = plan_data
    _save_plans_to_file(saved)
    return {"message": "Plano criado com sucesso", "plan": plan_data}


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: str,
    admin: str = Depends(require_admin)
):
    """Remove um plano customizado. Planos padrao nao podem ser removidos."""
    from models.plan import PlanType
    for pt in PlanType:
        if pt.value == plan_id:
            raise HTTPException(403, "Planos padrao nao podem ser removidos")
    
    saved = _load_plans_from_file()
    if plan_id not in saved:
        raise HTTPException(404, "Plano nao encontrado")
    
    del saved[plan_id]
    _save_plans_to_file(saved)
    return {"message": "Plano removido com sucesso"}

class TenantEditRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    pix_key: Optional[str] = None


@router.put("/tenants/{tenant_id}/edit")
async def edit_tenant(
    tenant_id: str,
    edit: TenantEditRequest,
    admin: str = Depends(require_admin)
):
    """Edita dados de um tenant (nome, email, plano, status, etc)."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        existing = conn.execute("SELECT id, plan FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Tenant nao encontrado")
        
        old_plan = existing["plan"]
        new_plan = edit.plan if edit.plan is not None else old_plan
        
        updates = []
        params = []
        for field, value in edit.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(tenant_id)
            conn.execute(f"UPDATE tenants SET {', '.join(updates)} WHERE id = ?", params)
        
        # Se o plano foi alterado manualmente pelo admin, registra no historico de pagamentos
        if edit.plan is not None and edit.plan != old_plan:
            plan_data = _get_plan_data(edit.plan)
            plan_price = plan_data.get("price", 0) if plan_data else 0
            conn.execute("""
                INSERT INTO payments (tenant_id, amount, currency, method, source, status, plan_id, subscription_months, created_at, updated_at, paid_at)
                VALUES (?, ?, 'BRL', 'manual', 'manual', 'confirmed', ?, 1, datetime('now'), datetime('now'), datetime('now'))
            """, (tenant_id, plan_price, edit.plan))
        
        row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        conn.commit()
        return {"message": "Tenant atualizado", "tenant": dict(row)}
    finally:
        conn.close()



# ─── Pagamentos ────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: Optional[str] = Query(None),
    admin: str = Depends(require_admin)
):
    """Lista pagamentos (placeholder - integração com gateway)."""
    return {
        "payments": [],
        "total": 0,
        "page": page,
        "limit": limit
    }


# ─── Criar Tenant (Admin) ────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    name: str
    email: str
    password: str
    plan: str = "free"
    company: Optional[str] = None
    phone: Optional[str] = None


@router.post("/tenants")
async def create_tenant(
    req: CreateTenantRequest,
    admin: str = Depends(require_admin)
):
    """Cria um novo tenant diretamente pelo admin."""
    import secrets
    from database.connection import get_conn
    from core.auth import AuthManager

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE email = ?",
            (req.email,)
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email ja cadastrado"
            )

        tenant_id = secrets.token_hex(16)
        password_hash = AuthManager.hash_password(req.password)

        conn.execute("""
            INSERT INTO tenants (id, name, email, password_hash, plan, status, company, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            req.name,
            req.email,
            password_hash,
            req.plan,
            "active",
            req.company,
            req.phone,
            datetime.utcnow().isoformat()
        ))

        from middleware.tenant import create_tenant_dirs
        create_tenant_dirs(tenant_id)
        conn.commit()

        return {
            "message": "Tenant criado com sucesso",
            "tenant": {
                "id": tenant_id,
                "name": req.name,
                "email": req.email,
                "plan": req.plan,
                "status": "active"
            }
        }
    finally:
        conn.close()


# ─── Produtos Digitais CRUD ──────────────────────────────────────

class ProductRequest(BaseModel):
    name: str
    description: str = ""
    icon: str = "📦"
    image_url: str = ""
    category: str = "Geral"
    price: float = 0
    original_price: Optional[float] = None
    badge: str = ""
    badge_color: str = ""
    features: List[str] = []
    download_url: str = ""
    status: str = "available"
    sort_order: int = 0


@router.get("/products")
async def list_products(
    admin: str = Depends(require_admin)
):
    """Lista todos os produtos digitais."""
    from database.connection import get_conn
    import json
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM products ORDER BY sort_order ASC, created_at DESC").fetchall()
        products = []
        for r in rows:
            p = dict(r)
            p["features"] = json.loads(p.get("features", "[]"))
            products.append(p)
        return {"products": products}
    finally:
        conn.close()


@router.post("/products")
async def create_product(
    req: ProductRequest,
    admin: str = Depends(require_admin)
):
    """Cria um novo produto digital."""
    import secrets, json
    from database.connection import get_conn
    conn = get_conn()
    try:
        product_id = secrets.token_hex(8)
        conn.execute("""
            INSERT INTO products (id, name, description, icon, image_url, category, price, original_price, badge, badge_color, features, download_url, status, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id, req.name, req.description, req.icon, req.image_url,
            req.category, req.price, req.original_price, req.badge, req.badge_color,
            json.dumps(req.features), req.download_url, req.status, req.sort_order,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        return {"message": "Produto criado", "id": product_id}
    finally:
        conn.close()


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    req: ProductRequest,
    admin: str = Depends(require_admin)
):
    """Atualiza um produto digital."""
    import json
    from database.connection import get_conn
    conn = get_conn()
    try:
        existing = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Produto nao encontrado")
        conn.execute("""
            UPDATE products SET name=?, description=?, icon=?, image_url=?, category=?,
            price=?, original_price=?, badge=?, badge_color=?, features=?, download_url=?,
            status=?, sort_order=?, updated_at=? WHERE id=?
        """, (
            req.name, req.description, req.icon, req.image_url, req.category,
            req.price, req.original_price, req.badge, req.badge_color,
            json.dumps(req.features), req.download_url, req.status, req.sort_order,
            datetime.utcnow().isoformat(), product_id
        ))
        conn.commit()
        return {"message": "Produto atualizado"}
    finally:
        conn.close()


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    admin: str = Depends(require_admin)
):
    """Deleta um produto digital."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        conn.execute("DELETE FROM tenant_products WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return {"message": "Produto removido"}
    finally:
        conn.close()


# ─── Upload de Arquivos ──────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    admin: str = Depends(require_admin)
):
    """Upload de arquivo para downloads. Retorna URL para usar no produto."""
    from fastapi import UploadFile, File
    from pathlib import Path
    import secrets

    # Note: This endpoint requires multipart form data
    # We handle it via a separate approach below


# Endpoint alternativo via JSON (base64)
class UploadRequest(BaseModel):
    filename: str
    content_base64: str
    content_type: str = "application/octet-stream"


@router.post("/upload-file")
async def upload_file_json(
    req: UploadRequest,
    admin: str = Depends(require_admin)
):
    """Upload de arquivo via JSON (base64). Retorna URL de download."""
    import base64, secrets
    from pathlib import Path
    from urllib.parse import quote

    uploads_dir = Path("/root/DEEP-OS/downloads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Decode base64
    try:
        file_bytes = base64.b64decode(req.content_base64)
    except Exception:
        raise HTTPException(400, "Base64 invalido")

    # Sanitiza nome do arquivo
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in req.filename)
    unique_name = f"{secrets.token_hex(4)}_{safe_name}"
    filepath = uploads_dir / unique_name

    filepath.write_bytes(file_bytes)

    download_url = f"/api/download?path={quote(str(filepath))}"
    return {
        "message": "Arquivo uploadado",
        "filename": unique_name,
        "original_name": req.filename,
        "size": len(file_bytes),
        "download_url": download_url,
    }


# ─── Liberar Produtos para Tenants ───────────────────────────────

class GrantProductRequest(BaseModel):
    tenant_id: str
    product_id: str


@router.post("/grant-product")
async def grant_product(
    req: GrantProductRequest,
    admin: str = Depends(require_admin)
):
    """Libera um produto para um tenant."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM tenant_products WHERE tenant_id=? AND product_id=?",
            (req.tenant_id, req.product_id)
        ).fetchone()
        if existing:
            return {"message": "Produto ja liberado"}
        conn.execute(
            "INSERT INTO tenant_products (tenant_id, product_id, granted_by) VALUES (?, ?, ?)",
            (req.tenant_id, req.product_id, "admin")
        )
        conn.commit()
        return {"message": "Produto liberado com sucesso"}
    finally:
        conn.close()


@router.post("/revoke-product")
async def revoke_product(
    req: GrantProductRequest,
    admin: str = Depends(require_admin)
):
    """Remove acesso de um tenant a um produto."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM tenant_products WHERE tenant_id=? AND product_id=?",
            (req.tenant_id, req.product_id)
        )
        conn.commit()
        return {"message": "Acesso removido"}
    finally:
        conn.close()


@router.get("/tenants/{tenant_id}/products")
async def get_tenant_products(
    tenant_id: str,
    admin: str = Depends(require_admin)
):
    """Lista produtos liberados para um tenant."""
    from database.connection import get_conn
    import json
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


@router.get("/tenants/{tenant_id}/all-products")
async def get_tenant_all_products(
    tenant_id: str,
    admin: str = Depends(require_admin)
):
    """Lista todos os produtos com indicacao de acesso do tenant."""
    from database.connection import get_conn
    import json
    conn = get_conn()
    try:
        all_products = conn.execute("SELECT * FROM products ORDER BY sort_order ASC").fetchall()
        granted = conn.execute(
            "SELECT product_id FROM tenant_products WHERE tenant_id=?", (tenant_id,)
        ).fetchall()
        granted_ids = {r["product_id"] for r in granted}
        result = []
        for r in all_products:
            p = dict(r)
            p["features"] = json.loads(p.get("features", "[]"))
            p["granted"] = r["id"] in granted_ids
            result.append(p)
        return {"products": result}
    finally:
        conn.close()


# ─── Historico de Pagamentos (Admin) ─────────────────────────────

@router.get("/payments/all")
async def list_all_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: str = Depends(require_admin)
):
    """Lista historico completo de pagamentos."""
    from database.connection import get_conn
    conn = get_conn()
    try:
        where = ["1=1"]
        params = []
        if tenant_id:
            where.append("tenant_id = ?")
            params.append(tenant_id)
        if status:
            where.append("status = ?")
            params.append(status)
        
        where_sql = " AND ".join(where)
        
        total = conn.execute(
            f"SELECT COUNT(*) as count FROM payments WHERE {where_sql}",
            params
        ).fetchone()["count"]
        
        offset = (page - 1) * limit
        rows = conn.execute(
            f"""
                SELECT p.*, t.name as tenant_name, t.email as tenant_email
                FROM payments p
                LEFT JOIN tenants t ON p.tenant_id = t.id
                WHERE {where_sql}
                ORDER BY p.created_at DESC
                LIMIT ? OFFSET ?
            """,
            [*params, limit, offset]
        ).fetchall()
        
        payments = []
        for r in rows:
            p = dict(r)
            payments.append(p)
        
        return {
            "payments": payments,
            "total": total,
            "page": page,
            "limit": limit,
        }
    finally:
        conn.close()
