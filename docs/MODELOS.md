# DEEP-OS — Modelos de IA: por que davam 404 e como manter as listas corretas

**Ultima atualizacao:** 2026-09-12

Este documento explica o bug relatado — *"quase todos os modelos davam erro 404
e, quando eu selecionava o provedor, não carregava todos de cada provedor"* —
o que estava errado exatamente, e como impedir que volte.

---

## 1. Resumo do que estava errado

Eram **quatro problemas independentes** que se somavam e produziam o mesmo
sintoma. Cada um sozinho já causaria erro.

| # | Problema | Efeito para o usuário |
|---|----------|----------------------|
| 1 | **IDs de modelo extintos** nas listas do frontend (9+ confirmados) | Escolher o modelo → 404 |
| 2 | **Listas divergentes** entre `constants.ts` e `JarvisPage.tsx` | O mesmo modelo funcionava num lugar e falhava no outro |
| 3 | **`zhipu` ausente** do array `PROVIDERS` | O provedor tinha modelos mas nunca aparecia no seletor |
| 4 | **Lista dinâmica não cancelada** ao trocar de provedor | Apareciam os modelos do provedor *anterior* → 404 |

O agravante: **nenhum desses erros aparecia na interface**. O backend devolvia
404 e o frontend apenas não respondia — daí a sensação de "quase tudo quebrado".

---

## 2. A armadilha central: `/models` mente

A descoberta mais importante desta investigação, e a razão de o problema ter
durado tanto:

> **O endpoint `/models` de um provedor NÃO prova que o modelo funciona.**

Dois exemplos medidos de verdade:

**OpenRouter** — `/api/v1/models` é **público**:
```
GET /api/v1/models com chave FALSA  ->  HTTP 200  (445 modelos)
GET /api/v1/key   com a chave real  ->  HTTP 401  "User not found."
```
Ou seja: a chave do OpenRouter estava inválida e a lista de modelos continuava
respondendo normalmente. Comparar IDs com o `/models` "passava".

**NVIDIA** — `/v1/models` lista modelos que a conta **não tem habilitados**:
```
/v1/models          ->  lista nvidia/llama-3.1-nemotron-70b-instruct
chat/completions    ->  HTTP 404  "Function '9b96341b-...': Not found for account"
```

**Conclusão prática:** a única verificação confiável é **fazer uma chamada de
chat de verdade** e exigir HTTP 200 com texto. Foi o que passamos a fazer.

---

## 3. Como verificar (ferramentas criadas)

Todas em `tools/`. Rodam com `node`, na raiz do projeto, usando as chaves de
`backend/.env`. Nenhuma delas grava ou imprime chave.

| Ferramenta | Para que serve |
|-----------|----------------|
| `tools/diagnostico-chaves.cjs` | Diz se cada chave é **válida**, usando endpoints que existem só para validar credencial |
| `tools/provar-modelos.cjs` | Prova **cada** modelo com uma chamada de chat real → gera `modelos-provados.json` e `MODELOS-PROVADOS.md` |
| `tools/modelos-atuais.cjs` | Baixa as listas reais dos provedores e compara com os IDs do código |
| `tools/reteste-rede.cjs` | Retesta o que falhou por erro de rede (não confundir "servidor caiu" com "modelo não existe") |
| `tools/validar-opencode-real.cjs` | Confere se um endpoint responde de verdade — ver a pegadinha da seção 5 |

**Regra de ouro:** rode `tools/provar-modelos.cjs` antes de adicionar qualquer
modelo novo à interface.

---

## 4. Pegadinhas de URL que já custaram tempo

Errar o prefixo do endpoint faz **todos** os modelos falharem com 404, o que
parece "modelo inexistente" mas é URL errada:

| Provedor | Caminho correto |
|----------|----------------|
| Groq | `https://api.groq.com/openai/v1/chat/completions` |
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` |
| NVIDIA | `https://integrate.api.nvidia.com/v1/chat/completions` |
| Zhipu | `https://open.bigmodel.cn/api/paas/v4/chat/completions` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key=...` |
| MiMo | `https://api.xiaomimimo.com/v1` |
| OpenCode | `https://opencode.ai/zen/v1` |

Repare que Groq usa `/openai` e OpenRouter usa `/api` **antes** do `/v1`. Foi
exatamente esse detalhe que produziu um relatório inteiro de falsos 404 na
primeira versão do script.

---

## 5. A pegadinha do `api.opencode.ai` (HTTP 200 falso)

Durante a investigação, `api.opencode.ai/v1/chat/completions` respondeu **HTTP
200** para todos os modelos testados — parecia a solução. Mas:

```
POST api.opencode.ai/v1  (modelo "modelo-que-nao-existe-xyz")
  -> HTTP 200
  -> corpo:  Not Found
```

Um serviço que aprova **até modelo inexistente** não é uma API. O corpo não era
JSON e o `200` não significava nada.

**Lição:** ao validar, exija três coisas, não só o código HTTP:
1. HTTP 200
2. corpo JSON legível
3. **conteúdo verificável** — ex.: "Quanto é 17 × 23?" deve responder `391`

E inclua sempre um **controle negativo** (modelo inexistente): se ele passar, o
teste não vale nada.

---

## 6. Estado real de cada provedor (medido em 2026-09-12)

### Funcionando

| Provedor | Modelos verificados |
|----------|--------------------|
| **Groq** | 7 de 7 testados — `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `qwen/qwen3.8-27b`, `groq/compound`, `groq/compound-mini`, `allam-2-7b` |
| **Gemini** | 7 funcionando — `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3-flash-preview`, `gemini-flash-latest`, `gemini-2.5-flash`, `gemini-2.5-flash-lite` |
| **NVIDIA** | 8 funcionando — ver nota do prefixo abaixo |
| **Ollama (local)** | 25+ modelos na máquina local; na VPS está instalado mas **sem nenhum modelo** |

### Com problema — precisa de ação sua

| Provedor | Código | O que significa | O que fazer |
|----------|--------|-----------------|-------------|
| **OpenRouter** | `401 User not found.` | A chave é **inválida ou foi revogada**. O `/models` continuava respondendo porque é público — por isso passou despercebido | Gerar nova chave em <https://openrouter.ai/keys> e salvar no Jarvis → Configurações |
| **OpenAI** | `401 Incorrect API key provided` | Chave **inválida** | Gerar nova chave em <https://platform.openai.com/api-keys> |
| **Zhipu (GLM)** | `429 余额不足或无可用资源包,请充值。` | Tradução: *"Saldo insuficiente ou nenhum pacote de recursos disponível, por favor recarregue."* — a conta está **sem crédito** | Recarregar a conta em <https://open.bigmodel.cn> |
| **MiMo** | `402 Insufficient account balance` | Conta **sem saldo** | Recarregar, ou usar `mimo.exe` local |
| **OpenCode** | `401 Insufficient balance` | Conta **sem saldo** (o endpoint está certo) | Recarregar em <https://opencode.ai/workspace> |
| **OpenClaude** | — | Não é API na nuvem: aponta para `http://localhost:4000/api/v1` (servidor local) | Rodar o servidor local, ou não usar este provedor |

Nenhum desses seis é bug de código — **são estados de conta**. O código estava
certo em apontar para eles.

### O prefixo da NVIDIA é obrigatório (correção de um commit anterior)

O commit `a8527c4` ("remove nvidia/ prefix from NVIDIA model IDs") **estava
errado**. Medido:

```
nvidia/nemotron-3-super-120b-a12b  ->  HTTP 200   (funciona)
nemotron-3-super-120b-a12b         ->  HTTP 404   (não existe)
```

O prefixo (`nvidia/`, `meta/`, `deepseek-ai/`) **faz parte do ID**. Os IDs foram
revalidados um a um e o prefixo foi restaurado.

Modelos NVIDIA que funcionam nesta conta:
`nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3.5-lightning-30b-a3b`,
`deepseek-ai/deepseek-v4-pro-0813`, `deepseek-ai/deepseek-v4-flash-0731`,
`meta/muse-glimmer-30b`, `meta/llama-3.2-11b-vision-instruct`,
`z-ai/glm-5.3-flash`, `openai/gpt-oss-20b`.

Modelos NVIDIA que o `/models` lista mas a conta **não tem** (404 "Not found for
account"): `nvidia/llama-3.1-nemotron-70b-instruct`,
`nvidia/llama-3.1-nemotron-ultra-253b-v1`, `nvidia/llama-3.1-nemotron-51b-instruct`,
`google/gemma-3-12b-it`, `moonshotai/kimi-k2.6`, `mistralai/mistral-large-2-instruct`.

Modelos que derrubam a conexão (`ECONNRESET`, testado 2×): 
`nvidia/nemotron-3-ultra-550b-a55b`, `meta/llama-3.2-90b-vision-instruct`,
`google/gemma-4-31b-it`, `moonshotai/kimi-k3`.

---

## 7. Onde as listas vivem (e por que havia divergência)

Havia **quatro** lugares com IDs de modelo, e eles saíram de sincronia:

| Arquivo | Conteúdo |
|---------|----------|
| `frontend/src/lib/constants.ts` | `MODELS` (chat clássico) + `PROVIDERS` |
| `frontend/src/components/saas/JarvisPage.tsx` | `PROVIDERS` (Jarvis) |
| `frontend/src/components/saas/InstancesPage.tsx` | `MODELS` (criação de instância) |
| `frontend/src/components/saas/ChatBotPage.tsx` | defaults do chatbot embutido |

Mais os defaults do backend: `backend/core/config.py` (`MODEL_ROUTING`) e
`backend/routes/chatbot.py`.

**Enquanto não existir uma fonte única**, o teste
`tests-manual/test_model_lists.py` garante que `constants.ts` e `JarvisPage.tsx`
não divirjam e que nenhum ID da lista de extintos volte.

---

## 8. O bug do seletor ("não carregava todos de cada provedor")

### 8.1 Ausência de cancelamento

```tsx
useEffect(() => {
  if (selectedProvider === 'ollama') {
    fetch('/ollama/models').then(...).then(data => setDynamicModels(models));
  }
}, [selectedProvider]);
```

Ao trocar de Ollama para Groq, a requisição do Ollama **continuava em voo**. Se
ela respondesse depois (rede lenta), chamava `setDynamicModels` e **sobrescrevia
a lista do Groq**. O `<select>` mostrava os modelos do provedor errado, e
escolher um deles dava 404 — porque aquele modelo não existe no provedor
selecionado.

Corrigido com uma flag de cancelamento (`let ativo = true` + `return () => {
ativo = false }`).

### 8.2 O `<select>` confiava na lista dinâmica

```tsx
{dynamicModels.length > 0 ? dynamicModels : provider.models}
```

Sempre que `dynamicModels` tinha qualquer conteúdo, ele ganhava — mesmo com
outro provedor selecionado. Agora os modelos são derivados **do provedor ativo**:

```tsx
const providerAtual = PROVIDERS.find(p => p.id === selectedProvider);
const modelosDisponiveis = providerAtual?.dynamic
  ? dynamicModels
  : (providerAtual?.models || []);
```

### 8.3 Modelo selecionado fora da lista

Ao trocar de provedor, o `value` do `<select>` podia não casar com nenhuma
`<option>` — o campo aparecia **em branco**, parecendo "não carregou". Agora a
troca de provedor também redefine o modelo.

---

## 9. Regras para não repetir isso

1. **Nunca copie IDs de modelo do `/models` sem testar.** Faça uma chamada de
   chat real (`tools/provar-modelos.cjs`).
2. **Sempre inclua um controle negativo** (modelo inexistente). Se ele passar, o
   endpoint não é confiável.
3. **Não confie só no código HTTP.** Exija JSON legível e conteúdo verificável.
4. **Provedores diferentes precisam de caminhos diferentes** (`/openai`,
   `/api`, `/paas/v4`). Errar isso gera 404 em massa.
5. **Mantenha o prefixo do ID** quando o provedor exigir (NVIDIA).
6. **Toda linha do tempo assíncrona precisa de guarda de cancelamento** ao trocar
   de contexto.
7. **Uma lista de modelos em dois arquivos vai divergir.** Rode
   `tests-manual/test_model_lists.py`.
8. **Antes de concluir "o modelo não existe", verifique a chave.** `401`
   (inválida) e `429/402` (sem saldo) parecem "modelo quebrado" para o usuário.

---

## 10. Não havia onde colar a chave da OpenAI (bug de interface)

Queixa do usuário: *"no projeto não tem onde inserir a chave do provedor openai"*.
Estava **certo** — e o mesmo valia para `opencode` e `openclaude`.

**Causa:** o modal *Chaves de API* monta um campo por item de `PROVIDERS`
(`PROVIDERS.filter(p => !p.dynamic)`). Esses três provedores **não existiam** em
`PROVIDERS`, então nenhum campo era renderizado. Agravante: todo o resto do
sistema já os suportava —

| Camada | Suportava? |
|--------|-----------|
| `backend/core/llm_native.py` (`get_client`) | ✅ `openai`, `opencode`, `openclaude` |
| `backend/routes/config.py` (`key_map`) | ✅ `OPENAI_API_KEY`, `OPENCODE_API_KEY`, `OPENCLAUDE_API_KEY` |
| `JarvisPage` — carga de chaves (`apiKeys`) | ✅ os nove provedores |
| `JarvisPage` — mapa de envio (`envKeyMap`) | ✅ os nove |
| **`JarvisPage` — `PROVIDERS` (os campos na tela)** | ❌ **faltavam três** |

Ou seja: o campo era a única peça ausente. Corrigido.

**Teste de regressão:** a seção 7 do `tests-manual/test_model_lists.py` compara
os provedores de `llm_native.py` com os da interface e **reprova** se algum ficar
sem campo — os dois lados não podem mais divergir.

### 10.1 "Salvo" não significa "funcionando"

A experiência que gerou o prejuízo de tempo: a chave era gravada com sucesso (a
tela dizia "salvo") e **só na hora de conversar** aparecia o erro — `401` chave
revogada, `402/429` conta sem saldo, `404` modelo extinto.

Foi criado o endpoint **`POST /api/config/testar-chave`** e um botão **"Testar"**
ao lado de cada chave. O teste:

- usa o **mesmo caminho de código do chat** (`core.llm_native.complete_chat`),
  então o veredito reflete a realidade e não uma verificação paralela;
- **não usa `/models`** de propósito — aquele endpoint mente (seção 2);
- traduz o erro técnico em algo acionável: *chave inválida*, *conta sem saldo*,
  *modelo extinto*, *sem conexão*.

Detalhe importante: `openclaude` **não é API na nuvem** — aponta para
`OPENCLAUDE_BASE_URL`, por padrão `http://localhost:4000/api/v1`. Sem esse
servidor local rodando, o erro é de conexão e **não** de chave.

---

## 11. Comandos rápidos

```bash
# As chaves que uso estao validas?
node tools/diagnostico-chaves.cjs

# Quais modelos funcionam DE VERDADE agora?
node tools/provar-modelos.cjs

# As listas do codigo batem com os catalogos reais?
node tools/modelos-atuais.cjs

# As listas do codigo estao coerentes entre si? (offline)
python tests-manual/test_model_lists.py
```

---

## Ver também

- [`../memory.md`](../memory.md) — regras e armadilhas do projeto
- [`CHARON-VOZ.md`](CHARON-VOZ.md) — a parte mais complexa do sistema (voz)
- [`../STATUS.md`](../STATUS.md) — histórico de sessões
- `tools/MODELOS-PROVADOS.md` — resultado bruto da última sondagem
