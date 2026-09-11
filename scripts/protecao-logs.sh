#!/bin/bash
# ============================================================================
# DEEP-OS — Proteção contra disco cheio (logs)
#
# Uso:  sudo bash scripts/protecao-logs.sh
#
# CONTEXTO (2026-09-11)
# ---------------------
# O VPS ficou com o disco 100% cheio (48 GB) e o deploy falhou com
# "fatal: unable to write loose object file: No space left on device".
#
# Causa: /var/log/syslog com 27 GB. O serviço do backend escrevia no stdout
# ~400 mil linhas/dia (uma por chunk de áudio do Charon), e o syslog recebe
# tudo isso. O logrotate do Ubuntu rotacionava, mas o volume vencia.
#
# Correções aplicadas em dois níveis:
#   1. CÓDIGO (voice_ws.py): log agregado por turno em vez de por chunk (~99%)
#   2. INFRA (este script): limites de tamanho para o journal e o syslog
#
# Este script é idempotente: pode rodar quantas vezes quiser.
# ============================================================================
set -uo pipefail

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()  { printf '    \033[0;32mOK\033[0m %s\n' "$1"; }
warn(){ printf '    \033[0;33mAVISO\033[0m %s\n' "$1"; }

[ "$(id -u)" = "0" ] || { echo "Rode como root."; exit 1; }

say "1/5  Espaco atual"
df -h / | tail -1

say "2/5  Limitar o journal do systemd"
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/deepos-limites.conf <<'EOF'
# DEEP-OS — limite de tamanho do journal.
# Sem isto ele cresce sem teto ate encher o disco.
[Journal]
SystemMaxUse=300M
SystemKeepFree=1G
MaxRetentionSec=2week
EOF
systemctl restart systemd-journald 2>/dev/null && ok "journald reiniciado" || warn "falha ao reiniciar journald"
journalctl --vacuum-size=300M 2>&1 | tail -2
journalctl --disk-usage

say "3/5  Limitar o /var/log/syslog"
cat > /etc/logrotate.d/deepos-syslog <<'EOF'
# DEEP-OS — rotacao agressiva do syslog.
# O padrao do Ubuntu (weekly, 4 rotacoes) nao segurava o volume do backend.
#
# `su root adm` e OBRIGATORIO aqui: o logrotate recusa rodar quando o diretorio
# pai tem permissao considerada insegura ("parent directory has insecure
# permissions"), o que acontece com /var/log neste servidor. Sem esta linha a
# rotacao simplesmente nao acontece — e o arquivo cresce ate encher o disco.
/var/log/syslog
{
    su root adm
    daily
    rotate 3
    maxsize 100M
    compress
    delaycompress
    missingok
    notifempty
    create 0640 syslog adm
    sharedscripts
    postrotate
        /usr/lib/rsyslog/rsyslog-rotate 2>/dev/null || systemctl kill -s HUP rsyslog.service 2>/dev/null || true
    endscript
}
EOF
ok "config de logrotate criada em /etc/logrotate.d/deepos-syslog"

# Testa de verdade (o -d faz dry-run e mostra o erro sem alterar nada se falhar)
if logrotate -d /etc/logrotate.d/deepos-syslog >/tmp/lr_test.log 2>&1; then
    if grep -qi "error" /tmp/lr_test.log; then
        warn "a config ainda reporta erro:"
        grep -i "error" /tmp/lr_test.log | head -3
    else
        ok "config validada (dry-run sem erro)"
    fi
else
    warn "logrotate -d falhou; veja: cat /tmp/lr_test.log"
fi

logrotate -f /etc/logrotate.d/deepos-syslog 2>&1 | tail -2 && ok "rotacao forcada agora" || warn "falha na rotacao"

say "4/5  Caches que se regeneram"
rm -rf /root/.cache/pip /root/.npm/_cacache 2>/dev/null && ok "caches de pip/npm removidos"
rm -rf /root/DEEP-OS/frontend/node_modules/.vite 2>/dev/null && ok "cache do Vite removido"
find /root/DEEP-OS/backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null && ok "bytecode Python removido"

say "5/5  Limpar backups antigos (mantendo os 3 mais recentes)"
if [ -d /root/backup-deepos ]; then
    ANTES=$(ls -1 /root/backup-deepos 2>/dev/null | wc -l)
    cd /root/backup-deepos && ls -1t | tail -n +4 | xargs -r rm -f
    DEPOIS=$(ls -1 /root/backup-deepos 2>/dev/null | wc -l)
    ok "backups: $ANTES -> $DEPOIS"
else
    warn "pasta de backups nao existe"
fi

printf '\n\033[1;36m=============== RESULTADO ===============\033[0m\n'
df -h / | tail -1
echo ""
echo "Limites agora ativos:"
echo "  - journal do systemd ... 300 MB (retencao 2 semanas)"
echo "  - /var/log/syslog ...... rotacao diaria, max 100 MB, mantem 3"
echo "  - log do backend ....... agregado por turno (corrigido no codigo)"
echo ""
echo "Se o disco voltar a encher, verifique primeiro:"
echo "  du -ah /var/log 2>/dev/null | sort -rh | head -10"
echo "  journalctl --disk-usage"
