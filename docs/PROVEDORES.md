# DEEP-OS — Provedores de IA: comuns e personalizados

**Ultima atualizacao:** 2026-09-12

Este documento explica como o DEEP-OS lida com provedores de LLM: quais já vêm
prontos, como adicionar um novo **sem alterar código**, e as armadilhas que já
custaram tempo.

---

## 1. O problema que originou isso

Queixa do usuário:

> *"no projeto não tem onde inserir a chave do provedor openai"*
> *"pode inserir outros provedores ou uma opção para que eu crie provedores novos,
> pois sempre tem provedores novos; já deixa no projeto os mais comuns incluso"*

Ele estava **certo**, e a falha era pior do que parecia:

| Camada | Suportava `openai` / `opencode` / `openclaude`? |
|--------|--------------------------------------------------|
| `backend/core/llm_native.py` (`get_client`) | ✅ |
| `backend/routes/config.py` (`key_map`) | ✅ |
| `JarvisPage` — carga de chaves (`apiKeys`) | ✅ |
| `JarvisPage` — mapa de envio (`envKeyMap`) | ✅ |
| **`JarvisPage` — `PROVIDERS` (os campos da tela)** | ❌ **faltavam os três** |

O modal de chaves é montado a partir de `PROVIDERS`. Como esses três não estavam
lá, **nenhum campo era renderizado** — não havia onde colar a chave da OpenAI,
apesar de todo o resto do sistema já funcionar.

A correção foi adicioná-los, **mas a causa raiz era arquitetural**: adicionar um
provedor exigia editar quatro lugares, e esquecer um deles produz uma falha
silenciosa. Por isso nasceu o registro.

---

## 2. Arquitetura atual

```
backend/core/provedores.py            ← o registro
├── PRESETS ......................... provedores comuns (no código, estáveis)
└── config/provedores_custom.json ... provedores criados pelo usuário (fora do git)

backend/routes/config.py              ← a API
├── GET    /api/config/provedores           (comuns + personalizados)
├── POST   /api/config/provedores            (criar/editar)
├── DELETE /api/config/provedores/{id}       (remover)
└── POST   /api/config/provedores/modelos    (buscar modelos do provedor)
```

**A interface não tem mais lista própria de provedores para os campos de chave:**
ela usa a lista do backend. Assim, um provedor novo no registro **aparece
sozinho** — sem alterar o frontend.

### Como um provedor novo funciona sem código novo

`get_client` consulta o registro antes de desistir:

```python
meta = provedores.resolver(provider)      # PRESETS ou provedores_custom.json
if meta and meta.get("base_url"):
    return AsyncOpenAI(base_url=meta["base_url"], api_key=chave, ...)
```

A chave é lida de `<ID>_API_KEY` no `.env` e de `<id>_api_key` no
`api_keys.json` — o padrão é derivado do identificador, então o salvamento
também funciona sem alteração de código.

---

## 3. Provedores comuns inclusos (25)

### Já existiam
`gemini` · `openai` · `openrouter` · `groq` · `nvidia` · `zhipu` · `mimo` ·
`opencode` · `openclaude` · `ollama` · `llamacpp`

### Adicionados nesta sessão
| Provedor | URL base |
|----------|----------|
| `deepseek` | `https://api.deepseek.com/v1` |
| `xai` (Grok) | `https://api.x.ai/v1` |
| `mistral` | `https://api.mistral.ai/v1` |
| `anthropic` | `https://api.anthropic.com/v1/` ⚠️ ver nota |
| `together` | `https://api.together.xyz/v1` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` |
| `cerebras` | `https://api.cerebras.ai/v1` |
| `perplexity` | `https://api.perplexity.ai` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` |
| `hyperbolic` | `https://api.hyperbolic.xyz/v1` |

### Servidores locais (compatíveis com OpenAI)
| Provedor | URL base | Observação |
|----------|----------|------------|
| `lmstudio` | `http://localhost:1234/v1` | LM Studio |
| `vllm` | `http://localhost:8000/v1` | vLLM |
| `textgenwebui` | `http://localhost:5000/v1` | text-generation-webui |
| `jan` | `http://localhost:1337/v1` | Jan |

Servidores locais **não exigem chave** (o cliente envia `local` automaticamente)
e, claro, só funcionam na máquina onde o servidor roda — não no VPS headless.

> ⚠️ **Nota sobre a Anthropic:** ela tem API própria (`/v1/messages`). A entrada
> usa a camada compatível com o SDK do OpenAI. Se não funcionar, use Claude via
> **OpenRouter**, que é o caminho mais confiável.

> ⚠️ **Os modelos dos provedores novos NÃO foram verificados** — não temos chaves
> deles. Use o botão **Modelos** (carrega a lista do próprio provedor) e depois
> **Testar** para confirmar o que você for usar. Ver `docs/MODELOS.md`.

---

## 4. Como usar na interface

**Jarvis → ⚙️ Configurações → Chaves de API.** Cada provedor tem três botões:

| Botão | O que faz |
|-------|-----------|
| **Salvar** | Grava a chave no `.env` e no `api_keys.json` (só aquele provedor) |
| **Modelos** | Pergunta ao provedor quais modelos ele tem e preenche a lista |
| **Testar** | Faz uma **chamada de chat real** e diz se a chave funciona |
| **X** | Remove (aparece só nos provedores criados por você) |

### Criar um provedor novo

Clique em **+ Adicionar provedor** e informe:

| Campo | Exemplo |
|-------|---------|
| **Nome** | `Meu Provedor` |
| **URL base** | `https://api.exemplo.com/v1` |
| **Chave** | `sk-...` |

O que acontece: o provedor é registrado, a chave é salva e a lista de modelos é
**buscada automaticamente**. Depois clique em **Testar** para confirmar.

Serve para **qualquer** serviço que fale a API do OpenAI — inclusive servidores
locais e qualquer provedor novo que apareça no futuro. **Sem deploy.**

Se você não souber os nomes dos modelos: crie o provedor, clique em **Modelos**,
escolha um e clique em **Testar**.

---

## 5. Por que "Testar" é indispensável

Uma chave **salva** não é uma chave **funcionando**. Os quatro casos já
encontrados de verdade neste projeto:

| Resposta | Significado | Ação |
|----------|-------------|------|
| `401 Incorrect API key` / `User not found` | chave inválida ou revogada | gerar nova |
| `402/429 Insufficient balance` | conta sem saldo | recarregar |
| `404 Model not found` | modelo extinto | escolher outro |
| erro de conexão | servidor local não está rodando | subir o servidor |

O teste usa o **mesmo caminho de código do chat** (`complete_chat`), então o
veredito reflete a realidade — e **não** usa `/models`, que mente (ver
`docs/MODELOS.md` seção 2).

---

## 6. Armadilhas registradas

1. **`openai`, `opencode`, `openclaude` sem campo na interface.** O modal é
   montado a partir de `PROVIDERS`; faltar um item = não há onde colar a chave.
   *Agora a lista vem do backend.*
2. **O `/models` mente.** O do OpenRouter é **público** (aprova chave falsa) e o
   da NVIDIA lista modelos que a conta não tem. Por isso o botão **Modelos**
   marca `confiavel: False` para esses dois e avisa na tela.
3. **Todo provedor precisa do seu prefixo de caminho.** Groq `/openai/v1`,
   OpenRouter `/api/v1`, Zhipu `/api/paas/v4`, OpenCode `/zen/v1`.
4. **A URL base costuma terminar em `/v1`.** Sem isso, 404 em tudo.
5. **Nome do provedor vira nome de variável de ambiente.** `slug()` remove
   acentos e caracteres inválidos: "Configuração Nova" → `configuracao_nova`.
   Nome que colida com um provedor existente é **recusado**.
6. **Remover um provedor não apaga a chave.** Recriar com o mesmo nome volta a
   funcionar sem redigitar — evita perda por clique errado.
7. **Salvar e testar são separados de propósito.** Testar durante o salvamento
   faria "salvar" falhar por rede instável.

---

## 7. Para desenvolvedores

**Adicionar um provedor comum ao código** (só se for estável e amplamente usado):
acrescente uma entrada em `PRESETS` (`backend/core/provedores.py`). Nada mais.

**Onde NÃO é preciso mexer:** `get_client`, `key_map`, `_load_key_from_file` —
todos consultam o registro.

**Testes:**
```bash
python tests-manual/test_provedores.py     # registro, slug, criar/remover, get_client
python tests-manual/test_model_lists.py    # todo provedor do backend tem campo na tela
```

---

## Ver também

- [`MODELOS.md`](MODELOS.md) — por que modelos davam 404, o `/models` que mente, estado de cada provedor
- [`../memory.md`](../memory.md) — regras e armadilhas do projeto
- [`../STATUS.md`](../STATUS.md) — histórico de sessões
