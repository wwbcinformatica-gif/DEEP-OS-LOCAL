# MEMORY — Identidade por tenant + Lembretes + Audio do Charon (2026-09-10)

Sessao de correcao apos o incidente do backend 502
(ver `MEMORY-incidente-2026-09-10-backend-502.md`).

---

## 1. BUG: nome do assistente aparecia para todos os usuarios

### Causa raiz

`assistant_name` e `user_name` viviam **apenas** em `config.yaml` (arquivo GLOBAL):

- `GET /api/config/identity` lia de `config.yaml`
- `PUT /api/config/identity` **sobrescrevia** `config.yaml`

Um unico arquivo compartilhado por todos os assinantes. Quando qualquer usuario
salvava o nome, mudava para todo mundo. O ultimo a salvar vencia.

Pior: a rota **nao tinha autenticacao nenhuma**. O backend nem sabia quem era
o usuario — nem `tenant_id`, nem token. Por isso nao havia como isolar.

Detalhe: o `middleware/tenant.py` **nao e montado no main.py** — e codigo morto.
Ele sugere isolamento por bancos separados, que o projeto nao usa na pratica.

### Solucao implementada

**Schema** (`database/connection.py`): colunas novas em `tenants`, com migracao
idempotente via `PRAGMA table_info` (SQLite nao tem `ADD COLUMN IF NOT EXISTS`):

```python
("assistant_name", "ALTER TABLE tenants ADD COLUMN assistant_name TEXT"),
("user_name",      "ALTER TABLE tenants ADD COLUMN user_name TEXT"),
```

**Modulo novo** `core/tenant_identity.py` — resolucao nesta ordem:
1. Banco, por `tenant_id` (isolamento real)
2. `config.yaml` global (fallback p/ app desktop sem login)
3. `api_keys.json` / default

**`core/tenant_identity.py` tambem centraliza o ContextVar `current_tenant_id`**,
preenchido em dois pontos:
- `routes/config.py` — via JWT, por requisicao HTTP
- `routes/voice_ws.py` — via `?token=`, por conexao de WebSocket

ContextVar e copiado para threads do `run_in_executor`, entao as **actions do
Charon tambem enxergam o tenant**.

**Rotas** (`routes/config.py`): `GET`/`PUT /api/config/identity` agora usam
`Depends(get_current_tenant_optional)`:
- com JWT -> grava/le **so no tenant** (`config.yaml` global fica intocado)
- sem JWT -> grava no global (app desktop), preservando compatibilidade

**Frontend** (`CharonPage.tsx`): passa `Authorization: Bearer <saas_token>` nas
chamadas de identity, e `?token=` na URL do WebSocket de voz.

### Regra aprendida
`custom_color` e `voice` continuam globais de proposito — sao preferencia de UI,
nao identidade. So `assistant_name` e `user_name` sao por tenant.

---

## 2. BUG: "Nao consegui registrar o lembrete no agendador do sistema"

### Causa raiz

A action `reminder` agendava via `schtasks` (Windows), `launchctl` (macOS),
`systemd-run --user` ou `at` (Linux). **Num VPS headless NENHUMA funciona:**

| Via | Por que falha |
|---|---|
| `systemd-run --user` | Exige session bus do D-Bus; nao existe em servico root |
| `at` | Nao vem instalado no Ubuntu por padrao |
| `notify-send` (no script) | Nao ha desktop para notificar |
| `schtasks`/`launchctl` | Sao de Windows/macOS |

As duas vias Linux falham -> retorna `""` -> mensagem de erro.

### Solucao implementada

`core/reminders.py` + tabela `reminders` no SQLite:

```sql
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT, message TEXT NOT NULL, fire_at DATETIME NOT NULL,
    status TEXT DEFAULT 'pending', channel TEXT DEFAULT 'voice',
    fired_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

- `actions/reminder.py` tenta **primeiro** persistir no banco; o agendador do
  sistema virou **fallback** (desktop com UI).
- `core/reminders.py` roda um loop asyncio (20s) que dispara os vencidos.
- `voice_ws.deliver_reminder()` entrega pelo WebSocket: manda `transcript`
  (aparece na conversa) + `reminder` + pede pra IA falar em voz.
- Rotas: `GET/POST /api/reminders`, `DELETE /api/reminders/{id}` (JWT, plano >= 1).
- Iniciado no `@app.on_event("startup")` do main.py.

**Vantagens:** funciona headless, sobrevive a restart/reboot, isolado por tenant,
reaproveita o WebSocket do Charon.

**Importante:** se nao houver sessao ativa, o lembrete NAO e marcado como `fired`
— fica pendente e tenta de novo no proximo ciclo (nao perde o lembrete).

### Limitacao conhecida
O parametro `repeat` (daily/weekly/monthly) esta declarado na tool do Gemini mas
**nao e implementado**. Lembretes sao de disparo unico.

---

## 3. BUG: voz do Charon engasgando e cortando o fim das frases

### Causa raiz

No `AudioWorklet` de playback (`CharonPage.tsx`, `PLAYBACK_WORKLET`):

```js
// ANTES
if (!this._started) { ...zeros...; return true; }   // nunca voltava a false
for (...) {
  if (this._available > 0) { ch[i] = this._ring[this._readPos]; ... }
  else { ch[i] = 0; }        // sub-run: emitia SILENCIO e seguia
}
```

**Nao havia drenagem nem recuperacao.** Quando o audio do Gemini atrasava:

1. **Meio da frase engasgava** — o ring esvaziava e o worklet emitia silencio
   no meio da fala, sem esperar mais audio.
2. **Fim da frase cortava as ultimas letras** — `_started` ficava `true` para
   sempre. A cauda da ultima palavra era consumida em silencio.

Agravantes:
- `_prebuf` de 24000 amostras (1s) era marginal.
- Dedup descartava apos 5 chunks iguais e **o contador nunca era zerado**, entao
  audio real podia ser engolido (fala picada).
- Backend fechava o turno com `sleep(0.5)` fixo — curto para a cauda do Gemini.

### Solucao implementada

**Worklet** (`frontend/src/components/saas/CharonPage.tsx`):
- `_ringSize` 192000 -> **384000** (16s de margem a 24kHz)
- `_prebuf` 24000 -> **36000** (1.5s de prebuffer)
- **Recuperacao de sub-run**: apos 5 amostras sem dado, volta a `_started = false`
  e re-arma o prebuffer — em vez de emitir silencio e comer a cauda
- Dedup: margem 5 -> 6, e o contador zera quando chega audio real
- `clear` tambem zera `_underruns`

**Backend** (`routes/voice_ws.py`): `TURN_TAIL_GRACE_S = 0.9` (era 0.5 fixo)
antes de fechar o turno, para os ultimos chunks chegarem.

### Como diagnosticar de novo
Se voltar a cortar, medir o atraso entre chunks. O backend ja loga:
`[VoiceWS] Recebido: data=True, ... (delay=Xms)`. Delays altos e regulares
indicam gargalo de rede/Gemini, nao do buffer.

---

## VERIFICACOES QUE PASSARAM

`tests-manual/test_tenant_identity.py` (3 tenants):
- cada tenant le o SEU nome
- salvar em t1 NAO altera t2/t3 (era exatamente o bug)
- tenant inexistente/None nao explode
- `set_identity` em tenant inexistente retorna False

`tests-manual/test_reminders.py`:
- criacao, listagem, isolamento por tenant
- deteccao de vencidos, marcacao de disparado, cancelamento
- a action responde "Lembrete criado para ..." (nao mais o erro do agendador)
- a action respeita o tenant
- casos de borda: passado, sem data, "em 2 horas"

Backend: `import main` OK (242 rotas), sintaxe OK em todos os arquivos alterados.
Frontend: typecheck sem erros novos (o projeto tem 17 erros PRE-EXISTENTES,
herdados de sessoes anteriores — nenhum introduzido aqui).
Worklet: sintaxe validada com o parser do Node.

## ARMADILHA DO AMBIENTE
`npm run build:saas` **falha neste PC com `spawn EPERM`** — o esbuild precisa
criar processo filho com stdio em pipe, bloqueado pelo sandbox. Nao e bug do
codigo. Buildar no VPS.
