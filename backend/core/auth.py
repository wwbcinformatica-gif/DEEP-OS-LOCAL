"""
Sistema de Autenticação JWT para DEEP-OS SaaS
"""
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import bcrypt

# ─── Chave de assinatura dos tokens ─────────────────────────────────────────
#
# ANTES: havia um default PUBLICO no codigo
#   SECRET_KEY = os.environ.get("JWT_SECRET", "DEEP-OS-saas-secret-key-change-in-production")
# Qualquer pessoa com acesso ao repositorio podia FORJAR tokens validos e se
# passar por qualquer tenant. Como o repositorio e privado mas ja foi exposto
# varias vezes, isso era risco real.
#
# AGORA, nesta ordem:
#   1. variavel de ambiente JWT_SECRET (recomendado em producao)
#   2. arquivo local gerado automaticamente na primeira execucao
#      (backend/config/jwt_secret.key, no .gitignore, chmod 600)
#
# A chave e PERSISTIDA de proposito: se fosse aleatoria a cada boot, todos os
# usuarios seriam deslogados a cada restart.

_SECRET_FILE = Path(__file__).resolve().parent.parent / "config" / "jwt_secret.key"


def _load_or_create_secret() -> str:
    env = os.environ.get("JWT_SECRET", "").strip()
    if env:
        return env

    try:
        if _SECRET_FILE.exists():
            salvo = _SECRET_FILE.read_text(encoding="utf-8").strip()
            if len(salvo) >= 32:
                return salvo

        nova = secrets.token_urlsafe(48)
        _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SECRET_FILE.write_text(nova, encoding="utf-8")
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except Exception:
            pass  # Windows pode nao suportar; o arquivo esta no .gitignore
        print(f"[auth] JWT_SECRET gerado e salvo em {_SECRET_FILE}")
        return nova
    except Exception as e:
        # Ultimo recurso: chave efemera. Desloga todos no restart, mas nao
        # deixa o sistema com uma chave publica.
        print(f"[auth] AVISO: nao consegui persistir o JWT_SECRET ({e}). Usando chave efemera.")
        return secrets.token_urlsafe(48)


SECRET_KEY = _load_or_create_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

# Security scheme
security = HTTPBearer(auto_error=False)


class AuthManager:
    """Gerencia autenticação e autorização."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Gera hash da senha usando bcrypt."""
        pwd_bytes = password.encode("utf-8")[:72]
        return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifica se a senha corresponde ao hash."""
        pwd_bytes = password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Cria um token JWT."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decodifica e valida um token JWT."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )


def get_current_tenant_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Extrai o tenant_id do token JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado"
        )
    
    payload = AuthManager.decode_token(credentials.credentials)
    tenant_id = payload.get("sub")
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
    
    return tenant_id


def get_current_tenant_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """Versão opcional - retorna None se não autenticado."""
    if not credentials:
        return None
    
    try:
        payload = AuthManager.decode_token(credentials.credentials)
        return payload.get("sub")
    except Exception:
        return None


def require_plan(minimum_plan_level: int):
    """
    Dependency que verifica se o tenant tem o plano mínimo necessário.

    Uso:
        @router.get("/feature")
        async def feature(tenant_id: str = Depends(require_plan(1))):
            # 1 = monthly, 2 = quarterly, 3 = annual
            pass

    Contas de ADMINISTRADOR passam sem checagem de plano.

    Por que: o master admin e hardcoded (nao tem linha na tabela `tenants`),
    e o `sub` do JWT dele e "master-admin". Antes, a consulta ao banco nao
    achava esse tenant e a dependency devolvia **404 "Tenant nao encontrado"**
    — o que fazia uma rota existente parecer inexistente (o sintoma confuso
    de 401 sem token e 404 com token).
    """
    from models.plan import PLAN_HIERARCHY

    def check_plan(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> str:
        from database.connection import get_conn

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Não autenticado"
            )

        payload = AuthManager.decode_token(credentials.credentials)
        tenant_id = payload.get("sub")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )

        # Admin/master nao tem assinatura: libera direto.
        if payload.get("is_admin") or payload.get("is_master"):
            return tenant_id

        conn = get_conn()
        try:
            result = conn.execute(
                "SELECT plan FROM tenants WHERE id = ?",
                (tenant_id,)
            ).fetchone()

            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant não encontrado"
                )

            tenant_plan = result["plan"]
            # PLAN_HIERARCHY e indexado por PlanType (enum); aceita tanto o
            # enum quanto a string para nao depender da forma de armazenamento.
            plan_level = PLAN_HIERARCHY.get(tenant_plan, 0)
            if plan_level == 0 and isinstance(tenant_plan, str):
                for k, v in PLAN_HIERARCHY.items():
                    if getattr(k, "value", k) == tenant_plan:
                        plan_level = v
                        break

            if plan_level < minimum_plan_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Plano insuficiente para esta funcionalidade"
                )

            return tenant_id
        finally:
            conn.close()

    return check_plan


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Verifica se o usuário é administrador."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado"
        )
    
    payload = AuthManager.decode_token(credentials.credentials)
    
    if not payload.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores"
        )
    
    return payload.get("sub", "admin")


class AdminAuth:
    """Autenticação específica para o painel administrativo."""
    
    @staticmethod
    def create_admin_token(admin_id: str = "admin") -> str:
        """Cria token de administrador."""
        return AuthManager.create_access_token({
            "sub": admin_id,
            "is_admin": True
        })
    
    @staticmethod
    def verify_admin_password(password: str) -> bool:
        """Verifica senha do admin (configurada via variável de ambiente)."""
        admin_password = os.environ.get("ADMIN_PASSWORD", "DEEP-OS-admin")
        return password == admin_password
