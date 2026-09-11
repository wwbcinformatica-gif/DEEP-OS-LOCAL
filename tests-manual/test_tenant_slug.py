"""
Teste: compatibilidade entre a pasta do tenant com ':' (antiga) e com '_' (nova).

BUG CORRIGIDO
Havia dois sanitizadores no projeto:
  - routes/download.py e core/reminder_doc.py -> removiam ':' e '@'
  - scripts/migrar-downloads-legados.sh (shell) -> usava o id CRU
Resultado: os arquivos ficaram em `downloads/master-admin:wwbc22@gmail.com/`
enquanto o backend procurava `downloads/master-adminwwbc22gmail.com/` — pasta
diferente. TODO download dava 404.

Agora existe UMA fonte (core.tenant_identity.tenant_slug) e o download procura
nas duas variacoes, para nao perder arquivos ja gravados.
"""
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import routes.download as dl
from core.tenant_identity import tenant_slug

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


TMP = Path(tempfile.mkdtemp(prefix="deepos_slug_"))
dl._RAIZ = TMP

TENANT = "master-admin:wwbc22@gmail.com"
SLUG = tenant_slug(TENANT)

print(f"tenant_id ......: {TENANT}")
print(f"tenant_slug ....: {SLUG}")
print()

# A pasta com ':' so pode ser criada no Linux — o Windows rejeita nomes com
# dois-pontos (NotADirectoryError). Isso explica por que o bug do download
# nunca se reproduziu no PC: o script de migracao (shell, rodado no VPS) foi o
# unico codigo a criar essa pasta, e ela so existe em Linux.
PODE_CRIAR_CRUA = True
try:
    (TMP / "downloads").mkdir(parents=True, exist_ok=True)
    (TMP / "downloads" / TENANT).mkdir()
except (OSError, ValueError, NotADirectoryError):
    PODE_CRIAR_CRUA = False

pasta_nova = TMP / "downloads" / SLUG
pasta_nova.mkdir(parents=True, exist_ok=True)
(pasta_nova / "documento_novo.md").write_text("novo", encoding="utf-8")

if PODE_CRIAR_CRUA:
    (TMP / "downloads" / TENANT / "documento_antigo.md").write_text("antigo", encoding="utf-8")
else:
    print("AVISO: este SO nao aceita ':' em nome de pasta (esperado no Windows).")
    print("       Testando so a variacao sanitarizada; o caso da pasta crua e")
    print("       validado no Linux (VPS).")
    print()

print("=== estrutura ===")
for p in sorted(TMP.rglob("*")):
    if p.is_file():
        print("  ", p.relative_to(TMP))
print()

if PODE_CRIAR_CRUA:
    print("1) Arquivo na pasta ANTIGA (com ':') e encontrado...")
    achado = dl._find_file("documento_antigo.md", TENANT)
    check(achado is not None and achado.name == "documento_antigo.md",
          f"encontrou em {achado.parent.name if achado else '?'}",
          "NAO encontrou documento antigo (era o bug do 404)")
else:
    print("1) [pulado] pasta com ':' — SO nao suporta (validado no Linux)")
    check(True, "caso reconhecido e explicitamente pulado", "")

print("\n2) Arquivo na pasta NOVA (com '_') tambem e encontrado...")
achado = dl._find_file("documento_novo.md", TENANT)
check(achado is not None and achado.name == "documento_novo.md",
      f"encontrou em {achado.parent.name if achado else '?'}",
      "NAO encontrou documento novo")

print("\n3) As bases cobrem as duas variacoes...")
bases = [b.name for b in dl._bases_para_tenant(TENANT)]
print(f"   {bases}")
check(SLUG in bases, "procura na pasta sanitarizada", f"faltou: {bases}")
check(TENANT in bases, "procura tambem na pasta do id cru (compatibilidade)",
      f"faltou a variacao crua: {bases}")

print("\n4) O isolamento continua valido (nao vaza para outro tenant)...")
outro = "a48abdaccf57524c2e4b6e5ccd8dc287"
pasta_outro = TMP / "downloads" / outro
pasta_outro.mkdir(parents=True)
(pasta_outro / "segredo.md").write_text("SEGREDO", encoding="utf-8")
achado = dl._find_file("segredo.md", TENANT)
check(achado is None, "nao acessa arquivo de outro tenant",
      f"VAZAMENTO: {achado}")

print("\n5) O sanitizador e unico para todos os modulos...")
from core.reminder_doc import _downloads_dir  # noqa: E402

check(dl._sanitize(TENANT) == tenant_slug(TENANT),
      "download.py e tenant_identity concordam",
      "divergencia entre sanitizadores")

# _downloads_dir usa o ContextVar; sem tenant cai na raiz
raiz_dl = _downloads_dir()
check("downloads" in str(raiz_dl), f"reminder_doc usa downloads/ ({raiz_dl.name})",
      f"caminho inesperado: {raiz_dl}")

print("\n" + "=" * 66)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — slug unificado e compativel")

shutil.rmtree(TMP, ignore_errors=True)
