"""
Teste: historico das conversas do Jarvis (salvar, restaurar e exportar).

QUEIXA DO USUARIO
"ao clicar no historico nao volta para o historico, nao aparece nenhuma
informacao do historico salvo"

CAUSA (uma coisa simples, efeito devastador)
O `chatStorage.ts` tinha `getTranscripts`/`saveTranscripts` — que servem para a
TRANSCRICAO DE VOZ do Charon — mas NUNCA teve `getMessages`/`saveMessages`.
Ou seja: as mensagens do chat do Jarvis nao eram gravadas em lugar nenhum. A
conversa era criada e batizada com o texto da primeira mensagem, mas o CONTEUDO
se perdia. Nao havia historico para mostrar porque ele nunca foi salvo.

SEGUNDO DEFEITO: CORRIDA ENTRE CARREGAR E SALVAR
Os dois useEffects (carregar e salvar) dependem de `activeConvId`. Ao trocar de
conversa, ambos rodam no MESMO commit — e o de salvar ainda enxerga as mensagens
da conversa ANTERIOR (o estado so muda no render seguinte). Resultado: abrir uma
conversa GRAVAVA nela o conteudo da anterior, destruindo o historico que o
usuario tinha acabado de abrir.

Terceiro pedido: "colocar um download no historico para salvar o estudo ou
pesquisa".

Roda OFFLINE.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
STORAGE = RAIZ / "frontend" / "src" / "components" / "saas" / "chatStorage.ts"
JARVIS = RAIZ / "frontend" / "src" / "components" / "saas" / "JarvisPage.tsx"

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


storage = STORAGE.read_text(encoding="utf-8")
jarvis = JARVIS.read_text(encoding="utf-8")

print("=== 1. As mensagens do chat agora sao persistidas ===")
check("export function getMessages" in storage,
      "existe getMessages() no chatStorage",
      "nao existe getMessages — o chat continua sem historico")
check("export function saveMessages" in storage,
      "existe saveMessages() no chatStorage",
      "nao existe saveMessages — as mensagens continuam sendo perdidas")
check("messages_${convId}" in storage,
      "as mensagens sao gravadas por conversa (chave propria)",
      "as mensagens nao usam chave por conversa (uma sobrescreveria a outra)")
check("getMessages, saveMessages" in jarvis,
      "o JarvisPage importa as funcoes novas",
      "o JarvisPage nao usa getMessages/saveMessages")
check("saveMessages(activeConvId" in jarvis,
      "o JarvisPage grava as mensagens ao mudarem",
      "o JarvisPage nunca grava as mensagens")
check("getMessages(activeConvId)" in jarvis,
      "o JarvisPage restaura as mensagens ao trocar de conversa",
      "o JarvisPage nao restaura nada ao trocar de conversa")

print()
print("=== 2. A corrida entre carregar e salvar esta travada ===")
check("carregandoConversaRef" in jarvis,
      "existe a trava `carregandoConversaRef`",
      "sem a trava, abrir uma conversa grava nela o conteudo da anterior")
m = re.search(r"if \(carregandoConversaRef\.current\) return;", jarvis)
check(m is not None,
      "o efeito de SALVAR respeita a trava",
      "a trava existe mas o efeito de salvar nao a consulta — a corrida continua")

# A trava precisa ser liberada, senao nada mais e salvo
check("carregandoConversaRef.current = false" in jarvis,
      "a trava e liberada depois do carregamento",
      "a trava nunca e liberada — o historico pararia de salvar para sempre")

# Precisa ser REF (vale no mesmo commit), nao estado
check(re.search(r"const carregandoConversaRef = useRef\(", jarvis) is not None,
      "a trava e um useRef (vale no mesmo commit, nao so no proximo render)",
      "a trava nao e useRef — um useState so valeria no render seguinte, tarde demais")

print()
print("=== 3. Exportar / baixar a conversa ===")
check("export function conversationToMarkdown" in storage,
      "existe conversationToMarkdown()",
      "nao ha como gerar o texto da conversa para exportar")
check("export function baixarTexto" in storage,
      "existe baixarTexto() (dispara o download)",
      "nao ha funcao de download")
check("a.download" in storage,
      "o download usa o atributo `download` (nao abre em nova aba)",
      "o download nao esta configurado")
# Nome de arquivo seguro: Windows proibe < > : " / \ | ? *
check("replace(/[^A-Za-z0-9._-]+/g" in storage,
      "o nome do arquivo e sanitizado (Windows proibe : ? * < > | \" / \\)",
      "o nome do arquivo nao e sanitizado — pode falhar ao salvar no Windows")
check("normalize('NFD')" in storage,
      "acentos sao removidos do nome do arquivo",
      "nome com acento pode falhar no Windows")

check("conversationToMarkdown(activeConvId" in jarvis,
      "o botao de download usa a conversa ativa",
      "o botao nao esta ligado a conversa ativa")
check("baixarTexto(" in jarvis,
      "o botao de download chama baixarTexto",
      "o botao nao dispara o download")
check("Baixar esta conversa" in jarvis,
      "o botao tem titulo explicativo",
      "o botao nao explica o que faz")

# O formato exportado precisa ser util: titulo, quem falou, horario e o texto.
# (procurado SEM aspas: o codigo usa template literal com crase, nao string simples)
check("# ${nome" in storage and "## ${quem}" in storage,
      "o Markdown exportado tem titulo e um bloco por mensagem",
      "o Markdown exportado nao tem estrutura util")
check("getTranscripts(convId)" in storage,
      "a transcricao de voz entra como anexo quando existir",
      "a transcricao de voz do Charon nao entra no arquivo")

print()
print("=== 4. O Charon tem o mesmo defeito? (mesmo padrao de codigo) ===")
CHARON = RAIZ / "frontend" / "src" / "components" / "saas" / "CharonPage.tsx"
charon = CHARON.read_text(encoding="utf-8")
# No Charon, o que importa e a transcricao (nao ha "mensagens de chat"), e ela
# JA era salva. A verificacao e so para registrar a diferenca.
check("saveTranscripts(activeConvId" in charon,
      "o Charon salva a transcricao por conversa (ja funcionava)",
      "o Charon tambem nao salva nada")
check("getTranscripts(activeConvId)" in charon,
      "o Charon restaura a transcricao ao trocar de conversa",
      "o Charon nao restaura a transcricao")

print()
print("=== 5. Workspaces (raiz) no historico ===")
# Pedido: "queria que o historico tivesse um Workspaces estilo raiz igual aqui no
# dsh, mas sem atrapalhar o visual do painel, tem que ser discreto".
check("workspace?: string" in storage,
      "a conversa tem o campo `workspace` (opcional, para nao quebrar as antigas)",
      "nao existe o campo workspace — nao ha como agrupar")
check("workspace?" in storage and "WORKSPACE_PADRAO" in storage,
      "ha um workspace padrao para conversas sem raiz definida",
      "conversa sem workspace ficaria orfa, fora de qualquer grupo")
check("export function getWorkspaces" in storage,
      "existe getWorkspaces()",
      "nao ha como listar as raizes")
check("export function setConversationWorkspace" in storage,
      "existe setConversationWorkspace()",
      "nao ha como mover uma conversa de raiz")
check("workspace" in re.search(r"export function createConversation\([^)]*\)", storage).group(0),
      "createConversation aceita o workspace",
      "conversa nova nao pode nascer numa raiz")

check("getWorkspaces, setConversationWorkspace, WORKSPACE_PADRAO" in jarvis,
      "o JarvisPage importa as funcoes de workspace",
      "o JarvisPage nao usa o recurso")
check("workspaceAtivo" in jarvis, "existe o estado `workspaceAtivo`",
      "nao ha workspace ativo na tela")
check("jarvis_workspace" in jarvis,
      "o workspace ativo e lembrado entre sessoes (localStorage)",
      "o workspace ativo se perde ao recarregar")
# Discreto: precisa ser um chip pequeno, nao um painel
m_chip = re.search(r"Workspace atual: \$\{workspaceAtivo\}", jarvis)
check(m_chip is not None, "o chip tem tooltip explicando", "o chip nao explica o que faz")
# Discreto: o estilo do chip vem logo depois do tooltip e precisa usar fonte
# pequena. (Procurar numa janela fixa a partir do tooltip e mais preciso do que
# partir o arquivo por uma palavra.)
trecho_chip = jarvis[m_chip.start():m_chip.start() + 700] if m_chip else ""
check("fontSize: 9" in trecho_chip,
      "o chip usa fonte pequena (discreto, como pedido)",
      f"o chip nao usa fonte pequena — estilo encontrado: {trecho_chip[:200]!r}")
# Agrupamento na lista
check("conversations.filter(c => (c.workspace || WORKSPACE_PADRAO) === ws)" in jarvis,
      "a lista agrupa as conversas por workspace",
      "a lista continua solida, sem agrupamento")
check("ws.toUpperCase()" in jarvis,
      "o cabecalho da raiz e discreto (caixa alta, cinza)",
      "o cabecalho da raiz nao segue o padrao discreto")
# Conversa nova precisa herdar a raiz ativa
check("createConversation(undefined, workspaceAtivo)" in jarvis,
      "conversa nova nasce no workspace ativo",
      "conversa nova cai sempre na raiz padrao")

print()
print("=== 6. Abrir o Jarvis deve comecar LIMPO ===")
# BUG RELATADO: "quando eu limpo o cache e entro novamente no jarvis ele deveria
# comecar com uma conversa limpa mas ele tras a conversa anterior automaticamente"
#
# O estado inicial era `convs[0]?.id` — o Jarvis adotava a conversa MAIS RECENTE
# ao abrir e carregava as mensagens dela.
m_init = re.search(r"const \[activeConvId, setActiveConvId\] = useState<string>\(([^;]*)\);", jarvis, re.S)
inicial = m_init.group(1) if m_init else ""
check("getConversations" not in inicial,
      "o estado inicial NAO busca a conversa mais recente",
      f"o Jarvis ainda abre na conversa anterior: {inicial.strip()[:90]!r}")
check("''" in inicial or '""' in inicial,
      "o estado inicial e vazio (sessao limpa)",
      f"o estado inicial nao esta vazio: {inicial.strip()[:90]!r}")

# Mas a conversa PRECISA ser criada na primeira mensagem, senao o historico
# nunca existiria (o efeito de salvar exige um activeConvId).
m_send = re.search(r"const handleSendMessageDirect = async \(text: string\) => \{(.*?)\n  \};", jarvis, re.S)
corpo_send = m_send.group(1) if m_send else ""
check(bool(corpo_send), "isolei o corpo do envio de mensagem", "nao achei handleSendMessageDirect")
check("if (!activeConvId)" in corpo_send and "createConversation(text.trim(), workspaceAtivo)" in corpo_send,
      "a primeira mensagem CRIA a conversa (no workspace ativo)",
      "sem isto, abrir limpo significaria nunca salvar nada")

# E a criacao nao pode apagar a mensagem recem-enviada (a corrida de novo)
check("pularCarregamentoRef.current = conv.id" in corpo_send,
      "a criacao avisa o efeito de carregar para nao mexer nas mensagens",
      "a troca dispararia o carregamento e apagaria a mensagem do usuario")
check(re.search(r"if \(pularCarregamentoRef\.current === activeConvId\)", jarvis) is not None,
      "o efeito de carregar respeita esse aviso",
      "o aviso existe mas o carregar nao o consulta")
check(re.search(r"pularCarregamentoRef\.current = null", jarvis) is not None,
      "o aviso e consumido uma unica vez (nao vale para sempre)",
      "o aviso nunca e limpo — trocar de conversa depois nao carregaria nada")

print()
print("=== 7. O menu explica o mecanismo (queixa: 'confuso de entender') ===")
# "+" (esquerda) e workspace (direita) pareciam se anular. A explicacao fica
# dentro da propria lista, onde a duvida acontece.
check("abre uma conversa" in jarvis and "escolhe o" in jarvis,
      "a lista explica o que o '+' e o workspace fazem",
      "a lista nao explica o mecanismo — o usuario continua sem entender")
check("independentes" in jarvis,
      "deixa explicito que as duas coisas sao independentes",
      "nao fica claro que trocar de workspace nao apaga conversa")
check("restaura" in jarvis,
      "explica que clicar numa conversa RESTAURA ela",
      "nao explica que clicar restaura a conversa")
check("nao apaga nenhuma conversa do historico" in jarvis,
      "o '+' avisa que criar conversa nova nao apaga nada",
      "o '+' nao avisa que nao apaga o historico")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — historico salvo, restaurado e exportavel")
