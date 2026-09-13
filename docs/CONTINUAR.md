# DEEP-OS — Como continuar (handoff)

**Atualizado:** 2026-09-13, fim da sessão 50 (Charon/VPS, identidade, GPU, monitor)

Este arquivo existe para que **outro modelo de IA continue o trabalho sem
depender do histórico da conversa**. Leia isto primeiro, depois `memory.md`.

> ### ⏭️ PARA AMANHÃ (o que fazer primeiro)
>
> 1. **Subir o deploy do VPS** — comandos logo abaixo, na seção 1.
>    A VPS está em `73d139c`; o PC está em `f725228` (o gêmeo em `3d7a751`).
>    Sem isso o usuário **não tem** nenhuma das correções desta sessão.
> 2. **Atenção ao nginx:** ele mudou nesta rodada (ganhou o `/monitor`). Rode
>    `nginx -t` ANTES do reload — config quebrada derruba o site.
> 3. **O usuário precisa testar no navegador** (não deu para testar tudo hoje):
>    monitor de CPU/RAM/VRAM, escolha de contexto, `<ctrl46>`, identidade
>    separada e o novo layout do Jarvis. Ver seção 6.1.

---

## 1. Estado atual (confira antes de agir)

| | Commit | Onde |
|---|--------|------|
| **DEEP-OS** (principal) | `f725228`+ | `C:\DEEP-OS`, branch `master` |
| **DEEP-OS-LOCAL** (gêmeo) | `3d7a751`+ | `C:\DEEP-OS-LOCAL`, branch `main` |
| **VPS** | `d08de05` | `/root/DEEP-OS` ✅ **deployado** |

Suíte: **25/25 nos dois**. `tsc` limpo, build OK.

> ### ⚠️ O NGINX NAO E INSTALADO PELO DEPLOY (leia antes de mexer em rota)
>
> - A config **REAL** da VPS e **`/etc/nginx/sites-enabled/deepos`**, escrita a
>   mao. Ela tem TLS, `server_name` e `root /var/www/deep-os/frontend/dist-saas`.
> - `nginx/vps-nginx.conf` (no projeto) e **so referencia** e ja divergiu (aponta
>   para o Vite na 5176, tem `server_name` e certificado `-0001` diferentes).
>   **NUNCA** substitua o arquivo real por ele.
> - `scripts/deploy-faf8f93.sh` publica o frontend e faz `systemctl reload`, mas
>   **nao instala config de nginx**.
>
> Consequencia real (aconteceu): o `/monitor` foi adicionado no arquivo do
> projeto, o deploy subiu, e as barras de CPU/RAM/VRAM ficaram vazias — porque o
> pedido caia no `location /` (SPA fallback) e voltava `index.html` com **HTTP
> 200**. O `fetch` "dava certo", o `.json()` falhava e o sintoma nao apontava
> para o nginx.
>
> **O deploy agora AVISA** (passo 7b): testa `/monitor`, `/llamacpp/models` e
> `/ollama/status` e diz quais nao chegam ao backend.

### Rotas que o nginx precisa encaminhar (confira depois de qualquer mudanca)

| Rota | Para que serve | Status na VPS |
|---|---|---|
| `/monitor` | barras de CPU/RAM/VRAM | ✅ aplicada em 13/09 |
| `/llamacpp/models` | lista de modelos GGUF | ❌ **faltando** (lista vazia pelo site) |
| `/ollama/status` | lista de modelos do Ollama | ❌ **faltando** |

Para adicionar (troque `ROTA` pelo caminho, **antes** do `location / {`):

```
printf '    location ROTA/ {\n        proxy_pass http://127.0.0.1:8001;\n        proxy_set_header Host $host;\n    }\n\n' > /tmp/r.conf
```

Depois insira `r` na linha anterior ao `location / {` e **sempre** valide:
```
nginx -t && systemctl reload nginx
```

### Como subir na VPS (console Hostinger — ele embaralha texto longo: va em blocos)

**Bloco 1:**
```
cd /root/DEEP-OS
```

**Bloco 2** (leva 1 a 3 min; o script ja faz `git fetch` e o reset sozinho):
```
bash scripts/deploy-faf8f93.sh
```

No fim da saida, confira `commit publicado : <sha>` e
`backend : active (deepos-backend.service)`, e olhe o passo **7b** (rotas do
nginx).

**Depois, no PC**, para provar que o bundle publicado tem o codigo novo:
```powershell
cd C:\DEEP-OS
node tools\verificar-deploy.cjs
```
Ele procura marcas do codigo novo dentro do JS publicado **e testa a rota
`/monitor` de verdade** (exige JSON, nao so HTTP 200 — HTML com 200 e reprovado).

Para conferir se a VPS está em dia: `git -C /root/DEEP-OS log --oneline -1`


Para atualizar a VPS:

```
cd /root/DEEP-OS
git fetch origin master
git reset --hard origin/master
```
```
cd /root/DEEP-OS && bash scripts/deploy-faf8f93.sh
```

Depois do deploy, **confirme que o código subiu** (o "HTTP 200" do script não
prova isso):

```powershell
cd C:\DEEP-OS
node tools\verificar-deploy.cjs
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
.\venv\Scripts\python.exe tests-manual\run_all.py     # 21 arquivos, todos devem passar
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

## 5. O que foi resolvido na sessão 50 (não refaça)

Sessão focada no **Charon** (voz). Três coisas, todas com teste próprio:

### 5.1 `<ctrl46>` — o Charon "para de responder e não retorna"

**O relato (print do painel do usuário):**

```
⚡ Charon  19:33:17  <ctrl46>
⚡ Charon  19:33:17  <ctrl46>
```

…e daí não saía nada. Não era sempre — "às vezes".

**O que era.** `<ctrl46>` **não é texto do DEEP-OS**: é um *token de controle*
interno do Gemini (`<ctrlN>`). Nos modelos Live *preview* a geração às vezes
degenera, o token **vaza como texto** na `output_transcription` e o turno fecha
com **zero voz e zero texto real**. Como **não havia erro nenhum**, nada
disparava a reconexão automática: ele ficava mudo para sempre.

**O que foi feito (em `backend/routes/voice_ws.py`):**

1. `_TOKEN_CONTROLE` + `_limpar_tokens_controle()` — o token é **filtrado** e
   nunca mais chega ao painel;
2. contadores de saúde **por turno** (`_turno_bytes_audio`, `_turno_texto_real`,
   `_turno_tokens_controle`) e `_iniciar_turno()`;
3. `_fechar_turno()` — turno que fecha sem áudio e sem texto é **falha
   detectada**:
   - **1ª falha** → `_recuperar_turno('pedir_de_novo')`: pede ao modelo para
     responder de novo;
   - **2ª falha seguida** → `_recuperar_turno('reconectar')`: **reabre a sessão**
     (estado do Gemini corrompido) e reenvia o contexto (`restaurar_contexto=True`);
4. **barge-in não conta como falha** (turno interrompido fecha sem áudio de
   propósito) e turno com áudio zera o contador.

**Bug sério achado de quebra:** `_reconnect()` montava a instrução do sistema
**só com a voz** — sem fuso, idioma e **sem as instruções personalizadas** (de
onde vem o nome do usuário). Ou seja: **toda reconexão fazia o Charon esquecer
quem era o usuário**. Agora `start()` guarda `_user_tz` / `_user_locale` /
`_extra_prompt` e a reconexão reusa.

Teste: `tests-manual/test_charon_barge_in.py`, seção 8 (comportamental, instancia
a sessão de verdade e reproduz o turno só com `<ctrl46>`).

### 5.2 Charon não inicia sozinho — o usuário ESCOLHE o contexto

**Pedido literal:** *"quando clicar no menu charon eu escolho do lado direito no
workspace novo chat ou clico em algum historico registrado das conversas
anteriores para que ele ja comece com um novo contexto ou com aquele contexto
salvo do historico selecionado, igual aqui no nosso painel DSH LOCAL"*;
*"não faz nenhuma das duas até eu escolher"*; e:

> "exemplo 1 nova conversa → charon ja começa automaticamente
> 2 se eu escolher um dos historicos ele ja começa sabendo de todo o conteudo
> daquele historico e ja pergunta de onde quer continua"

**Antes:** ao abrir a página o Charon **ligava sozinho** (timer de 1 s + listener
do primeiro gesto) e cumprimentava, sem o usuário ter escolhido nada.

**Agora (`frontend/src/components/saas/CharonPage.tsx`):**

- **auto-start removido** (timer e listeners de gesto);
- novo estado `modoInicio: 'escolher' | 'novo' | 'historico'` — a página abre em
  **`'escolher'`** e o Charon fica **parado**;
- tela de escolha no painel direito (e um `+ Novo chat` **explícito** no topo da
  árvore, ao lado dos workspaces — antes era um `+` solto no canto que passava
  despercebido);
- **`+ Novo chat`** → `createConversation(..., assistantName)` + conecta
  **automaticamente**, sem histórico → o backend **cumprimenta**;
- **clique numa sessão da árvore** → carrega `getTranscripts(convId)`, manda como
  `history` e **reconecta** → o backend reenvia o contexto e **pergunta de onde
  continuar**;
- `entrarNaConversa()` centraliza "trocar contexto = reconectar" (usado pelos
  dois caminhos);
- apagar a conversa em uso volta para a tela de **escolha** (não liga sozinho).

No backend, `_pedir_retomada()` foi reescrito para **terminar com uma pergunta
sobre o histórico** ("de onde quer continuar"), continuando proibido se
reapresentar ou resumir tudo.

Teste: `tests-manual/test_charon_historico.py`, seção 7.

### 5.3 `TranscriptEntry` duplicado no CharonPage

Havia um `interface TranscriptEntry` **local** (mesmos 3 campos) sombreando o
tipo importado do `chatStorage` → erro `TS2440`. Removido: **um lugar só**.
(É a armadilha nº 0 deste documento acontecendo de novo.)

### 5.4 Ferramentas por ambiente — o Jarvis não filtrava o que a VPS não tem

**Pedido:** *"este projeto `C:\DEEP-OS` sendo executado pelo arquivo
`start-saas.bat` poderia ter as duas funções: no vps funcionar somente as
ferramentas que funciona no vps e no local funcionar todas as ferramentas"*.

**O que já existia (e o usuário não sabia — foi por isso que ele criou o
gêmeo):** `is_headless()` responde "tem tela aqui?" — no Windows é sempre
`False`; no Linux é `True` quando não há `DISPLAY`/`WAYLAND_DISPLAY` (a VPS).
**O mesmo código já se comportava diferente por ambiente.**

**O defeito:** o filtro existia em **UM lugar só** — `_HEADLESS_EXCLUDED` em
`routes/voice_ws.py`, que vale para o **Charon (voz)**. O **Jarvis (texto) não
filtrava nada**. Na VPS ele oferecia `open_app`, `desktop_control`,
`browser_control`… e elas **falhavam na execução**: `pyautogui` levanta
`KeyError: 'DISPLAY'` (não `ImportError`) e `mss` não tem tela para capturar.

**Correção escolhida (Opção A):**

- `tools/function_defs.py` passou a ter a **fonte única**:
  `FERRAMENTAS_COM_GUI` (12 nomes) + `filtrar_tools_sem_gui(tools, headless=None)`;
- o Charon agora faz `_HEADLESS_EXCLUDED = FERRAMENTAS_COM_GUI` (a lista **é** a
  única, não uma cópia — que divergiria);
- `routes/chat.py` monta `TOOLS_DO_AMBIENTE` e usa nos **dois** caminhos
  (`call_model_stream` e o loop de tarefas); `LOCAL_TOOLS` sai dele também.

**Números medidos:** Jarvis **58** tools no PC → **46** na VPS.
Charon **26** tools no PC → **18** na VPS. As 12 que saem: `open_app`,
`close_app`, `computer_settings`, `computer_control`, `desktop_control`,
`screen_process`, `browser_control`, `game_updater`, `send_message`,
`upload_video`, `media_play`, `explorer`.

**O parâmetro `headless` existe por um motivo específico:** no Windows
`is_headless()` é sempre `False`, então **sem ele não haveria como testar no PC
o caminho que só roda na VPS** — e caminho que só roda em produção é justamente
o que costuma estar errado. Com ele, o teste força os dois cenários.

Teste: `tests-manual/test_tools_headless.py` (seis blocos, incluindo "nenhum
caminho ficou usando a lista crua" — a armadilha nº 4).

**Armadilha nova encontrada no caminho:** o `run_all.py` tinha **lista fixa** de
testes. Eu criei `test_tools_headless.py`, rodei sozinho (passou) e a suíte
continuou dizendo "20 testes", **sem ele**. Agora o runner avisa sozinho quais
arquivos `test_*.py` existem na pasta e **não** estão na lista. Teste que não
roda não protege nada.

---

## 6. O que está PENDENTE

### 6.1 Falta testar (depende do usuário, precisa dele)

- **Charon: a tela de escolha** (novo em 4.2). Abrir o Charon e conferir que ele
  **não liga sozinho**; clicar em `+ Novo chat` e ouvir a saudação; clicar numa
  sessão da árvore e conferir que ele **começa sabendo daquele assunto e pergunta
  de onde continuar**. Nada disso foi verificado com microfone real.
- **Charon: o `<ctrl46>`** (4.1). O teste prova a lógica com turno simulado, mas
  só o uso real confirma que a recuperação pega o caso de verdade.
- **Voz do Charon com microfone**: saudação curta e interrupção falando por
  cima. Nada disso foi verificado com áudio real — eu não consigo.
- **Firefox**: microfone (a permissão foi bloqueada pelo auto-start antigo — que
  agora **não existe mais**, então vale retestar; o clique em `+ Novo chat` ou na
  sessão já é o gesto que o Firefox exige).
- **Lembretes** ponta a ponta pela interface; **PIX/QRCode**; conversas e
  documentos.
- **Workspaces e download do histórico**: abrir uma conversa antiga e conferir se
  as mensagens voltam; clicar na seta e conferir o `.md`.

### 6.2 Problema conhecido, NÃO corrigido

**O erro de uma tentativa recuperada aparece como se fosse o resultado.**
No print do usuário, o painel central mostrou `Erro na API: 429` (cota do
Gemini) enquanto o painel direito mostrava a execução bem-sucedida e
"Resposta concluida, 86 tokens". A resposta boa existe, mas o erro fica por
cima.

Causa provável: em `JarvisPage.tsx`, o evento `error` faz
`fullAnswer += '\n\nErro: ...'`, e o `done` só substitui se `event.answer`
existir. Se o erro chega depois do `done`, ele permanece.

---

### 6.2.1 ⚠️ MAIS GRAVE: o modelo INVENTA o ambiente quando não tem ferramentas

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

### 6.2.2 A cota gratuita do Gemini (5 req/min) inviabiliza tarefas

Com `gemini-2.5-flash` no plano gratuito o limite é **5 requisições por minuto**,
e o loop de tarefas faz **uma por passo**. Uma pergunta que executa 4 comandos
estoura sozinha, e o usuário vê `429`.

**Orientação ao usuário:** usar **Groq `openai/gpt-oss-120b`** para tarefas com
ferramentas — é o padrão do DEEP-OS e não tem essa cota. Gemini segue bom para
conversa.

**Melhoria possível no código:** tratar `429` como "aguarde e tente de novo"
(respeitando o `retryDelay` que a própria resposta traz) em vez de devolver o erro
cru como texto na conversa.

### 6.3 Segurança (depende do usuário — não são bugs)

- Trocar a **senha de root do VPS** (foi exposta em conversa).
- Trocar o **`MASTER_PASSWORD`** (ainda é `admin123@`).
- Definir **`JWT_SECRET`** por variável de ambiente.
- `systemctl mask deep-os-backend` — blinda a unit duplicada que já brigou pela
  porta 8001.

### 6.4 Chaves que precisam de ação do usuário

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

## 7. Armadilhas que já custaram tempo (leia antes de editar)

0. **⚠️ A PIOR: código duplicado — corrija nos DOIS (ou nos TRÊS) lugares.**
   Já causou quatro bugs nesta sessão, todos do mesmo tipo: eu conserto um lugar
   e esqueço o outro, que é uma cópia.
   - `carregandoConversaRef` (trava da corrida carregar/salvar): existe no
     **JarvisPage** e no **CharonPage**. Eu pus só no Jarvis e o Charon
     **apagava o histórico** a cada abertura.
   - fallback de tool-call em texto: `stream_chat_with_tools` **e**
     `complete_chat_with_tools` — só um tinha, e o modelo "anunciava e não fazia".
   - `self._interrupted = False`: estava em **dois** caminhos de alta frequência
     (loop de recebimento **e** `send_audio`).
   - `createConversation`: **três** pontos criam conversa (botão `+`,
     auto-create da primeira mensagem, e o fallback da exclusão).
   **Antes de fechar qualquer correção, procure as cópias.** `grep` pelo nome da
   função/variável que você acabou de mudar.

1. **Rotas FastAPI resolvem por ordem de registro.** Catch-all `/{param}` sempre
   por último. Já causou o vazamento de identidade entre tenants.
2. **`/models` MENTE.** O do OpenRouter é público (aprova chave falsa) e o da
   NVIDIA lista modelos que a conta não tem. Só a chamada de chat prova.
3. **O delimitador DSML é U+FF5C** (barra vertical de largura total), não `|`.
4. **Caminhos com e sem streaming precisam ter a mesma capacidade.**
5. **Testes desta suíte se enganam lendo COMENTÁRIO/DOCSTRING como código** —
   aconteceu 5 vezes. Sempre remova comentários antes de procurar texto.
6. **Regra que depende de disciplina vai ser quebrada** (inclusive por mim, na
   mesma sessão em que a escrevi). Prefira fazer a FERRAMENTA recusar.
7. **Os dois projetos têm `venv` em pastas diferentes** — confira antes de passar
   comando ao usuário. Na VPS é `/root/DEEP-OS/venv/bin/python`.
8. **Cada tenant tem banco PRÓPRIO.** `data/interactions.db` é o padrão;
   `data/tenants/{tenant_id}/database.sqlite` é o do usuário. Limpar só o
   primeiro não limpa "o histórico" — eu disse isso errado uma vez. Use
   `tools/limpar-historico.py` (lista todos, e limpa com `--limpar`) ou a ação
   "Limpar tudo" na interface, que passa pelo middleware e acerta o banco certo.
9. **O nginx só encaminha `/api/ /auth/ /chat/ /voice/ /admin/ /ws/`.** Rota nova
   fora disso responde 200 com o HTML do frontend — o frontend leria como
   sucesso sem nada ter acontecido. Por isso existe `/api/history` **e**
   `/history`. Ao criar rota que o **navegador** vai chamar, use prefixo `/api/`.
10. **Efeito que carrega e efeito que salva, ambos dependendo do mesmo id, rodam
    no MESMO commit** — e o de salvar enxerga o estado ANTERIOR. É a corrida que
    apagou histórico duas vezes (Jarvis e Charon). Trave com um `useRef`.
11. **Tipo/constante duplicado em dois arquivos sombreia o importado.** O
    `CharonPage.tsx` tinha um `interface TranscriptEntry` local igual ao do
    `chatStorage` → `TS2440`, e uma mudança no formato gravado não alcançava o
    arquivo. Se `tsc` acusar "conflicts with local declaration", é isto.
12. **Recuperar de turno vazio não pode confundir com barge-in.** Turno
    interrompido fecha sem áudio **de propósito** — se contar como falha, o
    Charon reabre sessão toda vez que o usuário fala por cima. Ver `_fechar_turno`.
13. **Ao fechar um turno sem `turn_complete`, o texto do turno fica "colado" no
    próximo** — e um turno vazio passaria por saudável, escondendo a falha. Por
    isso `_iniciar_turno()` é chamado também quando o usuário começa a falar
    (`send_audio` com silêncio > 0,5 s e `input_transcription`).
14. **Teste que não está no `run_all.py` não existe.** A lista de testes é fixa:
    um arquivo novo passa quando rodado na mão e nunca mais roda na suíte (já
    aconteceu — ver 5.4). O runner agora avisa quais `test_*.py` ficaram de fora.
15. **Caminho que só executa em produção é onde o bug se esconde.** O filtro
    headless nunca rodava no PC (no Windows `is_headless()` é sempre `False`).
    Por isso `filtrar_tools_sem_gui()` aceita `headless=` explícito: sem esse
    parâmetro, o comportamento da VPS não teria como ser testado antes do deploy.

---

## 8. Como o usuário trabalha (para não atrapalhar)

- Ele **roda os comandos no VPS** e cola a saída. O console da Hostinger
  **embaralha textos longos** → mande blocos de 2-3 linhas.
- Ele **testa no navegador** e cola os dois painéis (chat + atividade). Os prints
  dele foram decisivos em quase todos os bugs desta sessão.
- Ele **valoriza documentação** e atualiza `STATUS.md`/`memory.md` a cada sessão.
- Ele **prefere honestidade a otimismo**: quando eu errei (quebrei uma função
  editando rápido, criei um bug no painel, passei o caminho errado do venv), dizer
  claramente foi melhor do que disfarçar.
