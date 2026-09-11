"""
Teste: cada conta MASTER tem identidade propria.

Bug: as duas contas admin emitiam o MESMO `sub` ("master-admin") e nenhuma
tinha linha em `tenants`. As duas caiam no config.yaml global, entao a voz
(e o nome) que uma escolhia aparecia na outra — e tambem nos assinantes que
nunca personalizaram.
"""
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

TMP = Path(tempfile.mkdtemp(prefix="deepos_master_"))

import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from core.tenant_identity import (
    get_identity,
    is_master_key,
    master_email_from_key,
    master_identity_key,
    set_identity,
)

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


A = "wwbc22@gmail.com"
B = "wwbcinformatica@gmail.com"

print("1) Chaves de identidade sao UNICAS por conta...")
ka, kb = master_identity_key(A), master_identity_key(B)
print(f"   {A:28} -> {ka}")
print(f"   {B:28} -> {kb}")
check(ka != kb, "chaves diferentes para contas diferentes", "MESMA chave — vao compartilhar identidade")
check(master_email_from_key(ka) == A, "extrai o e-mail de volta", master_email_from_key(ka))
check(is_master_key(ka) and is_master_key("master-admin"),
      "reconhece a chave nova E o token antigo", "nao reconheceu")

print("\n2) A linha de identidade e criada automaticamente...")
conn = db.get_conn()
antes = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
conn.close()
check(antes == 0, "banco comeca sem tenants", f"ja tinha {antes}")

ident_a = get_identity(ka)  # deve auto-criar a linha
conn = db.get_conn()
depois = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
linha = conn.execute("SELECT id, email, plan, status FROM tenants WHERE id = ?", (ka,)).fetchone()
conn.close()
print(f"   tenants apos a consulta: {depois}")
if linha:
    print(f"   linha criada: {dict(linha)}")
check(depois == 1, "criou a linha da conta master", f"esperava 1 linha, tem {depois}")
check(linha is not None and linha["email"] == A, "linha tem o e-mail correto", "e-mail errado/ausente")
check(linha is not None and linha["plan"] == "master", "linha marcada como master", "plano errado")

print("\n3) Antes de personalizar, herda o padrao global...")
padrao = ident_a["voice"]
print(f"   voz herdada: {padrao}")
check(bool(padrao), "tem voz padrao", "sem voz")

print("\n4) O CENARIO DO BUG: admin A troca a voz — admin B NAO pode mudar...")
set_identity(ka, "Charon A", "Wilson A", voice="Kore")
set_identity(kb, "Charon B", "Wilson B", voice="Puck")

ia, ib = get_identity(ka), get_identity(kb)
print(f"   A -> voz={ia['voice']!r} nome={ia['assistant_name']!r}")
print(f"   B -> voz={ib['voice']!r} nome={ib['assistant_name']!r}")
check(ia["voice"] == "Kore", "A ficou com Kore", ia["voice"])
check(ib["voice"] == "Puck", "B ficou com Puck", ib["voice"])
check(ia["voice"] != ib["voice"], "as vozes sao DIFERENTES", "VAZAMENTO entre contas master")

print("\n5) A troca de um NAO altera o outro...")
set_identity(ka, "Charon A", "Wilson A", voice="Aoede")
ib2 = get_identity(kb)
check(ib2["voice"] == "Puck", "B continua Puck", f"VAZAMENTO: B virou {ib2['voice']}")
check(get_identity(ka)["voice"] == "Aoede", "A mudou para Aoede", get_identity(ka)["voice"])

print("\n6) Assinante comum (com plano) continua isolado...")
conn = db.get_conn()
conn.execute(
    "INSERT INTO tenants (id, name, email, password_hash, plan) VALUES (?,?,?,?,'quarterly')",
    ("t_assinante", "Assinante", "cliente@teste.com", "x"),
)
conn.commit()
conn.close()
set_identity("t_assinante", "Atena", "Cliente", voice="Fenrir")
check(get_identity("t_assinante")["voice"] == "Fenrir", "assinante com a voz dele", "assinante errado")
check(get_identity(ka)["voice"] == "Aoede", "admin A intacto", "admin A mudou junto")
check(get_identity(kb)["voice"] == "Puck", "admin B intacto", "admin B mudou junto")

print("\n7) Token antigo (master-admin) nao quebra...")
try:
    velho = get_identity("master-admin")
    print(f"   get_identity('master-admin') -> voz={velho['voice']!r}")
    check(True, "aceita o formato antigo sem estourar", "")
except Exception as e:
    check(False, "", f"estourou com token antigo: {e}")

print("\n" + "=" * 64)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — identidade master isolada")

db.set_db_path(BACKEND.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
