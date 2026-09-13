"""
Teste: o Charon NAO pode achar que esta na VPS quando roda no PC.

O QUE O USUARIO VIU (e ele estava certo)
Perguntado "por que voce nao consegue?", o Charon respondeu:

    "Estou em um ambiente de servidor (headless), sem interface grafica.
     Isso impede que eu utilize ferramentas de controle de navegador ou
     abertura de aplicativos diretamente."

...rodando no PC do usuario, que TEM desktop. Na mesma maquina, o Jarvis fazia
a mesma tarefa sem problema — era isso que deixava a situacao absurda ("kkkkk").

CAUSA RAIZ
O `CHARON_CONTEXT.md` entra inteiro no system prompt e descrevia OS DOIS modos:

    ## Modo de Execucao
    ### Local (Windows/Mac/Linux com desktop)
    ### VPS/Servidor (Headless - sem desktop)
    ## Ferramentas Disponiveis no VPS (headless)
    ## Ferramentas que NAO funcionam no VPS
    ...
    5. Se pedirem algo que nao pode fazer no VPS, explique e liste as ferramentas

O arquivo dizia tudo sobre os dois ambientes e **nada sobre qual estava ativo**.
O modelo tinha de escolher — e escolheu o restritivo, ainda mais porque as
ferramentas de tela estavam indisponiveis naquele momento por outro bug (o
`API_BASE` fixo em localhost), o que "confirmava" a teoria errada dele.

Foi por isso que o usuario criou o projeto gemeo local: o Charon dizia que nao
podia fazer o que o Jarvis fazia na mesma maquina.

CORRECAO
`_substituir_secao_ambiente()` remove as secoes de ambiente do texto enviado e
poe no lugar UMA declaracao montada a partir do `is_headless()` — a MESMA funcao
que decide quais ferramentas sao oferecidas. Assim a lista do prompt e a lista
real nunca discordam.

Roda OFFLINE.
"""
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


from config import is_headless  # noqa: E402
from routes.voice_ws import (  # noqa: E402
    _SECOES_DE_AMBIENTE,
    _build_system_instruction,
    _load_project_context,
)

CONTEXTO_BRUTO = (RAIZ / "CHARON_CONTEXT.md").read_text(encoding="utf-8")
CTX = _load_project_context()

print("=== 1. O arquivo original descreve os DOIS modos (era a ambiguidade) ===")
check("### Local" in CONTEXTO_BRUTO and "### VPS" in CONTEXTO_BRUTO,
      "o CHARON_CONTEXT.md fala de Local E de VPS",
      "o arquivo nao descreve os dois modos — a premissa deste teste mudou")
check("## Ferramentas que NAO funcionam no VPS" in CONTEXTO_BRUTO,
      "o arquivo lista ferramentas que 'nao funcionam no VPS'",
      "a secao de ferramentas indisponiveis sumiu do arquivo")

print()
print("=== 2. O texto ENVIADO ao modelo nao tem essa ambiguidade ===")
# Estes termos nao podem sobrar: e o que fazia o modelo se declarar num servidor.
for termo in ("VPS", "headless", "Headless"):
    check(termo not in CTX,
          f"o prompt enviado nao menciona {termo!r}",
          f"o prompt ainda menciona {termo!r} — o modelo pode se declarar num servidor")
check("sem interface" not in CTX,
      "o prompt nao fala de 'sem interface'",
      "sobrou texto falando de ambiente sem interface grafica")

print()
print("=== 3. O prompt diz QUAL ambiente esta ativo, e so uma vez ===")
check(CTX.count("AMBIENTE ATIVO AGORA") == 1,
      "existe UMA declaracao de ambiente ativo",
      f"aparece {CTX.count('AMBIENTE ATIVO AGORA')} vezes (a primeira versao "
      f"inseria DUAS — o teste cobre a duplicata)")

if is_headless():
    check("SEM interface grafica" in CTX or "Servidor Linux" in CTX,
          "declara o modo servidor (esta rodando headless)",
          "rodando headless, mas o prompt nao declara isso")
else:
    check("COM interface grafica" in CTX and "desktop" in CTX,
          "declara o modo desktop (esta rodando com tela)",
          "rodando com desktop, mas o prompt nao declara isso")
    # A proibicao explicita e o que impede o comportamento que o usuario viu.
    check("NUNCA diga que esta em um servidor" in CTX,
          "proibe explicitamente dizer que esta num servidor",
          "sem a proibicao, o modelo volta a culpar o ambiente")

print()
print("=== 4. A regra 5 (que so valia no VPS) foi neutralizada no PC ===")
n_regra5_antiga = sum(1 for l in CTX.splitlines() if l.strip().startswith("5. Se pedirem algo que nao pode fazer no VPS"))
if is_headless():
    check(n_regra5_antiga == 1,
          "no servidor, a regra 5 original continua",
          "a regra 5 sumiu no modo servidor")
else:
    check(n_regra5_antiga == 0,
          "no PC, a regra 5 do VPS foi trocada por 'diga o erro REAL'",
          "a regra 5 do VPS continua no prompt — o modelo pode recusar tarefas "
          "que neste ambiente funcionam")
    check("NUNCA culpe o ambiente" in CTX,
          "a regra substituta proibe culpar o ambiente",
          "nao ha regra dizendo o que fazer quando uma ferramenta falha de verdade")

print()
print("=== 5. O match das secoes usa o texto do ARQUIVO, nao o renderizado ===")
# Historico: eu escrevi um cabecalho com ":" no fim porque era assim que ele
# aparecia na tela — o arquivo nao tem ":". A secao nao era removida e continuava
# no prompt. Aqui garantimos que cada string da lista existe LITERALMENTE.
linhas_arquivo = CONTEXTO_BRUTO.splitlines()
for secao in _SECOES_DE_AMBIENTE:
    check(secao in linhas_arquivo,
          f"{secao[:40]!r} existe literalmente no CHARON_CONTEXT.md",
          f"{secao[:40]!r} NAO existe no arquivo (typo?) — a secao nao seria removida")

print()
print("=== 6. O system instruction completo tambem esta limpo ===")
# O contexto do projeto e so uma parte; conferimos o prompt inteiro, porque a
# string "VPS" tambem aparece em outros trechos do voice_ws.py.
try:
    full = _build_system_instruction(voice_name="Charon", user_tz="America/Sao_Paulo",
                                    user_locale="pt-BR", extra_prompt="")
    check("VPS" not in full,
          "o system instruction completo nao cita VPS",
          "o prompt inteiro ainda cita VPS em algum trecho")
    check("MODO SERVIDOR (headless)" not in full or is_headless(),
          "o bloco 'MODO SERVIDOR' so entra quando realmente e headless",
          "o bloco de modo servidor foi injetado num ambiente com tela")
except Exception as e:
    check(False, "o system instruction foi montado", f"{type(e).__name__}: {e}")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — o Charon sabe onde esta rodando")
