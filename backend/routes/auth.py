"""
Rotas de Autenticação para DEEP-OS SaaS
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr

from core.auth import AuthManager, get_current_tenant_id, AdminAuth
from models.tenant import (
    TenantCreate, TenantLogin, TenantResponse, TokenResponse,
    hash_password, verify_password
)
from models.plan import PlanType
from middleware.tenant import (
    get_tenant_db, create_tenant_dirs, TenantContext
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    company: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """Registra um novo tenant (assinante)."""
    conn = None
    try:
        # Conecta ao banco administrativo
        from database.connection import get_conn as get_admin_conn
        conn = get_admin_conn()
        
        # Verifica se o email já existe
        existing = conn.execute(
            "SELECT id FROM tenants WHERE email = ?",
            (req.email,)
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email já cadastrado"
            )
        
        # Gera ID único
        import secrets
        tenant_id = secrets.token_hex(16)
        
        # Hash da senha
        password_hash = AuthManager.hash_password(req.password)
        
        # Insere o tenant
        conn.execute("""
            INSERT INTO tenants (id, name, email, password_hash, plan, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            req.name,
            req.email,
            password_hash,
            PlanType.FREE.value,
            "active",
            datetime.utcnow().isoformat()
        ))
        
        # Cria diretórios do tenant
        create_tenant_dirs(tenant_id)
        
        # Commit - salva no banco
        conn.commit()
        
        # Gera token
        token = AuthManager.create_access_token({"sub": tenant_id})
        
        return TokenResponse(
            access_token=token,
            tenant=TenantResponse(
                id=tenant_id,
                name=req.name,
                email=req.email,
                plan=PlanType.FREE.value,
                status="active",
                license_key="",
                company=req.company,
                created_at=datetime.utcnow()
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Autentica um tenant existente."""
    from core.security_config import avisar_se_inseguro, check_master_credentials

    avisar_se_inseguro()

    # Master admin login (credenciais via core/security_config.py, nao hardcoded)
    if check_master_credentials(req.email, req.password):
        # `sub` UNICO por conta master. Antes as duas recebiam "master-admin",
        # entao compartilhavam a mesma identidade: a voz que uma escolhia
        # aparecia na outra (e nos assinantes que nao personalizaram).
        from core.tenant_identity import master_identity_key

        token = AuthManager.create_access_token({
            "sub": master_identity_key(req.email),
            "is_master": True,
            "is_admin": True
        })
        return TokenResponse(
            access_token=token,
            tenant=TenantResponse(
                # Mantido "master-admin" para nao quebrar o frontend, que usa
                # este id em telas e comparacoes.
                id="master-admin",
                name="Master Admin",
                email=req.email,
                plan="master",
                status="active",
                license_key="",
                company="DEEP-OS",
                created_at=datetime.utcnow()
            )
        )

    conn = None
    try:
        from database.connection import get_conn as get_admin_conn
        conn = get_admin_conn()
        
        # Busca o tenant por email
        result = conn.execute(
            "SELECT * FROM tenants WHERE email = ?",
            (req.email,)
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha inválidos"
            )
        
        # Verifica a senha
        if not AuthManager.verify_password(req.password, result["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha inválidos"
            )
        
        # Verifica se está ativo
        if result["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta suspensa ou expirada"
            )
        
        # Atualiza último login
        conn.execute(
            "UPDATE tenants SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), result["id"])
        )
        conn.commit()
        
        # Gera token
        token_data = {"sub": result["id"]}
        if result["plan"] == "master":
            token_data["is_admin"] = True
        token = AuthManager.create_access_token(token_data)
        
        r = dict(result)
        return TokenResponse(
            access_token=token,
            tenant=TenantResponse(
                id=r["id"],
                name=r["name"],
                email=r["email"],
                plan=r["plan"],
                status=r["status"],
                license_key=r.get("license_key", ""),
                company=r.get("company"),
                created_at=datetime.fromisoformat(r["created_at"]),
                expires_at=datetime.fromisoformat(r["expires_at"]) if r.get("expires_at") else None
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao fazer login: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/admin/login")
async def admin_login(req: AdminLoginRequest):
    """Login do painel administrativo com email e senha."""
    from core.security_config import avisar_se_inseguro, check_master_credentials

    avisar_se_inseguro()

    if not check_master_credentials(req.email, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos"
        )
    
    token = AdminAuth.create_admin_token()
    return {"access_token": token, "token_type": "bearer", "admin_email": req.email}


@router.get("/me", response_model=TenantResponse)
async def get_me(tenant_id: str = Depends(get_current_tenant_id)):
    """Retorna os dados do tenant autenticado."""
    # Master admin - dados hardcoded (a senha e fixa, nao vem do banco).
    # O `sub` agora e "master-admin:<email>" (unico por conta); aceitamos
    # tambem o valor antigo "master-admin" por compatibilidade com tokens
    # emitidos antes desta mudanca.
    from core.tenant_identity import is_master_key, master_email_from_key

    if is_master_key(tenant_id):
        return TenantResponse(
            id="master-admin",
            name="Master Admin",
            email=master_email_from_key(tenant_id) or "wwbcinformatica@gmail.com",
            plan="master",
            status="active",
            license_key="",
            company="DEEP-OS",
            created_at=datetime.utcnow()
        )
    
    conn = None
    try:
        from database.connection import get_conn as get_admin_conn
        conn = get_admin_conn()
        
        result = conn.execute(
            "SELECT * FROM tenants WHERE id = ?",
            (tenant_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant não encontrado"
            )
        
        r = dict(result)
        return TenantResponse(
            id=r["id"],
            name=r["name"],
            email=r["email"],
            plan=r["plan"],
            status=r["status"],
            license_key=r.get("license_key", ""),
            company=r.get("company"),
            created_at=datetime.fromisoformat(r["created_at"]),
            expires_at=datetime.fromisoformat(r["expires_at"]) if r.get("expires_at") else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar dados: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Altera a senha do tenant."""
    conn = None
    try:
        from database.connection import get_conn as get_admin_conn
        conn = get_admin_conn()
        
        result = conn.execute(
            "SELECT password_hash FROM tenants WHERE id = ?",
            (tenant_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant não encontrado"
            )
        
        if not AuthManager.verify_password(req.current_password, result["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Senha atual incorreta"
            )
        
        new_hash = AuthManager.hash_password(req.new_password)
        conn.execute(
            "UPDATE tenants SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, datetime.utcnow().isoformat(), tenant_id)
        )
        conn.commit()
        
        return {"message": "Senha alterada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao alterar senha: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/pix-key")
async def update_pix_key(
    pix_key: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Atualiza a chave PIX do tenant."""
    conn = None
    try:
        from database.connection import get_conn as get_admin_conn
        conn = get_admin_conn()
        
        conn.execute(
            "UPDATE tenants SET pix_key = ?, updated_at = ? WHERE id = ?",
            (pix_key, datetime.utcnow().isoformat(), tenant_id)
        )
        conn.commit()
        
        return {"message": "Chave PIX atualizada com sucesso", "pix_key": pix_key}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar chave PIX: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/api-key")
async def update_api_key(
    api_key: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Atualiza a chave de API do tenant."""
    conn = None
    try:
        from database.connection import get_conn as get_admin_conn
        conn = get_admin_conn()
        
        conn.execute(
            "UPDATE tenants SET api_key = ?, updated_at = ? WHERE id = ?",
            (api_key, datetime.utcnow().isoformat(), tenant_id)
        )
        conn.commit()
        
        return {"message": "Chave de API atualizada com sucesso", "api_key": api_key}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar chave de API: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
