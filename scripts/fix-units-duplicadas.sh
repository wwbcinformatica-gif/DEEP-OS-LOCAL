#!/bin/bash
# ============================================================================
# DEEP-OS — Resolver units DUPLICADAS que brigam pela porta 8001
#
# Uso:  bash /root/DEEP-OS/scripts/fix-units-duplicadas.sh
#
# DESCOBERTA (a causa real de tudo):
#   /etc/systemd/system/deepos-backend.service    <- ATIVA, atende o site
#   /etc/systemd/system/deep-os-backend.service   <- DUPLICADA, em loop
#
# As duas estao `enabled` e ambas sobem no boot, disputando a porta 8001.
# Matar processos nunca resolvia porque a duplicada tinha Restart=always e
# ressuscitava em ~5s. Os dois nomes diferem por UM HIFEN.
#
# Este script mantem `deepos-backend` (a que funciona), desabilita a
# duplicada e endurece as configuracoes.
# ============================================================================
set -uo pipefail

MANTER="deepos-backend"      # a que atende o site (sem hifen)
REMOVER="deep-os-backend"    # a duplicada (com hifen)
DROPIN_DIR="/etc/systemd/system/$REMOVER.service.d"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()  { printf '    \033[0;32mOK\033[0m %s\n' "$1"; }
warn(){ printf '    \033[0;33mAVISO\033[0m %s\n' "$1"; }
die() { printf '\n\033[0;31m### PAROU: %s\033[0m\n' "$1"; exit 1; }

[ "$(id -u)" = "0" ] || die "rode como root"

# ── 1. Estado atual ─────────────────────────────────────────────────────────
say "1/6  Estado das units"
for u in "$MANTER" "$REMOVER"; do
  printf '    %-22s active=%-12s enabled=%s\n' "$u" \
    "$(systemctl is-active "$u" 2>/dev/null)" "$(systemctl is-enabled "$u" 2>/dev/null)"
done
echo ""
echo "    --- ExecStart de cada uma ---"
systemctl cat "$MANTER" 2>/dev/null  | grep -E "^ExecStart" | sed "s/^/    [$MANTER] /"
systemctl cat "$REMOVER" 2>/dev/null | grep -E "^ExecStart" | sed "s/^/    [$REMOVER] /"

# ── 2. Remover o drop-in com --reuse-port ───────────────────────────────────
# O uvicorn desta versao nao suporta --reuse-port (dava "No such option"),
# o que deixava a unit em loop de INVALIDARGUMENT.
say "2/6  Removendo o drop-in com --reuse-port (nao suportado)"
if [ -d "$DROPIN_DIR" ]; then
  rm -rf "$DROPIN_DIR" && ok "drop-in removido de $DROPIN_DIR"
else
  warn "nao havia drop-in"
fi

# ── 3. Desabilitar a duplicada ──────────────────────────────────────────────
say "3/6  Desabilitando a unit duplicada ($REMOVER)"
systemctl stop "$REMOVER" 2>/dev/null && ok "parada" || warn "ja estava parada"
systemctl disable "$REMOVER" 2>/dev/null && ok "disable feito (nao sobe mais no boot)" || warn "falha no disable"

# Impede que ela volte mesmo se algo a iniciar
systemctl mask "$REMOVER" 2>/dev/null && ok "mask aplicado (a unit fica inutilizavel)" || warn "falha no mask"
echo "    para reverter: systemctl unmask $REMOVER && systemctl disable $REMOVER"

systemctl daemon-reload && ok "systemd recarregado"

# ── 4. Endurecer a unit que fica ────────────────────────────────────────────
say "4/6  Endurecendo $MANTER"
mkdir -p "/etc/systemd/system/$MANTER.service.d"
cat > "/etc/systemd/system/$MANTER.service.d/override.conf" <<'EOF'
# DEEP-OS — ajustes de robustez.
# RestartSec evita rajada de restarts (o padrao do systemd e 100ms, o que
# martela o servico quando ha falha de config). StartLimit evita loop
# infinito: apos 5 falhas em 60s o systemd desiste e para de tentar.
[Service]
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5
EOF
ok "override gravado"
systemctl daemon-reload && ok "systemd recarregado"

# ── 5. Subir a boa e confirmar ──────────────────────────────────────────────
say "5/6  Subindo $MANTER"
systemctl reset-failed "$MANTER" 2>/dev/null
systemctl restart "$MANTER"
sleep 6

for i in 1 2 3; do
  A="$(systemctl is-active "$MANTER")"
  [ "$A" = "active" ] && break
  printf '    aguardando... (%s) estado=%s\n' "$i" "$A"
  sleep 3
done

A="$(systemctl is-active "$MANTER")"
if [ "$A" = "active" ]; then
  ok "backend ativo"
else
  journalctl -u "$MANTER" --no-pager -n 30
  die "backend em estado '$A'"
fi

# ── 6. Verificacao final ────────────────────────────────────────────────────
say "6/6  Verificacao"
code() { curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$1"; }

echo "    plans/public ....... HTTP $(code http://127.0.0.1:8001/plans/public)   (esperado 200)"
echo "    api/reminders ...... HTTP $(code http://127.0.0.1:8001/api/reminders)   (esperado 401)"
echo "    site publico ....... HTTP $(code https://deep-os.tech/)   (esperado 200)"
echo ""
echo "    PID principal: $(systemctl show -p MainPID --value "$MANTER")"
echo "    --- quem atende a porta 8001 (deve ser 1 so) ---"
ss -lptn 'sport = :8001' 2>/dev/null || true
echo "    --- total de uvicorn rodando ---"
ps -eo pid,cmd 2>/dev/null | grep -E "uvicorn main:app" | grep -v grep | wc -l | sed 's/^/    /'
echo ""
echo "    --- units ativas citando uvicorn ---"
for u in "$MANTER" "$REMOVER"; do
  printf '    %-22s %s\n' "$u" "$(systemctl is-active "$u" 2>/dev/null)"
done

printf '\n\033[1;36m==> Agora rode o deploy completo:\033[0m\n'
echo "    cd /root/DEEP-OS && bash scripts/deploy-faf8f93.sh"
