"""Teste de isolamento de identidade por tenant.

Cria 3 tenants de teste num banco temporario, define nomes diferentes e
verifica que cada um le de volta o SEU nome, sem vazar entre si.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Este arquivo fica em tests-manual/; o app vive em backend/
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

TMP = Path(tempfile.mkdtemp(prefix="deepos_identity_"))
print(f"Banco temporario: {TMP / 'interactions.db'}")

# Aponta o pool para o banco temporario ANTES de importar o app
import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from core.tenant_identity import get_identity, set_identity

conn = db.get_conn()
for tid, nome in (("t1", "inicial"), ("t2", "inicial"), ("t3", "inicial")):
    conn.execute(
        "INSERT INTO tenants (id, name, email, password_hash, plan) VALUES (?,?,?,?,'free')",
        (tid, f"Tenant {tid}", f"{tid}@test.local", "x"),
    )
conn.commit()
conn.close()

falhas = []

# 1. Antes de personalizar: todos usam o padrao global
base = get_identity("t1")["assistant_name"]
print(f"\n1) Padrao inicial (todos iguais): {base!r}")
for tid in ("t1", "t2", "t3"):
    v = get_identity(tid)["assistant_name"]
    if v != base:
        falhas.append(f"esperava padrao {base!r} para {tid}, veio {v!r}")

# 2. Cada um personaliza com um nome DIFERENTE
print("2) Cada tenant salva um nome diferente...")
set_identity("t1", "Atena", "Wilson")
set_identity("t2", "Hermes", "Maria")
set_identity("t3", "Apolo", "Joao")

esperado = {"t1": ("Atena", "Wilson"), "t2": ("Hermes", "Maria"), "t3": ("Apolo", "Joao")}

# 3. Cada um le o SEU nome (o bug era todos lerem o do ultimo)
print("3) Verificando isolamento...")
for tid, (esp_a, esp_u) in esperado.items():
    ident = get_identity(tid)
    ok_a = ident["assistant_name"] == esp_a
    ok_u = ident["user_name"] == esp_u
    marca = "OK " if (ok_a and ok_u) else "FALHOU"
    print(f"   {marca} {tid}: assistant={ident['assistant_name']!r} user={ident['user_name']!r}")
    if not ok_a:
        falhas.append(f"{tid} assistant: esperava {esp_a!r}, veio {ident['assistant_name']!r}")
    if not ok_u:
        falhas.append(f"{tid} user: esperava {esp_u!r}, veio {ident['user_name']!r}")

# 4. Testar o cenario do bug: salvar de novo no t1 nao pode mudar t2/t3
print("4) t1 salva de novo — t2 e t3 NAO podem mudar...")
set_identity("t1", "Zeus", "Wilson")
for tid, esp in (("t2", "Hermes"), ("t3", "Apolo")):
    v = get_identity(tid)["assistant_name"]
    if v != esp:
        falhas.append(f"VAZAMENTO: {tid} mudou para {v!r} (esperava {esp!r})")
    else:
        print(f"   OK  {tid} intacto: {v!r}")
if get_identity("t1")["assistant_name"] != "Zeus":
    falhas.append("t1 nao salvou 'Zeus'")

# 5. Tenant inexistente / None nao explode
print("5) Casos de borda (tenant inexistente / None)...")
try:
    a = get_identity("nao-existe")["assistant_name"]
    b = get_identity(None)["assistant_name"]
    print(f"   OK  inexistente={a!r}  None={b!r}")
except Exception as e:
    falhas.append(f"caso de borda explodiu: {e}")

# 6. set_identity em tenant inexistente retorna False (nao grava nada)
if set_identity("nao-existe", "X", "Y") is not False:
    falhas.append("set_identity deveria retornar False para tenant inexistente")
else:
    print("   OK  tenant inexistente nao grava (retorna False)")

print("\n" + "=" * 60)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — isolamento por tenant OK")

db.set_db_path(Path(__file__).resolve().parent.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
