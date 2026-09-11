# MEMORY — Fuso horario nos lembretes + units systemd duplicadas

Sessão de 2026-09-10/11. Continuação de `MEMORY-identidade-tenant-lembretes-audio.md`.

---

## 1. BUG: "esse horário já passou" ao pedir lembrete

### Causa raiz

**O VPS roda em UTC. O usuário está em Brasília (UTC-3).**

`backend/actions/reminder.py` calculava "agora" com `datetime.now()` — o relógio
do **servidor**. Às 21h em Brasília, o servidor achava que eram 00h do dia
seguinte. Um lembrete pedido para "14:30" parecia já ter passado.

E ia além do `now`: o `fire_at` era gravado como se fosse hora local do
servidor, então mesmo quando aceitava, dispararia **3 horas errado**.

O `voice_ws` já recebia o fuso do usuário (campo `timezone` que o frontend
envia via `Intl.DateTimeFormat().resolvedOptions().timeZone`), mas usava
**só para a fala** — nunca para agendar.

### Correção (convenção de fuso)

| Camada | Antes | Agora |
|---|---|---|
| Cálculo do "agora" | `datetime.now()` (UTC) | `now_local()` no fuso do usuário |
| Gravação no banco | hora do servidor | **UTC** (convertido) |
| Coluna `tz` | não existia | guarda `America/Sao_Paulo` |
| Exibição | direto do banco | UTC → hora local |
| Disparo (`due_reminders`) | `datetime.now()` | `datetime.utcnow()` |

Arquivos:
- `core/tenant_identity.py` — `ContextVar current_timezone` + helpers
  `now_utc()`, `now_local()`, `get_tzinfo()`, `safe_zoneinfo()`, `DEFAULT_TZ`
- `actions/reminder.py` — usa `now_local()`
- `core/reminders.py` — `add_reminder(fire_at, ..., tz=)` converte para UTC;
  `due_reminders` compara com `utcnow()`
- `core/reminder_doc.py` — `_fmt_humano(fire_at, tz)` converte na exibição
- `routes/voice_ws.py` — `set_current_timezone(user_tz)` no start da conexão
- `routes/reminders.py` — aceita `timezone` no corpo ou header `X-Timezone`
- `database/connection.py` — coluna `reminders.tz` com migração

### REGRA APRENDIDA
**Nunca usar `datetime.now()` para lógica de negócio.** O servidor está em UTC
e o usuário não. Sempre: calcular na hora local do usuário, gravar em UTC,
exibir convertendo de volta.

### Verificação
`tests-manual/test_reminder_timezone.py` — envia 23:11 local, confirma gravação
as 02:11 UTC e exibição de volta como 23:11.

**ATENÇÃO:** a máquina de dev do usuário está em Brasília, então
`datetime.now()` == `utcnow()` **localmente** — o bug NÃO se reproduz no
Windows. A validação real é no VPS (UTC).

---

## 2. BUG GRAVE: duas units systemd disputando a porta 8001

### Sintoma
Backend em loop `[Errno 98] address already in use`, mesmo matando os
processos. O site ficava no ar por causa do processo "errado".

### Causa raiz
```
/etc/systemd/system/deepos-backend.service     <- a BOA (atende o site)
/etc/systemd/system/deep-os-backend.service    <- DUPLICADA
```
Diferem por **um hífen**. As duas `enabled`, as duas subindo no boot.

Matar processos nunca resolvia: a duplicada tinha `Restart=always` e
ressuscitava em ~5s (o padrão do systemd é `RestartSec=100ms`, agressivo).

### REGRA APRENDIDA
**Quando a porta é reocupada sozinha, suspeitar de unit systemd duplicada
ANTES de processo solto.** O comando que revela:
```bash
grep -rl "uvicorn" /etc/systemd/system/
systemctl list-units --all | grep -i backend
```

### Correção
`scripts/fix-units-duplicadas.sh`: remove o drop-in com `--reuse-port`,
`disable` + `mask` na duplicada, e endurece a boa com `RestartSec=5` +
`StartLimitBurst=5` (evita loop infinito).

### Erros que cometi neste episódio (não repetir)
1. `fuser -k` sozinho não resolve — corrida com o `Restart=always`.
2. Apliquei `--reuse-port` **sem checar se o uvicorn suporta**. Quem define o
   suporte é a versão do **uvicorn**, não a do Python. Deu
   `No such option '--reuse-port'` e piorou o loop.
3. Assumi o nome da unit (`deep-os-backend`) no `deploy.sh` em vez de
   **detectar**. O script parava a unit errada. Agora detecta via
   `ss -lptnH 'sport = :8001'` + `ps -o unit= -p <pid>`.

---

## 3. BUG: 404 numa rota que existe (`/api/reminders`)

### Sintoma confuso
```
GET /api/reminders sem token  -> 401  {"detail":"Não autenticado"}   (rota existe)
GET /api/reminders com token  -> 404  {"error":"Recurso não encontrado"}
```

### Causa raiz
O **master admin é hardcoded** e **não tem linha na tabela `tenants`**, mas o
`sub` do JWT dele é `"master-admin"`. O `require_plan(1)` consultava
`SELECT plan FROM tenants WHERE id = ?` e, não achando, levantava
**404 "Tenant não encontrado"** — fazendo uma rota existente parecer
inexistente.

### Correção
`core/auth.py::require_plan` agora lê `is_admin`/`is_master` do payload e
libera sem checar plano. Também aceita `PLAN_HIERARCHY` indexado por enum
**ou** por string.

### REGRA APRENDIDA
**Quando der 401 sem token e 404 com token no mesmo path, o problema está na
dependency de auth, não no roteamento.** O 401 prova que a rota existe.

### Erro que cometi
Meu primeiro teste usou um tenant **real** de teste, então passou — não
reproduziu. Faltou testar o caso do **master admin** (sub sem linha no banco).

---

## Estado final verificado (produção)

```
commit            3e2f400
backend           active (deepos-backend.service)
porta 8001        1 único dono
nginx             active
tenants.assistant_name / user_name   OK
tabela reminders + coluna tz         OK
is_headless()     True
config.py shim    ativo (get_os disponivel: True)

/plans/public              200
/api/config/identity       200  {"assistant_name":"Charon","user_name":"Wilson"}
/api/reminders             200  (era 404)
/api/reminders/summary     200
POST /api/reminders        200  fuso convertido corretamente
```

## Pendências
1. **Frontend não envia fuso nas chamadas HTTP de lembrete** — as rotas aceitam
   `X-Timezone`, mas nenhum componente as usa ainda (hoje os lembretes vêm por
   voz, onde o fuso chega). Se usar a lista por HTTP, incluir o header.
2. **`systemctl mask` falhou** na unit duplicada; o `disable` funcionou.
   Se quiser garantia, rodar `systemctl mask deep-os-backend`.
3. **`downloads/` é compartilhado entre tenants** (ver memória anterior).
4. **Senha de root do VPS exposta em chat** — trocar.
