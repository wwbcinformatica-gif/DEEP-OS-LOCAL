"""
Teste da protecao de rotas sensiveis — com o cenario REAL do proxy reverso.

POR QUE ESTE TESTE EXISTE
-------------------------
A primeira versao do middleware liberava acesso quando o IP do cliente era
127.0.0.1, pensando no app desktop. Mas em producao o nginx faz proxy para
127.0.0.1:8001 — entao TODA requisicao externa chega vinda do localhost. A
regra liberou o mundo inteiro e o vazamento continuou aberto, mesmo com o
middleware registrado e todos os testes locais passando.

A licao: testar com `TestClient` sem header `Host` NAO reproduz producao (o
host padrao e "testserver", que eu tratava como local). Este teste cobre os
dois cenarios explicitamente.
"""
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import main  # importa antes de apontar o banco (main chama set_db_path)
import database.connection as db

TMP = Path(tempfile.mkdtemp(prefix="deepos_secmw_"))
db.set_db_path(TMP / "interactions.db")
db.init_db()

from fastapi.testclient import TestClient  # noqa: E402

from core.auth import AuthManager  # noqa: E402

cliente = TestClient(main.app)

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


PROTEGIDAS = [
    # Estes sao alcancaveis PELA INTERNET (o nginx encaminha /api/ ao backend)
    "/api/config",
    "/api/config/agent",
    "/api/config/mcp-servers",
    "/api/config/api-key",
    "/api/instances",
    # Estes existem so na raiz -> nao chegam de fora, mas protegemos igual
    "/secrets",
    "/logs",
    "/memory",
    "/tool/list",
    "/knowledge",
    "/history",
]
PUBLICAS = ["/health", "/plans/public", "/shop/products", "/api/config/identity"]

ADMIN_TOKEN = AuthManager.create_access_token(
    {"sub": "master-admin:t@t.com", "is_master": True, "is_admin": True}
)

print("=" * 74)
print("1) VIA PROXY (Host: deep-os.tech) — o cenario de PRODUCAO")
print("=" * 74)
print("   Sem token: as rotas sensiveis DEVEM responder 401.")
print("   (era aqui que o bug passava: requisicao chegava do 127.0.0.1 do nginx)")
print()
for rota in PROTEGIDAS:
    r = cliente.get(rota, headers={"Host": "deep-os.tech"}, timeout=15)
    check(r.status_code == 401,
          f"{rota:16} -> 401 (bloqueado)",
          f"{rota:16} -> {r.status_code} (EXPOSTO!)")

print()
print("=" * 74)
print("2) VIA PROXY com token de admin — o painel precisa funcionar")
print("=" * 74)
for rota in PROTEGIDAS:
    r = cliente.get(rota, headers={"Host": "deep-os.tech",
                                   "Authorization": f"Bearer {ADMIN_TOKEN}"}, timeout=15)
    check(r.status_code == 200,
          f"{rota:16} -> 200 (admin acessa)",
          f"{rota:16} -> {r.status_code} (quebrou o painel!)")

print()
print("=" * 74)
print("3) Rotas publicas continuam abertas (com Host externo)")
print("=" * 74)
for rota in PUBLICAS:
    r = cliente.get(rota, headers={"Host": "deep-os.tech"}, timeout=15)
    check(r.status_code == 200,
          f"{rota:16} -> 200 (publica)",
          f"{rota:16} -> {r.status_code} (quebrou rota publica)")

print()
print("=" * 74)
print("4) APP DESKTOP (Host: 127.0.0.1) — sem login, precisa funcionar")
print("=" * 74)
for rota in ["/secrets", "/logs", "/tool/list"]:
    r = cliente.get(rota, headers={"Host": "127.0.0.1:8001"}, timeout=15)
    check(r.status_code == 200,
          f"{rota:16} -> 200 (desktop local)",
          f"{rota:16} -> {r.status_code} (quebrou o desktop)")

print()
print("=" * 74)
print("5) Host externo NAO pode se passar por local")
print("=" * 74)
for host_falso in ["deep-os.tech", "2.25.143.185", "evil.com", "deep-os.tech:8001"]:
    r = cliente.get("/api/config", headers={"Host": host_falso}, timeout=15)
    check(r.status_code == 401,
          f"Host {host_falso:20} -> 401",
          f"Host {host_falso:20} -> {r.status_code} (BYPASS!)")

print()
print("=" * 74)
print("6) /api/config/identity continua PUBLICO (lido no boot do frontend)")
print("=" * 74)
for host in ("deep-os.tech", "127.0.0.1:8001"):
    r = cliente.get("/api/config/identity", headers={"Host": host}, timeout=15)
    check(r.status_code == 200,
          f"Host {host:18} -> 200 (identidade acessivel)",
          f"Host {host:18} -> {r.status_code} (quebrou o frontend no boot)")
print("   (devolve apenas assistant_name/user_name/voice — nao a config inteira)")

print()
print("=" * 74)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: protecao OK — bloqueia o mundo, libera desktop e admin")
