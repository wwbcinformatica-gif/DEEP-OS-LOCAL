"""
Teste de SEGURANCA — isolamento de downloads e configuracao de segredos.

Bug corrigido: `_find_file` usava `rglob` recursivo sobre a raiz de downloads,
entao um assinante que descobrisse o nome do arquivo de outro conseguia
baixa-lo. Alem disso havia caminhos hardcoded (C:/DEEP-OS/docs,
/root/DEEP-OS/docs).
"""
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import routes.download as dl

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


TMP = Path(tempfile.mkdtemp(prefix="deepos_dl_"))
# Redireciona a raiz do modulo para o temporario
dl._RAIZ = TMP
(TMP / "downloads" / "tenantA").mkdir(parents=True)
(TMP / "downloads" / "tenantB").mkdir(parents=True)
(TMP / "downloads" / "tenantA" / "meu_doc.md").write_text("doc do A", encoding="utf-8")
(TMP / "downloads" / "tenantB" / "segredo_do_B.md").write_text("SEGREDO", encoding="utf-8")
# Arquivo solto na raiz (legado)
(TMP / "downloads" / "legado.md").write_text("antigo", encoding="utf-8")

print("=== Estrutura ===")
for f in sorted(TMP.rglob("*")):
    if f.is_file():
        print("  ", f.relative_to(TMP))

print("\n1) Tenant A acessa o PROPRIO arquivo...")
achado = dl._find_file("meu_doc.md", "tenantA")
check(achado is not None and achado.name == "meu_doc.md",
      "A encontrou meu_doc.md", f"nao encontrou: {achado}")

print("\n2) CENARIO DO BUG: A NAO pode acessar arquivo do B...")
achado = dl._find_file("segredo_do_B.md", "tenantA")
check(achado is None,
      "A NAO acessou segredo_do_B.md",
      f"VAZAMENTO: A acessou {achado}")

print("\n3) Nem por caminho absoluto...")
caminho_abs = str(TMP / "downloads" / "tenantB" / "segredo_do_B.md")
achado = dl._find_file(caminho_abs, "tenantA")
check(achado is None,
      "A NAO acessou por caminho absoluto",
      f"VAZAMENTO por caminho absoluto: {achado}")

print("\n4) Nem por busca parcial (glob)...")
achado = dl._find_file("segredo*", "tenantA")
check(achado is None, "A NAO achou por glob", f"VAZAMENTO por glob: {achado}")

print("\n5) Path traversal tambem e bloqueado...")
for tentativa in ("../tenantB/segredo_do_B.md",
                  "..\\tenantB\\segredo_do_B.md",
                  "tenantA/../tenantB/segredo_do_B.md"):
    achado = dl._find_file(tentativa, "tenantA")
    marcador = "OK " if achado is None else "FALHOU "
    print(f"   {marcador} {tentativa!r} -> {achado}")
    if achado is not None:
        falhas.append(f"PATH TRAVERSAL: {tentativa} acessou {achado}")

print("\n6) B acessa o PROPRIO arquivo...")
achado = dl._find_file("segredo_do_B.md", "tenantB")
check(achado is not None and achado.name == "segredo_do_B.md",
      "B encontrou o seu", f"B nao encontrou: {achado}")

print("\n7) Sem tenant (app desktop) NAO acessa subdiretorio de assinante...")
achado = dl._find_file("segredo_do_B.md", None)
check(achado is None,
      "sem tenant nao entra em pasta de assinante",
      f"VAZAMENTO sem tenant: {achado}")

print("\n8) Bases por tenant estao corretas...")
bases_a = dl._bases_para_tenant("tenantA")
print(f"   A -> {[str(b.relative_to(TMP)) for b in bases_a]}")
check(all("tenantA" in str(b) for b in bases_a),
      "bases do A apontam so para tenantA", f"bases erradas: {bases_a}")

print("\n9) Sanitizacao de id malicioso...")
from core.tenant_identity import tenant_slug  # noqa: E402

# A sanitizacao e FONTE UNICA agora (tenant_slug). Antes havia duas diferentes
# no projeto e o script de migracao usava o id cru -> os arquivos iam para
# `downloads/master-admin:wwbc22@gmail.com/` e o backend procurava
# `downloads/master-adminwwbc22gmail.com/`. Todo download dava 404.
check(tenant_slug("master-admin:wwbc22@gmail.com") == "master-admin_wwbc22_gmail.com",
      f"slug do tenant master: {tenant_slug('master-admin:wwbc22@gmail.com')!r}",
      f"slug inesperado: {tenant_slug('master-admin:wwbc22@gmail.com')!r}")
# O que importa nao e o texto conter "..", e sim NAO conter separador de
# caminho — sem `/` ou `\`, o resultado e um unico nome de pasta e nao pode
# escapar. Ex: '../../etc/passwd' -> '.._.._etc_passwd' (seguro).
_slug_malicioso = tenant_slug("../../etc/passwd")
check("/" not in _slug_malicioso and "\\" not in _slug_malicioso,
      f"id malicioso vira um unico nome de pasta: {_slug_malicioso!r}",
      f"slug ainda contem separador de caminho: {_slug_malicioso!r}")
check(tenant_slug("") is None, "id vazio -> None", "id vazio devolveu string")
check(tenant_slug("///") == "___", f"so simbolos vira slug seguro: {tenant_slug('///')!r}",
      f"slug inseguro: {tenant_slug('///')!r}")

# O modulo de download deve usar a MESMA sanitizacao
check(dl._sanitize("master-admin:wwbc22@gmail.com") == tenant_slug("master-admin:wwbc22@gmail.com"),
      "download.py usa a mesma sanitizacao (fonte unica)",
      "download.py divergiu da fonte unica")

# E deve encontrar a pasta com o id CRU tambem (arquivos gravados antes)
bases_brutas = [str(b) for b in dl._bases_para_tenant("master-admin:wwbc22@gmail.com")]
tem_cru = any("master-admin:wwbc22@gmail.com" in b for b in bases_brutas)
check(tem_cru, "procura tambem na pasta do id cru (compatibilidade)",
      f"nao procura a pasta antiga: {bases_brutas}")

bases = dl._bases_para_tenant("../../etc/passwd")
for b in bases:
    try:
        b.resolve().relative_to(TMP.resolve())
    except ValueError:
        check(False, "", f"base ESCAPOU da raiz: {b}")
        break
else:
    check(True, "bases de id malicioso ficam dentro da raiz", "")

print("\n9b) LEGADO: documento antigo na raiz de downloads/ continua acessivel...")
# Antes do isolamento, os documentos ficavam soltos em downloads/. Sem o
# fallback, todos os links ja enviados ao usuario dariam 404 (regressao).
achado = dl._find_file("legado.md", "tenantA")
check(achado is not None and achado.name == "legado.md",
      "tenant autenticado acessa documento legado",
      f"REGRESSAO: documento legado inacessivel ({achado})")
# Mas NAO pode acessar arquivo que esta dentro da pasta de outro tenant
achado = dl._find_file("segredo_do_B.md", "tenantA")
check(achado is None, "legado nao abre porta para pastas de outros",
      "VAZAMENTO pelo fallback legado")
# Sem tenant = app desktop: nao ha isolamento, a raiz de downloads/ E a base
# dele. Entao o arquivo legado e legitimamente acessivel (comportamento
# esperado — o desktop roda na propria maquina do usuario).
# O que NAO pode acontecer e um tenant acessar a pasta de OUTRO (teste 2).
achado = dl._find_file("legado.md", None)
check(achado is not None,
      "sem tenant (desktop) acessa a raiz de downloads/ — correto",
      "desktop perdeu acesso aos proprios arquivos")

print("\n10) Configuracao de seguranca (senha master)...")
from core.security_config import (check_master_credentials, master_emails,
                                  using_default_master_password)

check(len(master_emails()) >= 1, f"{len(master_emails())} e-mail(s) master", "nenhum e-mail")
check(check_master_credentials("wwbc22@gmail.com", "admin123@"),
      "login master funciona com a senha padrao", "login master quebrou")
check(not check_master_credentials("wwbc22@gmail.com", "senha-errada"),
      "senha errada e rejeitada", "ACEITOU senha errada")
check(not check_master_credentials("outro@gmail.com", "admin123@"),
      "e-mail nao-master e rejeitado", "ACEITOU e-mail nao-master")
check(using_default_master_password(),
      "detecta que a senha padrao esta em uso (para avisar)", "nao detectou")

print("\n11) JWT_SECRET nao e o default publico...")
import core.auth as auth

check(auth.SECRET_KEY != "DEEP-OS-saas-secret-key-change-in-production",
      "chave NAO e o default publico do codigo",
      "AINDA usa a chave publica!")
check(len(auth.SECRET_KEY) >= 32, f"chave com {len(auth.SECRET_KEY)} chars", "chave curta")

print("\n" + "=" * 64)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — seguranca OK")

shutil.rmtree(TMP, ignore_errors=True)
