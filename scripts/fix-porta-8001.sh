#!/bin/bash
# ============================================================================
# DEEP-OS — Reparo da porta 8001 (backend nao sobe: "address already in use")
#
# Uso:  bash /root/DEEP-OS/scripts/fix-porta-8001.sh
#
# Sintoma que este script resolve:
#   ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8001)
#
# Causa tipica: existe um uvicorn rodando FORA do systemd (iniciado na mao em
# algum teste). O systemd sobe, nao consegue a porta, e morre em loop — mas o
# site continua no ar pelo processo manual, o que confunde o diagnostico.
# ============================================================================
set -uo pipefail

UNIT="deep-os-backend"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()  { printf '    \033[0;32mOK\033[0m %s\n' "$1"; }
warn(){ printf '    \033[0;33mAVISO\033[0m %s\n' "$1"; }

mostrar_donos() {
  say "Quem esta usando a porta 8001"
  if command -v ss >/dev/null 2>&1; then
    ss -lptn 'sport = :8001' 2>/dev/null || true
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -i :8001 -sTCP:LISTEN 2>/dev/null || true
  fi
  echo "    --- processos uvicorn ---"
  ps -eo pid,ppid,etimes,cmd 2>/dev/null | grep -E "uvicorn|main:app" | grep -v grep || echo "    (nenhum)"
}

# ── 1. Diagnostico ──────────────────────────────────────────────────────────
mostrar_donos

# ── 2. Parar tudo ───────────────────────────────────────────────────────────
say "Parando o servico e qualquer uvicorn solto"
systemctl stop "$UNIT" 2>/dev/null && ok "servico parado" || warn "servico ja parado"

# Mata por padrao de linha de comando (pega processos fora do systemd)
pkill -f "uvicorn main:app" 2>/dev/null && ok "uvicorn solto encerrado" || warn "nenhum uvicorn solto"
pkill -f "uvicorn.*main:app" 2>/dev/null || true

# Mata quem ainda segurar a porta
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8001/tcp 2>/dev/null && ok "porta 8001 liberada (fuser)" || warn "fuser nao encontrou dono"
fi

# ── 3. Esperar a porta liberar de verdade ───────────────────────────────────
say "Aguardando a porta 8001 liberar"
LIBEROU=0
for i in $(seq 1 20); do
  if command -v ss >/dev/null 2>&1; then
    if ! ss -lnt 2>/dev/null | grep -q ':8001 '; then LIBEROU=1; break; fi
  else
    sleep 1; LIBEROU=1; break
  fi
  printf '    tentativa %s/20...\n' "$i"
  sleep 1
done

if [ "$LIBEROU" = "1" ]; then
  ok "porta 8001 livre"
else
  warn "a porta continua ocupada — donos restantes:"
  mostrar_donos
  echo ""
  warn "Mate manualmente com: kill -9 <PID>   e rode este script de novo"
  exit 1
fi

# Mostra o que o servico vai executar (ajuda a achar unit duplicada)
say "Config do servico $UNIT"
systemctl cat "$UNIT" 2>/dev/null | grep -E "^(ExecStart|WorkingDirectory|Restart)" || warn "nao consegui ler a unit"

# ── 4. Subir limpo ──────────────────────────────────────────────────────────
say "Subindo o backend pelo systemd"
systemctl reset-failed "$UNIT" 2>/dev/null
systemctl start "$UNIT"
sleep 6

ACTIVE="$(systemctl is-active "$UNIT")"
if [ "$ACTIVE" = "active" ]; then
  ok "backend ativo"
else
  warn "estado: $ACTIVE"
  journalctl -u "$UNIT" --no-pager -n 30
  exit 1
fi

# ── 5. Verificar ────────────────────────────────────────────────────────────
say "Verificacao"
code() { curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$1"; }

echo "    plans/public ....... HTTP $(code http://127.0.0.1:8001/plans/public)   (esperado 200)"
echo "    api/reminders ...... HTTP $(code http://127.0.0.1:8001/api/reminders)   (esperado 401)"
echo "    site publico ....... HTTP $(code https://deep-os.tech/)   (esperado 200)"

# Confirma que quem atende e o processo do systemd
say "Processo atendendo a porta"
if command -v ss >/dev/null 2>&1; then
  ss -lptn 'sport = :8001' 2>/dev/null || true
fi
echo "    PID do systemd: $(systemctl show -p MainPID --value "$UNIT" 2>/dev/null)"

printf '\n\033[1;36m==> Pronto. Agora rode o deploy completo:\033[0m\n'
echo "    cd /root/DEEP-OS && bash scripts/deploy-faf8f93.sh"
