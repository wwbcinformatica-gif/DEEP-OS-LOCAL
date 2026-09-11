# DEEP-OS — Memoria do Projeto

## Visao Geral
Sistema operacional de agentes de IA com 3 modos de interacao:
- **Chat** (texto) — Jarvis via OpenRouter ou modelos locais
- **Voz** (Live API) — Charon via Google Gemini Live
- **SaaS** — Multi-tenant para venda/locacao

## Status Atual (2026-09-11)
**SESSAO 48 — CORRECOES CRITICAS (isolamento, lembretes, audio, microfone)** ✓

### ⚠️ TRES REPOSITORIOS — NAO CONFUNDIR (causa do incidente inicial)
| Repositorio | Caminho |
|---|---|
| PC | `C:\DEEP-OS` |
| GitHub | `origin/master` |
| **VPS** | `/root/DEEP-OS` |

**Um `git reset` no PC + `git push` NAO reverte o VPS.** Foi exatamente o que
derrubou o site: um modelo reverteu PC e GitHub, deixou o VPS quebrado, e ainda
relatou "deploy concluido" sem ter acesso ao servidor.

**Outra armadilha:** o agente rodava comandos Linux dentro do **PowerShell do
Windows** (`systemctl`, `chmod`, `grep` → "nao reconhecido"). Quando
`/root/DEEP-OS` nao existia, ele **caia para o repo local** e mexia nele.

### CAUSA RAIZ do vazamento de voz/nome entre usuarios (LER ANTES DE MEXER)
Em `backend/routes/config.py`, a rota **catch-all `/{section}` estava registrada
ANTES** das rotas literais. O FastAPI resolve rotas **por ordem de registro**:

```python
@router.get("/{section}")     # linha 102 — casava com /identity
@router.get("/identity")      # linha 147 — NUNCA alcancada
```

`GET /api/config/identity` caia no catch-all, que devolve o `config.yaml`
**GLOBAL**. Por isso o isolamento por tenant nunca funcionou por HTTP — e como o
catch-all e so GET, o `PUT` gravava certo e o `GET` devolvia o global
("salva mas aparece para todos").

**REGRA: rotas catch-all (`/{param}`) SEMPRE por ultimo no arquivo.**
O catch-all agora esta no fim de `routes/config.py`, com aviso em destaque.

### 502 Bad Gateway — o que significa neste projeto
`502` = nginx vivo, **ninguem na porta 8001** (backend morto). Ja `404` = backend
vivo, rota errada. E `Depends(...)` no **default de um parametro** e resolvido no
**import do modulo** — quebra o boot inteiro, nao a requisicao. O frontend recebe
o HTML do 502 e o `JSON.parse` estoura com "unexpected character at line 1".

### 8001 reocupada sozinha? Suspeite de UNIT DUPLICADA
Havia `deepos-backend.service` **e** `deep-os-backend.service` — um hifen de
diferenca — as duas `enabled`, brigando pela porta. `Restart=always` ressuscitava
a intrusa em ~5s, entao matar processo nunca resolvia.
Verificar: `grep -rl "uvicorn" /etc/systemd/system/`

### Outras correcoes da sessao 48
- **Identidade por tenant:** colunas `tenants.assistant_name`, `user_name`,
  `voice` (com migracao automatica); `core/tenant_identity.py`.
- **Contas master:** chave unica por conta (`master-admin:<email>`) + linha
  criada automaticamente. Antes as duas compartilhavam o `sub` `master-admin`.
- **Lembretes:** `schtasks`/`systemd-run --user`/`at` NAO funcionam em VPS
  headless. Agora tabela `reminders` + loop asyncio + resumo em documento
  (tool `list_reminders`, `/api/reminders/export`).
- **Fuso horario:** servidor em UTC, usuario em Brasilia (UTC-3). Grava em UTC,
  exibe na hora local. `ZoneInfo` precisa de `tzdata` no Windows (senao cai em
  UTC e os lembretes ficam 3h errados).
- **Audio do Charon:** worklet sem recuperacao de sub-run comia a cauda da
  ultima palavra.
- **Microfone (Firefox):** `AudioContext` com `sampleRate` forcado fica suspenso;
  agora ha watchdog de 2s e o auto-start espera gesto do usuario.
- **Tools:** `backend/config/` sombreava o `config.py` da raiz (3 tools nao
  importavam); `send_message` faltava na lista de exclusao headless.
- **`require_plan` devolvia 404** para o admin (sem linha em `tenants`), fazendo
  rota existente parecer inexistente.
- **`frontend/dist-saas`** deixou de ser versionado (commit `74c2a73`).

### Licao de metodo (custou muitas rodadas)
**Teste pela ROTA (HTTP), nao so pela funcao.** O bug do catch-all passou
despercebido porque `get_identity()` era testada direto e sempre funcionava —
nao era ela que respondia. Use `tests-manual/test_identity_endpoint.py`.

**E quando uma busca retorna vazio, confirme que o comando de busca funcionou.**
Concluí (errado) que `middleware/tenant.py` era codigo morto porque usei
`Select-String -Path ... -Recurse` — e `-Recurse` nao e parametro valido para
`Select-String`. O comando errou em silencio e eu tratei o vazio como ausencia.

---

## Historico

**SESSAO 47 — SISTEMA PIX COMPLETO** ✓
- **BACKEND PIX:** PUT /admin/pix com QR code upload, GET /admin/pix/public retorna QR
- **PAGAMENTO:** POST /plans/request-payment envia solicitacao, admin confirma via /admin/payments/confirm
- **PRICING MODAL:** Modal PIX com QR Code + chave + "Ja paguei" ao assinar plano pago
- **PIX PAGE:** Pagina dedicada com QR Code + instrucoes + passo a passo
- **ADMIN PAGAMENTOS:** Tab "Pagamentos" com config PIX + lista pendentes + confirmar/rejeitar

**SESSAO 46 — TENANT ISOLATION + CONVERSAS + HELP MENU** ✓
- **TENANT ISOLATION:** localStorage prefixado com ID do tenant (cada usuario tem seus dados isolados)
- **SISTEMA DE CONVERSAS:** Multiplas sessoes no Charon e Jarvis (estilo ChatGPT, dropdown discreto)
- **HELP MENU REESCRITO:** Instrucoes completas de uso do Charon/Jarvis e criacao de documentos
- **ADMIN AUTH FIX:** AdminDashboard verifica admin_token antes de buscar dados (nao mais erros 401)
- **PLAN CONFIG FIX:** Chaves do planConfig.ts alinhadas com backend (monthly/quarterly/annual)

**SESSAO 45 — DEPLOY VPS + AUTH ME + BACKEND FIX** ✓
- **/AUTH ME FUNCIONA:** Retorna dados hardcoded master-admin (plan: master)
- **BACKEND REINICIADO:** systemctl restart + limpeza pycache
- **BUILD FRONTEND CORRIGIDO:** Copiar para `/var/www/deep-os/frontend/dist-saas/`

**SESSAO 44 — FIX PLANOS ADMIN (PERSISTENCIA + PRICINGPAGE DINAMICO)** ✓
- **PLANOS PERSISTIDOS:** PUT /admin/plans salva em data/plans.json (antes so memoria)
- **ENDPOINT PUBLICO:** GET /plans/public retorna planos atuais (sem auth)
- **PRICINGPAGE DINAMICO:** Busca planos da API (nao mais hardcoded)
- **REFRESH USUARIO:** SaaSApp chama GET /auth/me ao carregar (plano atualizado)
- **FEEDBACK ADMIN:** Alert de sucesso ao salvar plano/usuario

**SESSAO 43 — ADMIN PRODUCTS + UPLOAD + CHATBOT API KEYS** ✓
- **ADMIN TAB PRODUTOS:** CRUD completo — criar, editar, excluir produtos digitais
- **UPLOAD DE ARQUIVOS:** Botao "Upload" nos modais de produto — salva em /root/DEEP-OS/downloads/
- **CHATBOT API KEYS:** Campos para Gemini e OpenAI — salva no servidor e usa nas chamadas
- **DOIS EMAILS ADMIN:** wwbcinformatica@gmail.com e wwbc22@gmail.com (mesma senha)
- **SIDEBAR ADMIN:** Link "Painel Mestre" aparece para os dois emails master

**SESSAO 42 — CHARON AUDIO FIX + REMINDER + DOCUMENTOS** ✓
- **CHARON AUDIO STREAMING:** Backend envia cada chunk imediatamente (sem acumular buffer) — zero atraso
- **PREBUFFER AUMENTADO:** 24000 samples (1 segundo) — playback mais fluido
- **TURN_COMPLETE FLUSH:** Delay 500ms + flush de audio restante mesmo quando interrompido
- **REMOVIDO DEDUP AGRESSIVO:** Antes descartava audio legitimo causando cortes
- **AUDIOCONTEXT AUTO-RECOVERY:** Se trava, recria playback automaticamente
- **WATCHDOG AUMENTADO:** 60s → 5 minutos (Charon nao para mais de ficar ocioso)
- **PING A CADA 30s:** Mantem sessao Gemini ativa
- **REMINDER NATURAL LANGUAGE:** Entende "amanha as 14:30", "em 2 horas", "sexta as 10h"
- **SAVE_DOCUMENT FORMATACAO:** Markdown → HTML bonito com headers, listas, paragrafos, negrito
- **SYSTEM INSTRUCTION ATUALIZADA:** Charon le textos longos em partes, termina frases completas
- **TRANSCRIPT NO LOCALSTORE:** Ultimas 200 mensagens persistem ao navegar entre menus
- **CONTEXTO COMPRESSION REMOVIDO:** session_resumption e context_window_compression desativados

**SESSAO 41 — FIX LOGIN + ADMIN SIDEBAR** ✓
- **BUG CRITICO CORRIGIDO:** Register nao dava commit (rollback silencioso em todas as rotas)
- **BUG CRITICO CORRIGIDO:** sqlite3.Row nao tem .get() — causava erro no login
- **ADMIN INTEGRADO NO SIDEBAR:** Rota /admin separada removida. "Painel Mestre" aparece no sidebar para users master
- **MASTER USER CRIADO:** wwbcinformatica@gmail.com / admin123@ / plan master (via sqlite3 direto)
- **COMMIT BUG:** Todas as rotas de escrita (register, login, admin CRUD) davam rollback. Todas corrigidas com conn.commit()
- Login normal funciona com bcrypt (passlib removido)
- Mobile scroll: overflow:hidden removido
- Charon: WS timeout 8s, botao conectar, Chrome iOS mic fallback para texto
- Disk cleanup feito

## Deploy Atual
- **VPS:** Hostinger, IP `2.25.143.185`, Ubuntu 26.04.1 LTS, 4GB RAM
- **Dominio:** `https://deep-os.tech`
- **Setup:** nginx + uvicorn (systemd) — Docker desabilitado
- **SSL:** Let's Encrypt (auto-renovacao)
- **Acesso:** https://deep-os.tech
- **Branch Git:** `master` (nao `main` — `main` esta 115+ commits atras)
- **Python:** 3.14 (venv em `/root/DEEP-OS/venv/`)
- **Frontend:** Buildado em `/var/www/deep-os/frontend/dist-saas/`
- **Banco:** `/root/DEEP-OS/data/interactions.db` (tenants, products,
  tenant_products, payments, reminders)
- **Banco Admin:** `/root/DEEP-OS/data/admin.db`

### ⚠️⚠️ UNIT SYSTEMD — O HIFEN IMPORTA
| Unit | Estado | Papel |
|---|---|---|
| **`deepos-backend.service`** | ✅ **active / enabled** | **A CORRETA** |
| `deep-os-backend.service` | ❌ disabled | Duplicada (sessao 48) |

**Sempre `deepos-backend`** (sem hifen). As duas estavam `enabled` e brigavam
pela porta 8001 em loop. Para descobrir qual atende de fato:
```bash
ps -o unit= -p $(ss -lptnH 'sport = :8001' | grep -oP 'pid=\K[0-9]+' | head -1)
```

## O que esta pendente (Sessao 49)
1. ~~**DOWNLOAD DOS DOCUMENTOS (404)**~~ — ✅ **RESOLVIDO** (`91d7abb`).
   **Causa raiz:** havia **DOIS sanitizadores de `tenant_id`** diferentes — o
   `routes/download.py` removia `:` e `@`, e o `scripts/migrar-downloads-legados.sh`
   (shell, rodado no VPS) usava o id **cru**. Os arquivos foram para
   `downloads/master-admin:wwbc22@gmail.com/` e o backend procurava
   `downloads/master-adminwwbc22gmail.com/` → pasta diferente → 404.
   **Correção:** fonte única (`core.tenant_identity.tenant_slug`) + o download
   procura nas duas variações. Teste: `tests-manual/test_tenant_slug.py`.
   **Nota:** `:` em nome de pasta é **proibido no Windows** — o caso nunca se
   reproduziria no PC. Ver a regra 3 em "Regras Importantes".
2. ~~**DIST-SAAS GITIGNORE**~~ — ✅ CONCLUIDO (`74c2a73`)
3. ~~**TESTAR TENANT ISOLATION**~~ — ✅ VERIFICADO em producao
4. **MICROFONE NO FIREFOX** — liberar a permissao (bloqueada pelo auto-start
   antigo): cadeado 🔒 → Microfone → Permitir → recarregar
5. **TESTAR LEMBRETES** — criar por voz, ouvir o disparo, gerar documento
6. **TESTAR CONVERSAS / DOCUMENTOS / HELP MENU** pela interface
7. **FLUXO PIX / QRCODE / NOTIFICACOES** — testar ponta a ponta
8. **SEGURANCA (depende de voce)** — trocar a senha de root do VPS e o
   `MASTER_PASSWORD` (ainda e `admin123@`; o log avisa a cada login)
9. **Git cleanup** — branch `main` desatualizada; trocar a default para `master`

### ✅ Concluido na sessao 48 (para referencia)
- Identidade/voz/nome isolados por tenant (causa raiz: catch-all antes das
  rotas literais em `routes/config.py`)
- Lembretes funcionando (tabela + loop asyncio) e com fuso correto
- Audio do Charon sem engasgo/corte | microfone com watchdog e diagnostico
- 3 tools que nao importavam (`backend/config.py` shim)
- Units systemd duplicadas resolvidas (`deepos-backend` = a correta)
- **Seguranca:** `/api/config` e `/api/instances` estavam expostos pela internet
  (agora 401), `JWT_SECRET` sem default publico, `MASTER_PASSWORD` fora do
  codigo, downloads isolados por tenant
- **Disco:** o log por chunk de audio encheu 27 GB de syslog; agora e agregado
  por turno (~99% menos) + logrotate e limites de journal
- **Testes:** 11 arquivos em `tests-manual/` + runner (`run_all.py`, ~20s)
- **RAG local:** `tools/rag_local.py` + `tools/perguntar.py` respondem sobre o
  projeto usando a documentacao, com modelo local via Ollama

## Comando de deploy (ATUAL — use este)
```bash
cd /root/DEEP-OS
git fetch origin master && git reset --hard origin/master && bash scripts/deploy-faf8f93.sh
```

O script faz backup das chaves, descobre a unit certa, valida o `import` ANTES
de reiniciar, roda a migracao, builda o frontend e publica no nginx.

### ❌ NAO USE o comando antigo
```bash
# NAO FACA: 'git checkout -- .' DESCARTA alteracoes locais,
# e 'git pull' da conflito quando o historico foi reescrito
cd /root/DEEP-OS && git checkout -- . && git pull origin master
```

## ⚠️ IMPORTANTE — Diretorio de deploy do nginx
- **CORRETO:** `/var/www/deep-os/frontend/dist-saas/`
- **ERRADO:** `/usr/share/nginx/html/` (nginx NAO serve daqui)
- **Config:** `/etc/nginx/sites-enabled/deepos` → `root /var/www/deep-os/frontend/dist-saas;`

## Contas conhecidas
- **Master admin 1:** wwbcinformatica@gmail.com / admin123@ (plan master, hardcoded)
- **Master admin 2:** wwbc22@gmail.com / admin123@ (plan master, hardcoded)
- **Banco:** /root/DEEP-OS/data/interactions.db

## Status Charon (2026-09-07)
**CHARON FUNCIONANDO NO VPS** ✓
- Conecta via `wss://deep-os.tech/ws/voice` → nginx → backend:8001
- Detecta modo headless, filtra tools GUI
- Greeting funcional, responde em portugues
- Chave Gemini salva em `api_keys.json` (nao versionada no Git)

## 🎙️ CHARON — VOZ (a parte MAIS COMPLEXA do sistema)
**Documentacao completa: [`docs/CHARON-VOZ.md`](docs/CHARON-VOZ.md)**

Leia ANTES de mexer em audio. Resumo do que mais morde:

- **Firefox ≠ Chrome:** `AudioContext` com `sampleRate` forcado fica **suspenso**
  no Firefox (ele nao reamostra como o Chrome) → o mic "conecta" e entrega
  silencio. Criar **sem** forcar taxa e so cair para `{sampleRate}` se falhar.
- **Gesto do usuario e obrigatorio:** chamar `getUserMedia` sem interacao faz o
  Firefox responder `NotAllowedError` **e memorizar o bloqueio do site** — depois
  nem pergunta mais. Usar `navigator.userActivation.hasBeenActive`.
- **Watchdogs assimetricos:** o playback tinha auto-recuperacao, o microfone
  **nao tinha**. Agora ha um de 2 s que retoma o contexto e readquire a track.
- **Numeros ajustados em campo** (nao mudar sem testar): ring `384000`,
  prebuffer `36000`, underruns `5`, dedup `6`, chunk do mic `1024`,
  downsample `ratio 3`, `TURN_TAIL_GRACE_S 0.9`, playback a `24000 Hz`.
- **O mic sobe ~16 kHz e o Charon desce 24 kHz.** PCM16 mono, sem cabecalho.
- **Uma sessao por vez:** ao receber `start`, o backend encerra as outras.

## 🤖 ASSISTENTE LOCAL (RAG) — pergunta sobre o projeto offline
**Documentacao: [`tools/README-RAG.md`](tools/README-RAG.md)**

Responde sobre o DEEP-OS usando a **propria documentacao** como base, com um
modelo local via Ollama. O modelo nao precisa "saber" o projeto: ele recebe os
trechos certos do `memory.md`/`STATUS.md`/`docs/`/`.memory/`.

```bash
python tools/rag_local.py indexar                  # constroi o indice (32 arquivos, ~493 trechos)
python tools/perguntar.py "por que a voz nao salvava por usuario?"
python tools/perguntar.py --modelos                # quais modelos voce tem
```

**Reindexar** depois de editar a documentacao (o indice nao se atualiza sozinho).

Limitacoes: pode errar a **citacao** da fonte (o conteudo costuma estar certo);
sinonimos sao lista curada em `SINONIMOS` (`tools/rag_local.py`); indice em
`.rag/` (no .gitignore).

## Arquitetura
- **Backend:** FastAPI (Python 3.14 no VPS)
- **Frontend:** React + Vite (TypeScript)
- **Config:** `config.yaml` (identity, tools, agent_models) — agora e apenas o
  **padrao global**; identidade personalizada vive por tenant no banco
- **Banco:** SQLite (`data/interactions.db`) — tenants, payments, usage_metrics,
  products, tenant_products, **reminders**
- **API Keys:** `backend/config/api_keys.json` (NAO no git — cada VPS tem a sua)

### Nginx (VPS)
- **Frontend:** `/var/www/deep-os/frontend/dist-saas` (config real em sites-available)
- **Config:** `/etc/nginx/sites-available/deep-os.conf`
- **API proxy:** `/api/` → `127.0.0.1:8001`
- **WebSocket proxy:** `/ws/` → `127.0.0.1:8001`
  - `proxy_http_version 1.1` obrigatorio
  - `proxy_read_timeout 86400s` obrigatorio
- **SSL:** Certbot/Let's Encrypt

### Vite proxy (dev)
- `/api/` → backend:8001
- `/auth/` → backend:8001
- `/chat/` → backend:8001
- `/voice/` → backend:8001 (WebSocket)
- `/ws/` → backend:8001 (WebSocket)
- `/admin/` → backend:8001
- `/plans/` → backend:8001 (adicionado sessao 44)
- `/shop/` → backend:8001 (adicionado sessao 44)

## Ferramentas Charon (Modo VPS/Headless)
**Disponiveis (16):** web_search, youtube_video (link clicavel), weather_report, 
system_status, send_message, reminder, file_controller, file_processor, 
download_image, code_helper, dev_agent, bash, read_file, background_monitor

**Filtradas (7) — requerem GUI:** open_app, browser_control, desktop_control, 
computer_control, computer_settings, screen_process, game_updater

## Regras Charon
1. Detectar idioma do usuario e responder NELE
2. Se pedirem algo que nao pode fazer no VPS, explicar e listar ferramentas disponiveis
3. Para hora/data: usar bash 'date' para obter horario correto
4. Modo headless detectado via `is_headless()` em `config.py`

## Como Iniciar no VPS
```bash
# Backend (systemd - ja inicia automatico)
# ATENCAO: a unit e 'deepos-backend' (SEM hifen). 'deep-os-backend' esta
# desabilitada — se voce usa-la, a porta 8001 fica com dono duplicado.
systemctl status deepos-backend
systemctl restart deepos-backend

# Nginx (systemd - ja inicia automatico)
systemctl status nginx
systemctl reload nginx

# Deploy atualizado (USE O SCRIPT — ele ja faz o build e o restart)
cd /root/DEEP-OS
git fetch origin master && git reset --hard origin/master && bash scripts/deploy-faf8f93.sh

# Verificar logs
journalctl -u deepos-backend -f --no-pager
```

## Estrutura Principal

### Backend (`backend/`)
- `main.py` — FastAPI + CORS + rotas
- `database/connection.py` — Pool SQLite + init_db (inclui tabelas SaaS)
- `routes/chat.py` — Chat com Jarvis
- `routes/voice_ws.py` — Gemini Live WebSocket (Charon)
  - `_get_gemini_key()` — le de `api_keys.json`
  - `_filter_headless()` — remove tools GUI em VPS
  - `_build_system_instruction()` — headless mode + multilingua
- `routes/auth.py` — Rotas de autenticacao SaaS (bcrypt)
- `routes/admin.py` — Dashboard admin + CRUD tenants + CRUD products + grant/revoke downloads
- `routes/shop.py` — API publica de produtos (GET /shop/products)
- `routes/agent.py` — Execucao de agentes
- `routes/config.py` — Endpoints de config (identity, agent-models, api-key)
  - `GET /api/config/api-key` — status da chave (mascarada)
  - `PUT /api/config/api-key` — salva chave em api_keys.json
- `routes/ws_terminal.py` — Terminal WebSocket (bash/powershell, detecta OS)
- `routes/terminal.py` — Terminal persistente (bash/cmd, detecta OS)
- `routes/download.py` — Download de arquivos do VPS para cliente
- `routes/chatbot.py` — Chatbot providers IA
- `routes/llamacpp_route.py` — Modelos GGUF (cross-platform)
- `routes/ollama_route.py` — Ollama status (cross-platform)
- `agents/orchestrator.py` — Resolucao de modelos
- `tools/executor.py` — Execucao de tools
- `actions/` — Actions do Charon (pyautogui com `except Exception`)
- `memory/config_manager.py` — Leitura/salvamento de config
- `config/api_keys.json` — API keys (NAO versionado no git)

### Frontend (`frontend/src/`)
- `components/saas/CharonPage.tsx` — Interface Charon (voz + chat + help + conversas)
  - `handleSaveApiKey()` — envia PUT para backend salvar em api_keys.json
  - `getWsUrl()` — gera `wss://deep-os.tech/ws/voice`
  - `tenantGet/tenantSet()` — storage isolado por tenant (chatStorage.ts)
- `components/saas/JarvisPage.tsx` — Interface Jarvis (chat + conversas)
  - `tenantGet/tenantSet()` — storage isolado por tenant
- `components/saas/chatStorage.ts` — Tenant-scoped storage + sistema de conversas
  - `getConversations()`, `createConversation()`, `deleteConversation()`
  - `getTranscripts()`, `saveTranscripts()`
  - `tenantGet()`, `tenantSet()`, `tenantRemove()`
- `components/saas/AuthPage.tsx` — Login/registro SaaS
- `components/saas/SettingsPage.tsx` — Configuracoes
  - `handleSaveApiKey()` — envia PUT para backend
- `components/saas/AdminDashboard.tsx` — Dashboard admin (verifica admin_token antes de buscar)
- `components/saas/HelpModal.tsx` — Menu de ajuda reescrito (Charon/Jarvis/Documentos)
- `components/saas/planConfig.ts` — Configuracao de planos (chaves em ingles)
- `components/saas/Sidebar.tsx` — Menu lateral (responsivo)
- `components/saas/SaaSApp.tsx` — Layout SaaS
- `styles.css` — Estilos globais + responsivo (mobile/tablet)
- `vite.config.ts` — Proxy + host config
- `nginx.conf` — Config nginx para VPS (proxy WebSocket)

### Arquivos Raiz
- `deploy.sh` — Script deploy VPS (sem Docker)
- `config.yaml` — Config (identity, tools, agent_models)
- `config.py` — `is_headless()`, `is_linux()`, `is_windows()` para deteccao VPS
- `.gitignore` — Inclui `backend/config/api_keys.json`

### Config (`config.yaml`)
```yaml
identity:
  assistant_name: Charon
  user_name: Wilson
  voice: Charon

charon_toolset: full

agent_models:
  jarvis: qwen2.5-coder:14b
  architect: qwen3:14b
  debugger: qwen2.5-coder:14b
  planner: qwen3.5:9b
  coder: qwen2.5-coder:14b
```

## Login SaaS
- **Master Admin:** wwbc22@gmail.com / admin123@
- **Tabela tenants:** Criada em `interactions.db` via `init_db()`

## Bugs Criticos Resolvidos (2026-09-07)

### 1. pyautogui KeyError: 'DISPLAY'
**Sintoma:** Backend crasha no VPS com `KeyError: 'DISPLAY'`
**Causa:** `pyautogui` levanta `KeyError` (nao `ImportError`) em headless
**Fix:** `except ImportError` → `except Exception` em todos actions com pyautogui
**Arquivos:** youtube_video.py, computer_control.py, computer_settings.py, desktop.py, send_message.py

### 2. Nginx WebSocket nao conecta
**Sintoma:** Charon fica "conectando..." infinitamente
**Causa:** nginx sem `proxy_http_version 1.1` nos locations `/ws/` e `/voice/`
**Fix:** Adicionar `proxy_http_version 1.1` + `proxy_read_timeout 86400s`

### 3. CORS rejeita deep-os.tech
**Sintoma:** WebSocket bloqueado pelo navegador
**Causa:** `ALLOWED_ORIGINS` nao incluia `https://deep-os.tech`
**Fix:** Restaurar origens do VPS no main.py

### 4. Chave API sobrescrita pelo git pull
**Sintoma:** Charon funciona, depois para apos `git pull`
**Causa:** `api_keys.json` versionado no git com chave vazada
**Fix:** `.gitignore` + `git rm --cached backend/config/api_keys.json`

### 5. Salvar chave API nao funcionava
**Sintoma:** Inserir chave na interface nao salvava
**Causa:** Frontend salvava apenas no localStorage; backend lia de api_keys.json
**Fix:** Endpoint `PUT /api/config/api-key` salva no api_keys.json; frontend envia PUT

### 6. voice_ws.py sem headless mode
**Sintoma:** Charon tentava usar open_app/desktop_control no VPS
**Causa:** Revert do backup removeu `is_headless()` e `_filter_headless()`
**Fix:** Reimportado `from config import is_headless`, recriado filtro headless

## Sessoes Recentes

### Sessao 46 (2026-09-10) — Tenant Isolation + Conversas + Help Menu
- **Tenant isolation:** localStorage prefixado com ID do tenant (cada usuario tem seus dados isolados)
- **Sistema de conversas:** Multiplas sessoes no Charon e Jarvis (estilo ChatGPT)
- **ChatStorage.ts:** Funcoes tenantGet/tenantSet/tenantRemove + CRUD de conversas
- **Conversas UI:** Dropdown discreto no topo do painel (Charon: direito, Jarvis: header)
- **HelpModal reescrito:** 5 secoes (Charon, Jarvis, Documentos, Instancias, FAQ)
- **AdminDashboard fix:** Verifica admin_token antes de buscar dados (nao mais erros 401)
- **PlanConfig fix:** Chaves alinhadas com backend (monthly/quarterly/annual)
- **Deploy:** fc12488 + c5c9682 + 30f3bb7

### Sessao 45 (2026-09-10) — Deploy VPS + Auth Me + Backend Fix
- **/auth/me:** Retorna dados hardcoded master-admin (plan: master)
- **Backend:** systemctl restart + limpeza pycache
- **Frontend:** Build para `/var/www/deep-os/frontend/dist-saas/`
- **Systemd:** Funcionando apos reinicio do VPS

### Sessao 44 (2026-09-10) — Fix Planos Admin
- **Planos persistidos:** PUT /admin/plans salva em data/plans.json
- **Endpoint publico:** GET /plans/public retorna planos (sem auth)
- **PricingPage dinamico:** Busca planos da API (nao mais hardcoded)
- **Refresh usuario:** SaaSApp chama GET /auth/me ao carregar
- **Feedback admin:** Alert de sucesso ao salvar

### Sessao 43 (2026-09-09) — Admin Products + Upload + ChatBot API Keys
- **Admin tab produtos:** CRUD completo — criar, editar, excluir produtos digitais
- **Upload de arquivos:** Botao "Upload" nos modais de produto
- **Chatbot API keys:** Campos para Gemini e OpenAI
- **Dois emails admin:** wwbcinformatica e wwbc22

### Sessao 42 (2026-09-09) — Charon Audio Fix + Reminder + Documentos
- **Charon audio streaming:** Chunks imediatos (sem acumular buffer)
- **Reminder natural language:** Entende "amanha as 14:30", "em 2 horas"
- **Save document formatacao:** Markdown → HTML bonito
- **Transcript persistente:** Ultimas 200 mensagens no localStorage

### Sessao 41 (2026-09-09) — Fix Login + Admin Sidebar
- **Register commit bug:** Todas as rotas davam rollback (corrigido com conn.commit())
- **sqlite3.Row .get() error:** Convertido para dict antes de .get()
- **Admin integrado no sidebar:** Rota /admin separada removida
- **Master user criado:** via sqlite3 direto

### Sessao 38 (2026-09-07) — Admin Mestre Funcional
- **AdminDashboard reescrito:** simples e funcional (sem fragmentos quebrados)
- **Nginx proxy /admin/:** /admin/dashboard/, /admin/tenants, /admin/plans → backend
- **Nginx:** SPA fallback (location /) por ultimo (antes interceptava /admin/)
- **Rota admin:** detecta /admin, #admin, ?admin=true (pathname retorna / no VPS)
- **isSaaSMode:** detecta dominio deep-os.tech (VITE_SaaS_MODE nao funcionava no build)
- **isAdminRoute:** inicializado no useState (primeiro render)
- **Acesso:** https://deep-os.tech/admin (wwbc22@gmail.com / admin123@)

### Sessao 37 (2026-09-07) — Admin Mestre + Planos Editaveis
- **Plano Free → Colaborador:** uso total gratuito (10 instancias, 1000 msg/dia, todas features)
- **Admin backend:** PUT /admin/plans/{id} (edita nome, preco, descricao)
- **Admin backend:** PUT /admin/tenants/{id}/edit (edita nome, email, plano, status)
- **Admin backend:** DELETE /admin/tenants/{id} (exclui usuario)
- **AdminDashboard:** aba Planos dinamica do backend com features reais
- **AdminDashboard:** botao Editar Preco em cada plano (modal)
- **AdminDashboard:** botao Editar usuario (nome, email, plano, status)
- **AdminDashboard:** botao Excluir usuario
- **Acesso:** https://deep-os.tech/admin (wwbc22@gmail.com / admin123@)

### Sessao 36 (2026-09-07) — Jarvis Multi-Provedor + Vozes + Instâncias + iOS
- **Jarvis multi-provedor:** Gemini, OpenRouter (gratis), Groq (gratis), MiMo
- **Jarvis selects:** provedor + modelo (modelos mudam por provedor)
- **Jarvis chaves:** separadas por provedor, salvas no localStorage
- **Jarvis vozes:** 10 opcoes (Edge TTS: Jarvis Cinematic, Francisca, Thalita, Dani Brandi)
- **Jarvis vozes:** fallback browser se Edge TTS falhar
- **Jarvis velocidade:** slider 0.5x a 3.0x
- **Jarvis tom:** slider Grave a Agudo (0-100%)
- **Jarvis botao parar:** sempre visivel (🔈/🔇), cancela Edge TTS + browser
- **Jarvis UI:** container 100vh, botoes discretos (transparentes)
- **Instâncias:** tabela SQLite + CRUD /api/instances
- **Instâncias:** InstancesPage com criar, configurar, excluir, ajuda (?)
- **Instâncias:** Jarvis usa instancia (modelo + prompt + temperatura)
- **Instâncias:** Charon NAO usa instancias (Gemini Live exclusivo)
- **Charon iOS:** getWsUrl sem porta 443, auto-start tenta conectar
- **Charon iOS:** fallback ScriptProcessorNode se audioWorklet falhar
- **Charon audio:** backend acumula 4 chunks (menos engasgo)
- **ESC:** fecha config Jarvis, volta chat Charon, fecha sidebar mobile
- **Modelos:** removido Gemini 2.0 Flash (404), adicionado 1.5 Flash/Pro
- **OpenRouter:** Llama 3.3 70B gratis (:free)
- **Groq:** Llama 3.3 70B Versatile, Llama 3.1 8B Instant

### Sessao 35 (2026-09-07) — Mobile + Download + Hora Local + Jarvis
- **Mobile responsive:** nginx limpo, CSS sem inline styles conflitando
- **Sidebar mobile:** cor solida (sem backdrop-filter), z-index 250, fonte 14px
- **Charon mobile:** retrato = coluna (atividades/voz), paisagem = lado a lado
- **Charon painel direito:** 240px (era 340px), mensagens compactas
- **Drag handle:** classe charon-drag-h (CSS controla display por orientacao)
- **Scroll planos:** classe .scrollable no main content, sem height/overflow inline
- **Download documentos:** save_document/write_file salvam em /root/DEEP-OS/downloads/
- **Download link:** /api/download?path= gera botao 📥 no painel atividades
- **Download limpo:** remove markdown (**, #, >), converte \\n em quebras reais
- **Hora local:** frontend envia timezone (Intl.DateTimeFormat) + locale (navigator.language)
- **Hora local:** backend usa ZoneInfo(user_tz) para hora correta do usuario
- **Hora local:** system instruction diz NUNCA usar bash 'date' (servidor em UTC)
- **Salvar chave API:** endpoint PUT /api/config/api-key salva em api_keys.json
- **Login:** olho 🙈/👁️ para ver senha em login, registro e confirmar
- **Seguranca:** api_keys.json no .gitignore (git pull nao sobrescreve)
- **Jarvis:** removidos modelos Ollama, adicionados OpenRouter (GPT-4o, Llama 3.3)
- **Jarvis:** engrenagem abre painel com chave API + salvar no backend
- **Jarvis:** voz mais rapida (rate 1.3, era 1.0)
- **Jarvis:** is_task_message detecta "pesquisa", "pesquisar", "pode fazer"
- **Nginx:** adicionado /chat/ proxy (Jarvis nao funcionava sem isso)
- **SettingsPage:** chaves duplicadas corrigidas (settingHeader2, etc)
- **CSS:** marginBottom corrigido para margin-bottom

### Sessao 34 (2026-09-07) — Charon VPS Funcionando
- CORS restaurado para deep-os.tech
- Nginx: proxy_http_version 1.1 + timeouts WebSocket
- pyautogui: except Exception (KeyError DISPLAY em headless)
- voice_ws.py: headless mode + multilingua + filtro tools restaurados
- Terminal/llamacpp/ollama: cross-platform (detecta OS)
- Tabelas SaaS restauradas em connection.py
- Rotas download/chatbot restauradas, teste_route removida
- Endpoint PUT /api/config/api-key para salvar chave
- CharonPage/SettingsPage enviam chave para backend
- api_keys.json removido do git (.gitignore)
- deploy.sh atualizado (sem Docker, com npm build)
- requirements.txt: opencv-python-headless
- **Resultado: Charon funcionando no VPS** ✓

### Sessao 33 (2026-09-06) — Revert Backup + Mobile Fix
- Revert para backup anterior (Charon nao funcionava com fixes Linux)
- Hamburger menu sempre visivel em mobile/tablet
- Sidebar escondida por padrao, desliza ao clicar
- Overlay escuro quando sidebar aberta

### Sessao 32 (2026-09-06) — Limpeza + Responsivo + Fix Linux
- Removido voice_ws_broken.py, teste_route.py, actions/ do root, backend/browser/
- Corrigido curl.exe → curl, cmd.exe/powershell → bash
- Corrigido llamacpp_route para Linux (taskkill/wmic → pkill/pgrep)
- Adicionado responsivo mobile/tablet em styles.css
- Fix Charon time: usar bash 'date'

### Sessao 31 (2026-09-05) — Deploy + SaaS Login + Debug
- Tabela tenants criada em interactions.db (fix auth)
- WebSocket via Vite proxy (fix Charon)
- UFW porta 5176 liberada
- Docker desabilitado (RAM insuficiente)

### Sessao 30 (2026-09-05) — Deploy VPS
- Deploy completo em VPS Hostinger
- CORS + Vite host 0.0.0.0
- pyautogui/sounddevice import fix (headless)
- Git history cleanup (removido .rar 554MB)
- Dominio `deep-os.tech` apontando para VPS

### Sessao 29 (2026-09-04) — Mark-LI Port
- Portacao de 10 funcionalidades do Mark-LI para Charon
- Audio fix (ring buffer 192000, prebuffer 12000)
- Filtro de contexto para topicos relevantes
- Painel central (atividades) separado do painel direito (voz)

### Sessao 28 (2026-08-27) — Audio Fix
- MIME type `audio/pcm` → `audio/pcm;rate=16000`
- `_resolve_voice()` case-insensitive
- Greeting dinamico com `identity.assistant_name`

## Ferramentas Charon (3 niveis)
- **BASIC (18):** open_app, web_search, system_status, weather_report, send_message, reminder, youtube_video, screen_process, computer_settings, browser_control, file_controller, desktop_control, code_helper, dev_agent, computer_control, file_processor, bash, read_file
- **MEDIUM (18):** Todas BASIC (recomendado)
- **FULL (26):** MEDIUM + write_file, save_document, file_edit, web_fetch, memory_save, memory_recall

## Vozes Gemini Live
| Voz | Tipo |
|-----|------|
| Charon | Masculina (padrao) |
| Puck | Masculina |
| Fenrir | Masculina |
| Orus | Masculina |
| Kore | Feminina |
| Leda | Feminina |
| Aoede | Feminina |
| Zephyr | Feminina |

## Pendencias

### Funcionalidades
- [ ] ElevenLabs — Configurar ELEVENLABS_API_KEY
- [ ] web_fetch — User-Agent upgrade (403 Cloudflare)
- [ ] Wake word — Reduzir falsos positivos
- [ ] Jarvis tools — web_search ainda com erro autenticacao
- [x] Admin Produtos — Funcionando (CRUD + liberar downloads)
- [x] Criar usuarios no admin — Funcionando (POST /admin/tenants)
- [x] Shop API — Funcionando (/shop/products publico)
- [x] Chrome iOS — Funcionando (WebSocket + mic fallback)
- [x] Download documentos — Funcionando (botao 📥 no painel atividades)
- [x] Hora local — Funcionando (timezone do navegador)
- [x] Login olho senha — Funcionando (🙈/👁️)
- [x] Mobile responsive — Funcionando (retrato/paisagem)
- [x] Salvar chave API — Funcionando (PUT /api/config/api-key)
- [x] Jarvis multi-provedor — Funcionando (Gemini + OpenRouter + Groq + MiMo)
- [x] Jarvis vozes naturais — Funcionando (10 vozes Edge TTS + browser)
- [x] Jarvis velocidade voz — Funcionando (0.5x a 3.0x)
- [x] Jarvis botao parar — Funcionando (sempre visivel)
- [x] Jarvis UI discreta — Funcionando (botoes transparentes)
- [x] Jarvis ESC fecha config — Funcionando
- [x] Instâncias — Funcionando (CRUD + config + ajuda)
- [x] Charon iOS — Funcionando (WebSocket + audio fallback)
- [x] Charon audio streaming — Funcionando (chunks imediatos, prebuffer 24k)
- [x] Charon idle timeout — Funcionando (watchdog 5min, ping 30s)
- [x] Charon respostas longas — Funcionando (flush no interrupted, 500ms delay)
- [x] Charon ESC volta chat — Funcionando
- [x] Reminder natural language — Funcionando (amanha, em 2 horas, sexta)
- [x] Save document formatacao — Funcionando (markdown→HTML bonito)
- [x] Transcript persistente — Funcionando (localStorage 200 msgs)
- [x] AudioContext auto-recovery — Funcionando (recria se trava)
- [x] Admin Mestre — Funcionando (editar planos, usuarios, precos)
- [x] Plano Colaborador — Funcionando (free com uso total)
- [x] Admin nginx proxy — Funcionando (/admin/dashboard, /admin/tenants, /admin/plans)

### Infra
- [ ] GitHub Actions CI/CD (secrets VPS_HOST + VPS_SSH_KEY)
- [ ] Script deploy automatizado (deploy.sh completo)
- [x] Nginx /chat/ proxy — Adicionado no VPS
- [x] Nginx /admin/ proxy — Adicionado no VPS

## Comandos Uteis

```bash
# Deploy no VPS (USE O SCRIPT — ver secao "Comando de deploy (ATUAL)")
cd /root/DEEP-OS
git fetch origin master && git reset --hard origin/master && bash scripts/deploy-faf8f93.sh

# Restart backend  (ATENCAO: deepos-backend, SEM hifen)
systemctl restart deepos-backend

# Reload nginx
systemctl reload nginx

# Verificar status  (deepos-backend = SEM hifen)
systemctl status deepos-backend
systemctl status nginx

# Logs do backend
journalctl -u deepos-backend --no-pager -n 30
journalctl -u deepos-backend -f --no-pager

# Verificar chave API
cat /root/DEEP-OS/backend/config/api_keys.json

# Testar chave Gemini
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=SUA_CHAVE" | head -5

# Verificar portas
lsof -i :8001
lsof -i :443
```

## Regras Importantes

1. **Branch Git** — Usar `master` (nao `main`)
2. **VPS** — Python 3.14, sempre usar `opencv-python-headless`
3. **Docker** — NAO USAR (VPS com 4GB RAM insuficiente)
4. **API keys** — `api_keys.json` NO .gitignore — nao commitar chaves
5. **pyautogui** — `except Exception` (nao `except ImportError`) — KeyError em headless
6. **Nginx WebSocket** — `proxy_http_version 1.1` + `proxy_read_timeout 86400s` obrigatorios
7. **Identity sync** — `PUT /api/config/identity` salva em 3 lugares
8. **WebSocket** — nginx proxy redireciona `/ws/` para `127.0.0.1:8001`
9. **SSH VPS** — Nao funciona de fora (Hostinger bloqueia). Usar terminal web.
10. **UFW** — Portas: 22, 80, 443, 5176, 8001, 8010
11. **Terminal** — bash no Linux, cmd.exe/powershell no Windows (detecta automaticamente)
12. **pip VPS** — Usar venv (`/root/DEEP-OS/venv/`) — ambiente externally-managed
13. **Frontend** — Rebuild necessario apos mudancas TSX (`npm run build:saas`),
    e publicar em `/var/www/deep-os/frontend/dist-saas` (o deploy faz os dois)
14. **Deploy no VPS** — Use `scripts/deploy-faf8f93.sh`. **NAO** use
    `git checkout -- .` (descarta alteracoes locais) nem `git pull` direto
    (da conflito apos reescrita de historico). Prefira
    `git fetch` + `git reset --hard origin/master`
15. **Unit systemd** — `deepos-backend` (SEM hifen depois de "deep").
    `deep-os-backend` esta desabilitada (duplicada)
16. **Rotas FastAPI** — catch-all (`/{param}`) SEMPRE por ultimo no arquivo,
    senao ele captura os paths literais
17. **Fuso horario** — o servidor roda em **UTC**; o usuario em Brasilia (UTC-3).
    Sempre calcular na hora local, gravar em UTC e exibir convertendo de volta
18. **Testes** — teste pela **rota (HTTP)**, nao so pela funcao. Bugs de
    roteamento passam despercebidos ao chamar a funcao direto
19. **Seguranca** — trocar `MASTER_PASSWORD` (hardcoded) e definir `JWT_SECRET`
    por variavel de ambiente
20. **Sanitizacao de caminho do tenant tem UMA fonte** —
    `core.tenant_identity.tenant_slug()`. Duas implementacoes diferentes geram
    duas pastas diferentes e os dados ficam inalcancaveis (foi o bug do
    download 404). Nunca sanitize por conta propria em rota nova.
21. **`:` e proibido em nome de pasta no Windows.** Pasta criada no Linux com
    `:` nao existe no PC — testes locais **nao** cobrem esses casos. Se um bug
    depende do nome de arquivo gerado no VPS, teste no VPS.
22. **Log em caminho de alta frequencia enche o disco.** Um `print` por chunk
    de audio gerou 27 GB de syslog. Logue por turno/resumo, ou so o anormal
23. **Deteccao local vs externo pelo `Host`, nao pelo IP.** Atras de proxy
    reverso o IP do cliente e sempre `127.0.0.1` — usar o IP libera o mundo
24. **Painel de VPS tem metrica em cache.** `df -h` no servidor e a verdade
    (o painel mostrava 47 GB quando o real era 20 GB)