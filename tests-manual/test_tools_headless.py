"""
Teste: o MESMO codigo oferece ferramentas diferentes conforme o ambiente.

PEDIDO DO USUARIO
"este projeto C:\\DEEP-OS sendo executado pelo arquivo start-saas.bat poderia ter
as duas funcoes exemplo: no vps funcionar somente as ferramentas que funciona no
vps e no local funcionar todas as ferramentas"

E a decisao tomada: **Opcao A** — aplicar no Jarvis (texto) o mesmo filtro que o
Charon (voz) ja fazia.

O QUE ESTAVA ERRADO
O filtro existia em UM lugar so: `routes/voice_ws.py` (`_HEADLESS_EXCLUDED`),
que remove as ferramentas de tela para o CHARON. O JARVIS nao filtrava nada.

Consequencia na VPS: o Charon nao oferecia `open_app`/`desktop_control`, mas o
Jarvis oferecia — e elas FALHAVAM na execucao, porque nao existe display.
`pyautogui` levanta `KeyError: 'DISPLAY'` (nao ImportError) e `mss` nao tem tela
para capturar. O usuario via "a ferramenta nao funciona" sem saber que a causa
era o ambiente, nao o codigo.

Correcao: fonte UNICA em `tools/function_defs.py` (`FERRAMENTAS_COM_GUI` +
`filtrar_tools_sem_gui()`), usada pelos dois. Era a armadilha nº 0 do
`docs/CONTINUAR.md` (codigo duplicado) acontecendo de novo.

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


from tools.function_defs import (  # noqa: E402
    FERRAMENTAS_COM_GUI,
    TOOLS,
    filtrar_tools_sem_gui,
)

print("=== 1. A fonte unica existe e bate com as ferramentas declaradas ===")
check(isinstance(FERRAMENTAS_COM_GUI, frozenset) and len(FERRAMENTAS_COM_GUI) > 0,
      f"FERRAMENTAS_COM_GUI existe ({len(FERRAMENTAS_COM_GUI)} nomes)",
      "a lista de ferramentas com GUI nao existe")

# Um nome errado aqui faz a ferramenta SUMIR no PC, onde ela funcionaria. Este e
# o erro mais provavel ao manter a lista, entao o teste confere nome por nome.
declarados = {t["function"]["name"] for t in TOOLS}
inexistentes = sorted(n for n in FERRAMENTAS_COM_GUI if n not in declarados)
check(not inexistentes,
      "todos os nomes da lista existem de verdade no catalogo de tools",
      f"nomes que NAO existem no catalogo (a ferramenta sumiria do PC a toa): {inexistentes}")

print()
print("=== 2. No PC (com desktop) NADA e removido ===")
# Este e o caminho do LOCAL/`start-saas.bat`: `is_headless()` e False no Windows.
# A regra do usuario: "no local funcionar todas as ferramentas".
mantidas_pc, removidas_pc = filtrar_tools_sem_gui(TOOLS, headless=False)
check(len(mantidas_pc) == len(TOOLS) and not removidas_pc,
      f"no PC ficam TODAS as {len(TOOLS)} ferramentas",
      f"o PC perdeu ferramentas: {removidas_pc}")
check(len(mantidas_pc) > 30,
      "o PC recebe o catalogo completo (mais de 30 ferramentas)",
      "o PC esta recebendo uma lista reduzida sem motivo")

print()
print("=== 3. Na VPS (sem tela) saem SO as que precisam de tela ===")
# `headless=True` forca o caminho da VPS. Sem este parametro seria impossivel
# testa-lo no PC — e o caminho que so roda em producao e o que costuma quebrar.
mantidas_vps, removidas_vps = filtrar_tools_sem_gui(TOOLS, headless=True)
check(len(removidas_vps) == len(FERRAMENTAS_COM_GUI),
      f"a VPS remove exatamente as {len(FERRAMENTAS_COM_GUI)} ferramentas de tela",
      f"a VPS removeu {len(removidas_vps)} (esperado {len(FERRAMENTAS_COM_GUI)}): {sorted(removidas_vps)}")
check(len(mantidas_vps) == len(TOOLS) - len(FERRAMENTAS_COM_GUI),
      f"a VPS mantem {len(mantidas_vps)} ferramentas que funcionam la",
      f"sobraram {len(mantidas_vps)} ferramentas")
for n in ("open_app", "desktop_control", "browser_control", "screen_process",
          "computer_control", "computer_settings", "game_updater", "send_message"):
    check(n in removidas_vps,
          f"{n} sai da lista na VPS (precisa de tela)",
          f"{n} continuaria sendo oferecida na VPS e falharia ao executar")

print()
print("=== 4. O que a VPS MANTEM tem de ser util de verdade ===")
# O filtro so vale se na VPS sobrar trabalho real. Se a lista ficasse vazia ou
# minuscula, o Jarvis viraria um chatbot sem ferramentas.
for n in ("bash", "read", "write", "file_edit", "web_search", "web_fetch",
          "reminder", "code_helper", "dev_agent", "system_status"):
    check(n in {t["function"]["name"] for t in mantidas_vps},
          f"{n} continua disponivel na VPS",
          f"{n} foi removida sem precisar de tela — a VPS perdeu capacidade")
check(len(mantidas_vps) >= 40,
      f"a VPS fica com um conjunto amplo ({len(mantidas_vps)} ferramentas)",
      f"a VPS ficou pobre demais: {len(mantidas_vps)}")

print()
print("=== 5. O Charon e o Jarvis leem a MESMA fonte ===")
# Era o defeito central: duas listas, uma so com filtro. Agora as duas pontas
# apontam para `FERRAMENTAS_COM_GUI`.
VOICE = (BACKEND / "routes" / "voice_ws.py").read_text(encoding="utf-8")
CHAT = (BACKEND / "routes" / "chat.py").read_text(encoding="utf-8")
check("from tools.function_defs import FERRAMENTAS_COM_GUI" in VOICE,
      "o Charon importa a lista unica",
      "o Charon voltou a ter lista propria — as duas vao divergir")
check("_HEADLESS_EXCLUDED = FERRAMENTAS_COM_GUI" in VOICE,
      "a lista do Charon E a lista unica (nao uma copia)",
      "_HEADLESS_EXCLUDED virou copia de novo")
check("filtrar_tools_sem_gui" in CHAT,
      "o Jarvis usa o filtro",
      "o Jarvis continua oferecendo ferramentas de tela na VPS")
check("TOOLS_DO_AMBIENTE" in CHAT,
      "o Jarvis tem o catalogo ja filtrado pelo ambiente",
      "o Jarvis nao tem catalogo por ambiente")

# As DUAS chamadas ao modelo precisam usar o catalogo filtrado. Sao os pares
# stream/nao-stream — a armadilha nº 4 do handoff: corrigir um e esquecer o outro.
import re  # noqa: E402

usos = len(re.findall(r"else TOOLS_DO_AMBIENTE", CHAT))
check(usos == 2,
      "os DOIS caminhos (streaming e tarefas) usam o catalogo filtrado",
      f"so {usos} caminho(s) usam TOOLS_DO_AMBIENTE — o outro segue oferecendo "
      f"ferramentas de tela na VPS")
check("else TOOLS\n" not in CHAT,
      "nenhum caminho ficou usando a lista crua",
      "ainda ha um `else TOOLS` — um dos caminhos nao foi corrigido")

print()
print("=== 6. A lista de modelos locais tambem respeita o ambiente ===")
check("LOCAL_TOOLS = [t for t in TOOLS_DO_AMBIENTE" in CHAT,
      "LOCAL_TOOLS (modelos locais) sai do catalogo filtrado",
      "LOCAL_TOOLS ainda vem da lista crua — modelo local na VPS receberia "
      "ferramenta de tela")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — mesmo codigo, ferramentas por ambiente")
