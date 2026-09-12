# CHARON — Arquitetura da Voz (documentacao tecnica)

Documento de referencia da parte mais complexa do DEEP-OS. Atualizado na
sessao 48 (2026-09-11), depois de corrigir engasgo/corte de audio e o
microfone no Firefox.

> **Para quem for mexer:** leia as secoes 5 (armadilhas) e 8 (diagnostico)
> antes de alterar qualquer coisa. Cada numero ali foi ajustado por tentativa e
> erro em campo — nao sao arbitrarios.

---

## 1. Visao geral do fluxo

```
   MICROFONE (navegador)
        │  getUserMedia → AudioContext → AudioWorklet 'mic-proc'
        │  PCM16 mono, ~16 kHz (downsample 3x), chunks de 1024 amostras
        ▼
   WebSocket  /ws/voice?token=<JWT>          [wss://deep-os.tech/ws/voice]
        │  nginx → 127.0.0.1:8001  (Upgrade + Connection: upgrade)
        ▼
   BACKEND  routes/voice_ws.py
        │  VoiceSession: recebe bytes do cliente → Gemini Live
        │  E tambem: recebe audio/transcricao/tool_calls do Gemini → cliente
        ▼
   GEMINI LIVE API  (bidirecional, streaming de audio nativo)
        │  models/gemini-2.5-flash-native-audio-preview-12-2025
        ▼
   BACKEND (resposta)
        │  response.data = PCM16 @ 24 kHz mono
        │  send_bytes(pcm) → WebSocket
        ▼
   ALTO-FALANTE (navegador)
        AudioContext @ 24000 Hz → AudioWorklet 'playback-proc' → destino
```

**Pontos-chave:**
- O audio do **usuario** sobe a ~16 kHz; o audio do **Charon** desce a 24 kHz.
- O formato e **PCM16 little-endian, mono, sem cabecalho** (raw bytes).
- O WebSocket e o **unico** transporte de voz. `/voice/disconnect-all` (HTTP)
  forca reconexao quando a identidade muda.

## 2. Arquivos e responsabilidades

| Arquivo | Papel |
|---|---|
| `frontend/src/components/saas/CharonPage.tsx` | Interface, WebSocket, mic e playback (worklets inline) |
| `backend/routes/voice_ws.py` | Sessao de voz, integracao Gemini Live, tools, system instruction |
| `backend/config.py` (raiz) | `is_headless()`, `get_os()` |
| `backend/core/tenant_identity.py` | Tenant e **fuso** da conexao (ContextVar) |
| `backend/actions/*.py` | As tools que o Charon pode chamar |

## 3. Ciclo de vida de uma conexao

### 3.1 Cliente (`connectVoice`)
1. Frontend monta o worklet de playback (`setupPlayback`).
2. Abre `new WebSocket(getWsUrl())` — a URL inclui `?token=<saas_token>` para o
   backend identificar o **tenant**.
3. Em `onopen`, envia `{"type":"start", voice, assistant_name, user_name,
   timezone, locale}`.
4. Adquire o microfone (ver secao 6) e passa a enviar PCM.
5. `onclose` limpa tudo e, se nao foi desconexao manual, **tenta reconectar em
   3 s**.

### 3.2 Servidor (`voice_websocket`)
1. `ws.accept()`
2. Extrai o tenant de `?token=` (JWT) ou `?tenant_id=` →
   `set_current_tenant()`
3. Cria `VoiceSession`, registra em `_sessions` e grava `session._tenant_id`
4. No `start`: resolve a identidade, grava o fuso (`set_current_timezone`),
   derruba sessoes antigas e chama `session.start(...)`
5. Loop: bytes do cliente → Gemini; eventos do Gemini → cliente

### 3.3 Regra das sessoes
Ao receber `start`, o backend **encerra as outras sessoes ativas**
(`for old_sid ... await old_session.stop()`). Só uma voz por vez, de proposito:
evita dois Charons falando. O `_tenant_id` em cada sessao permite entregar
lembretes só ao assinante certo.

## 4. Os dois AudioWorklets (frontend)

### 4.1 `mic-proc` — captura
```
entrada: Float32 (taxa do dispositivo, tipicamente 48000)
ratio = 3           → downsample por media de 3 amostras
saida:   Int16 PCM, acumulado em chunks de 1024 amostras
```
Envia via `port.postMessage(chunk.buffer, [chunk.buffer])` (transferivel).
O `CharonPage` converte para `Uint8Array` e faz `ws.send`.

> Nota: `ratio = 3` de 48000 dá 16000 Hz — que é o esperado pelo Gemini.
> Se o dispositivo entregar 44100, o resultado fica ~14700 Hz e o Gemini ainda
> entende, mas a qualidade cai. E um ponto a observar em maquinas diferentes.

### 4.2 `playback-proc` — reproducao (ring buffer)
| Constante | Valor | Por que |
|---|---|---|
| `_ringSize` | **384000** amostras | 16 s a 24 kHz de margem |
| `_prebuf` | **36000** amostras | 1,5 s antes de comecar a tocar |
| `_underruns` | limite **5** | antes de re-armar o prebuffer |
| dedup | margem **6** chunks iguais | descarta repeticao do Gemini |

**Estado:** `_started` (false = tocando silencio e aguardando), `_available`
(amostras prontas), `_readPos`/`_writePos` (ring circular).

**Recuperacao de sub-run (correcao da sessao 48):** quando o ring esvazia e
ainda nao chegou audio novo, o worklet **nao** segue emitindo silencio. Apos 5
amostras sem dado ele volta a `_started = false` e espera o prebuffer encher de
novo. Antes disso, a cauda da ultima palavra era consumida em silencio (o
usuario ouvia a frase "cortada") e o meio da fala engasgava.

### 4.3 Fallback iOS
`ScriptProcessorNode` de 4096 amostras quando `audioWorklet` nao esta
disponivel (Safari antigo no iOS). Usa uma fila `Float32Array[]` simples, sem
ring buffer nem prebuffer — qualidade inferior, mas funciona.

## 5. ⚠️ ARMADILHAS (as mais caras de descobrir)

### 5.1 `Depends()` no default quebra o BOOT, nao a requisicao
`Depends(...)` dentro do valor default de um parametro e resolvido **no import
do modulo**, quando o FastAPI monta as rotas. Um `NameError` ali derruba o
`main.py` inteiro → uvicorn nao sobe → **502**. Foi a causa do incidente de
10/09 em `routes/chatbot.py`.

### 5.2 Ordem de registro de rotas (catch-all por ultimo)
Em `routes/config.py`, o catch-all `/{section}` estava **antes** de `/identity`
e capturava aquele path. Isso manteve o isolamento por tenant inacessivel por
HTTP por varias sessoes. **Rotas catch-all sempre no fim do arquivo.**

### 5.3 Firefox ≠ Chrome no audio
- **`AudioContext` com `sampleRate` forcado:** o Chrome reamostra; o **Firefox
  deixa o contexto SUSPENSO**. Resultado: o mic "conecta" mas entrega silencio.
  Por isso criamos **sem** forcar taxa:
  `new AudioContext()` e so caímos para `{sampleRate: micRate}` se falhar.
- **Gesto do usuario e obrigatorio** para liberar audio. Chamar
  `getUserMedia` sem interacao faz o Firefox responder `NotAllowedError` **e
  memorizar a negativa como bloqueio do site** — depois nem pergunta mais, mesmo
  num clique posterior. Por isso o auto-start usa
  `navigator.userActivation.hasBeenActive` e espera o primeiro clique.
- **Limpar o bloqueio:** cadeado 🔒 → Microfone → **Permitir** → recarregar.

### 5.4 Nao ha backpressure no envio de audio
O worklet do mic posta chunks continuamente; se o WebSocket estiver lento, a
fila cresce em memoria. Em sessoes muito longas isso pode pesar. O
`lastSendTimeRef` existe para detectar silencio, nao para limitar vazao.

### 5.5 O `sampleRate` do playback e fixo em 24000
`new AudioContext({ sampleRate: 24000 })` no `setupPlayback`. E a taxa do
Gemini. Se o Gemini mudar de modelo/formato, isso precisa acompanhar — nao ha
negociacao automatica.

### 5.6 Watchdogs assimetricos (corrigido na sessao 48)
O **playback** ja tinha auto-recuperacao do `AudioContext`; o **microfone nao
tinha nada**. Por isso, quando o navegador suspendia o contexto do mic (troca de
aba, economia de energia, bloqueio de tela no celular), a captura parava em
silencio e o Charon ficava "ouvindo" sem receber nada. Agora existe
`micWatchdogRef` (intervalo de 2 s) que:
- retoma o `AudioContext` quando fica `suspended`
- readquire a track quando o navegador dispara `ended`
- desiste se `startedRef` for `false` (evita laco infinito)

## 6. Aquisicao do microfone (frontend)

Ordem importa — foi reorganizada para nao mentir na interface:

```
1. setVoiceStatus('connecting')
2. getUserMedia({channelCount:1, echoCancellation, noiseSuppression, autoGainControl})
3. new AudioContext()           ← SEM forcar taxa (Firefox)
4. resume() se 'suspended'; 2a tentativa apos 120 ms
5. audioWorklet.addModule(MIC_WORKLET)
6. createMediaStreamSource + AudioWorkletNode
7. node.port.onmessage → ws.send(bytes)
8. SO AGORA: setVoiceStatus('listening') + setIsCharonActive(true)
9. watchdog de 2 s
```

**Antes:** marcava `listening`/`ativo` **antes** do passo 2, entao a tela dizia
"Ouvindo... fale com o Charon" mesmo com o microfone falhado.

**Diagnostico de erro** (`_diagnosticoMic`): traduz `NotAllowedError`,
`NotFoundError`, `NotReadableError`, `OverconstrainedError`, `AbortError`,
`SecurityError` e `TypeError` em causa + acao acionavel. Aparece um botao
"Tentar microfone novamente" — e ele parte de um **clique**, que e o gesto que o
Firefox exige.

## 7. Backend: sessao e turnos

### 7.1 Constantes
| Constante | Valor | Papel |
|---|---|---|
| `LIVE_MODEL` | `models/gemini-2.5-flash-native-audio-preview-12-2025` | modelo de audio nativo |
| `TURN_TAIL_GRACE_S` | **0.9** | espera a cauda do turno antes de fechar |
| `_POLL_INTERVAL` (reminders) | 20 s | ciclo do loop de lembretes |

`TURN_TAIL_GRACE_S` era `sleep(0.5)` fixo. Curto demais cortava a ultima
palavra; longo demais atrasa o retorno a "ouvindo".

### 7.2 Vozes validas (`GEMINI_VOICES`)
`charon`, `puck`, `kore`, `fenrir`, `leda`, `orus`, `aoede`, `zephyr` —
resolvidas por `_resolve_voice()` **case-insensitive**.

### 7.3 Interrupcao (barge-in)
`self._interrupted` descarta audio antigo quando o usuario comeca a falar por
cima. No `turn_complete` com interrupcao, o buffer restante e **despejado**
(flush) antes de fechar — senao o fim da fala se perde.

**Corrigido em 2026-09-12 (Sessao 49).** A interrupcao NAO funcionava, por tres
motivos somados — e o usuario relatou exatamente isso:

1. **O backend ignorava `server_content.interrupted`** — o sinal do VAD do
   Gemini avisando "o usuario falou por cima". O audio antigo continuava a ser
   repassado e o navegador nunca era avisado.
2. **Cada chunk do microfone fazia `_interrupted = False`.** Como o mic envia
   audio a cada ~20-60 ms, qualquer interrupcao era desfeita no chunk seguinte.
   Este era o bug mais grave e o mais dificil de enxergar — a linha parecia
   correta isolada. **Quem libera a interrupcao agora e o `turn_complete`** do
   turno interrompido, com uma **rede de seguranca de 3 s** (`_interrupted_at`)
   para o Charon nunca ficar surdo para sempre.
3. **O frontend nunca enviava `type: 'interrupt'`** — o handler do backend era
   codigo morto. E nao esvaziava a **fila local** (`audioBufRef` + o ring do
   worklet): mesmo com o servidor calado, havia **segundos** de fala ja baixada
   tocando no navegador. E isso que se percebe como "o Charon nao para de falar".

Fluxo correto agora, em duas frentes:

| Frente | Quem detecta | O que faz |
|--------|--------------|-----------|
| Navegador | nivel do microfone (`>0.06` por 3 chunks seguidos) | esvazia a fila + o ring, descarta audio em transito por 400 ms, envia `interrupt` |
| Servidor | VAD do Gemini (`sc.interrupted`) | marca `_interrupted`, descarta a saida, envia `{"type": "interrupted"}` ao navegador |

A deteccao no navegador existe porque a latencia do VAD do servidor sozinha ja
deixava o Charon falando por cima do usuario. O limite de 3 chunks evita que um
estalo, o teclado ou a propria voz do Charon no alto-falante interrompam a fala.

**Detalhe que o teste comportamental revelou:** o `return` do portao de
interrupcao vinha ANTES do tratamento de `input_transcription`, entao **a fala do
usuario nao era transcrita justamente quando ele interrompia** — o momento em que
a transcricao mais importa. A transcricao do usuario agora e tratada antes do
portao: a interrupcao cala a **saida**, nao pode cegar a **entrada**.

### 7.3.1 Saudacao inicial
O gatilho de `_send_startup_briefing()` precisa impor brevidade **e proibir
explicitamente** os assuntos que faziam a fala se estender.

O gatilho antigo era um convite aberto:
`"Se apresente para {user_name} agora. Diga seu nome, horario e como pode ajudar."`
— e o Gemini Live respondia com uma introducao longa: o que e o sistema, quais
ferramentas tem, o que sabe fazer, o horario.

Agora o gatilho informa o **texto exato** e lista o que e proibido (sistema,
ferramentas, funcionalidades, status, horario/data/clima, listas), com limite de
15 palavras:

> "Ola Wilson, eu sou Charon. O que gostaria de fazer agora?"

Modelos de audio tendem a "encher linguica" quando a instrucao deixa margem —
por isso as proibicoes pesam tanto quanto o pedido. Coberto por
`tests-manual/test_charon_barge_in.py`.

### 7.3.2 ⚠️ Os DOIS paineis do Charon: não confundir, e não "melhorar" o direito

O Charon tem dois paineis com finalidades **deliberadamente diferentes**. Isso
foi uma decisão de projeto do usuário, não um acidente:

| Painel | O que mostra | Formato | Pode mexer? |
|--------|--------------|---------|-------------|
| **Esquerdo (central)** | as **atividades**: ferramentas, buscas, listagens, resultados, documentos — *a entrega organizada do trabalho* | formatado, com links e Markdown | ✅ é aqui que se organiza e melhora |
| **Direito** | a **transcrição da voz**, falante por falante | **empilhado**: cada pedaço do Gemini Live é uma entrada | ❌ **NÃO MEXER** |

**Por que o direito é empilhado e por que isso é proposital.** O Gemini Live
entrega a transcrição em **pedaços**, em tempo real, junto com o áudio. Cada
pedaço vira uma entrada — por isso o painel parece uma pilha de frases curtas.

Palavras do usuário:

> *"é neste formato que funcionou empilhando as conversas, passamos vários dias
> para descobrir que assim empilhado é melhor, não mexa neste formato"*

> *"por isso eu pedi para ele entregar de forma organizada as respostas, os
> projetos e listagem no painel central — por conta disso, para não mexer na
> forma que ele recebe as informações e escuta"*

Ou seja: **o painel central existe justamente para não precisar tocar no
direito.** A organização vai para o central; o direito continua espelhando o
fluxo do modelo, que é o que sustenta a escuta e o áudio.

**A tentação a resistir:** juntar os pedaços do mesmo falante numa frase única.
Parece uma melhoria óbvia — e eu tentei, por conta própria, inferindo do arquivo
exportado. **Foi revertido.** Alterar como a transcrição é acumulada é mexer no
caminho por onde as informações do modelo passam; o formato atual é o que
funcionou depois de dias. Há aviso em `CharonPage.tsx` e em `chatStorage.ts`, e
teste travando (`test_historico_conversa.py`, seção 11).

**O download da sessão ("Baixar sessão") exporta os DOIS** — transcrição (direito)
e atividades (central), em seções identificadas. É assim que se estuda ou arquiva
uma sessão sem violar a regra acima.

### 7.4 Tools
- `BASIC_TOOL_DECLARATIONS` (18) → `MEDIUM_TOOL_DECLARATIONS` (19) →
  `EXTRA_TOOL_DECLARATIONS` (8, so no toolset `full`) = **26 unicas**
- `_get_charon_toolset()` le `voice.charon_toolset` de `config.yaml`
  (`basic` / `medium` / `full`), com cache por mtime
- `_filter_headless()` remove as tools de GUI quando `is_headless()`
- `_HEADLESS_EXCLUDED`: `open_app`, `browser_control`, `desktop_control`,
  `computer_control`, `computer_settings`, `screen_process`, `game_updater`,
  `send_message`
- As tools rodam no **`run_in_executor`** (threadpool). O `ContextVar` de
  tenant/fuso e copiado no momento da chamada, entao elas **enxergam** o tenant

### 7.5 System instruction
Montada por `_build_system_instruction()` com: nome do assistente e do usuario,
**hora local** do usuario (nunca `bash date`), idioma, contagem de tools,
orientacao de documentos com link de download, bloco de **modo headless** e
`extra_prompt` do usuario.

### 7.6 Identidade e fuso por conexao
`_load_identity()` prioriza o **tenant** (banco) e so cai em `config.yaml` se
nao houver tenant. O cache de 5 s existe **apenas** no caminho global —
cachear por tenant vazaria identidade entre assinantes.

## 8. Diagnostico (o que olhar quando algo falha)

### 8.1 Console do navegador (F12)
```
[Charon] Sem interacao do usuario ainda — o microfone sera pedido no primeiro clique
[Charon] Auto-start ( gesto do usuario )
[Charon] AudioContext do mic: running | sampleRate real: 48000
[Charon] Microfone ativo. AudioContext state: running | sampleRate: 48000
[Charon] Microfone indisponivel: DOMException: ...     + motivo detalhado
```
Nunca aparecer: `AudioContext do mic: suspended` (o mic nao vai enviar audio).

### 8.2 Logs do backend
```bash
journalctl -u deepos-backend.service -f --no-pager
```
Linhas uteis:
- `[VoiceWS] Recebido: data=True, ... (delay=Xms)` — **delays altos e regulares
  indicam gargalo de rede/Gemini, nao do buffer**
- `[VoiceWS] Conexao do tenant: <id>`
- `[VoiceWS] Fuso do usuario: America/Sao_Paulo`
- `[VoiceWS] Identity: assistant=..., user=..., tools=N`
- `[VoiceWS] Headless mode: N -> M tools (removidas: ...)`

### 8.3 Sintomas → causa provavel
| Sintoma | Onde olhar |
|---|---|
| Charon "ouvindo" mas nao responde | mic: `AudioContext` suspenso / permissao |
| Engasgo no meio da frase | ring esvaziando; ver delays no log |
| Corta as ultimas letras | `_prebuf`/ring/tail grace; sub-run |
| Responde mas sem voz | playback suspenso; ver `setupPlayback` |
| WebSocket nao conecta | nginx: `proxy_http_version 1.1` + `Upgrade` |
| Reconecta em loop | `_sessions` encerrando a sessao anterior |
| Fala com voz/nome de outro | ordem de rotas do `/api/config` (catch-all) |

### 8.4 Testes sem navegador (backend)
```bash
cd /root/DEEP-OS/backend
/root/DEEP-OS/venv/bin/python -c "
import config; print('is_headless:', config.is_headless())
from routes.voice_ws import _get_active_tools, _build_system_instruction
print('tools ativas:', len(_get_active_tools()))
print(_build_system_instruction()[:400])
"
```

## 9. Checklist antes de mexer na voz

- [ ] Leia a secao 5 (armadilhas). Cada constante foi ajustada em campo
- [ ] Nao force `sampleRate` no `AudioContext` do microfone (quebra no Firefox)
- [ ] Nao chame `getUserMedia` sem gesto do usuario (o Firefox memoriza o bloqueio)
- [ ] Marque `listening`/`ativo` **somente apos** obter o stream
- [ ] Se adicionar watchdog, lembre de limpar o interval no `onclose` e no
      `toggleCharon`
- [ ] Teste em **Chrome e Firefox** — as politicas de audio sao diferentes
- [ ] Verifique o console do navegador **e** o `journalctl` juntos
- [ ] Depois de alterar `CharonPage.tsx`: rebuild (`npm run build:saas`) e
      publicar em `/var/www/deep-os/frontend/dist-saas`

## 10. Referencia rapida de valores

```
AudioContext playback        24000 Hz (fixo)
ring buffer (playback)       384000 amostras  (16 s)
prebuffer (playback)          36000 amostras  (1,5 s)
limite de underruns                   5
margem de dedup                       6 chunks
chunk do mic                       1024 amostras
downsample do mic               ratio 3  (~16 kHz)
watchdog do mic                    2000 ms
TURN_TAIL_GRACE_S                   0.9 s
reconexao automatica                3000 ms
LIVE_MODEL        gemini-2.5-flash-native-audio-preview-12-2025
```
