"""
Teste de INTEGRACAO: POST/GET /api/config/identity grava mesmo no banco?

Exercita o endpoint real (via TestClient) com um token master, e confere o
banco depois. Isola se o problema esta na rota, no core ou no banco.
"""
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
TMP = Path(tempfile.mkdtemp(prefix="dbg4_"))
DB = TMP / "interactions.db"

import database.connection as db

# IMPORTANTE: importar `main` PRIMEIRO. O main.py chama set_db_path(DB_PATH)
# no nivel do modulo — se apontarmos o banco antes, o import sobrescreve o
# caminho e o teste passa a ler o banco REAL (foi o que me enganou antes:
# o PUT gravava no temporario e o GET lia o real).
import main  # noqa: E402

db.set_db_path(DB)
db.init_db()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import AuthManager  # noqa: E402
from core.tenant_identity import master_identity_key  # noqa: E402

K = master_identity_key("wwbc22@gmail.com")
tok = AuthManager.create_access_token({"sub": K, "is_master": True, "is_admin": True})
H = {"Authorization": f"Bearer {tok}"}

c = TestClient(main.app)

print("=== 1. PUT /api/config/identity ===")
r = c.put("/api/config/identity", json={
    "assistant_name": "Atena", "user_name": "Wilson",
    "custom_color": "", "voice": "Kore",
}, headers=H)
print("  status:", r.status_code)
print("  body  :", r.text[:180])

print()
print("=== 2. BANCO (leitura direta, fora da app) ===")
conn = db.get_conn()
rows = conn.execute("SELECT id, assistant_name, user_name, voice, updated_at FROM tenants").fetchall()
for x in rows:
    print("  ", dict(x))
conn.close()

print()
print("=== 3. GET /api/config/identity ===")
g = c.get("/api/config/identity", headers=H)
print("  body:", g.text[:180])

print()
print("=== 3b. O que get_identity() enxerga? ===")
from core.tenant_identity import get_identity, is_master_key
print("  chave usada :", K)
print("  is_master_key(K):", is_master_key(K))
conn = db.get_conn()
row = conn.execute("SELECT id, assistant_name, voice FROM tenants WHERE id = ?", (K,)).fetchone()
print("  linha por id    :", dict(row) if row else None)
conn.close()
print("  get_identity(K) :", get_identity(K))

print()
print("=== 3c. O que a ROTA usa como tenant_id? ===")
from core.auth import get_current_tenant_optional
from fastapi.security import HTTPAuthorizationCredentials
cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok)
print("  get_current_tenant_optional ->", repr(get_current_tenant_optional(credentials=cred)))

print()
print("=== 4. VEREDITO ===")
import json
esperado = {"assistant_name": "Atena", "voice": "Kore"}
obtido = g.json()
ok = all(obtido.get(k) == v for k, v in esperado.items())
print("  esperado:", esperado)
print("  obtido  :", {k: obtido.get(k) for k in ("assistant_name", "voice")})
print("  " + ("OK — gravou e leu corretamente" if ok else "FALHOU — a gravacao NAO persistiu"))

db.set_db_path(BACKEND.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
