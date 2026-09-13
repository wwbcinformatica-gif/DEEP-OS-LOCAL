"""
Teste: isolamento das INSTANCIAS por assinante.

O QUE FOI ENCONTRADO (vazamento real entre clientes)

`backend/routes/instances.py` tirava o tenant de um PARAMETRO DA REQUISICAO:

    @router.get("")
    async def list_instances(tenant_id: str = ""):
        if tenant_id:
            ... WHERE tenant_id = ?
        else:
            cur.execute("SELECT * FROM instances ORDER BY created_at DESC")   # TODOS

E o frontend (`JarvisPage`) chama `/api/instances` **sem** passar `tenant_id`.
Ou seja: caia no ramo sem filtro e devolvia as instancias de **todos os
assinantes** — nome, modelo, provedor, `system_prompt` e `temperature`. A tela
usa esses campos, entao uma instancia de outro cliente podia ser listada e ate
adotada.

Em `PUT` e `DELETE` era pior: nao conferiam tenant NENHUM, entao qualquer
usuario autenticado podia ALTERAR ou APAGAR a instancia de outro sabendo o id.

Foi levantado pelo proprio usuario: "se for um usuario esperto como o programa e
de aluguel ele poderia ter acesso a outras conversas e pesquisas de outros
usuarios". Ele estava certo.

A CORRECAO: o tenant vem do JWT (`Depends(get_current_tenant_id)`), como em
`routes/shop.py` e `routes/auth.py`, e e conferido em toda operacao sobre UMA
instancia.

Roda OFFLINE (nao chama provedor nenhum).
"""
import ast
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
sys.path.insert(0, str(BACKEND))

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


def sem_docstrings(codigo: str) -> str:
    """
    Troca o conteudo de TODOS os literais de texto por espacos, mantendo as
    linhas no lugar.

    POR QUE ISTO E NECESSARIO (e foi necessario de verdade aqui)
    O docstring deste arquivo de rotas CITA o codigo errado, de proposito — e a
    explicacao do bug so faz sentido mostrando o defeito. Mas o teste lia esse
    texto como se fosse codigo e acusava "ainda ha tenant_id na query" num
    arquivo que ja estava corrigido: FALSO POSITIVO meu, na primeira execucao.

    Esta e a armadilha nº 5 do docs/CONTINUAR.md ("testes desta suite se enganam
    lendo COMENTARIO/DOCSTRING como codigo"), que ja custou tempo 5 vezes neste
    projeto. A defesa caseira anterior era "remover linhas que comecam com #", o
    que NAO resolve docstring de varias linhas nem string entre aspas.

    Aqui usamos o proprio parser do Python: e impossivel "esquecer" um literal.
    """
    arvore = ast.parse(codigo)
    linhas = codigo.splitlines()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            ini_l, ini_c = no.lineno - 1, no.col_offset
            fim_l, fim_c = no.end_lineno - 1, no.end_col_offset
            for i in range(ini_l, fim_l + 1):
                c0 = ini_c if i == ini_l else 0
                c1 = fim_c if i == fim_l else len(linhas[i])
                linhas[i] = linhas[i][:c0] + " " * (c1 - c0) + linhas[i][c1:]
    return "\n".join(linhas)


def consultas_sql(codigo: str) -> list[str]:
    """
    Devolve SO os literais de texto que sao SQL de verdade (SELECT/DELETE/UPDATE).

    POR QUE NAO USAR REGEX NO ARQUIVO INTEIRO
    O docstring deste modulo CITA a consulta defeituosa (`SELECT * FROM instances
    ORDER BY created_at DESC`, sem WHERE) para explicar o vazamento. Procurar por
    regex no arquivo todo encontra a citacao e acusa o arquivo ja corrigido —
    falso positivo real, que aconteceu duas vezes enquanto eu escrevia este teste.

    O AST resolve os dois lados: acha o SQL dentro de strings (o texto do
    docstring e um literal tambem, mas NAO comeca com SELECT/DELETE/UPDATE em
    posicao de comando... exceto nas linhas de exemplo). Por isso, alem de
    filtrar por prefixo, descartamos os literais que sao DOCSTRING das funcoes e
    do modulo — que e onde ficam os exemplos citados.
    """
    arvore = ast.parse(codigo)
    # Marca os nos que sao docstring (primeiro statement de modulo/classe/funcao).
    docstrings = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = getattr(no, "body", None)
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant) \
                    and isinstance(corpo[0].value.value, str):
                docstrings.add(id(corpo[0].value))
    achados = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docstrings:
            if no.value.lstrip().upper().startswith(("SELECT", "DELETE", "UPDATE", "INSERT")):
                achados.append(no.value)
    return achados


INST_BRUTO = (BACKEND / "routes" / "instances.py").read_text(encoding="utf-8")
INST = sem_docstrings(INST_BRUTO)
SQL = consultas_sql(INST_BRUTO)

print("=== 0. O teste nao le docstring como codigo ===")
check('tenant_id: str = ""' in INST_BRUTO,
      "o arquivo realmente cita o codigo antigo no docstring (e explica o bug)",
      "o docstring nao cita o defeito — a explicacao ficaria sem contexto")
check('tenant_id: str = ""' not in INST,
      "o teste ignora o que esta em docstring (nao confunde texto com codigo)",
      "o teste voltou a ler docstring como codigo — falso positivo garantido")
check(len(SQL) >= 4,
      f"o teste encontrou {len(SQL)} consultas SQL reais para inspecionar",
      f"so encontrou {len(SQL)} consultas — o teste nao esta vendo o SQL")

print()
print("=== 1. O tenant vem do TOKEN, nunca da requisicao ===")
check("from core.auth import get_current_tenant_id" in INST,
      "a rota importa o extrator de tenant do JWT",
      "o tenant nao vem do token — volta a poder ser falsificado pelo cliente")

# O defeito original era exatamente esta assinatura: tenant_id como parametro.
check('tenant_id: str = ""' not in INST,
      "nao existe mais tenant_id como parametro de query",
      'ainda ha `tenant_id: str = ""` — o cliente escolhe de quem sao os dados')

check(INST.count("tenant_id: str = Depends(get_current_tenant_id)") == 4,
      "as QUATRO operacoes (listar, criar, alterar, apagar) usam o token",
      f"so {INST.count('Depends(get_current_tenant_id)')} operacao(oes) usam o token")

print()
print("=== 2. Nao existe caminho que liste TUDO ===")
# Olha so o SQL REAL (ver `consultas_sql`): regex no arquivo inteiro encontraria
# a consulta defeituosa citada no docstring e acusaria um arquivo ja corrigido.
sem_where = [q for q in SQL if q.upper().startswith("SELECT") and "WHERE" not in q.upper()]
check(not sem_where,
      "nenhum SELECT de verdade devolve instancias sem filtrar",
      f"ha {len(sem_where)} SELECT sem WHERE — devolveria instancias de todos: {sem_where}")
check(any(q.upper().startswith("SELECT") and "WHERE tenant_id" in q for q in SQL),
      "a listagem filtra por tenant",
      "a listagem perdeu o filtro por tenant")

print()
print("=== 3. Alterar e apagar conferem o DONO ===")
check("_exigir_dono" in INST,
      "existe verificacao de dono antes de alterar/apagar",
      "sem isso, qualquer autenticado mexe na instancia de outro pelo id")
# As duas operacoes precisam passar pela checagem.
check(INST.count("_exigir_dono(conn, instance_id, tenant_id)") == 2,
      "as DUAS operacoes de escrita conferem o dono",
      "so uma delas confere — a outra continua aberta")
check(any(q.upper().startswith("DELETE") and "tenant_id" in q for q in SQL),
      "o DELETE tambem filtra por tenant no proprio SQL (defesa dupla)",
      "o DELETE confia so na checagem anterior")

print()
print("=== 4. Quem tenta o id de outro recebe 404 (nao 403) ===")
# 403 confirmaria que o id existe e e de outra pessoa. Nao ha por que contar isso.
check('404, "Instancia nao encontrada"' in INST_BRUTO,
      "instancia de outro assinante responde 404",
      "a resposta diferencia 'nao existe' de 'nao e seu' — vaza a existencia do id")

print()
print("=== 5. Roda de verdade: sem token tem de dar 401 ===")
try:
    import main  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402

    c = TestClient(main.app)
    r1 = c.get("/api/instances")
    check(r1.status_code == 401,
          f"GET /api/instances sem token -> 401",
          f"sem token respondeu {r1.status_code} — os dados estao abertos")
    # Tentar escolher o tenant pela query tambem NAO pode funcionar.
    r2 = c.get("/api/instances?tenant_id=master-admin")
    check(r2.status_code == 401,
          "tentar escolher o tenant pela query tambem da 401",
          f"a query ainda influencia: {r2.status_code}")
    check("instances" not in r2.text.lower()[:200],
          "a resposta de erro nao devolve instancia nenhuma",
          "a resposta carrega dados de instancias mesmo sem autorizacao")
except Exception as e:
    check(False, "o cenario HTTP executou", f"{type(e).__name__}: {e}")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — instancias isoladas por assinante")
