"""
Teste: historico de conversa no Charon (o contexto da sessao Live).

QUEIXA DO USUARIO
"quando eu clico no historico o Charon nao consegue ver o historico, ele sempre
esta em um contexto novo"

REGRA QUE ELE DEFINIU
"sempre for aberto pela primeira vez a sessao deve ser nova mas quando eu entro
no novo historico ele deve lembrar de tudo"

Ou seja: DUAS situacoes diferentes, que antes eram tratadas igual (nenhuma
carregava contexto).

CAUSA RAIZ
O Gemini Live cria uma sessao NOVA a cada conexao e guarda o estado da conversa
no servidor DELE. O frontend salvava os transcripts no localStorage e os exibia
na tela — mas nunca os enviava. Entao, do ponto de vista do modelo, a conversa
realmente comecava do zero. `switchConversation` so mexia no estado da tela.

BUG SECUNDARIO ENCONTRADO NO CAMINHO
Havia um SEGUNDO `self._interrupted = False` dentro de `send_audio` (o primeiro,
no loop de recepcao, ja tinha sido corrigido antes). Como `send_audio` roda a
cada chunk do microfone, ele desfazia a interrupcao do barge-in logo em seguida.
Sobreviveu a primeira correcao porque a busca foi feita no caminho do
RECEBIMENTO, nao no do ENVIO — e o usuario ainda nao tinha testado com voz.

Roda OFFLINE (nao chama o Gemini).
"""
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


VOICE = BACKEND / "routes" / "voice_ws.py"
CHARON = RAIZ / "frontend" / "src" / "components" / "saas" / "CharonPage.tsx"

texto_back = VOICE.read_text(encoding="utf-8")
texto_front = CHARON.read_text(encoding="utf-8")

from routes.voice_ws import MAX_HISTORICO_CHARS, MAX_HISTORICO_TURNOS, _montar_turnos_historico as montar  # noqa: E402

print("=== 1. Conversao dos transcripts em turnos do Gemini ===")
conversa = [
    {"speaker": "user", "text": "ola"},
    {"speaker": "charon", "text": "Ola Wilson, eu sou Charon."},
    {"speaker": "user", "text": "quais lembretes eu tenho"},
    {"speaker": "charon", "text": "Voce tem dois lembretes."},
]
t = montar(conversa)
check(len(t) == 4, f"4 falas -> {len(t)} turnos", f"esperado 4 turnos, veio {len(t)}")
if t:
    check(t[0]["role"] == "user" and t[1]["role"] == "model",
          "papel do assistente e 'model' (vocabulario do Gemini)",
          f"papeis errados: {[x['role'] for x in t]}")
    check(all("parts" in x and x["parts"] and "text" in x["parts"][0] for x in t),
          "cada turno tem parts[0].text (formato exigido pelo SDK)",
          f"estrutura invalida: {t[0]}")
    check(t[3]["parts"][0]["text"] == "Voce tem dois lembretes.",
          "o texto de cada turno e preservado",
          f"texto perdido: {t[3]}")

print()
print("=== 2. Casos degenerados nao podem quebrar a sessao ===")
check(montar([]) == [], "historico vazio -> lista vazia", "historico vazio gerou turnos")
check(montar(None) == [], "historico None -> lista vazia", "None gerou turnos")
check(montar([{"speaker": "user", "text": "   "}]) == [],
      "falas so com espaco sao descartadas", "fala vazia virou turno")
check(montar(["lixo", 123, None]) == [],
      "itens que nao sao dicionario sao ignorados", "item invalido quebrou a montagem")

# O SDK exige que o PRIMEIRO turno seja do usuario
so_charon = montar([{"speaker": "charon", "text": "oi"}, {"speaker": "user", "text": "tudo bem"}])
check(so_charon and so_charon[0]["role"] == "user",
      "se o corte deixar o assistente na frente, esse turno e descartado",
      f"o primeiro turno veio do assistente: {[x['role'] for x in so_charon]}")

# Falas seguidas do mesmo lado precisam virar uma so
seguidas = montar([
    {"speaker": "user", "text": "primeira"},
    {"speaker": "user", "text": "segunda"},
    {"speaker": "charon", "text": "resposta"},
])
check(len(seguidas) == 2,
      "falas seguidas do mesmo papel sao juntadas num turno",
      f"esperado 2 turnos, veio {len(seguidas)}")
check(seguidas and "primeira" in seguidas[0]["parts"][0]["text"] and "segunda" in seguidas[0]["parts"][0]["text"],
      "juntar preserva os dois textos na ordem",
      f"texto perdido ao juntar: {seguidas}")

print()
print("=== 3. Limites de tamanho (contexto grande custa latencia) ===")
longa = [{"speaker": "user" if i % 2 == 0 else "charon", "text": "x" * 500} for i in range(200)]
tl = montar(longa)
chars = sum(len(p["text"]) for x in tl for p in x["parts"])
check(chars <= MAX_HISTORICO_CHARS,
      f"respeita o teto de {MAX_HISTORICO_CHARS} caracteres (enviou {chars})",
      f"estourou o limite: {chars} chars")
check(len(tl) <= MAX_HISTORICO_TURNOS,
      f"respeita o teto de {MAX_HISTORICO_TURNOS} turnos (enviou {len(tl)})",
      f"estourou turnos: {len(tl)}")
# O que importa e manter o FIM da conversa (continuidade real)
ultima = montar([
    {"speaker": "user", "text": "antiga " + "z" * 300},
    {"speaker": "charon", "text": "resposta antiga"},
    {"speaker": "user", "text": "ASSUNTO ATUAL"},
    {"speaker": "charon", "text": "certo"},
])
check(any("ASSUNTO ATUAL" in p["text"] for x in ultima for p in x["parts"]),
      "o FIM da conversa e sempre preservado (e o que da continuidade)",
      f"o assunto atual se perdeu: {ultima}")

print()
print("=== 4. Backend: o historico chega do frontend e vai para a sessao ===")
check('data.get("history")' in texto_back,
      "o handler de 'start' le o campo `history`",
      "o backend ignora o historico enviado pelo frontend")
check("history=historico" in texto_back,
      "o historico e repassado para session.start()",
      "o historico e lido mas nao chega na sessao")
check("async def _enviar_historico" in texto_back,
      "existe _enviar_historico()", "nao existe a funcao que envia o historico")
check("turn_complete=False" in texto_back,
      "o historico vai com turn_complete=False (contexto, nao resposta)",
      "sem turn_complete=False o modelo responderia a cada turno antigo")

# A abertura precisa ESCOLHER entre retomar e cumprimentar
check("async def _abrir_sessao" in texto_back,
      "existe _abrir_sessao() que decide entre retomar e cumprimentar",
      "nao ha decisao entre sessao nova e retomada")
check("_pedir_retomada" in texto_back,
      "existe _pedir_retomada() para quando ha historico",
      "nao ha pedido de retomada — o Charon se reapresentaria no meio da conversa")
m_ret = re.search(r"async def _pedir_retomada.*?(?=\n    async def )", texto_back, re.S)
corpo_ret = m_ret.group(0) if m_ret else ""
check("SEM se reapresentar" in corpo_ret,
      "a retomada proibe se reapresentar",
      "sem isso o Charon se apresenta de novo no meio de uma conversa antiga")
check("SEM resumir" in corpo_ret,
      "a retomada proibe resumir o historico inteiro",
      "sem isso o modelo faz um resumo longo — ruim em voz")
print()
print("=== 5. Frontend: a regra das duas situacoes ===")
check("restaurarHistorico" in texto_front,
      "existe o estado 'restaurarHistorico'",
      "nao ha distincao entre sessao nova e conversa restaurada")
check("history: historico" in texto_front,
      "o payload de 'start' envia o campo `history`",
      "o frontend nao envia o historico — era a causa raiz do contexto novo")
# Estado inicial: sessao NOVA (a regra do usuario: primeira abertura = nova)
m_init = re.search(r"const \[restaurarHistorico, setRestaurarHistorico\] = useState\((\w+)\)", texto_front)
check(bool(m_init) and m_init.group(1) == "false",
      "abrir o Charon comeca como sessao NOVA (nao restaura nada)",
      f"estado inicial inesperado: {m_init.group(1) if m_init else '?'}")
# Clicar no historico ativa a restauracao
m_sw = re.search(r"const switchConversation = \(convId: string\) => \{(.*?)\n  \};", texto_front, re.S)
corpo_sw = m_sw.group(1) if m_sw else ""
check("setRestaurarHistorico(true)" in corpo_sw,
      "clicar numa conversa do historico ATIVA a restauracao",
      "clicar no historico nao ativa a restauracao — o Charon continua sem lembrar")
check("restaurarHistoricoRef.current = true" in corpo_sw,
      "o ref tambem e atualizado (o callback de conexao le o ref, nao o state)",
      "so o state foi atualizado; o callback de conexao leria valor antigo")
# Conversa nova volta a ser sessao nova
m_novo = re.search(r"const newConversation = \(\) => \{(.*?)\n  \};", texto_front, re.S)
corpo_novo = m_novo.group(1) if m_novo else ""
check("setRestaurarHistorico(false)" in corpo_novo,
      "criar conversa nova volta a ser sessao nova",
      "depois de restaurar, a conversa nova continuaria restaurando contexto")
# Trocar de conversa com a sessao aberta precisa RECONECTAR.
# O corpo que faz isso agora e `entrarNaConversa` (o `switchConversation` chama
# ele) — a reconexao saiu de dentro do switch para ser compartilhada com o
# "+ Novo chat", que tambem precisa ligar/reconectar. O teste olha o arquivo
# inteiro para nao ficar frágil a esse tipo de mudanca de lugar.
check("disconnectVoice()" in texto_front and "connectVoiceRef.current()" in texto_front,
      "trocar de conversa com a sessao aberta reconecta (o Gemini nao 'rebobina')",
      "so trocar o estado da tela nao muda nada no Gemini — o contexto continuaria o antigo")
check("entrarNaConversa" in corpo_sw,
      "o clique na conversa passa pelo caminho que reconecta",
      "o switch nao chama a reconexao — o contexto antigo continuaria")
# Indicador visual
check("lembra da conversa" in texto_front,
      "ha indicador visual de que o Charon esta lembrando da conversa",
      "o usuario nao tem como saber se o contexto foi carregado")

print()
print("=== 6. BUG SECUNDARIO: send_audio nao pode desfazer a interrupcao ===")
m_sa = re.search(r"async def send_audio\(self.*?(?=\n    async def )", texto_back, re.S)
corpo_sa = m_sa.group(0) if m_sa else ""
codigo_sa = "\n".join(l for l in corpo_sa.splitlines() if not l.strip().startswith("#"))
check("self._interrupted = False" not in codigo_sa,
      "send_audio NAO reseta _interrupted",
      "send_audio ainda reseta _interrupted — como roda a cada chunk do microfone, "
      "desfaz o barge-in logo em seguida")


print()
print("=== 7. As DUAS escolhas de contexto ao abrir o Charon ===")
# PEDIDO DO USUARIO (literal):
#   "exemplo 1 nova conversa -> charon ja comeca automaticamente
#    2 se eu escolher um dos historicos ele ja comeca sabendo de todo o conteudo
#    daquele historico e ja pergunta de onde quer continua ou alguma pergunta
#    sobre o historico"
#
# E antes disso: "nao faz nenhuma das duas ate eu escolher".
#
# Ou seja: ao ABRIR a pagina o Charon nao liga (nem cria conversa, nem pede
# microfone, nem cumprimenta). Ele espera a escolha — e a escolha, seja qual for,
# conecta sozinha.

# 7a. Sem auto-start: nada de timer nem de listeners de primeiro gesto.
check("tentarAutoStart" not in texto_front,
      "nao existe mais auto-start do Charon ao abrir a pagina",
      "o Charon ainda liga sozinho ao abrir — contraria 'nao faz nenhuma das duas ate eu escolher'")
check("setTimeout(() => tentarAutoStart" not in texto_front,
      "nao ha timer de auto-start",
      "o timer ligaria o Charon sozinho depois de 1s")

# 7b. Ha o estado de escolha, e ele comeca em 'escolher'.
check("modoInicio" in texto_front and "'escolher' | 'novo' | 'historico'" in texto_front,
      "existe o estado de escolha do contexto (escolher | novo | historico)",
      "sem esse estado nao ha como representar 'ainda nao escolhi'")
check("useState<'escolher' | 'novo' | 'historico'>('escolher')" in texto_front,
      "a pagina abre no estado 'escolher' (Charon parado)",
      "a pagina abriria ja num modo, ligando o Charon sem escolha")

# 7c. A tela de escolha mostra as DUAS opcoes.
check("Como voce quer comecar?" in texto_front,
      "ha uma tela perguntando como comecar",
      "o usuario nao ve a escolha — foi o pedido dele (igual ao painel do DSH)")
check("+ Novo chat" in texto_front,
      "'+ Novo chat' aparece como opcao explicita",
      "a opcao de conversa nova continua escondida num '+' pequeno")
check("Continuar uma conversa" in texto_front,
      "a opcao de continuar do historico aparece explicitamente",
      "nao esta claro que da para continuar uma conversa salva")

# 7d. ESCOLHA 1 (nova conversa): liga sozinho e cumprimenta.
m_nc = re.search(r"const newConversation = \(\) => \{(.*?)\n  \};", texto_front, re.S)
corpo_nc = m_nc.group(1) if m_nc else ""
check("connectVoiceRef.current()" in texto_front,
      "a escolha conecta o Charon (nao precisa de um terceiro clique)",
      "escolher nao ligaria o Charon — o usuario teria de clicar de novo")
check("modoInicioRef.current = 'novo'" in corpo_nc,
      "nova conversa marca o modo 'novo'",
      "nova conversa nao marcaria o modo, e o historico poderia ser restaurado")
check("restaurarHistoricoRef.current = false" in corpo_nc,
      "nova conversa NAO manda historico (o backend cumprimenta)",
      "nova conversa mandaria historico — nao seria 'contexto novo'")

# 7e. ESCOLHA 2 (historico): manda o historico E pede a pergunta de continuacao.
check("modoInicioRef.current = 'historico'" in texto_front,
      "escolher uma conversa salva marca o modo 'historico'",
      "o modo nao seria registrado ao escolher do historico")
check("getTranscripts(convId)" in texto_front or "getTranscripts(activeConvId)" in texto_front,
      "escolher do historico carrega os transcripts daquela conversa",
      "o historico salvo nao seria carregado antes de conectar")

# O backend precisa PERGUNTAR de onde continuar (pedido explicito do usuario).
m_ret = re.search(r"async def _pedir_retomada\(self.*?(?=\n    async def )", texto_back, re.S)
corpo_ret = m_ret.group(0) if m_ret else ""
check(bool(corpo_ret), "isolei _pedir_retomada", "nao achei _pedir_retomada")
check("PERGUNTA" in corpo_ret.upper(),
      "a retomada manda o Charon PERGUNTAR de onde continuar",
      "a retomada so diz que lembra, sem perguntar — era o pedido do usuario")
check("de onde" in corpo_ret.lower(),
      "o gatilho cita explicitamente 'de onde' continuar",
      "o gatilho nao orienta a pergunta de continuacao")
check("PROIBIDO" in corpo_ret,
      "a retomada continua proibindo se reapresentar/resumir tudo",
      "sem a proibicao o modelo volta a discursar no meio da conversa")


print()
print("=== 8. O botao 'Charon ouvindo' desliga/liga SEM perder o contexto ===")
# PEDIDO DO USUARIO: "tem este botao acima no painel direito 'Charon ouvindo'
# quando clica nele e para charon parar de ouvir e interagir mas ele tambem
# reconecta — verifica se ele e um problema para o historico".
# E depois: "ele pode funcionar como desativar charon e ativar charon mas nao
# pode perder o contexto da conversa".
#
# O botao e o cabecalho do painel direito (`s.rightHeader` com onClick
# `toggleCharon`). Clicar em "Charon ativo" DESLIGA; clicar de novo LIGA.
#
# O PROBLEMA REAL: religar mandava `history: []` — uma sessao NOVA no servidor do
# Gemini. Como o estado da conversa vive LA (por sessao), o Charon voltava sem
# lembrar de nada no meio da conversa. Nao era o historico GRAVADO que se
# perdia: era o CONTEXTO vivo do modelo.
check("toggleCharon" in texto_front,
      "o cabecalho do painel direito continua alternando ligar/desligar",
      "o botao de ativar/desativar sumiu")
m_rc = re.search(r"const reconectarContextoAtual = \(\) => \{(.*?)\n  \};", texto_front, re.S)
corpo_rc = m_rc.group(1) if m_rc else ""
check(bool(corpo_rc), "existe reconectarContextoAtual()", "o religar nao tem caminho proprio")
check("getTranscripts(convId)" in corpo_rc,
      "religar LE o historico gravado da conversa atual",
      "religar nao olha o historico — voltaria como sessao nova")
check("setRestaurarHistorico(true)" in corpo_rc and "restaurarHistoricoRef.current = true" in corpo_rc,
      "religar marca a restauracao (state E ref, que e o que o conectar le)",
      "marcar so o state nao chega no callback de conexao (ele le o ref)")
check("connectVoiceRef.current()" in corpo_rc,
      "religar conecta de fato",
      "religar so mexe no estado e nao abre a sessao")
# E o desligar nao pode mexer no que esta gravado.
m_dv = re.search(r"const disconnectVoice = useCallback\(\(\) => \{(.*?)\n  \}, \[\]\);", texto_front, re.S)
corpo_dv = m_dv.group(1) if m_dv else ""
check(bool(corpo_dv), "isolei disconnectVoice", "nao achei disconnectVoice")
check("deleteConversation" not in corpo_dv and "clearHistory" not in corpo_dv,
      "parar de ouvir NAO apaga nada do historico",
      "o desligar mexe no historico — parar de ouvir nunca deve perder conversa")
# Fechar a aba no meio da conversa: grava uma ultima vez (localStorage e sincrono).
check("beforeunload" in texto_front and "pagehide" in texto_front,
      "o historico e regravado ao fechar/recarregar a aba",
      "fechar a aba no meio da conversa pode perder a ultima fala")
check("transcriptsRef" in texto_front and "activeConvIdRef" in texto_front,
      "o gravador do beforeunload usa REFS (listener registrado uma vez)",
      "sem refs, o listener leria state da primeira renderizacao (closure velha)")

def funcao_que_contem(linhas: list, numero_linha: int) -> str:
    """
    Nome da funcao que contem a linha indicada.

    A primeira versao deste teste olhava os 300 caracteres anteriores e dava
    FALSO POSITIVO: acusava `__init__` (onde zerar _interrupted e a
    inicializacao correta) e o proprio `_handle_response`. Aqui procuramos de
    verdade a definicao que engloba a linha.
    """
    for i in range(numero_linha - 1, 0, -1):
        s = linhas[i - 1]
        if s.startswith("class "):
            break
        if s.lstrip().startswith(("def ", "async def ")):
            return s.strip().split("(")[0].replace("async def ", "").replace("def ", "")
    return "?"


# Onde zerar _interrupted E LEGITIMO:
#   __init__ ......... estado inicial da sessao
#   _handle_response . o turn_complete encerra o turno e o guarda de 3s libera
# Em qualquer outro lugar e suspeito, porque a maioria dos caminhos roda a cada
# chunk do microfone — foi assim que o bug sobreviveu a primeira correcao.
PERMITIDOS = {"__init__", "_handle_response"}

linhas_arq = texto_back.splitlines()
ocorrencias = [m.start() for m in re.finditer(r"self\._interrupted = False", texto_back)]
print(f"   (ocorrencias de '_interrupted = False' no arquivo: {len(ocorrencias)})")
for pos in ocorrencias:
    linha = texto_back[:pos].count("\n") + 1
    dono = funcao_que_contem(linhas_arq, linha)
    check(dono in PERMITIDOS,
          f"linha {linha}: reset em {dono}() (liberado)",
          f"linha {linha}: reset de _interrupted em {dono}() — fora dos lugares "
          f"permitidos ({sorted(PERMITIDOS)}); se esse caminho roda a cada chunk "
          f"do microfone, ele desfaz o barge-in")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — historico restaurado e barge-in corrigido")
