"""
Inicialização do Banco de Dados Administrativo
Cria as tabelas necessárias para o SaaS
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "admin.db"




def migrate_admin_db():
    """Cria tabelas e colunas faltantes no banco administrativo existente."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'BRL',
                    method TEXT NOT NULL,
                    source TEXT DEFAULT 'pix',
                    status TEXT DEFAULT 'pending',
                    plan_id TEXT,
                    subscription_months INTEGER DEFAULT 1,
                    transaction_id TEXT,
                    gateway_response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME,
                    expires_at DATETIME,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_tenant ON payments(tenant_id)")
            conn.commit()
            print(f"Tabela payments criada em: {DB_PATH}")
            return True
        
        # Adiciona coluna source se nao existir
        cursor.execute("PRAGMA table_info(payments)")
        columns = [col["name"] for col in cursor.fetchall()]
        if "source" not in columns:
            conn.execute("ALTER TABLE payments ADD COLUMN source TEXT DEFAULT 'pix'")
            conn.commit()
            print("Coluna source adicionada a tabela payments")
            conn.execute("""
                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'BRL',
                    method TEXT NOT NULL,
                    source TEXT DEFAULT 'pix',
                    status TEXT DEFAULT 'pending',
                    plan_id TEXT,
                    subscription_months INTEGER DEFAULT 1,
                    transaction_id TEXT,
                    gateway_response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME,
                    expires_at DATETIME,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_tenant ON payments(tenant_id)")
            conn.commit()
            print(f"Tabela payments criada em: {DB_PATH}")
        return True
    except Exception as e:
        print(f"Erro na migracao: {e}")
        return False
    finally:
        conn.close()

def init_admin_db():
    """Inicializa o banco de dados administrativo."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        with conn:
            # Tabela de tenants (assinantes)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    plan TEXT DEFAULT 'free',
                    status TEXT DEFAULT 'active',
                    license_key TEXT,
                    company TEXT,
                    phone TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    last_login DATETIME,
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # Tabela de pagamentos
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'BRL',
                    method TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    plan_id TEXT,
                    subscription_months INTEGER DEFAULT 1,
                    transaction_id TEXT,
                    gateway_response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME,
                    expires_at DATETIME,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                )
            """)
            
            # Tabela de uso/métricas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    messages_used INTEGER DEFAULT 0,
                    instances_active INTEGER DEFAULT 0,
                    tokens_used INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    storage_used_mb REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    UNIQUE(tenant_id, date)
                )
            """)
            
            # Índices para performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tenants_email ON tenants(email)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tenants_plan ON tenants(plan)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_tenant ON payments(tenant_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_tenant_date ON usage_metrics(tenant_id, date)")
            
        print(f"Banco administrativo inicializado em: {DB_PATH}")
        return True
        
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    init_admin_db()
