# DEEP-OS — Como continuar (handoff)

**Atualizado:** 2026-09-12, fim da sessão 49

Este arquivo existe para que **outro modelo de IA continue o trabalho sem
depender do histórico da conversa**. Leia isto primeiro, depois `memory.md`.

---

## 1. Estado atual (confira antes de agir)

| | Commit | Onde |
|---|--------|------|
| **DEEP-OS** (principal) | `0977ff8` + o commit dos workspaces | `C:\DEEP-OS`, branch `master` |
| **DEEP-OS-LOCAL** (gêmeo) | sincronizado no mesmo dia | `C:\DEEP-OS-LOCAL`, branch `main` |
| **VPS** | `742f376` | `/root/DEEP-OS` |

⚠️ **A VPS está ATRASADA.** Os commits do histórico das conversas e dos
workspaces **ainda não foram para produção**. Para atualizar:

```
cd /root/DEEP-OS
git fetch origin master
git reset --hard origin/master
```
```
cd /root/DEEP-OS && bash scripts/deploy-faf8f93.sh
```

---

## 2. REGRA Nº 1 — dois projetos gêmeos

Está detalhada no topo do `AGENTS.md` e em `docs/DOIS-PROJETOS.md`. Resumo:

- **Toda alteração em `C:\DEEP-OS` vai também para `C:\DEEP-OS-LOCAL`** (e
  vice-versa). São **repositórios separados**, com branches diferentes
  (`master` e `main`) e **um push não atualiza o outro**.
- **Nunca** `git reset --hard` entre eles. Use o procedimento:
  ```powershell
  cd C:\DEEP-OS
  git log --oneline -5                      # ache o commit ANTERIOR à mudança
  python tools\comparar-local.py <commit>   # se acusar DIFERENTE, PARE
  python tools\aplicar-no-local.py <commit> # a ferramenta ABORTA se houver divergência
  ```
- Ambientes diferentes: a VPS é Linux **headless com 4 GB**, o LOCAL é Windows
  **com desktop e GPU**. Bug de proxy/`Host`/401 só aparece na VPS; ferramenta de
  GUI só funciona no LOCAL.

---

## 3. Como rodar os testes

O venv fica em **pastas diferentes** — erro que já cometi:

| Onde | Python |
|------|--------|
| DEEP-OS no PC | `C:\DEEP-OS\venv\Scripts\python.exe` |
| DEEP-OS-LOCAL | `C:\DEEP-OS-LOCAL\backend\venv\Scripts\python.exe` |
| **VPS** | `/root/DEEP-OS/venv/bin/python` |

```powershell
cd C:\DEEP-OS
.\venv\Scripts\python.exe tests-manual\run_all.py     # 20 arquivos, todos devem passar
```

---

## 4. O que foi resolvido na sessão 49 (não refaça)

Ordem cronológica, com a causa real de cada um:

| # | Sintoma relatado | Causa real |
|---|---|---|
| 1 | Chave de API não salvava no `.env` | placeholder `***saved***` sobrescrevia a chave + `401` do middleware invisível na VPS |
| 2 | Modelos dando 404 | IDs extintos, listas divergentes entre 2 arquivos, `zhipu` fora do seletor |
| 3 | Charon não parava de falar | `_interrupted = False` em **dois** pontos de alta frequência |
| 4 | Saudação inicial longa | gatilho era convite aberto ("diga como pode ajudar") |
| 5 | Sem campo para a chave da OpenAI | lista que monta os campos não tinha `openai`/`opencode`/`openclaude` |
| 6 | Sem poder criar provedor | criado registro em `core/provedores.py` (25 comuns + personalizados) |
| 7 | Voz robótica | o regex de limpeza **apagava a letra "ã"** (U+00E3 na lista de remoção) |
| 8 | Barras de velocidade/tom sem efeito | `rate`/`pitch` fixos no backend; só o `speakBrowser` os recebia |
| 9 | Charon sem memória do histórico | o Gemini guarda o estado **no servidor dele**; o frontend nunca enviava |
| 10 | "Fala que vai fazer e não faz" | **três** portas: DSML desconhecido, fallback ausente no não-streaming, e classificação que nem oferecia ferramentas |
| 11 | `<｜DSML｜…>` vazando na tela | a limpeza existia só no texto **final**, não no **fluxo** |
| 12 | Barras do painel girando sem parar | eu marquei `thinking` como `running` e nada fechava |
| 13 | Duração das ferramentas sempre `0ms` | início guardado por NOME; 4× `bash` sobrescrevia |
| 14 | Histórico não aparecia | **as mensagens do chat nunca eram salvas** — não existia `getMessages`/`saveMessages` |
| 15 | Workspaces (pedido novo) | agrupamento por raiz, discreto |

Documentos criados: `docs/FERRAMENTAS.md`, `docs/MODELOS.md`,
`docs/PROVEDORES.md`, `docs/DOIS-PROJETOS.md`, `docs/CONTINUAR.md` (este).
Regras 25 a 56 no `memory.md`.

---

## 5. O que está PENDENTE

### 5.1 Falta testar (depende do usuário, precisa dele)

- **Voz do Charon com microfone**: saudação curta e interrupção falando por
  cima. Nada disso foi verificado com áudio real — eu não consigo.
- **Firefox**: microfone (a permissão foi bloqueada pelo auto-start antigo).
- **Lembretes** ponta a ponta pela interface; **PIX/QRCode**; conversas e
  documentos.
- **Workspaces e download do histórico** (acabou de ser implementado): abrir
  uma conversa antiga e conferir se as mensagens voltam; clicar na seta e
  conferir o `.md`.

### 5.2 Problema conhecido, NÃO corrigido

**O erro de uma tentativa recuperada aparece como se fosse o resultado.**
No print do usuário, o painel central mostrou `Erro na API: 429` (cota do
Gemini) enquanto o painel direito mostrava a execução bem-sucedida e
"Resposta concluida, 86 tokens". A resposta boa existe, mas o erro fica por
cima.

Causa provável: em `JarvisPage.tsx`, o evento `error` faz
`fullAnswer += '\n\nErro: ...'`, e o `done` só substitui se `event.answer`
existir. Se o erro chega depois do `done`, ele permanece.

---

### 5.2.1 ⚠️ MAIS GRAVE: o modelo INVENTA o ambiente quando não tem ferramentas

**O que aconteceu (2026-09-12, 18:04).** O usuário escreveu `"ola groq"` — uma
saudação, então **corretamente** o DEEP-OS não ofereceu ferramentas. O modelo
respondeu sobre o ambiente com detalhes **completamente inventados**:

> "sandbox de contêiner Linux... usuário não-root... sem acesso a GPUs físicas...
> acesso externo à internet está bloqueado... /tmp ou /workspace"

**Nada disso é verdade.** O real é: Ubuntu 26.04.1, hostname `srv1951736`,
usuário `root`, 4 GB de RAM.

**Por que é pior que os outros defeitos desta sessão.** Os anteriores faziam o
modelo *não fazer* algo — visível e chato. Este faz o modelo **afirmar coisas
falsas com confiança**, e o usuário pode acreditar. Um assistente que inventa
fatos sobre o próprio ambiente é pior do que um que trava.

**Correção recomendada (2 partes).**

1. **Injetar o ambiente REAL no system prompt.** O backend já sabe tudo:
   `platform.system()`, `platform.release()`, `platform.machine()`,
   `socket.gethostname()`, `getpass.getuser()`, `os.cpu_count()`, total de RAM,
   `os.getcwd()` e `is_headless()`. Um bloco
   "AMBIENTE DE EXECUÇÃO (dados reais, verificados)" resolve o caso **sem
   precisar de ferramenta** — e é a resposta certa para uma pergunta informativa.
2. **Proibir invenção explicitamente.** Acrescentar ao system prompt: *"NUNCA
   invente dados sobre o sistema, hardware, ambiente, rede ou sandbox. Se a
   informação não estiver no bloco AMBIENTE DE EXECUÇÃO, diga que não sabe e
   ofereça verificar."* Modelos preenchem lacunas com plausibilidade; a instrução
   precisa ser explícita, como já foi necessário na saudação do Charon.

**Onde mexer:** o construtor do system prompt do chat (a função que monta
`system` em `backend/routes/chat.py`, e `backend/core/prompts.py`). No Charon,
`_build_system_instruction()` em `backend/routes/voice_ws.py` já tem um bloco de
modo headless — dá para reaproveitar a ideia.

**Teste sugerido:** em `tests-manual/`, conferir que o system prompt gerado
contém hostname, usuário e `is_headless()`, e que contém a proibição de inventar.
Assim a regressão é pega por teste, não por print do usuário.

---

### 5.2.2 A cota gratuita do Gemini (5 req/min) inviabiliza tarefas

Com `gemini-2.5-flash` no plano gratuito o limite é **5 requisições por minuto**,
e o loop de tarefas faz **uma por passo**. Uma pergunta que executa 4 comandos
estoura sozinha, e o usuário vê `429`.

**Orientação ao usuário:** usar **Groq `openai/gpt-oss-120b`** para tarefas com
ferramentas — é o padrão do DEEP-OS e não tem essa cota. Gemini segue bom para
conversa.

**Melhoria possível no código:** tratar `429` como "aguarde e tente de novo"
(respeitando o `retryDelay` que a própria resposta traz) em vez de devolver o erro
cru como texto na conversa.

### 5.3 Segurança (depende do usuário — não são bugs)

- Trocar a **senha de root do VPS** (foi exposta em conversa).
- Trocar o **`MASTER_PASSWORD`** (ainda é `admin123@`).
- Definir **`JWT_SECRET`** por variável de ambiente.
- `systemctl mask deep-os-backend` — blinda a unit duplicada que já brigou pela
  porta 8001.

### 5.4 Chaves que precisam de ação do usuário

| Provedor | Situação |
|---|---|
| Groq | ✅ válida |
| Gemini | ✅ válida, mas **cota gratuita de 5 req/min** — estoura em tarefas com várias ferramentas |
| NVIDIA | ✅ válida (alguns modelos dão 404 por falta de acesso na conta) |
| OpenAI | ❌ chave inválida |
| OpenRouter | ❌ `401 User not found` — a chave do `.env` é antiga; há 2 válidas no painel dele |
| Zhipu | ❌ conta sem saldo |
| MiMo | ❌ conta sem saldo |
| OpenCode | ❌ conta sem saldo |
| OpenClaude | aponta para servidor local (`localhost:4000`) |

**Para tarefas com ferramentas, use Groq `openai/gpt-oss-120b`** — é o que o
DEEP-OS usa como padrão e não tem a cota apertada do Gemini grátis.

---

## 6. Armadilhas que já custaram tempo (leia antes de editar)

1. **Rotas FastAPI resolvem por ordem de registro.** Catch-all `/{param}` sempre
   por último. Já causou o vazamento de identidade entre tenants.
2. **`/models` MENTE.** O do OpenRouter é público (aprova chave falsa) e o da
   NVIDIA lista modelos que a conta não tem. Só a chamada de chat prova.
3. **O delimitador DSML é U+FF5C** (barra vertical de largura total), não `|`.
4. **Caminhos com e sem streaming precisam ter a mesma capacidade** — foi essa
   assimetria que fez o modelo anunciar e não entregar.
5. **Testes desta suíte se enganam lendo COMENTÁRIO/DOCSTRING como código** —
   aconteceu 5 vezes. Sempre remova comentários antes de procurar texto.
6. **Regra que depende de disciplina vai ser quebrada** (inclusive por mim, na
   mesma sessão em que a escrevi). Prefira fazer a FERRAMENTA recusar.
7. **Os dois projetos têm `venv` em pastas diferentes** — confira antes de passar
   comando ao usuário.

---

## 7. Como o usuário trabalha (para não atrapalhar)

- Ele **roda os comandos no VPS** e cola a saída. O console da Hostinger
  **embaralha textos longos** → mande blocos de 2-3 linhas.
- Ele **testa no navegador** e cola os dois painéis (chat + atividade). Os prints
  dele foram decisivos em quase todos os bugs desta sessão.
- Ele **valoriza documentação** e atualiza `STATUS.md`/`memory.md` a cada sessão.
- Ele **prefere honestidade a otimismo**: quando eu errei (quebrei uma função
  editando rápido, criei um bug no painel, passei o caminho errado do venv), dizer
  claramente foi melhor do que disfarçar.
