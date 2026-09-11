"""
Auditoria das rotas da API em DUAS partes.

Por que dividido: a primeira versao tentava requisitar TODAS as rotas e travava
— algumas varrem o disco (`/llamacpp/models`) ou fazem chamada de rede. Agora:

  PARTE 1 (offline, nunca trava): inspeciona o REGISTRO das rotas.
      Detecta rotas duplicadas, catch-all antes de literal, e rotas que
      somem. Foi esse tipo de checagem que teria pegado o bug do catch-all
      em `routes/config.py`, que sobreviveu 47 sessoes.

  PARTE 2 (runtime, com timeout rigido por rota): sonda as rotas criticas
      de seguranca e as novas da sessao 48.

Uso:
    python tests-manual/test_all_routes.py
"""
import signal
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import main  # importa ANTES de apontar o banco (main chama set_db_path)
import database.connection as db

TMP = Path(tempfile.mkdtemp(prefix="deepos_routes_"))
db.set_db_path(TMP / "interactions.db")
db.init_db()

TIMEOUT_S = 6


class TimeoutErro(Exception):
    pass


def _alarme(signum, frame):
    raise TimeoutErro()


def com_timeout(funcao, segundos=TIMEOUT_S):
    """Executa com limite de tempo (SIGALRM). Devolve ('timeout', None) se estourar."""
    if not hasattr(signal, "SIGALRM"):
        return funcao()
    antigo = signal.signal(signal.SIGALRM, _alarme)
    signal.alarm(segundos)
    try:
        return funcao()
    except TimeoutErro:
        return ("timeout", None)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, antigo)


def parte1_registro(problemas: list) -> None:
    """Inspecao offline do registro de rotas — nao faz requisicao."""
    print("=" * 78)
    print("PARTE 1 — Inspecao do REGISTRO de rotas (offline)")
    print("=" * 78)

    literais: dict[str, list[str]] = {}
    catch_alls: list[tuple[str, str, int]] = []   # (caminho, metodo, indice)
    total = 0
    registradas: set[tuple[str, str]] = set()

    for i, r in enumerate(main.app.routes):
        caminho = getattr(r, "path", "")
        if not caminho.startswith("/"):
            continue
        metodos = set(getattr(r, "methods", None) or {"WEBSOCKET"})
        for m in metodos:
            if m in ("HEAD", "OPTIONS"):
                continue
            total += 1
            chave = (m, caminho)
            if chave in registradas:
                problemas.append(f"ROTA DUPLICADA: {m} {caminho}")
            registradas.add(chave)

        # Segmento com {param} generico (ex: /{section}) = catch-all
        ultimo = caminho.rstrip("/").rsplit("/", 1)[-1]
        if ultimo.startswith("{") and ultimo.endswith("}"):
            nome = ultimo[1:-1]
            if ":" not in nome:  # {path:path} e intencional
                for m in metodos:
                    if m not in ("HEAD", "OPTIONS"):
                        catch_alls.append((caminho, m, i))
        else:
            literais.setdefault(caminho, []).append((i, metodos))

    print(f"  rotas (metodo, caminho) ......... {total}")
    print(f"  catch-alls encontrados .......... {len(catch_alls)}")

    # REGRA: um catch-all so e problema se vier ANTES de uma rota literal do
    # MESMO METODO. O FastAPI casa por metodo primeiro, entao
    # `DELETE /teams/{id}` nao captura `POST /teams/message` — nao e bug.
    for caminho_ca, metodo_ca, idx_ca in catch_alls:
        pai = caminho_ca.rsplit("/", 1)[0]
        conflitos = []
        for caminho_lit, entradas in literais.items():
            if not caminho_lit.startswith(pai + "/"):
                continue
            if "/" in caminho_lit[len(pai) + 1:]:
                continue  # subpath, nao colide
            for idx_lit, metodos_lit in entradas:
                if metodo_ca in metodos_lit and idx_lit > idx_ca:
                    conflitos.append((caminho_lit, metodo_ca, idx_lit))
        if conflitos:
            for caminho_lit, metodo, idx_lit in conflitos:
                problemas.append(
                    f"CATCH-ALL ANTES DE LITERAL: {metodo} {caminho_ca} (ordem {idx_ca}) "
                    f"captura {metodo} {caminho_lit} (ordem {idx_lit})"
                )
                print(f"  !! {metodo} {caminho_ca} vem ANTES de {metodo} {caminho_lit}")
        else:
            print(f"  OK   {metodo_ca:6} {caminho_ca} — sem conflito de ordem")

    # Rotas novas da sessao 48 precisam existir
    print()
    print("  Rotas da sessao 48 presentes?")
    for rota, metodo in (("/api/reminders", "GET"), ("/api/reminders/summary", "GET"),
                         ("/api/reminders/export", "GET"), ("/api/config/identity", "GET")):
        existe = (metodo, rota) in registradas
        print(f"    {'OK  ' if existe else 'FALHOU'} {metodo} {rota}")
        if not existe:
            problemas.append(f"ROTA AUSENTE: {metodo} {rota}")


def parte2_runtime(problemas: list) -> None:
    """Sondagem em runtime das rotas criticas, com timeout por rota."""
    from fastapi.testclient import TestClient

    cliente = TestClient(main.app)

    # Host EXTERNO: simula o trafego que chega pela internet (via nginx).
    # Sem isto o TestClient usa "testserver", que o middleware trata como
    # app desktop — e a protecao pareceria nao funcionar.
    EXTERNO = {"Host": "deep-os.tech"}

    # (metodo, rota, status esperados, descricao)
    casos = [
        # ALCANCAVEIS PELA INTERNET e que devolvem dados sensiveis.
        # O nginx encaminha /api/ ao backend, entao estes SAO exploraveis.
        ("GET", "/api/config", (401, 403), "config do agente exige auth"),
        ("GET", "/api/config/agent", (401, 403), "config do agente exige auth"),
        ("GET", "/api/config/mcp-servers", (401, 403), "servidores MCP exigem auth"),
        ("GET", "/api/config/api-key", (401, 403), "status da chave exige auth"),
        ("GET", "/api/instances", (401, 403), "instancias (com tenant_id) exigem auth"),
        # So na raiz: nao chegam de fora (nginx serve o SPA), mas protegidas
        ("GET", "/secrets", (401, 403), "secrets exige auth"),
        ("GET", "/logs", (401, 403), "logs exige auth"),
        ("GET", "/memory", (401, 403), "memory exige auth"),
        ("GET", "/tool/list", (401, 403), "tool/list exige auth"),
        ("GET", "/knowledge", (401, 403), "knowledge exige auth"),
        ("GET", "/history", (401, 403), "history exige auth"),
        # Publicas por design: DEVEM responder 200
        ("GET", "/health", (200,), "health publico"),
        ("GET", "/plans/public", (200,), "planos publicos"),
        ("GET", "/shop/products", (200,), "produtos publicos"),
        ("GET", "/api/config/identity", (200,), "identidade (rota literal, nao catch-all)"),
        # Novas da sessao 48: 401 sem token
        ("GET", "/api/reminders", (401, 403), "lembretes exigem auth"),
        ("GET", "/api/reminders/summary", (401, 403), "resumo exige auth"),
        ("GET", "/api/reminders/export", (401, 403), "export exige auth"),
    ]

    print()
    print("=" * 78)
    print("PARTE 2 — Sondagem em runtime (Host externo, timeout por rota)")
    print("=" * 78)

    for metodo, rota, esperados, descricao in casos:
        resultado = com_timeout(lambda: cliente.request(metodo, rota, headers=EXTERNO))
        if isinstance(resultado, tuple) and resultado and resultado[0] == "timeout":
            print(f"  ~~   {metodo:5} {rota:28} LENTA (>{TIMEOUT_S}s) — {descricao}")
            continue
        resp = resultado
        s = resp.status_code
        bom = s in esperados
        marca = "OK  " if bom else "FALHOU"
        print(f"  {marca} {metodo:5} {rota:28} {s}  {descricao}")
        if not bom:
            esperado_txt = "/".join(str(e) for e in esperados)
            problemas.append(f"{metodo} {rota}: HTTP {s} (esperado {esperado_txt}) — {descricao}")


def main_auditoria() -> int:
    problemas: list[str] = []

    parte1_registro(problemas)
    parte2_runtime(problemas)

    print()
    print("=" * 78)
    if problemas:
        print(f"RESULTADO: {len(problemas)} PROBLEMA(S)")
        for p in problemas:
            print(f"  - {p}")
        return 1

    print("RESULTADO: rotas OK — nada duplicado, catch-alls no fim, sensiveis protegidas")
    return 0


if __name__ == "__main__":
    sys.exit(main_auditoria())
