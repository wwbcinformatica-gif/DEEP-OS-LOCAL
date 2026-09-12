# DEEP-OS — Status do Projeto

**Ultima atualizacao:** 2026-09-12 (Sessao 50) - ver `docs/CONTINUAR.md` para o estado atual e o que falta

**Commit em producao:** (confira - ver `docs/CONTINUAR.md` secao 1) | **Backend:** `deepos-backend.service` (active) | **Site:** https://deep-os.tech

**Leia primeiro:** [`memory.md`](memory.md) (regras e armadilhas do projeto),
[`docs/CONTINUAR.md`](docs/CONTINUAR.md) (handoff: estado, pendências e armadilhas),
[`docs/PROVEDORES.md`](docs/PROVEDORES.md) (provedores comuns e como criar os seus),
[`docs/MODELOS.md`](docs/MODELOS.md) (por que os modelos davam 404 e como testar),
[`docs/CHARON-VOZ.md`](docs/CHARON-VOZ.md) (arquitetura da voz — a parte mais
complexa do sistema) e [`RECUPERAR-VPS.md`](RECUPERAR-VPS.md) (procedimento de
emergencia do servidor).

---

## Sessao 2026-09-12 (50) — Charon: `<ctrl46>`, escolha de contexto e sessão nomeada

### Resumo
Três queixas do usuário, todas no Charon (a voz):

1. *"tem hora que charon para de responder, não é sempre, mas às vezes fica
   assim -> `<ctrl46>` ... e não retorna"*
2. *"eu escolho do lado direito no workspace novo chat ou clico em algum
   histórico registrado ... não faz nenhuma das duas até eu escolher"*
3. *"se pudesse colocar a sessão com o nome da voz do assistente que foi
   selecionada seria bom"*

Resultado: correções no backend de voz (filtro + recuperação de turno morto),
mudança de fluxo na tela do Charon (o usuário escolhe o contexto) e sessões
nomeadas pelo campo **NOME DO ASSISTENTE** (Configurações → Identidade).
Suíte: **20/20 passando**.

### 1. `<ctrl46>` — o turno que nasce morto

`<ctrl46>` **não é texto do DEEP-OS**. É um *token de controle* interno do Gemini
(a família `<ctrlN>`) que, nos modelos Live *preview*, às vezes **vaza como
texto** na `output_transcription` quando a geração degenera. O turno fechava com
**zero voz e zero texto real** — e, como **não havia erro nenhum**, nada disparava
a reconexão automática: o Charon ficava **mudo para sempre**.

Correção em `backend/routes/voice_ws.py`:

- `_TOKEN_CONTROLE` + `_limpar_tokens_controle()` — o token é filtrado e não
  chega mais ao painel;
- contadores de saúde **por turno** + `_iniciar_turno()`;
- `_fechar_turno()` — turno vazio é falha: na **1ª** pede a resposta de novo
  (`_recuperar_turno('pedir_de_novo')`), na **2ª seguida** reabre a sessão
  (`_recuperar_turno('reconectar')`, com `restaurar_contexto=True`);
- **barge-in não conta como falha** (turno interrompido fecha sem áudio de
  propósito).

**Bug sério achado de quebra:** `_reconnect()` montava a instrução do sistema
**só com a voz** — sem fuso, idioma e **sem as instruções personalizadas** (de
onde vem o nome do usuário). Ou seja: **toda reconexão fazia o Charon esquecer
quem era o usuário**.

### 2. O Charon não inicia sozinho — o usuário escolhe o contexto

Antes, ao abrir a página o Charon **ligava sozinho** (timer de 1 s + listener do
primeiro gesto) e cumprimentava. Agora:

- **auto-start removido**;
- `modoInicio: 'escolher' | 'novo' | 'historico'` — abre em **`'escolher'`** e
  **nada** acontece até o usuário decidir;
- **`+ Novo chat`** (explícito, no topo da árvore): sessão nova, conecta
  sozinho, sem histórico → o backend **cumprimenta**;
- **clique numa sessão da árvore**: carrega `getTranscripts(convId)`, manda como
  `history` e **reconecta** → o backend reenvia o contexto e **pergunta de onde
  continuar** (o gatilho de retomada foi reescrito para terminar com pergunta);
- `entrarNaConversa()` centraliza "trocar contexto = reconectar".

### 3. Sessão com o nome do assistente

`createConversation()` ganhou o 3º parâmetro opcional (`nomePadrao`) e
`nomeUnico()` numera quando repete ("Charon", "Charon 2"). O nome vem de
**Configurações → Identidade → NOME DO ASSISTENTE**. Vale para o Charon **e**
para o Jarvis (cada um lê a identidade do tenant).

### 4. Correções menores

- `CharonPage.tsx` tinha um `interface TranscriptEntry` **local** sombreando o
  tipo do `chatStorage` → erro `TS2440`; removido (**um lugar só**).
- O aviso "Interrompido (voce falou)" saiu do **painel central** e foi para o
  painel **direito** (transcrição), como o usuário pediu — o central é para a
  entrega organizada.
- `STATUS.md` tinha **um byte inválido** (0x97) que impedia até de abrir o
  arquivo; corrigido (backup em `backup-docs/`).

---

## Sessao 2026-09-12 (49) — Chaves de API, modelos que davam 404 e Charon

### Resumo
Três queixas do usuário, todas com causa real — e **cada uma com bugs somados**
em que um escondia o outro:

1. *"ao trocar a chave api de um dos provedores não estava alterando o `.env`"*
2. *"quase todos os modelos davam erro 404 e, quando eu selecionava o provedor,
   não carregava todos de cada provedor"*
3. *"o Charon não para o que está falando para ouvir o usuário"* + *"a saudação
   inicial fala muita coisa sobre o sistema"*

Resultado: 9 correções de código, 3 testes novos (15 arquivos na suíte, todos
passando) e 6 ferramentas de diagnóstico em `tools/`. Além disso, descobrimos que
**5 das suas chaves/contas precisam de ação** — não é bug do código (seção 5).

---

### 1. Bug da chave de API — causa raiz

**Sintoma:** trocar a chave de um provedor não mudava o `backend/.env`.

Eram **dois** problemas, e o segundo escondia o primeiro.

**(a) O placeholder sobrescrevia a chave real.**
O `JarvisPage.tsx` marcava as chaves já salvas com o texto literal
`'***saved***'` no estado **e no `localStorage`**, e o botão Salvar montava o
payload com **todos** os provedores. Ao salvar a chave de um, o marcador dos
outros ia junto — e o backend gravava `'***saved***'` no `.env`, **destruindo a
chave verdadeira**. A tela dizia "salvo" e a chave parava de funcionar.

**(b) O erro era engolido — e o 401 também.**
As rotas `/api/config*` são protegidas pelo middleware `ProtecaoSensiveis`, que
libera apenas quando o header `Host` é local:

| Ambiente | Host | Resultado |
|----------|------|-----------|
| Local (`start-saas.bat`) | `localhost` | liberado — **por isso o teste local nunca mostrou o erro** |
| Produção (`deep-os.tech` via nginx) | externo | exige JWT |

As chamadas não mandavam `Authorization` → **401 na VPS**. E o
`.catch(() => {})` engolia, deixando a tela dizer *"chave salva no servidor"* sem
ter salvado nada.

**Correção:**
- `SENTINELA_CHAVE_SALVA` + `ehSentinela()`; o marcador **não vai mais** para o
  `localStorage`; Salvar envia **só** o provedor ativo; guarda que recusa enviar
  o marcador.
- Novo helper `authHeaders()` com o JWT em todas as chamadas de `/api/config*`
  e `/api/instances`.
- Fim do `.catch(() => {})`: agora o usuário vê o motivo real (`401 → "sessão
  expirada"`, `recusados` do backend, etc.).
- **Defesa em profundidade no backend:** `_PLACEHOLDERS_INVALIDOS` +
  `_chave_valida()`. `PUT /api-key` recusa com **HTTP 400**; `PUT /api-keys`
  ignora os inválidos e devolve `recusados` + `aviso`.

**Detalhe que quase passou:** o `raise HTTPException(400)` estava **dentro** do
`try/except Exception`, então viraria **500** — escondendo a causa. Corrigido com
`except HTTPException: raise`.

**Teste:** `tests-manual/test_api_keys.py` — 32 verificações, incluindo o cenário
exato do bug (salvar Groq sem destruir Gemini/OpenRouter), a checagem de que o
`.env` não recebe o marcador, e chamadas aos **endpoints reais** confirmando que
o 400 não vira 500. Faz backup/restore do `.env` e confirma que as chaves do
usuário ficaram intactas.

---

### 2. Bug dos modelos — quatro problemas somados

**(a) IDs extintos.** 9+ confirmados, ex.: `llama-3.3-70b-versatile` e
`llama-3.1-8b-instant` (sumiram da Groq), `gemini-1.5-*` e `gemini-2.0-flash`
(removidos pelo Google), `anthropic/claude-3.5-sonnet` (OpenRouter),
`minimaxai/minimax-m2.7` (nunca existiu na Groq).

**(b) Listas divergentes.** `constants.ts` usava `nvidia/llama-...` e
`JarvisPage.tsx` usava sem prefixo. Como o prefixo **é obrigatório** (seção 4),
um dos dois estava necessariamente quebrado.

**(c) `zhipu` invisível.** Tinha lista de modelos em `MODELS` mas **não estava**
no array `PROVIDERS` — o provedor nunca aparecia no seletor.

**(d) Lista dinâmica sem cancelamento.** Ao trocar de Ollama para Groq, a
requisição do Ollama continuava em voo e, ao responder, **sobrescrevia** a lista
do Groq. O seletor mostrava os modelos do provedor errado → 404. Também havia o
`dynamicModels.length > 0 ? dynamicModels : provider.models`, que dava prioridade
à lista dinâmica mesmo com outro provedor selecionado.

**Correção:**
- Listas reescritas **só com modelos provados** por chamada real.
- `authHeaders()` + guarda de cancelamento (`let ativo`) no `useEffect`.
- `modelosDisponiveis` derivado do **provedor ativo**, não do que estiver na
  memória.
- Trocar de provedor redefine o modelo (antes o `<select>` ficava em branco).
- `zhipu` adicionado a `PROVIDERS`.
- IDs extintos corrigidos **também** em `InstancesPage.tsx`, `ChatBotPage.tsx`,
  `backend/core/config.py` (`MODEL_ROUTING.analysis`) e
  `backend/routes/chatbot.py` (defaults).

**Teste:** `tests-manual/test_model_lists.py` — offline, garante coerência entre
os arquivos, ausência dos 41 IDs extintos conhecidos e o prefixo obrigatório da
NVIDIA.

> **Nota sobre o teste:** ele acusou dois falsos positivos no começo (parseava os
> modelos do provedor seguinte quando a lista era vazia, e lia as próprias
> mensagens de comentário como se fossem código). O teste foi corrigido — vale
> registrar porque "o teste falhou" nem sempre significa "o código está errado".

---

### 3. A armadilha central: `/models` MENTE

A descoberta mais importante da sessão:

**OpenRouter** — `/api/v1/models` é **público**:
```
GET /api/v1/models com chave FALSA -> HTTP 200 (445 modelos)
GET /api/v1/key   com a chave real -> HTTP 401 "User not found."
```
A chave estava inválida e a lista continuava respondendo. Comparar IDs com o
`/models` "passava".

**NVIDIA** — lista modelos que a conta **não tem**:
```
/v1/models       -> lista nvidia/llama-3.1-nemotron-70b-instruct
chat/completions -> HTTP 404 "Function '9b96341b-...': Not found for account"
```

**Regra adotada:** só vale o que responde **HTTP 200 com texto de verdade**, e
todo teste inclui um **controle negativo** (modelo inexistente) — se ele passar,
o endpoint não é confiável (ver `tools/validar-opencode-real.cjs` e a pegadinha
do `api.opencode.ai`, que devolvia `200` com o corpo `Not Found` para **qualquer**
modelo, inclusive inexistente).

---

### 4. Correção de um commit anterior errado (prefixo NVIDIA)

O commit `a8527c4` ("remove nvidia/ prefix from NVIDIA model IDs") **estava
errado**. Medido com chamada real:
```
nvidia/nemotron-3-super-120b-a12b -> HTTP 200
nemotron-3-super-120b-a12b        -> HTTP 404
```
O prefixo faz parte do ID. Restaurado e revalidado modelo por modelo.

---

### 5. ⚠️ Chaves/contas que precisam da sua ação (NÃO é bug de código)

| Provedor | Resposta | Significado | Ação |
|----------|----------|-------------|------|
| **OpenRouter** | `401 User not found.` | chave inválida/revogada | gerar nova em <https://openrouter.ai/keys> |
| **OpenAI** | `401 Incorrect API key` | chave inválida | gerar nova em <https://platform.openai.com/api-keys> |
| **Zhipu (GLM)** | `429 余额不足或无可用资源包,请充值。` | *saldo insuficiente* | recarregar em <https://open.bigmodel.cn> |
| **MiMo** | `402 Insufficient account balance` | sem saldo | recarregar, ou usar `mimo.exe` local |
| **OpenCode** | `401 Insufficient balance` | sem saldo (endpoint correto) | recarregar em <https://opencode.ai/workspace> |
| **OpenClaude** | — | aponta para servidor **local** (`localhost:4000`) | rodar o servidor local |

**Funcionando:** Groq (7/7 modelos), Gemini (7), NVIDIA (8), Ollama local.
**Chaves válidas:** Groq ✅, Gemini ✅, NVIDIA ✅.

---

### 6. Ferramentas criadas em `tools/`

| Arquivo | Função |
|---------|--------|
| `diagnostico-chaves.cjs` | diz se cada chave é válida (endpoints próprios para validar credencial) |
| `provar-modelos.cjs` | prova cada modelo com chamada real → gera `modelos-provados.json` e `MODELOS-PROVADOS.md` |
| `modelos-atuais.cjs` | baixa as listas reais e compara com os IDs do código |
| `reteste-rede.cjs` | retesta o que falhou por rede (não confundir "servidor caiu" com "modelo não existe") |
| `validar-opencode-real.cjs` | confere se um endpoint responde de verdade (pega o `200 Not Found`) |
| `teste-nvidia-id.cjs` | prova que o prefixo da NVIDIA é obrigatório |

**Pegadinha de URL documentada:** Groq usa `/openai/v1`, OpenRouter usa `/api/v1`,
Zhipu usa `/api/paas/v4`. Errar isso produziu **uma sessão inteira de falsos
404** na primeira versão do script.

---

### 7. Charon: interrupção (barge-in) e saudação curta
Duas queixas do usuário sobre a voz:

**(a) "o Charon deve parar o que está falando para ouvir o usuário, depois
continua — essa função não está funcionando."**
Estava quebrada por **três motivos somados**:

1. **O backend ignorava `server_content.interrupted`** — o sinal do VAD do Gemini
   avisando "o usuário falou por cima". O áudio antigo continuava sendo repassado
   e o navegador nunca era avisado.
2. **Cada chunk do microfone fazia `_interrupted = False`.** Como o mic envia
   áudio a cada ~20–60 ms, a interrupção era desfeita no chunk seguinte. Era o
   bug mais grave e o mais difícil de ver — a linha parecia correta isolada.
3. **O frontend nunca enviava `type: 'interrupt'`** — o handler do backend era
   **código morto**. E não esvaziava a fila local: mesmo com o servidor calado,
   havia **segundos** de fala já baixada tocando no navegador. É isso que se
   percebe como "o Charon não para de falar".

**Correção em duas frentes:**

| Frente | Detecção | Ação |
|--------|----------|------|
| Navegador | nível do mic (`>0.06` por 3 chunks seguidos) | esvazia fila + ring, descarta áudio em trânsito por 400 ms, envia `interrupt` |
| Servidor | VAD do Gemini (`sc.interrupted`) | marca `_interrupted`, descarta a saída, envia `{"type":"interrupted"}` |

Quem libera a interrupção agora é o `turn_complete`, com **rede de segurança de
3 s** (`_interrupted_at`) para o Charon nunca ficar surdo para sempre.

**Bug extra que o teste comportamental revelou:** o `return` do portão de
interrupção vinha **antes** do tratamento de `input_transcription` — então **a
fala do usuário não era transcrita justamente quando ele interrompia**, que é o
momento em que a transcrição mais importa. Corrigido: a interrupção cala a
**saída**, não pode cegar a **entrada**.

**(b) "a saudação inicial fala muita coisa sobre o sistema; quero breve, tipo
'Ola Wilson eu sou Charon o que gostaria de fazer agora'."**
O gatilho era um convite aberto: `"Se apresente para {nome} agora. Diga seu
nome, horario e como pode ajudar."` O Gemini Live obedecia discursando sobre o
sistema, ferramentas, funcionalidades e horário.

Agora o gatilho informa o **texto exato** e lista o que é **proibido** (sistema,
ferramentas, funcionalidades, status, horário/data/clima, listas), com limite de
15 palavras. Modelos de áudio tendem a "encher linguiça" quando a instrução deixa
margem — por isso as proibições pesam tanto quanto o pedido.

**Teste:** `tests-manual/test_charon_barge_in.py` (novo) — 30 verificações,
incluindo um **cenário comportamental** que instancia `VoiceSession`, injeta
respostas falsas do Gemini e confere: áudio descartado após interrupção,
transcrição do usuário preservada, liberação no `turn_complete`, e a rede de
segurança de 3 s. Foi esse cenário que achou o bug da transcrição — a análise
estática não pegava.

**Documentação:** `docs/CHARON-VOZ.md` seções 7.3 e 7.3.1 reescritas.

---

### 8. Não havia onde colar a chave da OpenAI + provedores personalizados

**Queixa:** *"no projeto não tem onde inserir a chave do provedor openai"*.
**Estava certo** — e o mesmo valia para `opencode` e `openclaude`.

**Causa:** o modal de chaves é montado a partir de `PROVIDERS`
(`PROVIDERS.filter(p => !p.dynamic)`). Esses três **não estavam na lista**, então
nenhum campo era renderizado. Agravante: **todo o resto do sistema já os
suportava** — `get_client`, o `key_map` do backend, a carga de chaves e o mapa de
envio. Faltava só a interface.

**Pedido seguinte:** *"pode inserir outros provedores ou uma opção para que eu
crie provedores novos, pois sempre tem provedores novos; já deixa no projeto os
mais comuns incluso"*.

**Solução — registro de provedores** (`backend/core/provedores.py`):

| Parte | Conteúdo |
|-------|----------|
| `PRESETS` | 25 provedores comuns (no código, estáveis) |
| `provedores_custom.json` | criados pelo usuário (fora do git) |
| `GET/POST/DELETE /api/config/provedores` | CRUD |
| `POST /api/config/provedores/modelos` | busca a lista de modelos do provedor |

Agora **a interface não tem lista própria para os campos de chave** — usa a do
backend. Um provedor novo aparece sozinho, sem alterar o frontend.
`get_client` e o salvamento de chave consultam o registro, então **criar provedor
não exige código nem deploy**.

**Provedores comuns adicionados:** DeepSeek, xAI (Grok), Mistral, Anthropic,
Together, Fireworks, Cerebras, Perplexity, DeepInfra, Hyperbolic + servidores
locais LM Studio, vLLM, text-generation-webui e Jan.

**Na interface:** botões **Salvar**, **Modelos** (carrega a lista do provedor),
**Testar** (chamada real) e **X** (remover, só nos personalizados), mais
**+ Adicionar provedor**.

**Cuidado documentado:** o botão **Modelos** usa `/models`, que **mente** no
OpenRouter (público) e na NVIDIA (lista o que a conta não tem). Por isso ele
marca `confiavel: False` nesses dois e avisa na tela — quem prova o modelo é o
**Testar**.

**Dois bugs da mesma família, encontrados ao revisar a própria correção** — o
mapa fixo de chaves continuava sendo a fonte, então um provedor novo não
funcionava de ponta a ponta:

| Onde | Bug | Efeito |
|------|-----|--------|
| Salvar (frontend) | `envKeyMap[prov.keyField]` era `undefined` para provedor novo | clicar em Salvar **não enviava nada** — chave descartada em silêncio |
| Ler (frontend) | `envToField` era fixo | campo aparecia **vazio** com a chave já gravada; o usuário salvava de novo achando que perdeu |
| Ler (backend) | `GET /api-keys` montava resultado de mapa fixo | nem reportava os provedores novos |

Corrigido com o padrão `<ID>_API_KEY` (o mesmo que o backend usa) e iterando as
chaves da resposta em vez de um mapa fixo. `GET /api-keys` passou de **9 para 25**
provedores reportados.

`docs/PROVEDORES.md` (novo) documenta tudo. Teste: `test_provedores.py`
(75 verificações, incluindo criar provedor → `get_client` aceitar → remover, e
executar `GET /api/config/api-keys` de verdade).

---

### 9. Ferramentas: o modelo "anunciava e não fazia" + painel estilo VS Code

**Queixa:** *"o modelo parece estar com dificuldade de utilizar as ferramentas…
o modelo fala que vai fazer e fica ali no plano de execução e não faz"* — e o
markup `<｜DSML｜og7d8j9uokjb…>` aparecia **cru** no chat.

**Eram dois bugs somados** (de novo um escondendo o outro):

**(a) O formato DSML era desconhecido.** Alguns modelos — sobretudo **DeepSeek
V3.2/V4 via OpenRouter** — não devolvem `tool_calls` estruturado: escrevem o
markup nativo **dentro do texto**. O DEEP-OS só conhecia XML do Gemini, JSON e
`bash("…")`. A palavra `DSML` **não existia em nenhum lugar do código** — foi a
pista que fechou o diagnóstico.

Detalhe decisivo: o delimitador é a barra vertical de **largura total**
(`｜`, U+FF5C), **não** o `|` ASCII (U+007C). Comparar com o caractere errado faz
o parser nunca casar. É problema conhecido e documentado do próprio DeepSeek
([issue](https://github.com/NousResearch/hermes-agent/issues/15453),
[PR](https://github.com/NousResearch/hermes-agent/pull/98764),
[discussão](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/discussions/209)).

**(b) Faltava o fallback no caminho das TAREFAS.** Assimetria:

| Caminho | Fallback de texto? |
|---|---|
| `stream_chat_with_tools` (chat) | ✅ tinha |
| **`complete_chat_with_tools`** (tarefas) | ❌ **não tinha** |

Sem ele, o texto era tratado como **resposta final** e o loop **terminava** — por
isso "anuncia e não faz". As tarefas usam justamente o não-streaming.

**Correção:**
- `extrair_dsml()` — containers `tool_calls` (V4) e `function_calls` (V3.2),
  parâmetros como tag XML **ou** JSON cru, invoke sem container, aspas simples,
  barra ASCII ou larga, e **várias chamadas** na mesma resposta;
- `extrair_tools_do_texto()` usado pelos **dois** caminhos (fim da assimetria);
- `limpar_markup_dsml()` — o markup some do texto exibido, inclusive tags
  malformadas; texto sem markup volta intacto;
- tipagem que **não corrompe** `ls -la` (só converte o que parece JSON);
- o fallback do não-streaming só roda `if tools:` — evita virar chamada de
  ferramenta uma conversa que apenas cite JSON.

**Painel de execução refeito no estilo VS Code.** Antes era lista plana e o
frontend **ignorava** os eventos `task_checklist`, `task_progress` e `thinking`
que o backend já enviava — o "plano" era só texto do modelo.

| Antes | Agora |
|-------|-------|
| lista plana | **árvore** com conectores (`├─`, `└─`) |
| sem tempo | **duração** por ferramenta (`1.2s`, `840ms`) |
| plano só como texto | **plano real** do backend, com estado por passo |
| parecia travado | **ícone girando** no passo em execução |
| sem visão do todo | **barra de progresso** + contador `2/4` |

Barra âmbar enquanto executa, **verde** a 100%, **vermelha** se um passo falhar.

**Teste:** `tests-manual/test_dsml_tools.py` (novo) — 35 verificações offline,
incluindo uma checagem **estrutural** de que os dois caminhos usam o mesmo
extrator (foi essa assimetria que causou o bug).

**Documentação:** `docs/FERRAMENTAS.md` (novo).

---

### 10. Documentação

- **Novo:** [`docs/MODELOS.md`](docs/MODELOS.md) — por que davam 404, as
  armadilhas de teste, o estado real de cada provedor, as 8 regras para não
  repetir, e os comandos rápidos.
- **Novo:** [`docs/PROVEDORES.md`](docs/PROVEDORES.md) — catálogo de provedores,
  como criar um novo pela interface, e as armadilhas registradas.
- **Atualizado:** `docs/CHARON-VOZ.md` (barge-in + saudação), este `STATUS.md` e
  `memory.md` (regras novas).

---

### 11. Commits desta sessão

| Commit | Assunto |
|--------|---------|
| `436673e` | `fix(chaves)`: placeholder `***saved***` não sobrescreve mais a chave real |
| `b09cdec` | `fix(modelos)`: listas provadas, seletor de provedor e IDs extintos |
| `48ef87e` | `fix(charon)+feat(provedores)`: barge-in, saudação curta, campos de chave e provedores personalizados |
| `a6db871` | `fix(provedores)`: chave de provedor novo era descartada ao salvar e ao ler |
| (este) | `fix(ferramentas)`: parser DSML, fallback no caminho das tarefas e painel estilo VS Code |

---

### 12. Verificações executadas

- `tests-manual/run_all.py` → **19/19 arquivos passando** (17 na altura do primeiro deploy; 19 após o parser DSML, o histórico do Charon e a voz do Jarvis)
- `tsc --noEmit` → **0 erros novos** nos arquivos alterados (14 erros pré-existentes em outros)
- `import main` → OK, **250 rotas**
- Chaves reais do usuário **intactas** após os testes (9 provedores no `.env`)
- Barge-in validado por cenário **comportamental** (não só análise de texto)
- **Deploy verificado com `tools/verificar-deploy.cjs`** — baixa o JavaScript
  publicado e confirma que o código novo está no ar (o "HTTP 200" do script de
  deploy **não** provava isso: bundle antigo em cache também responde 200, e
  `/api/config/*` devolve 401 existindo ou não a rota)

---

### 13. ✅ Confirmado pelo usuário em produção (2026-09-12)

> *"perfeito salvou a chave testou ok funcionou no chat jarvis"*

O fluxo completo de chave passou a funcionar de ponta a ponta:
**abrir o campo → colar → Salvar → Testar → conversar no Jarvis**.

Antes desta sessão esse caminho era impossível: o campo da OpenAI **não
existia**, o placeholder `***saved***` sobrescrevia a chave real, o erro era
engolido por `.catch(() => {})` e na VPS o `401` do middleware ficava invisível.

**E a execução de ferramentas também foi confirmada** (mesma data). O pedido*"faça uma varredura procurando arquivos .gguf"* — o **exato cenário que
falhava** antes, quando o modelo só anunciava o plano — agora executa de verdade
e devolveu o resultado real:

```
/root/models/qwen2.5-coder-7b.gguf   4,4 GB   06/Set 19:18
Nenhum .gguf dentro de /root/DEEP-OS
```

O resultado confere com o inventário do servidor (o único `.gguf` da VPS, que
foi movido para `/root/models/` numa sessão anterior). Ou seja: o modelo não só
executou a ferramenta como **leu o disco certo** e respondeu com dados reais.

> **Nota sobre o modelo local na VPS:** a VPS tem 4 GB de RAM. Um 7B em Q4
> (4,4 GB) mais o cache de contexto **não cabe** — rodaria com swap e ficaria
> inviável. Esse `.gguf` é útil no PC (que tem GPU e 25+ modelos), não na VPS.

**Ainda não testado com voz real** (precisa de microfone): a interrupção do
Charon e a saudação curta. Ver a seção 14 mais abaixo para o roteiro.

**Filtro de fluxo DSML — verificado no servidor de produção** (commit `215741c`):

```
$ /root/DEEP-OS/venv/bin/python -c "from core.llm_native import FiltroDSML; print('FILTRO OK')"
FILTRO OK

$ ... -c "from core.llm_native import FiltroDSML as F;V=chr(0xFF5C);f=F();
         s=''.join(f.alimentar(x) for x in ['oi ','<'+V+'DS','ML'+V+'tool_calls>',' fim'])+f.finalizar();
         print('FILTRO OK' if 'DSML' not in s else 'FALHOU: '+s)"
FILTRO OK
```

O segundo teste é o que importa: prova que um marcador **partido entre tokens**
(como o streaming realmente entrega) é removido. Foi essa a causa de o usuário
continuar vendo o markup na tela mesmo com o parser já funcionando — a limpeza
existia só no texto final, não no fluxo.

---

### 14. Voz do Jarvis: soava robótica e as barras não faziam nada

**Queixas:** *"a resposta de voz parece robótica"* e *"a velocidade e o tom não
mudam nada ou quase nada"*.

**Três causas somadas:**

**(a) O regex de limpeza APAGAVA A LETRA "ã".** A alternância de um dos
`.replace` era `sdkjf|ã|©|®|™|°` — o caractere **U+00E3 estava na lista de
remoção**. Em português:

| Falado | Saía como |
|---|---|
| não | no |
| então | ento |
| informação | informaço |
| manhã | manh |

"não" é uma das palavras mais frequentes do idioma. A fala saía errada **o tempo
todo** — é exatamente o que se descreve como voz "robótica".

**(b) As barras de velocidade/tom não afetavam a voz padrão.** As vozes padrão do
Jarvis são do tipo `edge` (Edge TTS, neural). O `speak()` mandava para `/api/tts`
apenas `{ text, voice }`, e o backend tinha `rate="-5%"` e `pitch="-15Hz"`
**fixos no código**. As barras só chegavam ao `speakBrowser` — o plano B, quando
o Edge falha. Ou seja: **quem estava na voz boa não tinha controle; quem estava
na voz ruim tinha.** O inverso do desejado.

**(c) Texto longo ia numa única utterância**, perdendo a entonação do meio para
o fim — leitura corrida e monótona.

**Correção:**
- nova função `prepararTextoParaFala()` — ponto único da limpeza, que separa o
  que é **MARCA** (markdown) do que é **PALAVRA**: preserva acentos e cedilha,
  remove bloco de código (não se lê código), fala o **rótulo** do link em vez da
  URL, achata tabelas, expande `R$` → "reais", `%` → "por cento", `→` → "para",
  e tira emojis;
- `dividirEmFrases()` — fala **frase por frase**, para o motor reiniciar a
  prosódia e as pausas saírem naturais;
- `/api/tts` agora **aceita e aplica** `rate` e `pitch` (com limites, porque fora
  deles o provedor distorce a voz); as barras passaram a ter efeito na voz Edge;
- ponto **neutro no meio** da barra de tom (50 = voz original) — antes existia um
  `-15Hz` escondido que deixava a voz sempre mais grave e a barra inútil;
- a escolha da voz do navegador passou a **preferir vozes neurais/naturais** em
  vez de cair na pt padrão do Windows (a mais robótica);
- quando o Edge falha, o usuário é **avisado no painel** (antes era só um
  `console.warn`: ele não sabia que tinha caído para a voz robotizada).

**Teste:** `test_voz_jarvis.py` — executa a função **de verdade** (extraída do
`.tsx` e rodada no Node). Teste só de texto não pegaria o defeito (b), que é de
**efeito**, não de presença.

---

### 15. Charon: o histórico não era enviado à sessão

**Queixas:** *"quando eu clico no histórico o Charon não consegue ver o
histórico, ele sempre está em um contexto novo"* e a regra desejada: *"sempre
for aberto pela primeira vez a sessão deve ser nova, mas quando eu entro no novo
histórico ele deve lembrar de tudo"*.

**Causa:** o **Gemini Live guarda o estado da conversa no servidor dele** e cria
uma sessão nova a cada conexão. O frontend salvava os transcripts no
`localStorage` e os **exibia na tela**, mas nunca os enviava.
`switchConversation` apenas trocava o estado da tela — do ponto de vista do
modelo, a conversa realmente começava do zero.

**Correção, exatamente segundo a regra do usuário:**

| Situação | Comportamento |
|---|---|
| Abrir o Charon (primeira vez) | **sessão nova** + saudação curta |
| Clicar numa conversa do histórico | envia o histórico como **contexto** e faz uma **retomada curta** (sem se reapresentar) |

- `_montar_turnos_historico()` converte os transcripts em turnos do Gemini
  (papel `model`, não `assistant` — vocabulário diferente do OpenAI), junta falas
  seguidas do mesmo lado, descarta o primeiro turno se não for do usuário, e corta
  por **40 turnos / 12.000 caracteres** preservando sempre o **fim** da conversa;
- o histórico vai com `turn_complete=False` (é contexto, não pergunta) e a
  abertura escolhe entre **retomar** e **cumprimentar**;
- trocar de conversa com a sessão aberta **reconecta** — o Gemini não "rebobina"
  contexto, então a única forma confiável é nascer com o histórico certo;
- indicador na tela: **"lembra da conversa"** ou **"sessão nova"**.

**Bug secundário achado no caminho:** havia um **segundo**
`self._interrupted = False` dentro de `send_audio`. Como ele roda a cada chunk do
microfone, **desfazia o barge-in** logo em seguida. Sobreviveu à correção
anterior porque a busca foi feita no caminho do **recebimento**, não no do
**envio**. O teste agora varre o arquivo inteiro e exige que todo reset esteja em
`__init__` ou `_handle_response`.

---

### 16. Regra dos dois projetos gêmeos (pedido do usuário)

*"deixe isso especificado para que todos os modelos de AI saiba que sempre que
fazer as alterações no projeto `C:\DEEP-OS` tem que fazer também no outro
`C:\DEEP-OS-LOCAL`"* + *"cada um deles tem o seu repositório próprio"* +
*"lembrando que um é para uso com vps e outro para uso local"*.

A regra ficou **no topo do `AGENTS.md`** (o primeiro arquivo que um modelo lê) e
em **`docs/DOIS-PROJETOS.md`**, cobrindo:

- os dois projetos, seus **repositórios** e suas **branches** (`DEEP-OS.git`
  /`master` e `DEEP-OS-LOCAL.git`/`main`);
- **um push não atualiza o outro** — repositórios independentes: sincronizar os
  arquivos e dar push em só um deixa o outro com o código novo fora do GitHub, e
  um `reset --hard` depois apaga;
- **proibição** de `git reset --hard` entre os dois (apagaria histórico e
  arquivos exclusivos: `README-LOCAL.md`, `chatbot-server/`, `generated/`);
- a **distinção de finalidade**: VPS (Linux headless, 4 GB, nginx, sem tela)
  versus local (Windows com desktop, GPU, Ollama com 25+ modelos) — **o código é
  o mesmo, o comportamento não**;
- tabela de **onde cada tipo de bug aparece**: proxy/`Host`/401 só na VPS;
  ferramenta de GUI só no LOCAL; falta de modelo local só na VPS; memória/OOM só
  na VPS; caminho com `:` só na VPS;
- **o que não fazer**: remover o filtro `is_headless()` para tool de GUI
  "funcionar na VPS", assumir GPU/RAM sobrando lá, usar `C:\` em código da VPS ou
  `/root/...` no LOCAL;
- o procedimento de sincronização em 4 passos e o checklist final (suíte nos
  **dois**, commit + push nos **dois**).

---

### 17. ⚠️ Não testado (depende de você)

O barge-in e a saudação usam o Gemini Live, então **não dá para verificar sem
microfone**. Depois do deploy, confira na tela do Charon:

1. A saudação inicial deve ser **curta**: "Olá Wilson, eu sou Charon. O que
   gostaria de fazer agora?" — sem discurso sobre o sistema.
2. Peça algo longo ("me explique o projeto inteiro") e **fale por cima no meio**.
   O Charon deve **calar na hora** e a sua fala deve aparecer no chat.
3. Depois de você parar, ele deve **retomar** e responder o que você pediu.

Se o Charon não calar, o ponto mais provável é o **limite de sensibilidade** do
microfone (`nivel > 0.06` por 3 chunks, em `CharonPage.tsx`): microfone baixo ou
com muito ruído de fundo pode não atingir o limite. Ajuste esse número — é o
único parâmetro que precisa de calibração com o seu equipamento.

---

## Sessao 2026-09-10 (47) — Sistema PIX Completo

### Resumo
Implementado fluxo completo de pagamento PIX: admin configura chave PIX + QR Code, usuario ve QR Code e chave ao assinar plano pago, envia solicitacao de pagamento, admin confirma e ativa plano automaticamente.

### 1. Backend PIX (admin.py)
- **PUT /admin/pix:** Aceita `pix_qr_base64` para upload de QR Code
- **GET /admin/pix/public:** Retorna PIX com QR Code (sem 404 se nao configurado)
- **PIX salvo em:** `data/system_config.json`

### 2. Backend Pagamento (shop.py)
- **POST /plans/request-payment:** Usuario envia solicitacao de pagamento (tenant_id, plan_id, amount, notes)
- **Pagamento pendente salvo em:** `system_config.json > pending_payments[]`
- **POST /admin/payments/confirm:** Admin confirma e ativa plano (atualiza DB)
- **POST /admin/payments/reject:** Admin rejeita pagamento

### 3. PricingPage PIX Modal
- Botao "Assinar Agora" em planos pagos abre modal PIX
- Mostra QR Code do admin (se configurado)
- Mostra chave PIX + botao copiar
- Mostra instrucoes de pagamento
- Botao "Ja paguei" envia solicitacao ao admin
- Feedback visual pos-envio

### 4. PixPage (Novo Componente)
- Pagina dedicada para pagamentos via PIX
- Mostra QR Code, chave PIX, instrucoes
- Passo a passo de como pagar
- Mensagem se PIX nao configurado

### 5. AdminDashboard - Tab Pagamentos
- Botao "Pagamentos" com badge de pendencias
- Configuracao PIX: chave, tipo, titular, instrucoes, upload QR Code
- Lista de pagamentos pendentes com Confirmar/Rejeitar

### Commits da sessao
- feat: PIX payment system complete (backend + frontend)

### Proximos Passos (Sessao 48) — o que era esperado ao abrir a sessao
1. ~~**DIST-SAAS GITIGNORE**~~ — ✅ **CONCLUIDO na sessao 48** (commit `74c2a73`)
2. **TESTAR FLUXO PIX** — Configurar PIX no admin, assinar plano, confirmar pagamento
3. **TESTAR QRCODE** — Upload de QR Code no admin e visualizacao no PricingPage
4. **NOTIFICACOES** — Notificar usuario quando pagamento confirmado

> Os itens 2-4 continuam abertos. Ver "Proximos Passos (Sessao 49)" no topo.

---

## Sessao 2026-09-11 (48) — Correcoes de isolamento, lembretes, audio e microfone

### Resumo
Sessao longa de correcao. O site chegou a ficar com a **API fora do ar (502)** e
varias funcionalidades estavam quebradas. Todas resolvidas e verificadas em
producao.

---

### 1. INCIDENTE INICIAL — API fora do ar (502 Bad Gateway)

**Sintoma:** o frontend abria, mas o login dava
`JSON.parse: unexpected character at line 1 column 1`. A API respondia **502**.

**Causa:** um modelo de IA alterou `backend/routes/chatbot.py` adicionando
isolamento por tenant e quebrou o import:

```python
from core.auth import require_plan, get_current_tenant_id
from fastapi import APIRouter, HTTPException          # Depends NAO importado

async def save_config(config: ChatBotConfig, admin: str = Depends(require_admin)):
```

`Depends(...)` no **default do parametro** e resolvido **no import do modulo**
(quando o FastAPI monta as rotas) — nao e erro de requisicao, e erro de **BOOT**.
O `main.py` inteiro estourava com `NameError`, o uvicorn nao subia, o systemd
entrava em loop e o nginx ficava sem ninguem na 8001 → **502**. O HTML do 502
chegava no `JSON.parse` do frontend, que estourava.

**Agravante que confundiu tudo:** o modelo tentou reverter com
`git reset --hard HEAD~2`, mas **so afetou o PC e o GitHub** — o VPS nunca foi
revertido. Ele tentou deployar rodando comandos Linux dentro do **PowerShell do
Windows** (`systemctl`, `chmod`, `grep` → "nao reconhecido"), e quando
`/root/DEEP-OS` nao existia ele **caia para o repo local** e mexia nele. O
relatorio final dele afirmava "backend reiniciando com codigo original" e
"git push concluido" — **nada verificado**.

**Existem TRES repositorios:** `C:\DEEP-OS` (PC), GitHub e `/root/DEEP-OS`
(VPS). Um reset no PC + push **nao reverte o VPS**.

**Correcao:** restaurar `chatbot.py` do commit bom e subir o backend.

---

### 2. CAUSA RAIZ do vazamento de voz/nome entre usuarios

Em `routes/config.py` a rota **catch-all `/{section}` era registrada ANTES** das
rotas literais. O FastAPI resolve por ordem de registro, entao
`GET /api/config/identity` caia no catch-all e devolvia a identidade **GLOBAL**
do `config.yaml`. Resultado: o frontend nunca leu a identidade por tenant, e o
`PUT` gravava certo (catch-all e so GET) enquanto o `GET` devolvia o global —
"s**alva mas aparece para todos**". Correcao: catch-all movido para o FIM do arquivo.

> **REGRA:** rotas catch-all (`/{param}`) SEMPRE por ultimo em qualquer router
> FastAPI. Se um path literal "nao executa", suspeitar da ORDEM antes da logica.

---

### 3. Units systemd duplicadas (porta 8001 em loop)

`deepos-backend.service` e `deep-os-backend.service` — **um hifen de diferenca**
— as duas `enabled`, brigando pela 8001. Matar processos nunca resolvia: a
duplicada tinha `Restart=always` e ressuscitava em ~5s.

> **REGRA:** quando a porta e reocupada sozinha, suspeitar de **unit duplicada**
> antes de processo solto. Verificar com
> `grep -rl "uvicorn" /etc/systemd/system/`.

Correcao: duplicada desabilitada; a boa endurecida com `RestartSec=5` e
`StartLimitBurst=5`.

---

### 4. Outras correcoes da sessao
- **Identidade por tenant:** `tenants.assistant_name`, `user_name` e `voice`
  (com migracao); `/api/config/identity` com JWT opcional.
- **Contas master:** cada uma com chave propria (`master-admin:<email>`) e linha
  criada automaticamente. Antes as duas compartilhavam o `sub` `master-admin` e
  nao tinham linha, caindo ambas no global.
- **Lembretes:** `schtasks`/`systemd-run --user`/`at` nao funcionam em VPS
  headless (motivo do "Nao consegui registrar o lembrete"). Agora tabela
  `reminders` no SQLite + loop asyncio de disparo. Resumo em documento com link
  de download (tool `list_reminders` + `/api/reminders/export`).
- **Fuso horario:** o servidor roda em UTC e o usuario em Brasilia (UTC-3);
  `datetime.now()` fazia um lembrete das 14:30 parecer no passado ("esse horario
  ja passou"). Agora grava em UTC e exibe na hora local. `ZoneInfo` sem banco de
  fusos (Windows sem `tzdata`) caia em UTC — fallback de offset fixo + `tzdata`
  no requirements.
- **Audio do Charon:** o worklet nao tinha recuperacao de sub-run (`_started`
  nunca voltava a `false`), comendo a cauda da ultima palavra e engasgando.
- **Microfone no Firefox:** `AudioContext` com `sampleRate` forcado fica
  suspenso (o Firefox nao reamostra como o Chrome), e o auto-start chamava
  `getUserMedia` sem gesto do usuario. Agora watchdog de 2s retoma/readquire o
  mic, o auto-start espera o primeiro clique, e o erro e diagnosticado com
  precisao (permissao negada / dispositivo em uso / conexao insegura).
- **3 tools nao importavam:** `backend/config/` (sem `__init__.py`) sombreava o
  `config.py` da raiz; `youtube_video`, `game_updater` e `flight_finder`
  falhavam. Shim `backend/config.py` resolveu.
- **`_HEADLESS_EXCLUDED` incompleto:** faltava `send_message` (usa pyautogui).
- **`require_plan` devolvia 404** para o admin (sem linha em `tenants`), fazendo
  rota existente parecer inexistente.
- **`_parse_fire_at` rejeitava horario valido:** truncava a string em 19 chars e
  `YYYY-MM-DD HH:MM` tem 16 → HTTP 400 "precisa ser no futuro".

---

### Verificado em producao
```
commit d853617 | backend active (deepos-backend) | nginx active
site 200 | api publica 200
A (wwbc22)          voz=Kore  nome=Atena    -> persistiu
B (wwbcinformatica) voz=Charon nome=Charon  -> NAO afetado
/api/reminders 200 | POST /api/reminders 200 (fuso convertido)
frontend/dist-saas: 0 arquivos trackeados (pendencia fechada)
```

### Scripts de deploy criados
- `scripts/deploy-faf8f93.sh` — deploy completo; detecta qual unit atende a
  8001, valida o `import` ANTES de reiniciar, roda migracao, builda e publica.
- `scripts/fix-units-duplicadas.sh` — resolve as units duplicadas.
- `scripts/fix-porta-8001.sh` / `fix-definitivo-8001.sh` — reparo da porta.

### Arquivos de memoria desta sessao (.memory/)
`MEMORY-incidente-2026-09-10-backend-502.md`,
`MEMORY-identidade-tenant-lembretes-audio.md`,
`MEMORY-auditoria-tools-headless.md`,
`MEMORY-fuso-horario-e-units-duplicadas.md`,
`MEMORY-causa-raiz-catch-all-config.md`

---

### Testes automatizados (tests-manual/)
`test_identity_endpoint.py`, `test_master_identity.py`,
`test_voice_isolation.py`, `test_tenant_identity.py`,
`test_reminder_timezone.py`, `test_reminders.py`, `test_reminder_summary.py`,
`audit_headless_tools.py`

**Licao principal:** teste pela ROTA (HTTP), nao so pela funcao. O bug do
catch-all passou despercebido porque a funcao `get_identity()` era testada
direto e sempre funcionava — nao era ela que respondia.

---

### Proximos Passos (Sessao 49)

#### SEGURANCA — corrigido na sessao 48 (commit `100f0a7`)
1. ~~**VAZAMENTO DE ROTAS**~~ — ✅ **CORRIGIDO**. A auditoria automatica
   (`tests-manual/test_all_routes.py`) revelou ~48 rotas respondendo 200 sem
   autenticacao, incluindo `/secrets` (nomes e valores das API keys), `/logs`,
   `/memory` e `/tool/list`. Agora ha `middleware/security.py` bloqueando.
2. ~~**`downloads/` compartilhado entre tenants**~~ — ✅ **CORRIGIDO**. Agora
   `downloads/<tenant_id>/` com protecao contra path traversal.
3. ~~**`JWT_SECRET` com default publico no codigo**~~ — ✅ **CORRIGIDO**. Vem de
   env ou e gerado e persistido em `backend/config/jwt_secret.key`.
4. ~~**`MASTER_PASSWORD` hardcoded**~~ — ✅ **CORRIGIDO**. Agora em
   `core/security_config.py`, lido de variavel de ambiente.
5. **TROCAR AS SENHAS** (ainda pendente, depende de voce):
   - senha de root do VPS (apareceu em texto puro no chat)
   - `MASTER_PASSWORD` (`admin123@`, ainda e o padrao — o log avisa)
   - definir `JWT_SECRET` por env no systemd (hoje usa o arquivo gerado)
6. **Endurecer o resto**: as rotas fora da lista de bloqueio (`/plugins`,
   `/llamacpp`, `/ollama`, `/cron`, `/triggers`, `/tasks`, `/monitor`,
   `/opencode`) ainda respondem sem auth. Ficaram assim para nao quebrar o app
   desktop — revisar uma a uma quando houver tempo.

#### Testes funcionais pendentes (dependem de uso no navegador)
7. **MICROFONE NO FIREFOX** — a permissao foi bloqueada pelo auto-start antigo e
   ficou gravada. Liberar no cadeado 🔒 → Microfone → **Permitir** → recarregar.
8. **ISOLAMENTO POR TENANT** — ✅ verificado via API. Falta confirmar pela UI.
9. **LEMBRETES** — pedir por voz, ouvir o disparo, gerar o documento.
10. **CONVERSAS / DOCUMENTOS / HELP MENU** — testar pela interface.
11. **FLUXO PIX / QRCODE / NOTIFICACOES** — testar ponta a ponta.

#### Melhorias tecnicas
12. **`repeat` nos lembretes** — o parametro existe na tool mas nao e implementado.
13. **Frontend nao envia `X-Timezone`** nas chamadas HTTP de lembrete.
14. **`systemctl mask deep-os-backend`** — garantia total contra a duplicada.
15. **Branch `main` desatualizada** — 115+ commits atras; trocar a default.
16. **Arquivos gigantes** — `voice_ws.py` (~2160 linhas) e `CharonPage.tsx`
    (~1500) sao dificeis de manter. Candidatos a divisao.
17. **GitHub Actions CI/CD** — secrets `VPS_HOST` + `VPS_SSH_KEY`; o
    `tests-manual/run_all.py` ja devolve codigo de saida, pronto para CI.
18. **Auditoria das tools no VPS** — rodar `audit_headless_tools.py` no Linux.

#### Assistente local (RAG) — feito na sessao 48
19. ✅ **`tools/rag_local.py` + `tools/perguntar.py`** — responde sobre o projeto
    usando a documentacao, com modelo local via Ollama. Ver
    [`tools/README-RAG.md`](tools/README-RAG.md).
20. **Evoluir para busca semantica** (`pip install faiss-cpu
    sentence-transformers`) — melhora quando a pergunta usa vocabulario
    diferente do texto. Hoje a busca e lexical + lista de sinonimos curada.

#### Melhorias de processo
21. **Rodar `python tests-manual/run_all.py` antes de cada deploy** — 10 testes
    em ~20s, e foram eles que acharam o vazamento de rotas e a rota duplicada.
22. **Documentar enquanto resolve** — as secoes de armadilha do `memory.md` e do
    `docs/CHARON-VOZ.md` economizam horas em problemas recorrentes.

---

## Sessao 2026-09-10 (46) — Tenant Isolation + Conversas + Help Menu

### Resumo
Corrigido isolation de dados por tenant (localStorage prefixado com ID do usuario), adicionado sistema de conversas multiplas (estilo ChatGPT), reescrito menu de Ajuda com instrucoes de uso do Charon/Jarvis, e corrigido AdminDashboard para verificar admin_token antes de buscar dados.

### 1. Tenant Isolation (chatStorage.ts)
- **Problema:** Todas as chaves do localStorage eram genericas (`charon_transcripts`, `charon_user_name`). Quando um usuario muda o nome, afeta todos no mesmo navegador.
- **Solucao:** Criado `chatStorage.ts` com funcoes `tenantGet()`, `tenantSet()`, `tenantRemove()` que prefixam chaves com o ID do tenant.
- **Resultado:** Cada usuario tem seus dados isolados (configuracoes, transcripts, API keys)

### 2. Sistema de Conversas
- **Problema:** Charon e Jarvis tinham apenas um historico flat (sem sessoes separadas)
- **Solucao:** Adicionado sistema de conversas com:
  - Dropdown discreto no topo do painel direito (Charon) e header (Jarvis)
  - Botao "+" para criar nova conversa
  - Renomear conversa (botao ✎)
  - Excluir conversa (botao ✕)
  - Auto-nomeacao pela primeira mensagem
  - Historico por conversa (ultimas 300 mensagens)
- **Migracao:** Dados antigos sao migrados automaticamente para nova conversa

### 3. HelpModal Reescrito
- **Problema:** Menu de Ajuda era generico e nao explicava como usar Charon/Jarvis
- **Solucao:** Reescrito com 5 secoes:
  - **Charon (Voz):** Como usar, configuracoes, o que pode fazer
  - **Jarvis (Chat):** Provedores, modelos, funcionalidades
  - **Documentos:** Como pedir, formatos suportados, como baixar
  - **Instancias:** Limites por plano
  - **FAQ:** Perguntas atualizadas

### 4. AdminDashboard Auth Fix
- **Problema:** AdminDashboard buscava dados mesmo sem admin_token, causando erros 401 na tela
- **Solucao:** Verifica `admin_token` no localStorage antes de buscar dados. Se nao existe, mostra `AdminLogin`.
- **Logout:** Limpa `admin_token` e redireciona para planos

### 5. Deploy VPS
- Commit `fc12488` - fix: AdminDashboard checks admin_token before fetching data
- Commit `c5c9682` - feat: tenant isolation + conversation history + updated help menu
- Deploy concluido com sucesso (build 13.20s)

### Commits da sessao
- `30f3bb7` fix: align planConfig.ts keys with backend PlanType enum (Portuguese -> English)
- `c5c9682` feat: tenant isolation + conversation history + updated help menu
- `fc12488` fix: AdminDashboard checks admin_token before fetching data

### Proximos Passos (Sessao 47)
1. **DIST-SAAS GITIGNORE** — Adicionar dist-saas ao .gitignore e `git rm -r --cached frontend/dist-saas`
2. **TESTAR TENANT ISOLATION** — Verificar que dados de um usuario nao afetam outro
3. **TESTAR CONVERSAS** — Criar multiplas conversas, trocar entre elas, excluir
4. **TESTAR DOCUMENTOS** — Pedir para criar documento e verificar download
5. **TESTAR HELP MENU** — Verificar se instrucoes estao corretas

---

## Sessao 2026-09-10 (45) — Deploy VPS + Auth Me + Backend Fix

### Resumo
Deploy completo no VPS. Backend corrigido: `/auth/me` funciona (hardcoded master-admin), planos persistem em JSON, frontend busca planos da API.

### Commits da sessao
- `2c951db` fix: /auth/me retorna dados master admin hardcoded
- `e6c20b4` fix: vite proxy adiciona /plans e /shop
- `1212d0c` fix: PricingPage Fragment JSX tag corrigido
- `fbfae7d` fix: planos admin persistidos em JSON + PricingPage dinamico

---

## Estado Atual do Deploy

### ✅ Verificado funcionando em produção (2026-09-11, commit `72be050`)
```
backend: active (deepos-backend.service) | nginx: active | site 200 | API 200

SEGURANCA (confirmada de fora da rede, depois do fix do middleware)
  /api/config         -> 401   (era 200 EXPOSTO)
  /api/config/agent   -> 401   (era 200 EXPOSTO)
  /api/config/api-key -> 401   (era 200 EXPOSTO)
  /api/instances      -> 401   (era 200 EXPOSTO)
  /health /plans/public /shop/products /api/config/identity -> 200 (publicas)

ISOLAMENTO POR TENANT
  A (wwbc22) voz=Kore nome=Atena -> persistiu | B (wwbcinformatica) -> intacto

LEMBRETES
  /api/reminders 200 | POST 200 | fuso convertido (23:11 local -> 02:11 UTC)

DISCO / LOGS
  df: 20G de 48G (42%), 28G livres | /var/log/syslog 5.7K (era 27 GB)
  .gguf 4,4 GB movido para /root/models/ | ollama: inactive/disabled
```

### ✅ RESOLVIDO — download dos documentos (commit `91d7abb`)

**Era uma divergência entre DOIS sanitizadores de `tenant_id`.**

O projeto tinha duas implementações diferentes, e o script de migração usava o
id **cru**:

| Código | O que fazia com `master-admin:wwbc22@gmail.com` |
|---|---|
| `routes/download.py` + `core/reminder_doc.py` | removia `:` e `@` → `master-adminwwbc22gmail.com` |
| `scripts/migrar-downloads-legados.sh` (shell) | usava o id cru → `master-admin:wwbc22@gmail.com` |

Os documentos foram para **uma** pasta e o backend procurava **outra** → 404.

**Como foi encontrado:** o diagnóstico Python no VPS imprimiu a linha decisiva:
```
_sanitize("master-admin:wwbc22@gmail.com") -> 'master-adminwwbc22gmail.com'
                                   ^ o ':' e o '@' somem
```

**POR QUE ISSO NUNCA SE REPRODUZIU NO PC (importante):**
O **Windows rejeita `:` em nome de pasta** (`NotADirectoryError`). A pasta com
`:` só existe em Linux, e o único código que a criava era o script shell rodado
no VPS. Nenhum teste local poderia ter pego — e eu tratei vários 404 legítimos
do meu ambiente (onde `downloads/` está vazia) como se fossem o bug.

**Correção:**
1. `core/tenant_identity.py::tenant_slug()` — **fonte única** de sanitização
   (`[A-Za-z0-9._-]`; o resto vira `_`; nunca vazio)
2. `routes/download.py` — delega ao `tenant_slug()` e procura nas **duas**
   variações (`_pastas_do_tenant`), para não perder arquivos já gravados
3. `core/reminder_doc.py` — deixou de ter sanitização própria
4. Teste novo: `tests-manual/test_tenant_slug.py` (com tratamento explícito
   para SO que não aceita `:`)

**Validado em produção:** 5 documentos testados, todos HTTP 200.

> **REGRA:** sanitização de caminho derivada do tenant tem **uma** fonte.
> Duas implementações = duas pastas diferentes = dados inalcançáveis.

---

### 📌 REGRAS APRENDIDAS NESTA SESSÃO (leia antes de codar)

1. **Catch-all (`/{param}`) SEMPRE por último** em qualquer router FastAPI.
   Foi a causa raiz do vazamento de voz/nome (sobreviveu 47 sessões).
2. **Ao restringir o escopo de um endpoint, inspecione os DADOS JÁ EXISTENTES.**
   Isolar os downloads por tenant fechou um vazamento e quebrou os documentos
   antigos ao mesmo tempo.
3. **Uma fonte para sanitização de caminho.** Ver acima.
4. **Servidor roda em UTC; usuário em Brasília.** Calcular local, gravar UTC,
   exibir convertendo.
5. **Teste pela ROTA (HTTP), não só pela função.** Bugs de roteamento são
   invisíveis ao chamar a função direto.
6. **Não logar em caminho de alta frequência.** Um `print` por chunk de áudio
   gerou 27 GB de syslog e encheu o disco.
7. **Detecção de "local vs externo" pelo `Host`, nunca pelo IP** — atrás de
   proxy reverso o IP é sempre `127.0.0.1`.
8. **Painel de VPS tem métrica em cache.** `df -h` no servidor é a verdade.

---

---

### VPS Hostinger
- **IP:** 2.25.143.185
- **Dominio:** https://deep-os.tech
- **OS:** Ubuntu 26.04.1 LTS (Python 3.14)
- **User:** root
- **RAM:** 4GB
- **Projeto:** `/root/DEEP-OS`

### ⚠️ UNITS SYSTEMD — ATENCAO AO HIFEN
Existem **duas** units no servidor, com nomes que diferem por **um hifen**:

| Unit | Estado | Papel |
|------|--------|-------|
| **`deepos-backend.service`** | ✅ **active / enabled** | **A UNIT CORRETA** — usa `python3 -m uvicorn` |
| `deep-os-backend.service` | ❌ disabled (masked) | Duplicada — desabilitada na sessao 48 |

**Sempre use `deepos-backend`** (sem hifen depois de "deep"). As duas estavam
`enabled` e brigavam pela porta 8001 em loop de restart. Para conferir qual
atende de fato:

```bash
UNIT=$(ps -o unit= -p $(ss -lptnH 'sport = :8001' | grep -oP 'pid=\K[0-9]+' | head -1) | tr -d ' ')
echo "atendendo: $UNIT"
```

### Servicos
| Servico | Porta | Status |
|---------|-------|--------|
| Backend (uvicorn) | 8001 | OK (`deepos-backend.service`) |
| Nginx | 80/443 | OK (systemd) |
| SSL/Let's Encrypt | 443 | OK |
| Charon (WebSocket) | 8001 `/ws/voice` | OK |

### Nginx Config
- **Frontend:** `/var/www/deep-os/frontend/dist-saas` (estatico)
- **Config ativa:** `/etc/nginx/sites-enabled/deepos`
- **Proxies:** `/api/`, `/auth/`, `/chat/`, `/voice/`, `/ws/`, `/admin/`,
  `/plans/`, `/shop/` → `127.0.0.1:8001`
- ⚠️ Os docs do FastAPI (`/openapi.json`, `/docs`) **nao** sao expostos: caem na
  regra `/` e devolvem o HTML do frontend.

### Deploy — COMANDO ATUAL (recomendado)
```bash
cd /root/DEEP-OS
git fetch origin master && git reset --hard origin/master && bash scripts/deploy-faf8f93.sh
```

O script faz tudo com seguranca:
1. backup de `api_keys.json` e `config.yaml` em `/root/backup-deepos/`
2. descobre **qual unit** atende a 8001 (nao assume)
3. `git fetch` + `reset --hard` + `stash` das alteracoes locais
4. limpa `__pycache__`
5. **valida `import main` ANTES de reiniciar** — se falhar, nao sobe o servico
6. sobe o backend (a migracao roda no startup)
7. `npm run build:saas`
8. copia para `/var/www/deep-os/frontend/dist-saas` + reload do nginx
9. verifica: backend, site, colunas do banco e o shim do `config.py`

### ❌ NAO USE o deploy manual antigo
```bash
# NAO FACA ISSO
cd /root/DEEP-OS && git checkout -- . && git pull origin master
```
`git checkout -- .` **descarta alteracoes locais** (inclusive `api_keys.json`
se nao estivesse no .gitignore) e `git pull` da conflito quando o historico foi
reescrito. Use o script acima.

### Scripts de manutencao (`scripts/`)
| Script | Para que serve |
|--------|----------------|
| `deploy-faf8f93.sh` | Deploy completo (o de uso normal) |
| `fix-units-duplicadas.sh` | Resolve as duas units systemd brigando |
| `fix-porta-8001.sh` | Reparo simples da porta 8001 |
| `fix-definitivo-8001.sh` | Reparo com inventario completo de processos |

### Acesso
- **https://deep-os.tech** — Frontend + Backend via nginx
- **Login SaaS:** wwbc22@gmail.com / admin123@
- **Login Admin:** wwbcinformatica@gmail.com / admin123@ ("Painel Mestre")
- ⚠️ **As duas contas master compartilham a MESMA senha hardcoded** em
  `routes/auth.py` (`MASTER_EMAILS` + `MASTER_PASSWORD`). Trocar em producao.

### Tenants existentes (2026-09-11)
| id | e-mail | plano |
|---|---|---|
| `master-admin:wwbc22@gmail.com` | wwbc22@gmail.com | master |
| `master-admin:wwbcinformatica@gmail.com` | wwbcinformatica@gmail.com | master |
| `a48abdaccf57524c2e4b6e5ccd8dc287` | wwwbc26@gmail.com | quarterly |

> As contas master agora tem **linha propria** em `tenants` (criada
> automaticamente), com chave `master-admin:<email>`. Antes as duas emitiam o
> mesmo `sub` (`master-admin`) e nenhuma tinha linha — caiam ambas no
> `config.yaml` global, o que fazia a voz/nome de uma vazar para a outra.

---

## Arquivos Importantes

### Documentacao
| Arquivo | Conteudo |
|---|---|
| `README.md` | Visao geral do projeto |
| `manual.md` | Manual de uso |
| **`memory.md`** | **Memoria do projeto — regras, armadilhas, historico das sessoes** |
| **`STATUS.md`** | Este arquivo — status por sessao |
| **`docs/CHARON-VOZ.md`** | **Arquitetura da voz (audio, worklets, Firefox, diagnostico)** |
| **`RECUPERAR-VPS.md`** | Procedimento de emergencia quando o backend cai |
| `docs/SAAS_README.md` | Documentacao do modo SaaS |
| `AGENTS.md` / `CLAUDE.md` | Instrucoes para agentes de IA |
| `.memory/MEMORY-*.md` | Notas detalhadas de incidentes e correcoes |

### Backend — alterado na sessao 48
- `backend/config.py` — **NOVO**: shim que corrige o sombreamento de `config.py`
- `backend/core/tenant_identity.py` — **NOVO**: identidade, tenant e fuso (ContextVar)
- `backend/core/reminders.py` — **NOVO**: servico de lembretes + loop de disparo
- `backend/core/reminder_doc.py` — **NOVO**: resumo de lembretes em documento
- `backend/routes/reminders.py` — **NOVO**: API `/api/reminders`
- `backend/routes/config.py` — identidade por tenant + **catch-all movido para o fim**
- `backend/routes/voice_ws.py` — identidade/fuso por conexao, `list_reminders`,
  `TURN_TAIL_GRACE_S`, watchdog, `_HEADLESS_EXCLUDED`
- `backend/routes/auth.py` — `sub` unico por conta master
- `backend/core/auth.py` — `require_plan` libera admin/master
- `backend/database/connection.py` — colunas `tenants.*` e `reminders.tz`
- `backend/actions/reminder.py` — persiste no SQLite + fuso local
- `backend/requirements.txt` — adicionado `tzdata`

### Frontend — alterado na sessao 48
- `frontend/src/components/saas/CharonPage.tsx` — worklet de playback com
  recuperacao de sub-run, watchdog do mic, diagnostico de erro, auto-start por
  gesto, `?token=` no WebSocket

### Backend — arquivos principais
- `backend/main.py` — FastAPI, CORS, routers, startup (inicia o loop de lembretes)
- `backend/routes/voice_ws.py` — Charon (voz) — ver `docs/CHARON-VOZ.md`
- `backend/routes/chat.py` — Jarvis (chat)
- `backend/routes/admin.py` — dashboard admin, CRUD de tenants/produtos
- `backend/routes/shop.py` — API publica de produtos
- `backend/routes/download.py` — download/preview de arquivos gerados
- `backend/routes/ws_terminal.py` / `terminal.py` — terminal web
- `backend/middleware/tenant.py` — middleware multi-tenant (montado no `main.py`)
- `backend/tools/executor.py` — execucao de tools
- `backend/cron/scheduler.py` — agendador asyncio interno

### Frontend — componentes principais
- `frontend/src/components/saas/SaaSApp.tsx` — layout SaaS
- `frontend/src/components/saas/CharonPage.tsx` — Charon (voz + chat + config)
- `frontend/src/components/saas/JarvisPage.tsx` — Jarvis (chat multi-provedor)
- `frontend/src/components/saas/AdminDashboard.tsx` — Painel Mestre
- `frontend/src/components/saas/SettingsPage.tsx` — configuracoes
- `frontend/src/components/saas/chatStorage.ts` — storage isolado por tenant
- `frontend/src/components/saas/AuthPage.tsx` — login/registro
- `frontend/src/components/saas/HelpModal.tsx` — menu de ajuda
- `frontend/src/components/saas/PricingPage.tsx` / `PixPage.tsx` — planos e PIX
- `frontend/src/vite.config.ts` — proxy de dev

### Raiz
- `config.yaml` — config global (identity, tools, agent_models) — **agora e
  apenas o PADRAO**; identidade personalizada vive por tenant no banco
- `config.py` — `is_headless()`, `is_os()`
- `scripts/*.sh` — deploy e manutencao (ver tabela acima)
- `tests-manual/*.py` — testes de rota e de servico
- `.gitattributes` — forca LF em `*.sh`/`*.py`/`*.md` (CRLF quebra o bash)
- `.gitignore` — inclui `dist-saas/`, `Pessoal/`, `alterações*.txt`, `RECUPERAR-VPS.md`

### ⚠️ Nao versionados de proposito
- `backend/config/api_keys.json` — chave do Gemini (cada VPS tem a sua)
- `data/` — bancos SQLite (tenants, pagamentos, lembretes)
- `frontend/dist-saas/` — build gerada (publicada no nginx pelo deploy)
- `Pessoal/` — arquivos pessoais (contem senhas)
