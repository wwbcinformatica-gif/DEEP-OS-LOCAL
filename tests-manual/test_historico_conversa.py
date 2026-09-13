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
CHARON = RAIZ / "frontend" / "src" / "components" / "saas" / "CharonPage.tsx"

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


storage = STORAGE.read_text(encoding="utf-8")
jarvis = JARVIS.read_text(encoding="utf-8")
charon = CHARON.read_text(encoding="utf-8")

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
# Discreto: o chip na barra foi REMOVIDO (ver secao 10) — quem cuida da criacao
# de raiz agora e o "+" do cabecalho da arvore. Aqui so verificamos que a arvore
# tem esse ponto unico.
check('title="Criar uma nova pasta (raiz) para organizar conversas"' in jarvis,
      "a arvore tem o botao de criar raiz (ponto unico, rotulado)",
      "nao ha botao de criar raiz na arvore")
# Agrupamento na lista
check("conversations.filter(c => (c.workspace || WORKSPACE_PADRAO) === ws)" in jarvis,
      "a lista agrupa as conversas por workspace",
      "a lista continua solida, sem agrupamento")
check("ws.toUpperCase()" not in jarvis,
      "o nome da raiz aparece como o usuario digitou (nao gritado em caixa alta)",
      "o nome do workspace e forcado para caixa alta")
check("fontSize: 10, color: ws === workspaceAtivo" in jarvis,
      "a raiz tem estilo discreto (fonte pequena, cinza quando inativa)",
      "a raiz nao segue o padrao discreto")
# Conversa nova precisa herdar a raiz ativa
# O 3o argumento (nome do assistente) e opcional; o que importa aqui e a raiz.
check("createConversation(undefined, workspaceAtivo" in jarvis,
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
check("if (!activeConvId)" in corpo_send and "createConversation(text.trim(), workspaceAtivo" in corpo_send,
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
print("=== 7. Arvore do historico (explorer estilo VS Code) ===")
# Pedido: "no sidebar abaixo do menu jarvis aparecer como se fosse uma raiz
# explorer com os workspaces e em seguida uma setinha para expandir todos os
# historicos e do lado de cada historico tres pontos quando clicar poder
# renomear ou deletar, deixar mais completo".
#
# Antes era um dropdown que abria e fechava (sumia a cada clique). A lista que
# existia DENTRO do dropdown foi removida: manter as duas confundia.
check("wsExpandidos" in jarvis,
      "a arvore guarda quais workspaces estao expandidos",
      "nao ha estado de expansao — a setinha nao funcionaria")
check("u25BE" in jarvis and "u25B8" in jarvis,
      "a raiz usa seta de expandir",
      "a raiz nao tem seta de expandir")
check("menuConversa" in jarvis,
      "cada conversa tem estado de menu aberto",
      "nao ha menu por conversa")
check("u22EF" in jarvis,
      "o botao de opcoes e o de tres pontos",
      "nao ha botao de tres pontos")
check("Renomear" in jarvis, "o menu da conversa permite Renomear",
      "nao da para renomear pela arvore")
check("Excluir" in jarvis, "o menu da conversa permite Excluir",
      "nao da para excluir pela arvore")
check("Baixar" in jarvis, "o menu da conversa permite Baixar",
      "nao da para baixar pela arvore")
check("vive na arvore (explorer) acima" in jarvis,
      "a lista duplicada do dropdown foi removida (evita confusao)",
      "a conversa aparece em dois lugares com acoes diferentes")

print()
print("=== 7.1 O Charon tem a MESMA arvore + download da sessao ===")
CHARON = RAIZ / "frontend" / "src" / "components" / "saas" / "CharonPage.tsx"
charon = CHARON.read_text(encoding="utf-8")
check("wsExpandidos" in charon, "o Charon tem a arvore expandivel",
      "o Charon nao tem a arvore")
check("menuConversa" in charon, "o Charon tem o menu por sessao",
      "o Charon nao tem o menu por sessao")
check("Baixar sessao" in charon,
      "o Charon permite BAIXAR a sessao",
      "o Charon nao permite baixar a sessao")
check("conversationToMarkdown" in charon,
      "o download da sessao usa o mesmo exportador",
      "o download nao usa o exportador de Markdown")
check("workspaceAtivo" in charon,
      "o Charon agrupa as sessoes por workspace",
      "o Charon nao agrupa por workspace")
check("charon_workspace" in charon,
      "o workspace do Charon e lembrado entre sessoes",
      "o workspace do Charon se perde ao recarregar")

# O exportador precisa funcionar para SESSAO DE VOZ (sem mensagens de chat)
m_exp = re.search(r"export function conversationToMarkdown\(.*?\n\}", storage, re.S)
corpo_exp = m_exp.group(0) if m_exp else ""
check("msgs.length === 0 && transcricoes.length === 0" in corpo_exp,
      "o exportador aceita conversa SO com transcricao (caso do Charon)",
      "exige mensagens de chat — o download da sessao do Charon falharia sempre")
check("Transcricao de voz (Charon)" in corpo_exp,
      "a transcricao entra com titulo proprio no arquivo",
      "a transcricao nao e identificada no arquivo")

print()
print("=== 8. Limpar tudo: local + servidor (com as travas certas) ===")
# Pedido: "todos os contexto de teste nao e relevante, pode deixar tudo limpo
# para criar os historicos do zero".
storage = STORAGE.read_text(encoding="utf-8")
janela = jarvis

check("export function limparHistoricoLocal" in storage,
      "existe limparHistoricoLocal()", "nao ha como limpar as conversas locais")
# NAO pode usar localStorage.clear(): apagaria token, chave de API, voz e tema
m_limp = re.search(r"export function limparHistoricoLocal\(\): number \{(.*?)\n\}", storage, re.S)
corpo_limp = m_limp.group(1) if m_limp else ""
check("localStorage.clear" not in corpo_limp,
      "NAO usa localStorage.clear() (preserva token, chave, voz e tema)",
      "usa localStorage.clear() — deslogaria o usuario e perderia configuracoes")
check("messages_" in corpo_limp and "transcripts_" in corpo_limp and "activity_" in corpo_limp,
      "remove as chaves de conversa (mensagens, transcricoes, atividade)",
      "nao remove todas as chaves de conversa, ou remove de menos")

# O endpoint do servidor precisa ser alcancavel pelo nginx
BACKEND = RAIZ / "backend"
HIST = BACKEND / "routes" / "history.py"
SEG = BACKEND / "middleware" / "security.py"
hist = HIST.read_text(encoding="utf-8")
seg = SEG.read_text(encoding="utf-8")

check('@router.delete("/api/history")' in hist,
      "existe DELETE /api/history (alcancavel pelo nginx)",
      "so existe /history, que o nginx NAO encaminha — cairia no HTML do frontend")
check('"/api/history"' in seg,
      "a rota destrutiva esta protegida pelo middleware",
      "/api/history NAO esta em PREFIXOS_PROTEGIDOS — qualquer um apagaria o historico")
check("fetch('/api/history'" in janela,
      "o frontend chama /api/history (e nao /history)",
      "o frontend chama um caminho que o nginx nao encaminha — falso sucesso")

# A verificacao de que a resposta veio do backend
check("j.status === 'ok'" in janela,
      "o frontend confirma que a resposta veio do BACKEND",
      "sem confirmar o JSON, um HTML do nginx (200) seria lido como sucesso")
check("NAO confirmou a limpeza" in janela,
      "ha mensagem clara quando a limpeza nao e confirmada",
      "o usuario nao saberia que o contexto antigo continua ativo")

# Precisa de confirmacao antes de apagar (acao irreversivel)
check("Apagar TODAS as conversas?" in janela,
      "pede confirmacao antes de apagar (acao irreversivel)",
      "apaga sem confirmar")
check("NAO remove: sua conta" in janela,
      "a confirmacao explica o que NAO e removido",
      "a confirmacao nao tranquiliza sobre o que fica")

print()
print("=== 9. Charon: a corrida que APAGAVA o historico ===")
# BUG RELATADO: "quando clica no historico aparece 'Restaurando contexto: 300
# falas desta conversa' mas nunca restaura o historico no painel central".
#
# O carregar e o salvar dependem os dois de `activeConvId` e rodam no MESMO
# commit — quando o estado `transcripts` ainda e o anterior (vazio, na primeira
# montagem). O salvar gravava esse vazio POR CIMA da conversa. Nao era so um
# problema de exibicao: o dado ia embora.
check("carregandoConversaRef" in charon,
      "o Charon TEM a trava de carregamento (o Jarvis ja tinha)",
      "o Charon nao tem a trava — a corrida apaga o historico")
m_save = re.search(r"if \(activeConvId\) \{\s*(?://[^\n]*\n\s*)*if \(carregandoConversaRef\.current\) return;", charon)
check(m_save is not None,
      "o efeito de SALVAR do Charon respeita a trava",
      "a trava existe mas o salvar nao a consulta — continua gravando vazio")
check("carregandoConversaRef.current = false" in charon,
      "a trava do Charon e liberada",
      "a trava nunca e liberada — o Charon pararia de salvar")
check(re.search(r"const carregandoConversaRef = useRef\(", charon) is not None,
      "a trava do Charon e useRef (vale no mesmo commit)",
      "a trava nao e useRef — so valeria no render seguinte, tarde demais")

# Abrir o Charon tambem deve ser sessao nova (mesma regra do Jarvis), o que
# ainda reduz a superficie do bug (nao adota a conversa mais recente sozinho).
m_init_c = re.search(r"const \[activeConvId, setActiveConvId\] = useState<string>\(\(\) => \{(.*?)\n  \}\);", charon, re.S)
init_c = m_init_c.group(1) if m_init_c else ""
check("convs[0]?.id" not in init_c,
      "o Charon NAO adota a conversa mais recente ao abrir",
      "o Charon ainda abre na conversa anterior")
check("migrateLegacyData()" in init_c,
      "a migracao de dados antigos continua rodando",
      "a migracao foi removida junto — dados antigos ficariam sem migrar")

print()
print("=== 10. Um lugar so para criar workspace ===")
# O usuario viu DOIS workspaces ("Geral" e o que ele criou) e um campo "nova
# raiz" repetido: o chip da barra criava raiz num lugar e a arvore noutro.
check("O CHIP DE WORKSPACE FOI REMOVIDO" in jarvis,
      "o chip de workspace saiu da barra (ficou so a arvore)",
      "o chip continua na barra — dois lugares criando raiz")
check("Workspace atual:" not in jarvis,
      "o seletor de workspace duplicado foi removido",
      "ainda existe o seletor de workspace na barra")
check('title="Criar uma nova pasta (raiz) para organizar conversas"' in jarvis,
      "ha UM lugar para criar raiz (o botao do cabecalho da arvore)",
      "nao ha botao unico de criar raiz")
# E os dois botoes de "+" precisam ser distinguiveis: um cria CONVERSA, outro
# cria PASTA. O usuario viu os dois na tela e perguntou qual usar.
check("+ pasta" in jarvis,
      "o botao de pasta se distingue do de conversa",
      "dois '+' iguais lado a lado: o usuario tem de adivinhar")

# getWorkspaces nao pode forcar 'Geral' quando ha raizes em uso
m_ws = re.search(r"export function getWorkspaces\(\): string\[\] \{(.*?)\n\}", storage, re.S)
corpo_ws = m_ws.group(1) if m_ws else ""
check("new Set<string>([WORKSPACE_PADRAO])" not in corpo_ws,
      "getWorkspaces NAO forca 'Geral' sempre",
      "getWorkspaces ainda adiciona 'Geral' sempre — aparecem duas raizes")
check("usados.size === 0" in corpo_ws,
      "'Geral' so aparece quando esta em uso (ou quando nao ha nada)",
      "a regra de quando mostrar 'Geral' nao esta clara")

print()
print("=== 11. Download da sessao do Charon: os DOIS paineis ===")
# Pedido: "ao clicar em baixar ele baixa a secao do painel direito aquele que as
# mensagens segue empilhada; eu quero o contexto do painel central tambem, ou
# ele baixar as duas".
#
# Painel direito  = transcricao de voz (transcripts)
# Painel central  = atividades (ferramentas, buscas e o trabalho entregue)
m_exp = re.search(r"export function conversationToMarkdown\(.*?\n\}", storage, re.S)
corpo_exp = m_exp.group(0) if m_exp else ""
check(bool(corpo_exp), "isolei conversationToMarkdown", "nao achei a funcao")
check("getActivityLog(convId)" in corpo_exp,
      "o export inclui o painel CENTRAL (atividades)",
      "o painel central continua de fora do download — era a queixa")
check("atividades.length > 0" in corpo_exp,
      "as atividades sao escritas quando existem",
      "as atividades nao entram no arquivo")
check("getTranscripts(convId)" in corpo_exp,
      "o export inclui o painel direito (transcricao)",
      "a transcricao saiu do export")
check("painel central" in corpo_exp and "painel direito" in corpo_exp,
      "o arquivo identifica de qual painel cada secao veio",
      "as secoes nao estao identificadas — fica confuso ao estudar")

# ── NAO MEXER NO FORMATO EMPILHADO ──────────────────────────────────────────
# O usuario: "é neste formato que funcionou empilhando as conversas, passamos
# varios dias para descobrir que assim empilhado é melhor, não mexa neste
# formato". Eu havia juntado os pedacos por conta propria — inferencia minha,
# nao pedido dele. Este teste impede que a juncao volte.
check("juntarPedacosDeTranscricao" not in storage,
      "NAO existe juncao de pedacos no chatStorage",
      "a juncao voltou — o usuario pediu para NAO mexer no formato empilhado")
check("empilharTranscript" not in charon,
      "o Charon volta a EMPILHAR cada pedaco (formato validado pelo usuario)",
      "o Charon esta juntando os pedacos — formato que o usuario quer preservado")
check("setTranscripts(prev => [...prev, { speaker: 'user', text, time: now() }])" in charon,
      "o pedaco do usuario e acrescentado como entrada propria",
      "o append simples do usuario nao esta no formato original")
check("setTranscripts(prev => [...prev, { speaker: 'charon', text, time: now() }])" in charon,
      "o pedaco do Charon e acrescentado como entrada propria",
      "o append simples do Charon nao esta no formato original")
check("NAO JUNTAR OS PEDACOS" in charon and "NAO JUNTAR OS PEDACOS" in storage,
      "ha aviso nos DOIS arquivos para nao juntar de novo",
      "falta o aviso — alguem pode 'melhorar' isso outra vez")

print()
print("=== 12. Recado de status vai para o painel DIREITO, nao o central ===")
# Pedido: "estes retornos -> SYSTEM - 19:33:08 Interrompido (voce falou) -
# ouvindo voce; nao seria necessario entregar no painel central. se quiser pode
# deixar esse retorno no painel direito".
#
# Segue a divisao que o usuario definiu: o painel central e para a ENTREGA
# ORGANIZADA (ferramentas, buscas, resultados). Status ali e ruido.
check("addActivity(`Interrompido" not in charon,
      "a interrupcao NAO vai mais para o log de atividades (painel central)",
      "a interrupcao ainda aparece no painel central")
check("speaker: 'sistema', text: `Interrompido" in charon,
      "a interrupcao vai para a transcricao (painel direito)",
      "a interrupcao nao foi para o painel direito")
check("t.speaker === 'sistema'" in charon,
      "a renderizacao do painel direito trata o falante 'sistema'",
      "sem tratamento, a nota apareceria como se fosse fala do Charon")
check("'Sistema'" in charon,
      "a nota de sistema aparece rotulada como 'Sistema' (nao 'Charon')",
      "a nota de sistema nao tem rotulo proprio no painel direito")
check("t.speaker === 'system' ? 'Sistema'" in storage or "t.speaker === 'sistema' ? 'Sistema'" in storage,
      "o export rotula a nota de sistema corretamente",
      "no arquivo exportado a nota apareceria como fala do Charon")

# Os outros avisos de 'system' continuam no central — nao foram movidos sem
# pedido (o usuario apontou especificamente a interrupcao).
check("addActivity('Microfone pausado pelo navegador" in charon,
      "os avisos de microfone continuam no painel central (nao mexidos)",
      "os avisos de microfone foram movidos sem pedido")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — historico salvo, restaurado e exportavel")
