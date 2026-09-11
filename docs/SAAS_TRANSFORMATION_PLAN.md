# Plano de Transformação DEEP-OS → SaaS

## Visão Geral
Transformar o DEEP-OS em uma plataforma SaaS multi-tenant para aluguel, similar ao modelo CyberBot/Jarvis mostrado nas imagens.

---

## 1. Arquitetura Multi-Tenant

### 1.1 Isolamento de Dados
```
┌─────────────────────────────────────────────────────────┐
│                    SaaS Server                           │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Tenant A │  │ Tenant B │  │ Tenant C │  ...        │
│  │ (SQLite) │  │ (SQLite) │  │ (SQLite) │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│       ↓              ↓              ↓                  │
│  isolated_data/  isolated_data/  isolated_data/       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Estrutura de Pastas por Tenant
```
data/
├── tenants/
│   ├── tenant_001/
│   │   ├── config.yaml
│   │   ├── database.sqlite
│   │   ├── .env
│   │   └── workspace/
│   ├── tenant_002/
│   │   ├── config.yaml
│   │   ├── database.sqlite
│   │   └── workspace/
│   └── ...
├── shared/
│   ├── admin.db (dados administrativos)
│   └── templates/
└── uploads/
```

---

## 2. Sistema de Planos e Assinaturas

### 2.1 Planos (baseado nas imagens)

| Recurso | Mensal R$14,99 | Trimestral R$29,99 | Anual R$79,99 |
|---------|----------------|---------------------|---------------|
| Instâncias | ✓ | ✓ | ✓ |
| Suporte | ✓ | ✓ | ✓ |
| Acesso ao Painel | ✓ | ✓ | ✓ |
| Desconto | - | 33% | 71% |
| Jarvis Vitalício | ✗ | ✗ | ✓ |

### 2.2 Backend - Modelos de Dados

```python
# backend/models/tenant.py
class Tenant:
    id: str
    name: str
    email: str
    plan: PlanType  # monthly, quarterly, annual
    status: SubscriptionStatus  # active, suspended, expired
    created_at: datetime
    expires_at: datetime
    license_key: str
    
# backend/models/plan.py
class Plan:
    id: PlanType
    name: str
    price: float
    interval: str  # month, quarter, year
    features: list[str]
    max_instances: int
    max_messages_per_day: int
```

### 2.3 Tabelas SQLite Necessárias

```sql
-- Tenants (assinantes)
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    plan TEXT DEFAULT 'free',
    status TEXT DEFAULT 'active',
    license_key TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    last_login DATETIME
);

-- Planos disponíveis
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    interval TEXT NOT NULL,
    features TEXT,  -- JSON array
    max_instances INTEGER DEFAULT 1,
    max_messages_per_day INTEGER DEFAULT 100
);

-- Pagamentos
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT,  -- pix, card, boleto
    status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Uso (métricas)
CREATE TABLE usage_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    messages_used INTEGER DEFAULT 0,
    instances_active INTEGER DEFAULT 0,
    date DATE NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
```

---

## 3. Painel Administrativo (Master)

### 3.1 Funcionalidades do Admin

```
┌─────────────────────────────────────────────────────────┐
│  DEEP-OS Admin Panel                                 │
├─────────────────────────────────────────────────────────┤
│  📊 Dashboard                                           │
│     - Total de assinantes ativos                        │
│     - MRR (Monthly Recurring Revenue)                   │
│     - Churn rate                                        │
│     - Uso médio por tenant                              │
│                                                          │
│  👥 Assinantes                                          │
│     - Lista de todos os tenants                         │
│     - Status (ativo/suspenso/expirado)                  │
│     - Plano atual                                       │
│     - Data de expiração                                 │
│     - Ações: suspender, reativar, editar                │
│                                                          │
│  💰 Planos                                              │
│     - Criar/editar planos                               │
│     - Definir preços e features                         │
│     - Gerar cupons de desconto                          │
│                                                          │
│  📈 Relatórios                                          │
│     - Receita por período                               │
│     - Assinantes por plano                              │
│     - Uso de recursos                                   │
│     - Logs de atividade                                 │
│                                                          │
│  🔧 Configurações                                       │
│     - Configurar gateway de pagamento                   │
│     - Email de notificações                             │
│     - Integrações (Stripe, Mercado Pago, etc)           │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Rotas API Admin

```python
# backend/routes/admin.py
router = APIRouter(prefix="/admin")

# Auth
POST /admin/login
POST /admin/logout

# Dashboard
GET /admin/dashboard/stats

# Tenants
GET /admin/tenants
GET /admin/tenants/{id}
PUT /admin/tenants/{id}
DELETE /admin/tenants/{id}
POST /admin/tenants/{id}/suspend
POST /admin/tenants/{id}/reactivate

# Plans
GET /admin/plans
POST /admin/plans
PUT /admin/plans/{id}
DELETE /admin/plans/{id}

# Payments
GET /admin/payments
GET /admin/payments/stats

# Logs
GET /admin/logs
GET /admin/logs/{tenant_id}
```

---

## 4. Frontend - Interface do Assinante

### 4.1 Layout similar ao CyberBot

```
┌─────────────────────────────────────────────────────────┐
│  DEEP-OS                                    [Online] │
├─────────────────────────────────────────────────────────┤
│  │ 📋 Planos                  │                        │
│  │    OK                      │   Planos flexíveis     │
│  │ 📥 Download Jarvis         │   para qualquer        │
│  │ ⚡ Instância               │   tamanho de operação  │
│  │ 📜 Commands                │                        │
│  │ 🔥 Gatilhos                │  ┌──────────────┐     │
│  │ 🤖 ChatBot        [PRO]   │  │   Mensal     │     │
│  │ 📊 Radar de Leads  [BETA] │  │   R$14,99/mês│     │
│  │ 📈 Relatórios              │  └──────────────┘     │
│  │ 📢 Comunicado              │  ┌──────────────┐     │
│  │ 🚀 Campanha Manual         │  │ Trimestral   │     │
│  │ 💬 Msg Auto Grupo          │  │  R$29,99/tri │     │
│  │ 💬 Msg Auto Privado        │  └──────────────┘     │
│  │ 📱 PIX                     │  ┌──────────────┐     │
│  │ ⚙️ Configurações          │  │   Anual      │     │
│  │                            │  │   R$79,99/ano│     │
│  │ 🚪 Sair                    │  └──────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Novos Componentes React

```
frontend/src/components/
├── saas/
│   ├── Sidebar.tsx              # Menu lateral do assinante
│   ├── PlanCard.tsx             # Card de plano
│   ├── PricingPage.tsx          # Página de planos
│   ├── Dashboard.tsx            # Dashboard do usuário
│   ├── InstanceManager.tsx      # Gerenciar instâncias
│   ├── UsageMeter.tsx           # Medidor de uso
│   └── BillingPage.tsx          # Página de cobrança
├── admin/
│   ├── AdminLayout.tsx          # Layout do admin
│   ├── AdminDashboard.tsx       # Dashboard admin
│   ├── TenantList.tsx           # Lista de assinantes
│   ├── TenantDetail.tsx         # Detalhes do assinante
│   ├── PlanManager.tsx          # Gerenciar planos
│   └── PaymentHistory.tsx       # Histórico de pagamentos
└── auth/
    ├── LoginPage.tsx            # Login
    ├── RegisterPage.tsx         # Cadastro
    └── ForgotPassword.tsx       # Esqueci senha
```

---

## 5. Sistema de Autenticação

### 5.1 Backend Auth

```python
# backend/core/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    # Validar JWT token
    # Retornar tenant_id
    pass

def require_plan(minimum_plan: PlanType):
    """Decorator para verificar se o tenant tem o plano mínimo"""
    async def check_plan(tenant_id: str = Depends(get_current_user)):
        tenant = get_tenant(tenant_id)
        if PLAN_HIERARCHY[tenant.plan] < PLAN_HIERARCHY[minimum_plan]:
            raise HTTPException(403, "Plano insuficiente")
        return tenant_id
    return check_plan
```

### 5.2 Rotas Protegidas

```python
# Proteção por plano
@router.get("/chatbot")
async def chatbot(tenant_id: str = Depends(require_plan("monthly"))):
    pass

@router.get("/radar-leads")
async def radar_leads(tenant_id: str = Depends(require_plan("quarterly"))):
    pass
```

---

## 6. Integração com Pagamentos

### 6.1 Gateway Recomendado

| Gateway | PIX | Cartão | Boleto | Recorrência |
|---------|-----|--------|--------|-------------|
| **Stripe** | ✓ | ✓ | ✓ | ✓ |
| **Mercado Pago** | ✓ | ✓ | ✓ | ✓ |
| **Asaas** | ✓ | ✓ | ✓ | ✓ |
| **PagSeguro** | ✓ | ✓ | ✓ | ✓ |

### 6.2 Fluxo de Pagamento

```
1. Usuário escolhe plano
2. Redireciona para gateway de pagamento
3. Pagamento aprovado → webhook notifica backend
4. Backend cria/atualiza tenant
5. Envia email de boas-vindas com chave de licença
6. Usuário acessa o painel
```

---

## 7. Deploy e Infraestrutura

### 7.1 Docker Compose Atualizado

```yaml
version: '3.8'

services:
  # Servidor principal
  saas-server:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data/tenants:/app/data/tenants
      - ./data/shared:/app/data/shared
    environment:
      - SaaS_MODE=true
      - ADMIN_SECRET=${ADMIN_SECRET}
    restart: unless-stopped

  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - saas-server
    restart: unless-stopped

  # Nginx (reverse proxy + SSL)
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certbot/conf:/etc/letsencrypt
    depends_on:
      - saas-server
      - frontend
    restart: unless-stopped

  # Certbot (SSL automático)
  certbot:
    image: certbot/certbot
    volumes:
      - ./certbot/conf:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
```

### 7.2 Nginx Config

```nginx
# nginx.conf
upstream backend {
    server saas-server:8000;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 80;
    server_name *.DEEP-OS.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name *.DEEP-OS.com;
    
    ssl_certificate /etc/letsencrypt/live/DEEP-OS.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DEEP-OS.com/privkey.pem;

    # Rota para cada tenant
    location ~ ^/(?<tenant>[a-z0-9-]+)/api/ {
        proxy_pass http://backend;
        proxy_set_header X-Tenant-ID $tenant;
    }

    location / {
        proxy_pass http://frontend;
    }
}
```

---

## 8. Implementação - Fases

### Fase 1: Fundação (1-2 semanas)
- [ ] Criar modelos de dados (Tenant, Plan, Payment)
- [ ] Implementar sistema de autenticação (JWT)
- [ ] Criar middleware de isolamento por tenant
- [ ] Setup do banco de dados administrativo

### Fase 2: Backend SaaS (2-3 semanas)
- [ ] Rotas CRUD para tenants
- [ ] Rotas CRUD para planos
- [ ] Sistema de cobrança/integração
- [ ] API de verificação de licença
- [ ] Rate limiting por plano

### Fase 3: Frontend Assinante (2-3 semanas)
- [ ] Página de login/cadastro
- [ ] Página de planos/pricing
- [ ] Dashboard do usuário
- [ ] Gerenciador de instâncias
- [ ] Página de cobrança

### Fase 4: Painel Admin (2 semanas)
- [ ] Dashboard administrativo
- [ ] Gestão de tenants
- [ ] Gestão de planos
- [ ] Relatórios e métricas

### Fase 5: Deploy (1 semana)
- [ ] Configurar Docker Compose
- [ ] Configurar Nginx + SSL
- [ ] Setup de domínio wildcard
- [ ] Testes de produção

---

## 9. Estrutura Final do Projeto

```
C:\DEEP-OS\
├── backend/
│   ├── core/
│   │   ├── auth.py          # Autenticação JWT
│   │   ├── tenant.py        # Isolamento multi-tenant
│   │   └── license.py       # Sistema de licenças (atual)
│   ├── models/
│   │   ├── tenant.py        # Modelo Tenant
│   │   ├── plan.py          # Modelo Plan
│   │   └── payment.py       # Modelo Payment
│   ├── routes/
│   │   ├── admin.py         # Rotas admin
│   │   ├── auth.py          # Rotas de auth
│   │   ├── tenant.py        # Rotas tenant
│   │   └── ...              # Rotas existentes
│   └── middleware/
│       └── tenant.py        # Middleware de isolamento
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── saas/        # Componentes SaaS
│       │   ├── admin/       # Componentes Admin
│       │   └── auth/        # Componentes Auth
│       └── pages/
│           ├── PricingPage.tsx
│           ├── DashboardPage.tsx
│           └── AdminPage.tsx
├── data/
│   ├── tenants/             # Dados por tenant
│   ├── shared/              # Dados compartilhados
│   └── admin.db             # Banco admin
├── nginx.conf
├── docker-compose.yml
└── SAAS_TRANSFORMATION_PLAN.md
```

---

## 10. Estimativa de Custo

| Item | Custo Mensal |
|------|--------------|
| VPS 4GB RAM, 2 vCPU | ~R$80-150 |
| Domínio | ~R$40/ano |
| SSL (Let's Encrypt) | Gratuito |
| Gateway Pagamento | ~2-5% por transação |
| Email (SendGrid free) | Gratuito |
| **Total inicial** | **~R$100-200/mês** |

---

## Próximos Passos Imediatos

1. **Criar branch `saas`** para desenvolvimento isolado
2. **Implementar modelos de dados** (Tenant, Plan)
3. **Criar sistema de auth** (JWT + middleware)
4. **Criar rota `/admin`** básica
5. **Criar página de pricing** no frontend

---

*Plano criado em: 2026-09-01*
*Versão: 1.0*
