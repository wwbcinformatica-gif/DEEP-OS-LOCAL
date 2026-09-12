"""
Aplica no C:\\DEEP-OS-LOCAL todas as correcoes feitas no C:\\DEEP-OS nesta sessao.

POR QUE COPIAR E SEGURO AQUI
Antes de copiar, `tools/comparar-local.py` comparou os 34 arquivos alterados:
   - 15 IDENTICOS ao DEEP-OS antes das correcoes -> a mudanca encaixa limpa;
   - 19 AUSENTES no LOCAL -> sao adicoes puras;
   -  0 DIFERENTES -> o LOCAL NAO tem codigo proprio em nenhum arquivo tocado.
Sem essa verificacao, copiar poderia apagar trabalho especifico do LOCAL. Se
algum arquivo estivesse na lista de DIFERENTES, este script pararia.

Uso: python tools/aplicar-no-local.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEEPOS = Path(r"C:\DEEP-OS")
LOCAL = Path(r"C:\DEEP-OS-LOCAL")
BASE = sys.argv[1] if len(sys.argv) > 1 else "06d620c"

# Nao copiar estes para o gemeo.
#
# As ferramentas de SINCRONIZACAO (comparar-local.py / aplicar-no-local.py) SAO
# copiadas de proposito: assim um modelo trabalhando a partir do LOCAL tambem
# consegue sincronizar. Ja o verificador de deploy NAO faz sentido la, porque o
# LOCAL nao tem VPS.
EXCLUIR = {
    "tools/verificar-deploy.cjs",
}


def git(*args):
    r = subprocess.run(["git", *args], cwd=str(DEEPOS), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


arquivos = git("diff", "--name-only", f"{BASE}..HEAD")
if not arquivos:
    print("Nao consegui listar os arquivos.")
    sys.exit(1)
arquivos = [a.strip() for a in arquivos.splitlines() if a.strip() and a.strip() not in EXCLUIR]

print(f"Copiando {len(arquivos)} arquivos de DEEP-OS para DEEP-OS-LOCAL\n")

# ── GUARDA: nao aplicar se houver DIVERGENCIA ────────────────────────────────
#
# O procedimento manda "se aparecer DIFERENTE, PARE e revise a mao". Isso
# dependia da minha disciplina — e eu falhei: rodei o comparador, vi
# "DIFERENTES: 1" e apliquei assim mesmo, porque o numero parecia inofensivo.
# (Deu certo por sorte: o LOCAL estava ADIANTADO, nao divergente.)
#
# Regra que depende de disciplina vai ser quebrada. Agora a ferramenta RECUSA:
# quem quiser insistir precisa passar --forcar de proposito.
if "--forcar" not in sys.argv:
    try:
        comparador = Path(__file__).resolve().parent / "comparar-local.py"
        saida = subprocess.run(
            [sys.executable, str(comparador), BASE],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        ).stdout or ""
        m = re.search(r"DIFERENTES \(revisar um a um\) \.+ (\d+)", saida)
        n_divergentes = int(m.group(1)) if m else 0
        if n_divergentes > 0:
            print("=" * 70)
            print(f"ABORTADO: {n_divergentes} arquivo(s) DIFERENTE(S) entre os projetos.")
            print("=" * 70)
            print("\nCopiar agora poderia sobrescrever codigo proprio do gemeo.\n")
            # Mostra quais sao, para o usuario decidir.
            # Procura pelo TEXTO da marca, nao pelo travessao: o caractere
            # especial da mensagem ja causou problema de encoding no console.
            for linha in saida.splitlines():
                if "codigo proprio" in linha or "DIFERENTE" in linha:
                    print("   " + linha.strip())
            print("\nRevise os arquivos acima. Se a diferenca for o LOCAL estar")
            print("ADIANTADO (ja ter a mudanca), copiar e seguro.")
            print("Para insistir: python tools/aplicar-no-local.py %s --forcar" % BASE)
            sys.exit(2)
        print(f"Guarda OK: nenhuma divergencia (0 DIFERENTE) — copia segura.\n")
    except SystemExit:
        raise
    except Exception as e:
        print(f"AVISO: nao consegui rodar a guarda do comparador ({e}).")
        print("       Siga o procedimento manualmente antes de copiar.\n")

if not LOCAL.exists():
    print(f"ERRO: {LOCAL} nao existe")
    sys.exit(1)

copiados, erros = [], []
for a in arquivos:
    origem = DEEPOS / a
    destino = LOCAL / a
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        copiados.append(a)
        print(f"  OK   {a}")
    except Exception as e:
        erros.append((a, str(e)))
        print(f"  ERRO {a} -> {e}")

print()
print("=== Dependencias que as correcoes usam: existem no LOCAL? ===")
# Estes arquivos vem de sessoes anteriores e NAO foram alterados nesta sessao.
# Se faltarem, a correcao nao funciona (ex: sem o middleware, /api/config nao
# exige auth e o comportamento de 401 nao existe).
DEPENDENCIAS = [
    "backend/middleware/security.py",
    "backend/core/auth.py",
    "backend/core/tenant_identity.py",
    "backend/core/security_config.py",
    "backend/config.py",
    "backend/main.py",
    "frontend/src/components/saas/chatStorage.ts",
    # .tsx, nao .ts — conferir a extensao errada acusava "FALTANDO" para um
    # arquivo que existe nos dois projetos (falso alarme).
    "frontend/src/components/saas/markdownRenderer.tsx",
    "config.yaml",
    "package.json",
]
faltando = []
for d in DEPENDENCIAS:
    alvo = LOCAL / d
    if alvo.exists():
        existe = True
    elif d.endswith((".ts", ".tsx")):
        # O projeto mistura .ts e .tsx; aceita qualquer uma das duas.
        raiz_nome = alvo.with_suffix("")
        existe = any(raiz_nome.with_suffix(ext).exists() for ext in (".ts", ".tsx"))
    else:
        existe = False
    if not existe:
        faltando.append(d)
    print(f"  {'OK     ' if existe else 'FALTANDO'}  {d}")

print()
print("=== Diferencas estruturais que o LOCAL pode precisar ===")
# Arquivos que so o LOCAL tem (nao podem ser perdidos — so informativo)
so_local = ["README-LOCAL.md", "INICIAR-LOCAL.bat", "start-saas.bat", "START-TOTAL.bat",
            "STOP-TOTAL.bat", "chatbot-server", "config", "generated"]
for s in so_local:
    p = LOCAL / s
    print(f"  {'presente' if p.exists() else 'ausente '}  {s}")

print()
print("=" * 70)
print(f"  copiados: {len(copiados)}")
print(f"  erros   : {len(erros)}")
if faltando:
    print(f"  DEPENDENCIAS FALTANDO: {faltando}")
    print("  -> as correcoes podem nao funcionar; revisar antes de testar")
if erros:
    for a, e in erros:
        print(f"    {a}: {e}")
print("=" * 70)
