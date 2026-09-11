# DEEP-OS SaaS - Guia de Setup

## Visão Geral

O DEEP-OS pode operar como uma plataforma SaaS (Software as a Service) para aluguel, permitindo que múltiplos assinantes usem o sistema de forma isolada.

## Funcionalidades

- **Multi-Tenant**: Cada assinante tem seus dados isolados
- **Sistema de Planos**: Mensal, Trimestral e Anual
- **Autenticação JWT**: Login seguro para assinantes e admin
- **Painel Administrativo**: Gerencie assinantes, planos e pagamentos
- **Isolamento de Dados**: SQLite separado por tenant

## Setup Rápido

### 1. Instalar dependências

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Configurar variáveis de ambiente

Crie o arquivo `backend/.env`:

```env
# Modo SaaS
SaaS_MODE=true

# JWT Secret (MUDE EM PRODUÇÃO!)
JWT_SECRET=seu-secret-aqui-mude-em-producao

# Senha do Admin
ADMIN_PASSWORD=sua-senha-admin

# Porta do servidor
PORT=8000
```

### 3. Inicializar banco de dados

```bash
cd backend
python init_admin_db.py
```

### 4. Iniciar em modo SaaS

```bash
# Desenvolvimento
npm run dev:saas

# Produção
npm run start:saas
```

## Endpoints

### Autenticação

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/register` | Registrar novo tenant |
| POST | `/auth/login` | Login do tenant |
| POST | `/auth/admin/login` | Login do admin |
| GET | `/auth/me` | Dados do tenant logado |
| POST | `/auth/change-password` | Alterar senha |

### Admin

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/admin/dashboard/stats` | Estatísticas do dashboard |
| GET | `/admin/tenants` | Listar tenants |
| GET | `/admin/tenants/:id` | Detalhes do tenant |
| PUT | `/admin/tenants/:id` | Atualizar tenant |
| POST | `/admin/tenants/:id/suspend` | Suspender tenant |
| POST | `/admin/tenants/:id/reactivate` | Reativar tenant |
| GET | `/admin/plans` | Listar planos |

## Planos

| Plano | Preço | Features |
|-------|-------|----------|
| Gratuito | R$ 0 | 1 instância, 20 msgs/dia |
| Mensal | R$ 14,99/mês | 3 instâncias, 100 msgs/dia |
| Trimestral | R$ 29,99/tri | 5 instâncias, 300 msgs/dia, Radar de Leads |
| Anual | R$ 79,99/ano | 10 instâncias, 1000 msgs/dia, Jarvis Vitalício |

## Deploy com Docker

```bash
# Modo SaaS
docker-compose -f docker-compose.saas.yml up -d

# Parar
docker-compose -f docker-compose.saas.yml down
```

## Estrutura de Dados

```
data/
├── admin.db              # Banco administrativo
├── tenants/              # Dados dos tenants
│   ├── tenant_001/
│   │   ├── database.sqlite
│   │   ├── config.yaml
│   │   └── workspace/
│   └── tenant_002/
└── shared/               # Dados compartilhados
```

## Segurança

- Senhas hasheadas com bcrypt
- Tokens JWT com expiração
- Isolamento completo entre tenants
- Rate limiting por IP
- HTTPS obrigatório em produção

## Próximos Passos

1. [ ] Integrar gateway de pagamento (Stripe/Mercado Pago)
2. [ ] Configurar envio de emails (SendGrid/SES)
3. [ ] Adicionar monitoramento (Prometheus/Grafana)
4. [ ] Configurar backups automáticos
5. [ ] Implementar trial gratuito de 7 dias

---

*Última atualização: 01/09/2026*
