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

print()
print("=== 9. Botoes duplicados e a arvore que abria sozinha ===")
# O USUARIO, olhando a tela:
#   "esta aparecendo assim la acima do lado direito
#      + Nova conversa / sessao nova
#      + Novo chat / sem contexto
#      workspaces 2 / + / Geral 2 / qual destes e melhor para
#    neste botao continuar uma conversa ele esta morto
#    o workspace aparece expandido; para validar este botao o workspace poderia
#    aparecer ao clicar nele ou o workspace iniciar com a raiz escondida"
#
# Ele achou TRES problemas reais so olhando a tela.

# 9a. O "+" da barra de cima duplicava o "+ Novo chat" (mesma funcao).
barra = texto_front.split('Conversation selector bar')[-1][:1600] if 'Conversation selector bar' in texto_front else ''
check("onClick={newConversation}" not in barra,
      "o '+' duplicado saiu da barra de cima",
      "ainda ha dois caminhos para criar conversa (o usuario tem de adivinhar qual)")

# 9b. A raiz comeca FECHADA.
check("wsExpandidos[ws] === true" in texto_front,
      "a raiz do workspace comeca fechada e abre no clique",
      "a raiz abre sozinha e ocupa o painel — era a queixa do usuario")
check("wsExpandidos[ws] !== false" not in texto_front,
      "nao sobrou o padrao antigo (expandido)",
      "o padrao antigo (expandido) ainda esta no arquivo")

# 9c. "Continuar" faz algo de verdade.
m_arv = re.search(r"const abrirArvoreParaEscolher = \(\) => \{(.*?)\n  \};", texto_front, re.S)
corpo_arv = m_arv.group(1) if m_arv else ""
check(bool(corpo_arv),
      "existe abrirArvoreParaEscolher()",
      "o botao 'Continuar' continua sem acao propria")
check("setWsExpandidos(todas)" in corpo_arv,
      "o botao ABRE as raizes com conversa",
      "sem expandir, o usuario clica e nao ve os historicos")
check("for (const c of conversations)" in corpo_arv,
      "o botao abre TODAS as raizes com conversa, nao so a ativa",
      "sessoes em outra raiz ficariam escondidas")
check("scrollIntoView" in corpo_arv,
      "o botao leva a arvore para a vista",
      "as raizes nascem fechadas; sem rolar o usuario teria de procurar")
# O botao precisa CHAMAR isso (antes so chamava setActiveTab).
check("onClick={abrirArvoreParaEscolher}" in texto_front,
      "o botao 'Continuar' chama a funcao nova",
      "o botao continua ligado a algo que nao faz nada")
check("onClick={() => { setActiveTab('chat'); setWsExpandidos(" not in texto_front,
      "saiu o codigo morto que so trocava de aba",
      "o handler antigo (que nao fazia nada util) ainda esta la")

# 9d. Os dois botoes ficam no TOPO, junto dos workspaces.
# PEDIDO: "eu digo estes botoes deixar la encima -> + Novo chat / Continuar".
arvore_topo = texto_front.split('maxHeight: \'32vh\'')[-1][:2600] if "maxHeight: '32vh'" in texto_front else ""
check("Novo chat" in arvore_topo and "Continuar" in arvore_topo,
      "as duas escolhas ficam no topo da arvore, junto de workspaces",
      "os botoes nao estao no topo — o usuario pediu para subir")
# E nao podem estar DUPLICADOS no meio do painel: um botao em dois lugares
# deixa o usuario sem saber qual e o que vale.
check("onClick={newConversation}" in texto_front,
      "existe UM caminho para criar conversa",
      "o botao de criar conversa sumiu")
check(texto_front.count("onClick={newConversation}") == 1,
      "o botao de criar conversa aparece uma vez so",
      f"ha {texto_front.count('onClick={newConversation}')} botoes criando conversa "
      f"(duplicado: o usuario pergunta qual usar)")

# 9e. Os dois "+" precisam ser distinguiveis: um cria conversa, outro cria pasta.
check("+ pasta" in texto_front,
      "o botao de criar PASTA diz que cria pasta (nao parece um '+' de conversa)",
      "os dois '+' continuam ambiguos lado a lado: qual cria o que?")

print()
print("=== 10. O Jarvis nao pode ficar sem como criar conversa ===")
# Ao remover o "+" da barra do Jarvis, e preciso garantir que EXISTA um caminho
# para criar conversa. Um botao a menos sem substituto = o usuario preso.
JARVIS = RAIZ / "frontend" / "src" / "components" / "saas" / "JarvisPage.tsx"
texto_jarvis = JARVIS.read_text(encoding="utf-8")
check(texto_jarvis.count("onClick={newConversation}") >= 1,
      "o Jarvis tem botao explicito de criar conversa",
      "o Jarvis perdeu o unico caminho de criar conversa — o usuario fica preso")
# O rotulo passou de "Nova conversa" para "Novo chat": o Jarvis agora usa os
# MESMOS dois botoes do Charon ("+ Novo chat" / "Continuar"), a pedido do
# usuario — "no jarvis tem ficar igual charon o visual". O que o teste protege
# continua valendo: o botao precisa ter ROTULO (nao ser um "+" para adivinhar).
check("Novo chat" in texto_jarvis,
      "o botao do Jarvis tem rotulo (nao e um '+' para adivinhar)",
      "o usuario teria de adivinhar o que o botao faz")
check("Continuar" in texto_jarvis,
      "o Jarvis tambem tem o botao 'Continuar' (abre as conversas salvas)",
      "o Jarvis ficou sem o caminho de escolher uma conversa do historico")
check("wsExpandidos[ws] === true" in texto_jarvis,
      "a arvore do Jarvis tambem comeca fechada (mesma regra nos dois)",
      "os dois paineis ficariam com comportamentos diferentes")
check("+ pasta" in texto_jarvis,
      "o Jarvis tambem distingue criar pasta de criar conversa",
      "no Jarvis os dois '+' continuam ambiguos")

print()
print("=== 11. A conversa do Charon PRECISA ser gravada ===")
# BUG RELATADO: "ele ainda nao ve o contexto do historico".
#
# O log do VPS nao mostrou a linha "[VoiceWS] Historico recebido" -> o frontend
# nao estava MANDANDO historico nenhum. Causa: no Charon a conversa so nascia no
# "+ Novo chat" ou clicando numa sessao; quem abria a pagina e falava direto
# ficava com `activeConvId` vazio, e o efeito que grava exige um id. As falas
# apareciam na tela e NAO eram gravadas em lugar nenhum.
#
# O Jarvis ja criava a conversa na primeira mensagem. Era a armadilha nº 0 de
# novo: a mesma correcao existindo em um lugar so.
m_au = re.search(r"const addUserTranscript = useCallback\(\(text: string\) => \{(.*?)\n  \}, \[\]\);", texto_front, re.S)
corpo_au = m_au.group(1) if m_au else ""
check(bool(corpo_au), "isolei addUserTranscript", "nao achei addUserTranscript")
check("createConversation(" in corpo_au,
      "quando o usuario fala sem conversa aberta, a conversa e criada",
      "as falas do Charon continuam sem ser gravadas (nao ha onde salvar)")
check("!activeConvIdRef.current" in corpo_au,
      "a criacao so acontece quando NAO ha conversa aberta",
      "criaria uma conversa nova a cada fala")
check("setActiveConvId(conv.id)" in corpo_au,
      "a conversa criada passa a ser a ativa",
      "a conversa e criada mas o id nao e adotado — as falas seguiriam sem destino")
check("carregandoConversaRef.current = true" in corpo_au,
      "a criacao avisa o efeito de carregar (nao apaga a fala que chegou)",
      "o efeito de carregar apagaria a transcricao recem-chegada")
# NAO pode criar no primeiro transcript: o Charon manda a saudacao ANTES de o
# usuario falar, e isso criaria uma conversa a cada abertura de pagina.
check("if (!activeConvIdRef.current) {" not in texto_front.split("const addCharonTranscript")[1][:400],
      "a saudacao do Charon NAO cria conversa",
      "abrir a pagina criaria uma conversa por causa da saudacao")

print()
print("=== 12. O historico tambem vai COLADO no chat (sugestao do usuario) ===")
# PEDIDO: "a nao ser que quando clicar no historico ele ja cole novamente no chat
# do charon para ele ganhar o contexto novamente".
#
# Motivo de reforcar: "absorver turnos em silencio" e um comportamento que o
# modelo pode ignorar — e quando ignora, ele responde com o contexto do PROJETO
# (que vem do system prompt) e PARECE que esta lembrando. Foi exatamente o que o
# usuario viu: o Charon falou de DEEP-OS/C:\DEEP-OS/frontend/backend.
check("_resumo_do_historico" in texto_back,
      "existe o resumo que e colado como mensagem explicita",
      "so os turnos silenciosos sao enviados (o modelo pode ignorar)")
check("Trate como contexto ja estabelecido" in texto_back,
      "o reforco deixa claro que e contexto, nao fala a ser lida",
      "sem isso o modelo leria o historico em voz alta")
check("NAO leia em voz alta" in texto_back,
      "o reforco proibe ler/resumir o historico em voz alta",
      "o Charon poderia recitar o historico inteiro no audio")
check("_load_identity()" in texto_back.split("def _resumo_do_historico")[1][:700],
      "o resumo rotula quem falou com os nomes REAIS da identidade",
      "sem nomes, o resumo vira 'Voce: ... / Voce: ...' e confunde o modelo")

# O resumo nao pode quebrar quando o historico nao existe.
try:
    from routes.voice_ws import VoiceSession as _VS, _montar_turnos_historico as _montar  # noqa: E402

    _r_vazio = _VS._resumo_do_historico([])
    check(_r_vazio == "",
          "historico vazio nao gera reforco (nada e colado)",
          f"historico vazio gerou {_r_vazio!r}")
    _t = _montar([{"speaker": "user", "text": "oi"},
                  {"speaker": "charon", "text": "ola"}])
    _r = _VS._resumo_do_historico(_t)
    check("\n" in _r and ":" in _r,
          "o resumo sai em linhas rotuladas",
          f"formato inesperado: {_r!r}")
    check(_r.count(":") >= 2,
          "as duas falas entram no resumo",
          "o resumo perdeu falas")
except Exception as e:
    check(False, "o resumo do historico executa sem erro", f"{type(e).__name__}: {e}")

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
