"""Teste do resumo de lembretes em documento (texto + link de download)."""
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "actions"))

TMP = Path(tempfile.mkdtemp(prefix="deepos_remsum_"))

import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from core.reminders import add_reminder, list_reminders
from core.reminder_doc import build_spoken_summary, build_summary_markdown, save_summary_document

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


print("1) Sem lembretes...")
vazio = list_reminders("t1")
resumo = build_spoken_summary(vazio)
print(f"   voz: {resumo!r}")
check("nao tem nenhum lembrete" in resumo, "resumo de lista vazia correto", resumo)

print("\n2) Criando lembretes variados...")
agora = datetime.now()
add_reminder(agora + timedelta(hours=2), "Tomar remedio", tenant_id="t1")
add_reminder(agora + timedelta(days=1), "Reuniao com o contador", tenant_id="t1")
add_reminder(agora + timedelta(days=3), "Pagar a conta de luz", tenant_id="t1")
add_reminder(agora + timedelta(hours=5), "Ligar para Maria", tenant_id="t2")
meus = list_reminders("t1")
check(len(meus) == 3, f"3 lembretes no t1", f"esperava 3, tem {len(meus)}")

print("\n3) Resumo para FALAR (nao deve ter markdown nem URL)...")
voz = build_spoken_summary(meus)
print(f"   voz: {voz}")
check("Voce tem 3 lembretes" in voz, "cabecalho com a contagem", voz)
check("#" not in voz and "http" not in voz and "/api/" not in voz,
      "resumo de voz limpo (sem markdown/URL)", "resumo de voz tem markdown/URL")
check("Tomar remedio" in voz, "inclui a mensagem do lembrete", voz)

print("\n4) Resumo em MARKDOWN...")
md = build_summary_markdown(meus)
check(md.startswith("# "), "comeca com titulo H1", md[:40])
check("##" in md, "tem secoes por lembrete", "sem secoes")
check("Tomar remedio" in md and "Pagar a conta de luz" in md, "contem todos os lembretes", "faltam lembretes")
print("   --- primeiras linhas ---")
for linha in md.split("\n")[:8]:
    print(f"   | {linha}")

print("\n5) Salvando DOCUMENTO (o que o usuario pediu)...")
doc = save_summary_document(meus, titulo="Meus Lembretes")
if not doc:
    falhas.append("save_summary_document retornou None")
    print("   FALHOU: nao gerou o documento")
else:
    print(f"   arquivo : {doc['filename']}")
    print(f"   url     : {doc['url']}")
    print(f"   itens   : {doc['count']}")
    check(doc["count"] == 3, "documento com 3 itens", f"count={doc['count']}")
    check(doc["filename"].startswith("lembretes_") and doc["filename"].endswith(".md"),
          "nome do arquivo no padrao lembretes_<data>.md", doc["filename"])
    check(doc["url"].startswith("/api/download?path="), "link de download no formato certo", doc["url"])

    # O arquivo existe e esta dentro de downloads/ (unico dir liberado)
    p = Path(doc["path"])
    check(p.is_file(), "arquivo gravado no disco", f"nao existe: {p}")
    check(p.parent.name == "downloads",
          "esta em downloads/ (diretorio permitido pelo /api/download)",
          f"esta em {p.parent}")
    conteudo = p.read_text(encoding="utf-8")
    check("Reuniao com o contador" in conteudo, "conteudo do arquivo esta completo",
          "conteudo incompleto")

    # Confirma que save_document tambem consegue gravar aqui (mesmo mecanismo)
    outro = BACKEND.parent / "downloads" / "_teste_permissao.md"
    outro.write_text("teste", encoding="utf-8")
    check(outro.is_file(), "diretorio downloads/ gravavel", "downloads/ nao gravavel")
    outro.unlink(missing_ok=True)

print("\n6) Isolamento: o resumo do t2 nao contem lembretes do t1...")
voz_t2 = build_spoken_summary(list_reminders("t2"))
print(f"   voz t2: {voz_t2}")
check("Ligar para Maria" in voz_t2, "t2 ve o seu lembrete", voz_t2)
check("Tomar remedio" not in voz_t2, "t2 NAO ve lembrete do t1", "VAZAMENTO no resumo")

print("\n" + "=" * 64)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM")

# Limpa o arquivo de teste gerado em downloads/
try:
    if doc:
        Path(doc["path"]).unlink(missing_ok=True)
        print("(documento de teste removido)")
except Exception:
    pass

db.set_db_path(BACKEND.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
