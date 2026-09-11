#!/bin/bash
# ============================================================================
# DEEP-OS — Fix definitivo do conflito na porta 8001
#
# Uso:  bash /root/DEEP-OS/scripts/fix-definitivo-8001.sh
#
# Problema: aparecem DOIS uvicorn na porta 8001 (um da unit systemd, outro
# solto com PPID 1, invocado como `python3 -m uvicorn`). Quando o systemd
# reinicia, o outro esta segurando a porta -> [Errno 98] -> morte em loop.
# Com Restart=always, o servico entra em loop de falha.
#
# Solucao em duas partes:
#   1. Matar TODOS os uvicorn do projeto e liberar a porta
#   2. Aplicar drop-in com --reuse-port, para multiplos binds na mesma porta
#      serem aceitos pelo kernel (o conflito deixa de ser fatal)
# ============================================================================
set -uo pipefail

UNIT="deep-os-backend"
DROPIN_DIR="/etc/systemd/system/$UNIT.service.d"
DROPIN="$DROPIN_DIR/override.conf"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()  { printf '    \033[0;32mOK\033[0m %s\n' "$1"; }
warn(){ printf '    \033[0;33mAVISO\033[0m %s\n' "$1"; }
die() { printf '\n\033[0;31m### PAROU: %s\033[0m\n' "$1"; exit 1; }

[ "$(id -u)" = "0" ] || die "rode como root"

# ── 1. Inventario completo ──────────────────────────────────────────────────
say "1/6  Inventario: TODOS os processos uvicorn"
ps -eo pid,ppid,etimes,cmd 2>/dev/null | grep -E "uvicorn" | grep -v grep || echo "    (nenhum)"
echo ""
echo "    --- units systemd que citam uvicorn ---"
grep -rl "uvicorn" /etc/systemd/system/ 2>/dev/null | sed 's/^/    /' || echo "    (nenhuma)"
echo ""
echo "    --- quem esta na porta 8001 ---"
ss -lptn 'sport = :8001' 2>/dev/null || true

# ── 2. Parar tudo, sem deixar rastro ────────────────────────────────────────
say "2/6  Matando todos os uvicorn do projeto"
systemctl stop "$UNIT" 2>/dev/null && ok "unit parada" || warn "unit ja estava parada"
systemctl stop "$UNIT" 2>/dev/null; sleep 1      # confirma parada

# Mata qualquer uvicorn, de qualquer invocacao
pkill -9 -f "uvicorn main:app" 2>/dev/null && ok "uvicorn encerrado (pkill)" || warn "nenhum uvicorn pelo pkill"
pkill -9 -f "python3 -m uvicorn" 2>/dev/null || true
pkill -9 -f "/root/DEEP-OS/venv/bin/uvicorn" 2>/dev/null || true

command -v fuser >/dev/null 2>&1 && { fuser -k -9 8001/tcp 2>/dev/null && ok "porta limpa (fuser)" || true; }

# ── 3. Esperar a porta liberar de verdade ───────────────────────────────────
say "3/6  Aguardando a porta 8001 liberar"
for i in $(seq 1 25); do
  if ! ss -lnt 2>/dev/null | grep -q ':8001 '; then
    ok "porta 8001 livre (apos ${i}s)"
    break
  fi
  [ "$i" = "25" ] && { warn "porta ainda ocupada:"; ss -lptn 'sport = :8001'; die "nao consegui liberar a porta"; }
  sleep 1
done

# Confirma que nao sobrou nenhum processo
RESTANTES="$(ps -eo pid,cmd 2>/dev/null | grep -E "uvicorn" | grep -v grep | wc -l)"
[ "$RESTANTES" = "0" ] && ok "nenhum uvicorn restante" || { warn "ainda ha $RESTANTES processo(s):"; ps -eo pid,cmd | grep uvicorn | grep -v grep; }

# ── 4. Drop-in com --reuse-port ─────────────────────────────────────────────
say "4/6  Aplicando --reuse-port (evita conflito futuro)"
mkdir -p "$DROPIN_DIR"
cat > "$DROPIN" <<'EOF'
# DEEP-OS — override para tolerar multiplos binds na porta 8001.
#
# Sem isto, se qualquer processo solto segurar a 8001, o systemd falha com
# [Errno 98] e — por causa do Restart=always — entra em loop de falha.
# Com --reuse-port o kernel aceita o bind e divide as conexoes.
#
# Para desfazer: rm -rf /etc/systemd/system/deep-os-backend.service.d/
[Service]
ExecStart=
ExecStart=/root/DEEP-OS/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --reuse-port
EOF

ok "drop-in gravado em $DROPIN"
systemctl daemon-reload && ok "systemd recarregado"
echo "    --- config efetiva agora ---"
systemctl cat "$UNIT" 2>/dev/null | grep -E "^(ExecStart|WorkingDirectory|Restart)" | sed 's/^/    /'

# ── 5. Subir e confirmar ────────────────────────────────────────────────────
say "5/6  Subindo o backend"
systemctl reset-failed "$UNIT" 2>/dev/null
systemctl start "$UNIT"
sleep 6

ACTIVE="$(systemctl is-active "$UNIT")"
[ "$ACTIVE" = "active" ] || { journalctl -u "$UNIT" --no-pager -n 30; die "backend em estado '$ACTIVE'"; }
ok "backend ativo"

# ── 6. Verificacao ──────────────────────────────────────────────────────────
say "6/6  Verificacao"
code() { curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$1"; }

echo "    plans/public ....... HTTP $(code http://127.0.0.1:8001/plans/public)   (esperado 200)"
echo "    api/reminders ...... HTTP $(code http://127.0.0.1:8001/api/reminders)   (esperado 401)"
echo "    site publico ....... HTTP $(code https://deep-os.tech/)   (esperado 200)"
echo ""
echo "    PID do systemd: $(systemctl show -p MainPID --value "$UNIT")"
echo "    --- quem atende a porta ---"
ss -lptn 'sport = :8001' 2>/dev/null || true
echo "    --- total de uvicorn rodando (deve ser 1) ---"
ps -eo pid,cmd 2>/dev/null | grep -E "uvicorn main:app" | grep -v grep | wc -l | sed 's/^/    /'

printf '\n\033[1;36m==> Agora rode o deploy completo:\033[0m\n'
echo "    cd /root/DEEP-OS && bash scripts/deploy-faf8f93.sh"
