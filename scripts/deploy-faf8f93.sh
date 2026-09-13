#!/bin/bash
# ============================================================================
# DEEP-OS — Deploy do commit faf8f93 (identidade por tenant, lembretes, audio)
#
# Uso no VPS:
#   cd /root/DEEP-OS && bash <(curl -fsSL https://raw.githubusercontent.com/wwbcinformatica-gif/DEEP-OS/master/scripts/deploy-faf8f93.sh)
#
# Ou, se preferir baixar antes de executar:
#   cd /root/DEEP-OS
#   curl -fsSL -o /tmp/deploy.sh https://raw.githubusercontent.com/wwbcinformatica-gif/DEEP-OS/master/scripts/deploy-faf8f93.sh
#   less /tmp/deploy.sh          # revise antes de rodar
#   bash /tmp/deploy.sh
#
# O que faz:
#   1. backup das API keys      5. restart backend + migrate
#   2. para o backend           6. build do frontend (audio + token)
#   3. git reset --hard faf8f93 7. publica no nginx
#   4. limpa bytecode           8. verifica tudo
#
# NAO roda `pip install` (as dependencias ja estao instaladas) e NAO usa o
# deploy.sh antigo, que comeca com `git checkout -- .` (descarta mudancas).
# ============================================================================
set -uo pipefail

# Commit alvo. Usa o que estiver em origin/master em vez de um hash fixo,
# para o script nao ficar obsoleto a cada commit novo.
COMMIT="${COMMIT:-origin/master}"
REPO="/root/DEEP-OS"
WEBROOT="/var/www/deep-os/frontend/dist-saas"
BACKUP="/root/backup-deepos"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[0;32mOK\033[0m %s\n' "$1"; }
warn() { printf '    \033[0;33mAVISO\033[0m %s\n' "$1"; }
die()  { printf '\n\033[0;31m### PAROU: %s\033[0m\n' "$1"; exit 1; }

cd "$REPO" || die "nao achei $REPO"

# ── 0. Descobrir QUAL unit atende a porta 8001 ──────────────────────────────
# Existem DUAS units no sistema com nomes quase iguais (diferem por um hifen):
#   deepos-backend    /root/DEEP-OS/venv/bin/python3 -m uvicorn   <- a boa
#   deep-os-backend   /root/DEEP-OS/venv/bin/uvicorn              <- duplicada
# Detectar em vez de assumir evita mexer na unit errada.
detectar_unit() {
  local pid
  pid="$(ss -lptnH 'sport = :8001' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)"
  if [ -n "${pid:-}" ]; then
    local unit
    unit="$(ps -o unit= -p "$pid" 2>/dev/null | tr -d ' ')"
    if [ -n "$unit" ] && systemctl list-units --all --no-legend "$unit" >/dev/null 2>&1; then
      echo "$unit"; return
    fi
  fi
  # Fallback: a primeira que estiver ativa
  for u in deepos-backend deep-os-backend; do
    [ "$(systemctl is-active "$u" 2>/dev/null)" = "active" ] && { echo "$u"; return; }
  done
  echo "deepos-backend"
}

UNIT="$(detectar_unit)"
say "0/8  Unit que atende a porta 8001: $UNIT"
for u in deepos-backend deep-os-backend; do
  printf '    %-20s active=%-10s enabled=%s\n' "$u" \
    "$(systemctl is-active "$u" 2>/dev/null)" "$(systemctl is-enabled "$u" 2>/dev/null)"
done
if [ "$(systemctl is-active deep-os-backend 2>/dev/null)" = "active" ] \
   && [ "$UNIT" = "deepos-backend" ]; then
  warn "ha DUAS units ativas — a duplicada pode roubar a porta."
  warn "rode: bash scripts/fix-units-duplicadas.sh"
fi

# ── 1. Backup ───────────────────────────────────────────────────────────────
say "1/8  Backup das chaves de API"
mkdir -p "$BACKUP"
STAMP="$(date +%Y%m%d_%H%M%S)"
if [ -f backend/config/api_keys.json ]; then
  cp backend/config/api_keys.json "$BACKUP/api_keys.json.$STAMP" \
    && ok "chave salva em $BACKUP/api_keys.json.$STAMP" \
    || warn "nao consegui copiar api_keys.json"
else
  warn "backend/config/api_keys.json nao existe (Charon vai pedir a chave de novo)"
fi
cp config.yaml "$BACKUP/config.yaml.$STAMP" 2>/dev/null && ok "config.yaml salvo" || warn "sem config.yaml"

# ── 2. Parar o backend ──────────────────────────────────────────────────────
say "2/8  Parando o backend ($UNIT)"
systemctl stop "$UNIT" 2>/dev/null && ok "backend parado" || warn "backend ja estava parado"

# ── 3. Codigo ───────────────────────────────────────────────────────────────
say "3/8  Baixando o codigo ($COMMIT)"
git fetch origin master 2>&1 | tail -2

ALVO="$(git rev-parse "$COMMIT^{commit}" 2>/dev/null)" || true
if [ -z "$ALVO" ]; then
  die "nao consegui resolver o commit '$COMMIT'. O VPS alcanca o GitHub?"
fi
ok "commit alvo: $(git rev-parse --short "$ALVO")"

# Guarda qualquer alteracao local antes de descartar
git stash push -u -m "pre-deploy-$STAMP" >/dev/null 2>&1 && ok "alteracoes locais guardadas no stash" || true

git reset --hard "$ALVO" >/dev/null 2>&1 || die "git reset falhou"
ok "codigo em $(git rev-parse --short HEAD) — $(git log -1 --format=%s)"

# Recupera o que foi guardado (o stash pode ter o api_keys.json, que e ignorado)
git stash pop >/dev/null 2>&1 && ok "alteracoes locais restauradas" || true

# ── 4. Sanidade dos arquivos novos ──────────────────────────────────────────
say "4/8  Conferindo os arquivos novos"
FALTANDO=0
for f in backend/config.py backend/core/tenant_identity.py backend/core/reminders.py \
         backend/core/reminder_doc.py backend/routes/reminders.py; do
  if [ -f "$f" ]; then ok "$f"; else warn "FALTANDO: $f"; FALTANDO=1; fi
done
[ "$FALTANDO" = "1" ] && die "arquivos essenciais faltando — nao vou reiniciar com o codigo incompleto"

find backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
ok "bytecode antigo removido"

# Testa o import ANTES de subir o servico (pega erro de boot na hora)
# IMPORTANTE: rodar de dentro de backend/ — main.py fica la, e o sys.path
# precisa de backend/ para resolver `routes.*` e `core.*`.
cd "$REPO/backend" || die "nao achei $REPO/backend"
if /root/DEEP-OS/venv/bin/python -c "import main" 2>/tmp/import_err.txt; then
  ok "import do backend OK"
else
  echo "--- erro ---"; tail -25 /tmp/import_err.txt
  cd "$REPO"
  # Nao deixar o site caido: tenta subir de volta o servico de qualquer forma,
  # porque o codigo ja e o ultimo commit valido conhecido.
  systemctl start "$UNIT" 2>/dev/null
  sleep 3
  warn "tentei religar o backend: $(systemctl is-active "$UNIT")"
  die "o backend NAO importa. Veja o erro acima."
fi

# Confirma o shim do config (bug que impedia youtube_video de carregar)
if /root/DEEP-OS/venv/bin/python -c "
import config, sys
sys.exit(0 if getattr(config, '__file__', None) and hasattr(config, 'get_os') else 1)
" 2>/dev/null; then
  ok "config.py correto (get_os disponivel)"
else
  warn "config.py ainda com problema — youtube_video nao vai carregar"
fi

# ── 5. Subir o backend (a migracao roda no startup) ─────────────────────────
say "5/8  Subindo o backend (cria as tabelas/colunas novas)"
systemctl reset-failed "$UNIT" 2>/dev/null
systemctl start "$UNIT"

# Espera ficar ativo (ate 12s) em vez de confiar num sleep fixo — o startup
# leva alguns segundos e checar cedo demais reporta 'activating' por engano.
STATUS=""
for i in $(seq 1 6); do
  STATUS="$(systemctl is-active "$UNIT")"
  [ "$STATUS" = "active" ] && break
  sleep 2
done

if [ "$STATUS" = "active" ]; then
  ok "backend ativo ($UNIT)"
else
  warn "backend em estado '$STATUS' — veja os logs abaixo"
  journalctl -u "$UNIT" --no-pager -n 25
  die "backend nao subiu. O frontend NAO foi alterado; o site segue no ar."
fi

# ── 6. Build do frontend ────────────────────────────────────────────────────
say "6/8  Buildando o frontend (audio do Charon + token de identidade)"
cd "$REPO/frontend" || die "nao achei $REPO/frontend"
rm -rf node_modules/.vite
if npm run build:saas > /tmp/build.log 2>&1; then
  ok "build concluida"
  tail -4 /tmp/build.log | sed 's/^/    /'
else
  echo "--- ultimas linhas do build ---"; tail -25 /tmp/build.log
  warn "build FALHOU — o frontend antigo continua publicado (site no ar)"
fi
cd "$REPO"

# ── 7. Publicar no nginx ────────────────────────────────────────────────────
say "7/8  Publicando no nginx"
if [ -d frontend/dist-saas ] && [ -f frontend/dist-saas/index.html ]; then
  mkdir -p "$WEBROOT"
  rm -rf "${WEBROOT:?}"/*
  cp -r frontend/dist-saas/* "$WEBROOT"/
  ok "arquivos copiados para $WEBROOT"
  ls -1 "$WEBROOT" | head -5 | sed 's/^/    /'
else
  warn "frontend/dist-saas nao encontrado — mantive o que ja estava publicado"
fi
systemctl reload nginx 2>/dev/null && ok "nginx recarregado" || warn "falha ao recarregar o nginx"

# ── 7b. As ROTAS do nginx: o deploy NAO instala config ──────────────────────
#
# BUG QUE ISTO PEGA (aconteceu de verdade)
#
# Eu adicionei `location /monitor` em `nginx/vps-nginx.conf` (o arquivo DO
# PROJETO) e subi o deploy. O site ficou com as barras de CPU/RAM/VRAM vazias,
# porque:
#
#   1. a config REAL da VPS e `/etc/nginx/sites-enabled/deepos`, escrita a mao,
#      e NAO e o arquivo do projeto (esse e so referencia, e ja divergiu);
#   2. este script publica o frontend e recarrega o nginx, mas NUNCA instala
#      config de nginx.
#
# Resultado: o codigo novo estava publicado e a rota nao existia. O pedido caia
# no `location /` (SPA fallback) e voltava `index.html` com **HTTP 200** — o
# frontend le como sucesso, o `.json()` falha e o sintoma nao aponta para o
# nginx. Mesma armadilha da secao 9 do docs/CONTINUAR.md.
#
# Aqui a gente TESTA cada rota que o frontend chama com caminho relativo. Nao da
# para instalar a config automaticamente (o arquivo real tem TLS, server_name e
# outras coisas que nao estao no repo), mas da para AVISAR na hora do deploy em
# vez de o usuario descobrir pela tela quebrada.
say "7b/8  Conferindo se o nginx encaminha as rotas do frontend"
ROTAS_FALTANDO=0
for ROTA in /monitor /llamacpp/models /ollama/status; do
  RESP="$(curl -s --max-time 8 "http://127.0.0.1${ROTA}" 2>/dev/null | head -c 1)"
  if [ "$RESP" = "{" ] || [ "$RESP" = "[" ]; then
    ok "$ROTA -> JSON (nginx encaminha ao backend)"
  elif [ "$RESP" = "<" ]; then
    warn "$ROTA -> HTML (nginx NAO encaminha: caiu no location /)"
    echo "        Para corrigir, adicione ao /etc/nginx/sites-enabled/deepos,"
    echo "        ANTES do 'location / {':"
    echo "            location ${ROTA%%/*}/ { proxy_pass http://127.0.0.1:8001;"
    echo "                proxy_set_header Host \$host; }"
    ROTAS_FALTANDO=$((ROTAS_FALTANDO + 1))
  else
    warn "$ROTA -> sem resposta (backend fora do ar? rota inexistente?)"
  fi
done
if [ "$ROTAS_FALTANDO" -gt 0 ]; then
  echo ""
  echo "  ATENCAO: $ROTAS_FALTANDO rota(s) nao chegam ao backend."
  echo "           O site funciona, mas o recurso correspondente fica vazio"
  echo "           SEM erro visivel no navegador. Valide com: nginx -t"
fi

# ── 8. Verificacao ──────────────────────────────────────────────────────────
say "8/8  Verificacao"
code() { curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$1"; }

B="$(code http://127.0.0.1:8001/plans/public)"
echo "    backend local .................. HTTP $B"
[ "$B" = "200" ] && ok "backend respondendo" || warn "backend inesperado"

echo ""
echo "    --- isolamento por tenant ---"
/root/DEEP-OS/venv/bin/python - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "/root/DEEP-OS/backend")
try:
    # set_db_path PRIMEIRO: sem ele o pool nao existe e get_conn() falha
    # com "Pool nao inicializado". O app chama isso no startup; aqui
    # (script solto) precisamos chamar na mao.
    from database.connection import get_conn, init_db, set_db_path
    set_db_path(Path("/root/DEEP-OS/data/interactions.db"))
    init_db()
    conn = get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()}
    for c in ("assistant_name", "user_name"):
        print(f"    tenants.{c}: {'OK' if c in cols else 'FALTANDO'}")
    tabs = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    print(f"    tabela reminders: {'OK' if 'reminders' in tabs else 'FALTANDO'}")
    n = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    print(f"    lembretes registrados: {n}")
except Exception as e:
    print(f"    erro ao checar: {e}")
PY

echo ""
echo "    --- tools do Charon ---"
/root/DEEP-OS/venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "/root/DEEP-OS/backend")
try:
    import config
    from config import is_headless
    print(f"    config.py: {config.__file__}")
    print(f"    get_os disponivel: {hasattr(config, 'get_os')}")
    print(f"    is_headless(): {is_headless()}")
except Exception as e:
    print(f"    erro: {e}")
import os
os.environ.setdefault("DISPLAY", "")
try:
    import pyautogui  # noqa
    print("    pyautogui importou (o uso e que falha sem tela)")
except Exception as e:
    print(f"    pyautogui: {type(e).__name__} (esperado em algum caso)")
PY

echo ""
echo "    --- site publico (pode levar alguns segundos) ---"
S="$(code https://deep-os.tech/)"
A="$(code https://deep-os.tech/plans/public)"
echo "    frontend ....... HTTP $S"
echo "    API ............ HTTP $A"
[ "$A" = "200" ] && ok "API publica respondendo" || warn "API respondeu $A"

printf '\n\033[1;36m=============== RESUMO ===============\033[0m\n'
printf '  commit publicado : %s\n' "$(git rev-parse --short HEAD)"
printf '  backend          : %s (%s)\n' "$(systemctl is-active "$UNIT")" "$UNIT"
printf '  nginx            : %s\n' "$(systemctl is-active nginx)"
echo ""
echo "  Teste no navegador (https://deep-os.tech):"
echo "   1. Charon -> Config -> mude o nome do assistente -> salvar"
echo "   2. Logue com OUTRO usuario -> confirme que o nome NAO mudou para ele"
echo "   3. Peca um lembrete: 'me lembre de tomar agua em 2 horas'"
echo "   4. Peca: 'quais lembretes eu tenho' e depois 'gera um documento'"
echo ""
echo "  Se algo falhar:"
echo "   journalctl -u $UNIT --no-pager -n 40"
echo "   ls -la $BACKUP     # backups desta execucao"
