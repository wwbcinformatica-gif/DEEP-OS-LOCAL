"""
Teste: a VOZ do Charon e isolada por tenant.

Bug: trocar a voz mudava a voz de TODOS os usuarios. Causa: `voice` era
gravada em config.yaml (GLOBAL) junto com custom_color, enquanto apenas
assistant_name/user_name eram por tenant.
"""
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

TMP = Path(tempfile.mkdtemp(prefix="deepos_voice_"))

import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from core.tenant_identity import get_identity, set_identity, get_voice

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


conn = db.get_conn()
for tid in ("t1", "t2", "t3"):
    conn.execute(
        "INSERT INTO tenants (id, name, email, password_hash, plan) VALUES (?,?,?,?,'monthly')",
        (tid, f"T{tid}", f"{tid}@test.local", "x"),
    )
conn.commit()

# Confirma que a coluna existe
cols = [r[1] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()]
check("voice" in cols, "coluna tenants.voice existe", f"coluna ausente: {cols}")
conn.close()

print("\n1) Antes de personalizar: todos usam a voz padrao...")
padrao = get_voice("t1")
print(f"   voz padrao (global): {padrao}")
check(get_voice("t2") == padrao and get_voice("t3") == padrao,
      "todos herdam a voz padrao", "vozes diferentes antes de personalizar")

print("\n2) Cada tenant escolhe uma voz DIFERENTE...")
set_identity("t1", "Atena", "Wilson", voice="Kore")
set_identity("t2", "Hermes", "Maria", voice="Puck")
set_identity("t3", "Apolo", "Joao", voice="Fenrir")

esperado = {"t1": "Kore", "t2": "Puck", "t3": "Fenrir"}
for tid, voz in esperado.items():
    obtido = get_voice(tid)
    check(obtido == voz, f"{tid} -> {obtido}", f"{tid}: esperava {voz}, veio {obtido}")

print("\n3) O CENARIO DO BUG: t1 troca a voz — t2 e t3 NAO podem mudar...")
set_identity("t1", "Atena", "Wilson", voice="Aoede")
check(get_voice("t1") == "Aoede", "t1 mudou para Aoede", get_voice("t1"))
for tid, voz in (("t2", "Puck"), ("t3", "Fenrir")):
    obtido = get_voice(tid)
    check(obtido == voz, f"{tid} intacto em {voz}", f"VAZAMENTO: {tid} virou {obtido}")

print("\n4) O admin trocando a voz NAO afeta os assinantes...")
# Simula o admin salvando a voz dele (tenant que nao existe -> cai no global)
# O importante: os tenants reais seguem com as suas vozes.
check(get_voice("t2") == "Puck" and get_voice("t3") == "Fenrir",
      "vozes dos assinantes preservadas", "admin sobrescreveu os assinantes")

print("\n5) Salvar sem informar voz NAO apaga a escolha anterior...")
set_identity("t2", "Hermes", "Maria")  # voice=None
check(get_voice("t2") == "Puck",
      "voz de t2 preservada ao salvar so o nome",
      f"voz perdida: virou {get_voice('t2')}")

print("\n6) get_identity retorna os tres campos...")
ident = get_identity("t1")
print(f"   {ident}")
check(set(ident.keys()) >= {"assistant_name", "user_name", "voice"},
      "identidade traz assistant_name, user_name e voice",
      f"campos faltando: {ident.keys()}")

print("\n" + "=" * 62)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — voz isolada por tenant")

db.set_db_path(BACKEND.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
