#!/bin/bash
# DEEP-OS - Deploy/update script para VPS Hostinger
# Uso: ./deploy.sh
# Cores para output

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

cd /root/DEEP-OS

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}     🚀 DEEP-OS Deploy Script${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# 1. Backup do build anterior
echo -e "${YELLOW}1. Fazendo backup do build anterior...${NC}"
BACKUP_DIR="/var/www/deep-os/frontend/dist-saas.backup.$(date +%Y%m%d_%H%M%S)"
if [ -d "/var/www/deep-os/frontend/dist-saas" ]; then
    cp -r /var/www/deep-os/frontend/dist-saas "$BACKUP_DIR" 2>/dev/null || true
    echo -e "${GREEN}   Backup salvo em: $BACKUP_DIR${NC}"
fi

# 2. Atualizando codigo
echo -e "${YELLOW}2. Atualizando codigo...${NC}"
git checkout -- . 2>/dev/null || true
git pull origin master
echo -e "${GREEN}   Codigo atualizado${NC}"

# 3. Instalando dependencias Python
echo -e "${YELLOW}3. Instalando dependencias Python...${NC}"
cd backend
source /root/DEEP-OS/venv/bin/activate 2>/dev/null || true
pip install -r requirements.txt --quiet 2>&1 | tail -5
cd ..
echo -e "${GREEN}   Dependencias Python instaladas${NC}"

# 4. Build frontend
echo -e "${YELLOW}4. Buildando frontend...${NC}"
cd frontend
npm install --quiet 2>&1 | tail -3
npm run build:saas 2>&1 | tail -5
cd ..
echo -e "${GREEN}   Frontend buildado${NC}"

# 5. Copiando build para nginx
echo -e "${YELLOW}5. Copiando build para nginx...${NC}"
if [ -d "frontend/dist-saas" ]; then
    rm -rf /var/www/deep-os/frontend/dist-saas/*
    cp -r frontend/dist-saas/* /var/www/deep-os/frontend/dist-saas/
    echo -e "${GREEN}   Build copiado${NC}"
else
    echo -e "${RED}   ERRO: frontend/dist-saas nao encontrado${NC}"
    exit 1
fi

# 6. Testando configuracao nginx
echo -e "${YELLOW}6. Testando configuracao nginx...${NC}"
if nginx -t 2>&1 | grep -q "successful"; then
    echo -e "${GREEN}   Configuracao nginx OK${NC}"
else
    echo -e "${RED}   ERRO na configuracao nginx${NC}"
    nginx -t
    exit 1
fi

# 7. Reiniciando backend
echo -e "${YELLOW}7. Reiniciando backend...${NC}"
systemctl restart deep-os-backend
sleep 2

# Verificar se backend subiu
if systemctl is-active --quiet deep-os-backend; then
    echo -e "${GREEN}   Backend reiniciado com sucesso${NC}"
else
    echo -e "${RED}   ERRO: Backend nao subiu${NC}"
    echo -e "${YELLOW}   Tentando rollback do codigo...${NC}"
    git checkout -- . 2>/dev/null || true
    systemctl restart deep-os-backend
    sleep 2
    if systemctl is-active --quiet deep-os-backend; then
        echo -e "${GREEN}   Rollback feito, backend funcionando${NC}"
    else
        echo -e "${RED}   FALHA CRITICA: Backend nao funciona${NC}"
    fi
    exit 1
fi

# 8. Recarregando nginx
echo -e "${YELLOW}8. Recarregando nginx...${NC}"
systemctl reload nginx
echo -e "${GREEN}   Nginx recarregado${NC}"

# 9. Health check
echo -e "${YELLOW}9. Verificando servicos...${NC}"
sleep 2

BACKEND_OK=false
NGINX_OK=false

if systemctl is-active --quiet deep-os-backend; then
    BACKEND_OK=true
fi

if systemctl is-active --quiet nginx; then
    NGINX_OK=true
fi

echo ""
echo -e "${BLUE}============================================${NC}"
if [ "$BACKEND_OK" = true ] && [ "$NGINX_OK" = true ]; then
    echo -e "${GREEN}✅ Deploy concluido com sucesso!${NC}"
    echo -e "${GREEN}   Frontend: https://deep-os.tech${NC}"
    echo -e "${GREEN}   Backend:  http://127.0.0.1:8001${NC}"
else
    echo -e "${RED}❌ Deploy concluido com problemas:${NC}"
    [ "$BACKEND_OK" = false ] && echo -e "${RED}   - Backend: DOWN${NC}"
    [ "$NGINX_OK" = false ] && echo -e "${RED}   - Nginx: DOWN${NC}"
fi
echo -e "${BLUE}============================================${NC}"