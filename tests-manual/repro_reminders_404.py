"""
Reproduz o bug: /api/reminders da 401 SEM auth, mas 404 COM auth.

Se o 401 aparece, a rota existe. Se com token valido vira 404, algo entre a
dependency e a funcao da rota esta quebrando. Este teste isola a camada.
"""
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

TMP = Path(tempfile.mkdtemp(prefix="deepos_repro_"))

import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from fastapi.testclient import TestClient
import main
from core.auth import AuthManager

# Cria um tenant de teste e um token valido
conn = db.get_conn()
conn.execute(
    "INSERT INTO tenants (id, name, email, password_hash, plan) VALUES (?,?,?,?,'monthly')",
    ("t_teste", "Teste", "teste@local", "x"),
)
conn.commit()
conn.close()

token = AuthManager.create_access_token({"sub": "t_teste"})
print(f"tenant de teste: t_teste | token gerado: {token[:20]}...\n")

# Token de MASTER ADMIN: sub="master-admin", SEM linha na tabela tenants.
# Este e o caso real que produzia 404 em vez de 200.
token_master = AuthManager.create_access_token(
    {"sub": "master-admin", "is_master": True, "is_admin": True}
)
print(f"master admin -> sub=master-admin (NAO existe em tenants)\n")

c = TestClient(main.app)

print("=" * 66)
print("ROTAS REGISTRADAS que contem 'reminder':")
for r in main.app.routes:
    p = getattr(r, "path", "")
    if "reminder" in p:
        print(f"   {sorted(getattr(r,'methods',[]) or [])} {p}")

print("=" * 66)
casos = [
    ("/api/reminders", None, "sem auth"),
    ("/api/reminders", {"Authorization": f"Bearer {token}"}, "tenant real"),
    ("/api/reminders", {"Authorization": f"Bearer {token_master}"}, "MASTER ADMIN"),
    ("/api/reminders/summary", {"Authorization": f"Bearer {token_master}"}, "MASTER ADMIN"),
    ("/api/config/identity", {"Authorization": f"Bearer {token_master}"}, "MASTER ADMIN"),
    ("/plans/public", None, "sem auth"),
]
for path, headers, rotulo in casos:
    r = c.get(path, headers=headers or {})
    print(f"  [{rotulo:12}] GET {path:26} -> {r.status_code}  {r.text[:62]}")

print("=" * 66)
print("Teste do dependency require_plan(1) isolado:")
try:
    from core.auth import require_plan, security as _sec
    from fastapi.security import HTTPAuthorizationCredentials

    dep = require_plan(1)
    print(f"   require_plan(1) -> {dep!r} (callable: {callable(dep)})")

    # Assinatura nova: recebe o credential (nao mais tenant_id direto),
    # porque precisa ler is_admin/is_master do payload.
    for rotulo, tk in (("tenant real", token), ("master admin", token_master)):
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tk)
        print(f"   {rotulo:14} -> {dep(credentials=cred)!r}")
except Exception as e:
    print(f"   ERRO: {type(e).__name__}: {e}")

print("=" * 66)
print("Planos conhecidos (PLAN_HIERARCHY):")
try:
    from models.plan import PLAN_HIERARCHY
    print(f"   {PLAN_HIERARCHY}")
    print(f"   'monthly' presente? {'monthly' in PLAN_HIERARCHY}")
except Exception as e:
    print(f"   ERRO: {e}")

import shutil
db.set_db_path(BACKEND.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
