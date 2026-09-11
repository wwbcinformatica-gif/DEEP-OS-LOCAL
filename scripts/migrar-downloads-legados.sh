#!/bin/bash
# ============================================================================
# DEEP-OS — Migra documentos legados de downloads/ para downloads/<tenant_id>/
#
# Uso:  sudo bash scripts/migrar-downloads-legados.sh [tenant_id]
#
# CONTEXTO
# --------
# Antes do isolamento por tenant, os documentos gerados pelo Charon
# (save_document / write_file) ficavam soltos em `downloads/`. O
# `/api/download` procurava com rglob recursivo e achava qualquer um.
#
# Com o isolamento por tenant, cada assinante so enxerga
# `downloads/<tenant_id>/`. Resultado: os documentos antigos na raiz ficaram
# INACESSAVEIS — os links ja enviados ao usuario passaram a dar 404.
#
# Este script move os arquivos legados para o diretorio de um tenant, para os
# links antigos voltarem a funcionar.
#
# Se nenhum tenant_id for informado, o script LISTA os candidatos e mostra o
# comando pronto — nao move nada sem confirmacao explicita.
# ============================================================================
set -uo pipefail

BASE="/root/DEEP-OS/downloads"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()  { printf '    \033[0;32mOK\033[0m %s\n' "$1"; }
warn(){ printf '    \033[0;33mAVISO\033[0m %s\n' "$1"; }

[ "$(id -u)" = "0" ] || { echo "Rode como root."; exit 1; }
[ -d "$BASE" ] || { echo "Pasta $BASE nao existe."; exit 1; }

say "1/3  Arquivos legados (na raiz de downloads/)"
# Arquivos = somente tipo f (arquivo), na raiz (maxdepth 1)
mapfile -t LEGADOS < <(find "$BASE" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort)

if [ "${#LEGADOS[@]}" -eq 0 ]; then
    ok "nenhum arquivo legado na raiz — nada a migrar"
    exit 0
fi

for f in "${LEGADOS[@]}"; do
    printf '    %s\n' "$f"
done
echo "    total: ${#LEGADOS[@]} arquivo(s)"

say "2/3  Tenants disponiveis no banco"
TENANTS=$(/root/DEEP-OS/venv/bin/python - <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "/root/DEEP-OS/backend")
from pathlib import Path
try:
    from database.connection import get_conn, init_db, set_db_path
    set_db_path(Path("/root/DEEP-OS/data/interactions.db")); init_db()
    for r in get_conn().execute("SELECT id, email, plan FROM tenants ORDER BY plan").fetchall():
        print(f"{r['id']}\t{r['email']}\t{r['plan']}")
except Exception as e:
    print(f"ERRO\t{e}")
PY
)
if [ -z "$TENANTS" ]; then
    warn "nao consegui listar os tenants"
else
    echo "$TENANTS" | while IFS=$'\t' read -r id email plano; do
        printf '    %-42s %-30s %s\n' "$id" "$email" "$plano"
    done
fi

DESTINO="${1:-}"
if [ -z "$DESTINO" ]; then
    ALVO=$(echo "$TENANTS" | awk -F'\t' '$3=="master"{print $1; exit}')
    [ -z "$ALVO" ] && ALVO=$(echo "$TENANTS" | head -1 | cut -f1)

    say "3/3  Nada foi movido (modo seguro)"
    echo "    Escolha o tenant dono dos documentos e rode:"
    echo
    echo "      bash scripts/migrar-downloads-legados.sh $ALVO"
    echo
    echo "    Sugestao: '$ALVO' (conta master — os documentos foram gerados"
    echo "    nas suas sessoes com o Charon)."
    exit 0
fi

say "3/3  Migrando para downloads/$DESTINO/"
mkdir -p "$BASE/$DESTINO"
movidos=0
for f in "${LEGADOS[@]}"; do
    if [ -e "$BASE/$DESTINO/$f" ]; then
        warn "ja existe, pulando: $f"
        continue
    fi
    mv "$BASE/$f" "$BASE/$DESTINO/" && movidos=$((movidos+1))
done
ok "$movidos arquivo(s) movido(s)"

echo
echo "    Conteudo de downloads/$DESTINO/:"
ls -1 "$BASE/$DESTINO" | sed 's/^/      /'

echo
echo "Os links antigos (/api/download?path=/root/DEEP-OS/downloads/<arquivo>)"
echo "passam a resolver pelo nome: o backend procura em downloads/$DESTINO/."
echo "Teste com:  curl -s -o /dev/null -w '%{http_code}\\n' \\"
echo "  'http://127.0.0.1:8001/api/download?path=${LEGADOS[0]}'"
