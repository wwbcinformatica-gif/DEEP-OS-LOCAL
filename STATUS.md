# DEEP-OS — Status do Projeto

**Ultima atualizacao:** 2026-09-11 (Sessao 48) — Correcoes de isolamento, lembretes, audio e microfone

**Commit em producao:** `1c6acbf` | **Backend:** `deepos-backend.service` (active) | **Site:** https://deep-os.tech

**Leia primeiro:** [`memory.md`](memory.md) (regras e armadilhas do projeto),
[`docs/CHARON-VOZ.md`](docs/CHARON-VOZ.md) (arquitetura da voz — a parte mais
complexa do sistema) e [`RECUPERAR-VPS.md`](RECUPERAR-VPS.md) (procedimento de
emergencia do servidor).

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
