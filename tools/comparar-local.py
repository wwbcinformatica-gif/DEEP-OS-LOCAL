"""
Compara o estado do C:\\DEEP-OS ANTES das correcoes desta sessao (commit
06d620c) com o que existe hoje em C:\\DEEP-OS-LOCAL.

OBJETIVO: saber, para cada arquivo que eu mudei, se o LOCAL estava igual ao
DEEP-OS antes das mudancas. Se estiver, a correcao se aplica direto (copia ou
patch). Se estiver diferente, o LOCAL tem codigo proprio e eu preciso olhar antes
de sobrescrever — sobrescrever cegamente apagaria trabalho dele.

Uso: python tools/comparar-local.py
"""
import subprocess
import sys
from pathlib import Path

DEEPOS = Path(r"C:\DEEP-OS")
LOCAL = Path(r"C:\DEEP-OS-LOCAL")
BASE = sys.argv[1] if len(sys.argv) > 1 else "06d620c"  # commit do DEEP-OS ANTES da mudanca


def git(*args, cwd=DEEPOS):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def norm(texto):
    return (texto or "").replace("\r\n", "\n").replace("\r", "\n")


def conteudo_base(caminho):
    """Conteudo no commit BASE. None se o arquivo nao existia la."""
    return git("show", f"{BASE}:{caminho}")


arquivos = git("diff", "--name-only", f"{BASE}..HEAD")
if not arquivos:
    print("Nao consegui listar os arquivos alterados.")
    sys.exit(1)
arquivos = [a.strip() for a in arquivos.splitlines() if a.strip()]

print(f"Comparando {len(arquivos)} arquivos: DEEP-OS@{BASE}  x  DEEP-OS-LOCAL@HEAD\n")

identicos, diferentes, novos, ausentes = [], [], [], []

for a in arquivos:
    p_local = LOCAL / a
    base = conteudo_base(a)

    if not p_local.exists():
        ausentes.append(a)
        marca = "AUSENTE NO LOCAL"
    elif base is None:
        novos.append(a)
        marca = "NOVO (nao existia antes) — copia segura"
    elif norm(base) == norm(p_local.read_text(encoding="utf-8", errors="replace")):
        identicos.append(a)
        marca = "IDENTICO — correcao aplica limpo"
    else:
        diferentes.append(a)
        marca = "DIFERENTE — o LOCAL tem codigo proprio, revisar"

    print(f"  {marca:<42} {a}")

print()
print("=" * 78)
print(f"  IDENTICOS (aplicar direto) ......... {len(identicos)}")
print(f"  NOVOS (copiar) ..................... {len(novos)}")
print(f"  AUSENTES no LOCAL .................. {len(ausentes)}")
print(f"  DIFERENTES (revisar um a um) ....... {len(diferentes)}")
print("=" * 78)

if diferentes:
    print("\n>>> ARQUIVOS QUE PRECISAM DE ATENCAO:")
    for d in diferentes:
        print(f"    {d}")

if ausentes:
    print("\n>>> NAO EXISTEM NO LOCAL (talvez nao se apliquem):")
    for a in ausentes:
        print(f"    {a}")

# Salva as listas para as proximas etapas
saida = LOCAL / ".comparacao-tmp.txt"
LINHAS = [
    "IDENTICOS=" + "|".join(identicos),
    "NOVOS=" + "|".join(novos),
    "AUSENTES=" + "|".join(ausentes),
    "DIFERENTES=" + "|".join(diferentes),
]
try:
    saida.write_text("\n".join(LINHAS), encoding="utf-8")
    print(f"\nListas salvas em {saida}")
except Exception as e:
    print(f"\n(nao consegui salvar as listas: {e})")
