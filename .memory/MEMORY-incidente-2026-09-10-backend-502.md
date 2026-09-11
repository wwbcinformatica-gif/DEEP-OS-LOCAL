# MEMORY — Incidente 2026-09-10: Backend VPS morto (502) por revert no repositorio errado

**Severidade:** critica — site https://deep-os.tech ficou com API fora do ar
**Duracao:** ~2h (descoberta ate correcao)
**Status:** RESOLVIDO

---

## Sintoma reportado

- Site abria, mas login dava `JSON.parse: unexpected character at line 1 column 1`
- API retornava **502 Bad Gateway** (nginx `1.28.3`)

## Causa raiz

Um modelo de IA alterou `backend/routes/chatbot.py` adicionando isolamento por tenant
e quebrou o import do backend. A causa tecnica:

```python
from core.auth import require_plan, get_current_tenant_id
from fastapi import APIRouter, HTTPException          # Depends NAO importado

async def save_config(config: ChatBotConfig, admin: str = Depends(require_admin)):
async def test_provider(req: TestRequest, tenant_id: str = Depends(require_plan(1))):
```

### O detalhe que engana (REGRA IMPORTANTE)

`Depends(...)` no **default de um parametro** e resolvido **no import do modulo**,
quando o FastAPI monta as rotas. **Nao e erro de requisicao — e erro de BOOT.**

Consequencia: `main.py` inteiro estoura com `NameError` no import, o uvicorn **nao sobe**,
o systemd entra em loop de restart, e o nginx fica sem ninguem na porta 8001 → **502**.

O frontend recebe o HTML do 502 (`<!doctype html>`) em vez de JSON, e o `JSON.parse`
do navegador falha com "unexpected character at line 1 column 1". **Esse erro de
frontend e sintoma de backend morto, nao bug de frontend.**

## POR QUE DEMOROU — a licao principal

Existem **TRES repositorios** neste projeto e o modelo confundiu os tres:

| Repositorio | Caminho | Estado apos o incidente |
|---|---|---|
| PC local | `C:\DEEP-OS` | revertido para `80ae949` (ok) |
| GitHub | `origin/master` | revertido (ok) |
| **VPS** | `/root/DEEP-OS` | **NUNCA revertido — ficou quebrado** |

O modelo rodou `git reset --hard HEAD~2` + `push --force`, o que consertou PC e GitHub,
mas **o VPS nunca foi tocado**. Ele tentou deployar, mas:

- `bash /root/DEEP-OS/deploy.sh` → `Permission denied`
- `chmod +x ... && bash ...` → `O token '&&' nao e um separador valido` (era PowerShell)
- `systemctl restart` → `'systemctl' nao e reconhecido` (era PowerShell, nao Linux)
- `git -C /root/DEEP-OS reset` → `fatal: cannot change to '/root/DEEP-OS'`

**Ele estava rodando comandos Linux dentro do PowerShell do Windows.** Quando os comandos
Linux falhavam, ele **caia para o repo local** e mexia nele. Ele nao tinha acesso ao VPS.

### REGRA CRITICA

Quando um agente afirma "reverti tudo" ou "fiz deploy", **confirme em qual das tres
copias ele agiu**. Um `git reset` no PC + push no GitHub **nao reverte o VPS**.
O relatorio final do modelo afirmava "Backend reiniciando com codigo original" e
"git push concluido" — **ambos nunca verificados**.

### Como diagnosticar rapido

```bash
# Do PC — 3 testes que identificam o problema em segundos:
node -e "..."   # checar HTTP (Windows curl/git falham com SEC_E_NO_CREDENTIALS)
```

- `GET https://deep-os.tech/` → **200** = frontend ok
- `GET https://deep-os.tech/<rota-api>` → **502** = **BACKEND MORTO no VPS**

502 = nginx vivo, ninguem na 8001. 404 = backend vivo, rota errada.
**502 e a assinatura de backend morto.**

## Correcao aplicada

O `chatbot.py` foi o **unico** arquivo tocado pelos dois commits quebrados
(verificado: cada commit alterou exatamente 1 arquivo). Entao a correcao foi cirurgica:

```bash
cd /root/DEEP-OS
mkdir -p /root/backup-deepos
cp backend/routes/chatbot.py /root/backup-deepos/chatbot.py.quebrado
git show 80ae949:backend/routes/chatbot.py > backend/routes/chatbot.py
grep -cE "Depends|require_admin|core\.auth" backend/routes/chatbot.py   # deve ser 0

# validar sem subir servico:
cd backend && /root/DEEP-OS/venv/bin/python -c "import main; print('IMPORT OK')"

# subir:
systemctl reset-failed deep-os-backend
systemctl restart deep-os-backend
systemctl reload nginx
```

**Hash do arquivo bom** (`80ae949:backend/routes/chatbot.py`), 141 linhas:
`b29b5a1a0a2eb2802e61d092a475492f9b623255fc2f98914db5649a49c0719a`

### Verificacao final (confirmada)

```
plans/public   → 200  {"plans":[{"id":"free","name":"Colaborador",...
shop/products  → 200  {"products":[]}
auth/me        → 401  {"detail":"Nao autenticado"}     <- JSON, nao HTML
POST /auth/login → 200  JSON valido, user Master Admin, plan master
```

## Rotas publicas NAO usam prefixo /api

O nginx repassa direto. Descoberto durante o diagnostico:

| CORRETO | ERRADO (404) |
|---|---|
| `https://deep-os.tech/plans/public` | `/api/plans/public` |
| `https://deep-os.tech/shop/products` | `/api/shop/products` |
| `https://deep-os.tech/auth/me` | `/api/auth/me` |

## ARMADILHAS DESTE AMBIENTE

### 1. NAO rodar `deploy.sh` no VPS
Comeca com `git checkout -- .` (**descarta alteracoes locais**) e roda
`pip install -r requirements.txt` (17 deps `>=`, lento e desnecessario —
as deps ja estao instaladas). Ele tambem faz build de frontend, que
normalmente nao e necessario.

### 2. `requirements.txt` esta em `backend/`, nao na raiz
Foi isso que causou `ERROR: Could not open requirements file` quando o modelo
mandou `cd /root/DEEP-OS && pip install -r requirements.txt`.

### 3. Terminal do console Hostinger corrompe colagens grandes
Pastar blocos longos **embaralha as linhas** — comandos se fundem, `mkdir` some,
`sed` roda duas vezes. **Prefira blocos curtos** (3-5 linhas) no terminal do VPS.
Sintoma: `# remove "Depends" do import do fastapiackup-deepos/...`

### 4. TLS do Windows quebrado neste PC
`curl` e `git` falham com `schannel: AcquireCredentialsHandle failed:
SEC_E_NO_CREDENTIALS (0x8009030e)`. **Isso nao e problema do servidor.**
**Workaround: usar `node -e` com o modulo `https`** (Node usa OpenSSL proprio,
nao o schannel do Windows). Foi assim que o incidente foi diagnosticado.

### 5. `python` do PATH e o stub da Microsoft Store
`python` → "Python was not found". O real esta em `C:\DEEP-OS\venv\Scripts\python.exe`
(ou `py -3.12`). No VPS: `/root/DEEP-OS/venv/bin/python`.

## Preservacao do trabalho descartado

Os 2 commits desfeitos existiam **so no reflog** (iriam sumir no proximo `git gc`).
Salvos na branch **`backup/chatbot-tenant-isolation`** (commit `b4fced8`).

- `ef5c51b` = feat: tenant isolation no chatbot config
- `b4fced8` = fix INCOMPLETO (adicionou `Depends`, esqueceu `require_admin`)

**Ao refazer o isolamento por tenant:** `require_admin` esta em `core/auth.py:145`.
Nao esqueca de **importar** — foi exatamente isso que faltou.

## Pendencias que sobraram

1. **Bug do nome do assistente** — nao corrigido. Motivo original de tudo.
2. **VPS esta 1 commit atras** do GitHub (`ef5c51b` vs `80ae949`).
3. **`dist-saas` versionado no Git** — pendencia antiga (sessoes 46/47).
4. **SEGURANCA:** senha de root do VPS e `admin123@` das contas master foram
   expostas em texto puro (chat / STATUS.md / memory.md). **Trocar.**
