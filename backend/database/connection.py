import logging
import queue
import sqlite3
import threading
from pathlib import Path
from types import TracebackType

_log = logging.getLogger("wbc.db")

_db_path: Path | None = None
_pool: queue.Queue | None = None
_pool_lock = threading.Lock()
POOL_SIZE = 5


class PooledConnection:
    """Wraps sqlite3.Connection e devolve ao pool no close()."""

    def __init__(self, conn: sqlite3.Connection, pool: queue.Queue):
        self._conn = conn
        self._pool = pool
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if not self._closed:
            self._closed = True
            self._conn.rollback()
            self._pool.put(self._conn)

    def __enter__(self) -> "PooledConnection":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self.close()


def set_db_path(path: Path):
    global _db_path, _pool
    _db_path = path
    _init_pool()


def _init_pool():
    global _pool
    if _db_path is None:
        return
    with _pool_lock:
        if _pool is not None:
            return
        _pool = queue.Queue(maxsize=POOL_SIZE)
        for _ in range(POOL_SIZE):
            conn = sqlite3.connect(str(_db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            _pool.put(conn)
    _log.info("Pool SQLite inicializado com %d conexões", POOL_SIZE)


def get_conn() -> PooledConnection:
    if _pool is None:
        raise RuntimeError("Pool não inicializado. Chame set_db_path() primeiro.")
    conn = _pool.get()
    return PooledConnection(conn, _pool)


def init_db():
    conn = get_conn()
    with conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            approved BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS task_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            messages TEXT NOT NULL,
            tool_logs TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            step INTEGER DEFAULT 0,
            max_steps INTEGER DEFAULT 100,
            context TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS brain_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        # Tabelas SaaS
        cur.execute("""CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT DEFAULT 'free',
            status TEXT DEFAULT 'active',
            license_key TEXT,
            company TEXT,
            phone TEXT,
            pix_key TEXT,
            api_key TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            last_login DATETIME,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            metadata TEXT DEFAULT '{}'
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS payments (
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
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS usage_metrics (
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
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tenants_email ON tenants(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_tenant ON payments(tenant_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usage_tenant_date ON usage_metrics(tenant_id, date)")
        cur.execute("""CREATE TABLE IF NOT EXISTS instances (
            id TEXT PRIMARY KEY,
            tenant_id TEXT DEFAULT 'default',
            name TEXT NOT NULL,
            model TEXT DEFAULT 'gemini-2.5-flash',
            provider TEXT DEFAULT 'gemini',
            status TEXT DEFAULT 'active',
            messages_used INTEGER DEFAULT 0,
            message_limit INTEGER DEFAULT 20,
            system_prompt TEXT DEFAULT '',
            temperature REAL DEFAULT 0.7,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_instances_tenant ON instances(tenant_id)")
        # Tabela de produtos digitais (downloads)
        cur.execute("""CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            icon TEXT DEFAULT '📦',
            image_url TEXT DEFAULT '',
            category TEXT DEFAULT 'Geral',
            price REAL DEFAULT 0,
            original_price REAL,
            badge TEXT DEFAULT '',
            badge_color TEXT DEFAULT '',
            features TEXT DEFAULT '[]',
            download_url TEXT DEFAULT '',
            status TEXT DEFAULT 'available',
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        # Quem tem acesso a cada produto
        cur.execute("""CREATE TABLE IF NOT EXISTS tenant_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            granted_by TEXT DEFAULT 'admin',
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (product_id) REFERENCES products(id),
            UNIQUE(tenant_id, product_id)
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tp_tenant ON tenant_products(tenant_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tp_product ON tenant_products(product_id)")

        # ─── Migracao: identidade por tenant ───────────────────────────────
        # SQLite nao suporta ADD COLUMN IF NOT EXISTS, entao checamos o schema.
        _existing_cols = {
            row[1] for row in cur.execute("PRAGMA table_info(tenants)").fetchall()
        }
        for _col, _ddl in (
            ("assistant_name", "ALTER TABLE tenants ADD COLUMN assistant_name TEXT"),
            ("user_name", "ALTER TABLE tenants ADD COLUMN user_name TEXT"),
            ("voice", "ALTER TABLE tenants ADD COLUMN voice TEXT"),
        ):
            if _col not in _existing_cols:
                cur.execute(_ddl)
                _log.info("Migracao: coluna tenants.%s criada", _col)

        # ─── Lembretes ─────────────────────────────────────────────────────
        # Substitui o agendamento via schtasks/systemd-run/at, que nao funciona
        # em VPS headless. Fica no SQLite para sobreviver a restart e reboot.
        # `fire_at` e gravado em UTC; `tz` guarda o fuso do usuario (IANA) para
        # exibir de volta na hora local dele.
        cur.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT,
            message TEXT NOT NULL,
            fire_at DATETIME NOT NULL,
            status TEXT DEFAULT 'pending',
            channel TEXT DEFAULT 'voice',
            tz TEXT,
            fired_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        # Migracao para bancos criados antes da coluna tz existir
        _rem_cols = {row[1] for row in cur.execute("PRAGMA table_info(reminders)").fetchall()}
        if "tz" not in _rem_cols:
            cur.execute("ALTER TABLE reminders ADD COLUMN tz TEXT")
            _log.info("Migracao: coluna reminders.tz criada")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(status, fire_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reminders_tenant ON reminders(tenant_id, status)")
    _log.info("Banco de dados inicializado em %s", _db_path)
