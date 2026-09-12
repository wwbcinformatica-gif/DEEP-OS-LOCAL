"""
Lista e limpa o historico de contexto em TODOS os bancos do DEEP-OS.

POR QUE ESTE ARQUIVO EXISTE
Cada tenant tem banco PROPRIO: `data/tenants/{tenant_id}/database.sqlite`.
Existe tambem o banco padrao `data/interactions.db`. Sao arquivos diferentes —
e eu havia passado ao usuario um comando que limpava so o padrao, dizendo que
limpava "o historico". Nao limpava o do tenant.

A tabela `history` (por banco) guarda as ultimas perguntas/respostas e entra no
prompt como CONTEXTO. Ou seja: enquanto ela nao for limpa, um assunto antigo
volta mesmo com o navegador limpo.

USO

    # so listar (nao apaga nada) — seguro, rode primeiro
    python tools/limpar-historico.py

    # limpar de verdade
    python tools/limpar-historico.py --limpar

No PC:  .\\venv\\Scripts\\python.exe tools\\limpar-historico.py
Na VPS: ./venv/bin/python tools/limpar-historico.py

Prefira a acao "Limpar tudo" na interface: ela passa pelo middleware de tenant e
acerta o banco do usuario logado. Este script serve para limpar tudo de uma vez,
ou quando o navegador nao estiver a mao.
"""
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"

limpar = "--limpar" in sys.argv


def bancos() -> list[Path]:
    if not DADOS.exists():
        return []
    achados = list(DADOS.rglob("*.sqlite")) + list(DADOS.rglob("*.db"))
    return sorted(set(achados))


def contar(caminho: Path) -> int | None:
    """Quantos registros de historico o banco tem. None se nao tiver a tabela."""
    try:
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
        try:
            return con.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        finally:
            con.close()
    except Exception:
        return None


def apagar(caminho: Path) -> int:
    con = sqlite3.connect(caminho)
    try:
        n = con.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        con.execute("DELETE FROM history")
        con.commit()
        return n
    finally:
        con.close()


print(f"{'LIMPANDO' if limpar else 'LISTANDO (nada sera apagado)'} — {DADOS}\n")

total_geral = 0
afetados = 0
for b in bancos():
    n = contar(b)
    rel = b.relative_to(RAIZ)
    if n is None:
        continue  # banco sem tabela history (nao e de conversa)
    if n == 0:
        print(f"    0 registros   {rel}")
        continue
    if limpar:
        apagados = apagar(b)
        total_geral += apagados
        afetados += 1
        print(f"  {apagados:4d} apagados  {rel}")
    else:
        total_geral += n
        afetados += 1
        print(f"  {n:4d} registros   {rel}")

print()
if not limpar:
    if total_geral:
        print(f"TOTAL: {total_geral} registros de historico em {afetados} banco(s).")
        print("Para apagar tudo, rode de novo com --limpar")
    else:
        print("Nenhum historico para limpar — ja esta tudo zerado.")
else:
    print(f"LIMPO: {total_geral} registros apagados em {afetados} banco(s).")
    print("As conversas do NAVEGADOR sao separadas: use a acao 'Limpar tudo' na")
    print("interface do Jarvis (ou limpe os dados do site no navegador).")
