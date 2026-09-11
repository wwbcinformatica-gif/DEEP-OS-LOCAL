"""
Middleware de Isolamento Multi-Tenant
Isola dados de cada assinante em SQLite separado
"""
import os
from pathlib import Path
from typing import Optional
from contextvars import ContextVar

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Contexto do tenant atual
current_tenant_id: ContextVar[Optional[str]] = ContextVar("current_tenant_id", default=None)

# Diretório base dos tenants
TENANTS_DIR = Path(os.environ.get("TENANTS_DIR", "data/tenants"))
SHARED_DIR = Path(os.environ.get("SHARED_DIR", "data/shared"))


class TenantContext:
    """Contexto do tenant atual na requisição."""
    
    @staticmethod
    def get_tenant_id() -> Optional[str]:
        """Retorna o ID do tenant atual."""
        return current_tenant_id.get()
    
    @staticmethod
    def set_tenant_id(tenant_id: str):
        """Define o ID do tenant atual."""
        current_tenant_id.set(tenant_id)
    
    @staticmethod
    def get_tenant_dir(tenant_id: str) -> Path:
        """Retorna o diretório do tenant."""
        tenant_dir = TENANTS_DIR / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir
    
    @staticmethod
    def get_tenant_db_path(tenant_id: str) -> Path:
        """Retorna o caminho do banco de dados do tenant."""
        return TenantContext.get_tenant_dir(tenant_id) / "database.sqlite"
    
    @staticmethod
    def get_tenant_config_path(tenant_id: str) -> Path:
        """Retorna o caminho do config.yaml do tenant."""
        return TenantContext.get_tenant_dir(tenant_id) / "config.yaml"
    
    @staticmethod
    def get_tenant_workspace(tenant_id: str) -> Path:
        """Retorna o diretório de trabalho do tenant."""
        workspace = TenantContext.get_tenant_dir(tenant_id) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
    
    @staticmethod
    def ensure_tenant_dirs():
        """Garante que os diretórios base existem."""
        TENANTS_DIR.mkdir(parents=True, exist_ok=True)
        SHARED_DIR.mkdir(parents=True, exist_ok=True)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware que extrai o tenant_id da requisição e configura o contexto.
    
    Suporta:
    - Header X-Tenant-ID
    - Subdomínio (tenant.DEEP-OS.com)
    - Query parameter ?tenant_id=xxx
    """
    
    async def dispatch(self, request: Request, call_next):
        tenant_id = None
        
        # 1. Tenta extrair do header
        tenant_id = request.headers.get("X-Tenant-ID")
        
        # 2. Tenta extrair do subdomínio
        if not tenant_id:
            host = request.headers.get("host", "")
            if host and "." in host:
                parts = host.split(".")
                if len(parts) > 2:
                    tenant_id = parts[0]
        
        # 3. Tenta extrair do query parameter
        if not tenant_id:
            tenant_id = request.query_params.get("tenant_id")
        
        # Define no contexto
        if tenant_id:
            TenantContext.set_tenant_id(tenant_id)
        
        response = await call_next(request)
        return response


def get_tenant_db(tenant_id: str):
    """
    Retorna uma conexão SQLite isolada para o tenant.
    Cada tenant tem seu próprio banco de dados.
    """
    from database.connection import set_db_path, get_conn, init_db
    
    db_path = TenantContext.get_tenant_db_path(tenant_id)
    
    # Cria o banco se não existir
    if not db_path.exists():
        set_db_path(db_path)
        init_db()
        _init_tenant_tables(tenant_id)
    
    set_db_path(db_path)
    return get_conn()


def _init_tenant_tables(tenant_id: str):
    """Inicializa tabelas específicas do tenant."""
    from database.connection import get_conn
    
    conn = get_conn()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    approved BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
    finally:
        conn.close()


def list_tenants():
    """Lista todos os tenants registrados."""
    tenants = []
    TENANTS_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in TENANTS_DIR.iterdir():
        if item.is_dir() and (item / "database.sqlite").exists():
            tenants.append(item.name)
    
    return tenants


def tenant_exists(tenant_id: str) -> bool:
    """Verifica se um tenant existe."""
    tenant_dir = TENANTS_DIR / tenant_id
    return tenant_dir.exists() and (tenant_dir / "database.sqlite").exists()


def create_tenant_dirs(tenant_id: str):
    """Cria a estrutura de diretórios para um novo tenant."""
    tenant_dir = TENANTS_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    (tenant_dir / "workspace").mkdir(exist_ok=True)
    (tenant_dir / "logs").mkdir(exist_ok=True)
    (tenant_dir / "uploads").mkdir(exist_ok=True)
