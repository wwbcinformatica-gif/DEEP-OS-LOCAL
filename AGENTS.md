# DEEP-OS - Agent Instructions

## Project Overview
DEEP-OS is an AI Agent Operating System (Sistema Operacional de Agentes de IA). It orchestrates multiple specialized AI agents to automate software engineering tasks. Runs 100% locally with support for multiple LLM providers.

## Tech Stack
- **Backend**: Python (FastAPI + Uvicorn) at `backend/`
- **Frontend**: React + TypeScript (Vite) at `frontend/`
- **Config**: `config.yaml` for agent settings
- **Memory**: Spiral Memory system in `backend/core/spiral_memory.py`
- **Database**: SQLite with pooled connections at `backend/database/`

## Commands
- `START-TOTAL.bat` - Start both backend and frontend (recommended)
- `npm run dev` - Start both backend and frontend
- `npm run dev:backend` - Start backend only (port 8001)
- `npm run dev:frontend` - Start frontend only (port 5175)
- `npm run build` - Build frontend
- `npm run test` - Run all tests
- `npm run lint` - Run linters
- `STOP-TOTAL.bat` - Stop all services

## Project Structure
```
C:\DEEP-OS\
├── backend/          # Python FastAPI backend
│   ├── core/         # Core modules (spiral_memory, lifecycle, agent_config, secrets, log_viewer, auth)
│   ├── models/       # SaaS models (tenant, plan, payment, usage)
│   ├── middleware/    # Multi-tenant middleware
│   ├── agents/       # Agent loop and configurations
│   ├── browser/      # Browser automation via CDP (Chrome DevTools Protocol)
│   ├── cron/         # Cron scheduler (real asyncio execution)
│   ├── database/     # SQLite pool + triggers system
│   ├── memory/       # Elastic memory, vector memory (FAISS), brain
│   └── routes/       # API routes (chat, cron, triggers, secrets, logs, browser, auth, admin)
├── frontend/         # React + TypeScript (Vite)
│   └── src/
│       └── components/  # UI components (ArchitecturePage, ChatPanel, saas/)
├── skills/           # Agent skills
│   ├── browser-automation/  # Browser automation skill (CDP)
│   │   ├── SKILL.md
│   │   └── interaction-skills/  # 12 interaction techniques
│   └── software-development/    # Dev skills
├── data/             # SaaS data (tenants, shared)
├── nginx/            # Nginx config for production
├── .memory/          # Portable project memory (junction from mimocode)
├── docs/             # Documentation (architecture.html, SAAS_README.md)
├── config.yaml       # Main configuration file
├── .mimocode/        # MiMo Code portable installation
│   └── bin/mimo.exe  # MiMo Code executable
└── mimo.bat          # Launch MiMo Code from this project
```

## Portable Memory (CRITICAL)
The MiMo Code memory system stores durable knowledge in `.memory/` inside the project directory. A junction links from `~/.local/share/mimocode/memory/projects/global/` to `C:\DEEP-OS\.memory\`.

**When moving this project to another machine:**
1. Copy the entire `C:\DEEP-OS\` folder
2. On the new machine, run: `mklink /J "%USERPROFILE%\.local\share\mimocode\memory\projects\global" "C:\DEEP-OS\.memory"`
3. Memory is now portable — all 14+ files of project knowledge travel with the project

## Auto-Learning Rule
The agent MUST automatically:
1. Save knowledge to `.memory/MEMORY.md` without being asked
2. Create and update tasks in the task tracker without asking
3. Learn from every interaction and store patterns
4. Execute tasks autonomously without waiting for confirmation at each step

## APIs do Sistema
- `POST/GET/DELETE /cron` — Scheduler real com execucao via asyncio
- `POST/GET/DELETE /triggers` — Database triggers (watch SQLite tables)
- `POST/GET/DELETE /secrets` — Gerenciamento de .env
- `GET/DELETE /logs` — Viewer estruturado de logs
- `POST /chat/stream` — Chat SSE com streaming
- `GET/POST /memory` — Sistema de memoria
- `POST /agent/execute` — Execucao direta de agentes
- `GET /browser/status` — Status da conexao CDP
- `POST /browser/navigate` — Navegar para URL
- `GET /browser/page-info` — Info da pagina atual
- `POST /browser/click` — Clique em coordenadas
- `POST /browser/type` — Digitar texto
- `POST /browser/fill` — Preencher input (React/Vue)
- `POST /browser/key` — Pressionar tecla
- `POST /browser/scroll` — Scroll
- `POST /browser/js` — Executar JavaScript
- `GET /browser/screenshot` — Capturar screenshot
- `GET /browser/tabs` — Listar abas
- `POST /browser/tab/new` — Nova aba
- `POST /browser/tab/switch` — Trocar aba
- `POST /browser/tab/close` — Fechar aba
- `POST /browser/upload` — Upload de arquivo
- `GET /browser/doctor` — Diagnosticos

## Browser Setup (Chrome Remote Debugging)
O modulo browser precisa que o Chrome esteja com remote debugging habilitado.

### Opcao 1: Ativar pelo Chrome
1. Abra o Chrome e va para `chrome://inspect/#remote-debugging`
2. Clique em "Ativar" (Enable)

### Opcao 2: Atalho com porta 9222
Crie um atalho do Chrome com parametro:
```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

### Verificar se funciona
Apos ativar, acesse: `http://localhost:8001/browser/doctor`
Deve retornar `"status": "healthy"`

## SaaS Mode (Plano de Aluguel)
O DEEP-OS pode operar como plataforma SaaS para múltiplos assinantes.

### Ativar modo SaaS
```bash
# Desenvolvimento
npm run dev:saas

# Produção
npm run start:saas
```

### Variáveis de ambiente SaaS
```env
SaaS_MODE=true
JWT_SECRET=seu-secret-aqui
ADMIN_PASSWORD=sua-senha-admin
```

### Estrutura de dados SaaS
```
data/
├── admin.db          # Banco administrativo
├── tenants/          # Dados por tenant
│   └── {tenant_id}/
│       ├── database.sqlite
│       ├── config.yaml
│       └── workspace/
└── shared/
```

### APIs SaaS
- `POST /auth/register` — Registrar novo tenant
- `POST /auth/login` — Login do tenant
- `POST /auth/admin/login` — Login do admin
- `GET /admin/dashboard/stats` — Estatísticas
- `GET /admin/tenants` — Listar assinantes
- `GET /admin/plans` — Listar planos

### Planos disponíveis
| Plano | Preço | Features |
|-------|-------|----------|
| Gratuito | R$ 0 | 1 instância |
| Mensal | R$ 14,99 | 3 instâncias |
| Trimestral | R$ 29,99 | 5 instâncias + Radar |
| Anual | R$ 79,99 | 10 instâncias + Jarvis |

Documentação completa: `docs/SAAS_README.md`

## Guidelines
- Backend runs on port 8001 (dev) or 8000 (production)
- Frontend runs on port 5175 (Vite dev server) or 5176 (SaaS mode)
- Config is centralized in config.yaml
- Use Portuguese (PT-BR) for all user-facing messages
- Follow existing code patterns in backend/ and frontend/
- Memory is AUTOMATIC — agent saves learnings without being asked
