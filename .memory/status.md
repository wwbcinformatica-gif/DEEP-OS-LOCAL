# DEEP-OS — Status do Projeto

**Última atualização:** 2026-08-25

## Estado Atual

| Componente | Status | Notas |
|---|---|---|
| Backend (FastAPI) | ✅ Funcional | Porta 8001 |
| Frontend (React/Vite) | ✅ Funcional | Porta 5175 |
| Charon (agente de voz) | ✅ Corrigido | Disco arranhado resolvido |
| Memória Espiral | ✅ Funcional | Snapshot determinístico sem LLM |
| Provider padrão | OpenCode | deepseek-v4-flash-free ($0) |

## Correções Recentes (2026-08-25)

### Bug: Charon "disco arranhado" (repetição de respostas)

**Causa raiz (3 bugs combinados):**

1. **`planning_enforced=True`** ainda estava ativo em `lifecycle.py` e `chat.py`, forçando o modelo a gerar checkboxes/task_plan antes de usar ferramentas → loop infinito de planejamento.

2. **`or msg.mood == "opencode"`** em 4 locations do `chat.py` fazia com que TODAS as mensagens fossem roteadas para o handler de tarefas (com tools+lifecycle engine), mesmo Saudações e perguntas simples.

3. **`build_system_prompt()`** tinha `if is_greeting and msg.mood != "opencode"` que forçava o prompt completo de ferramentas no mood opencode mesmo para greetings.

**Correções aplicadas:**

- `backend/core/lifecycle.py:181` — `planning_enforced=False`
- `backend/routes/chat.py:682` — Removido `or msg.mood == "opencode"` do endpoint `/chat`
- `backend/routes/chat.py:1151` — `planning_enforced=False` no config do lifecycle
- `backend/routes/chat.py:1841` — Removido `or msg.mood == "opencode"` no fluxo de urgência
- `backend/routes/chat.py:1952` — Removido `or msg.mood == "opencode"` no generate()
- `backend/routes/chat.py:1980` — Removido `or msg.mood == "opencode"` no _process_queued_message
- `backend/routes/chat.py:600` — `if is_greeting:` (removida条件 `and msg.mood != "opencode"`)

**Efeito:** Charon agora roteia corretamente perguntas/saudações para `handle_question()` (conversacional, sem tools) em vez de `handle_task()` (lifecycle engine completo).

## Funcionalidades Implementadas

### Core
- Lifecycle engine com anti-loop (circuit breaker + state hash tracker)
- Planning enforcement (desativado globalmente)
- Context compression automática
- Memória espiral (snapshot determinístico + Keeper LLM opcional)
- Sistema de fila de mensagens com triagem de urgência
- Tool confirmation para operações de alto risco
- Auto-continue para checklists pendentes

### Ferramentas (33)
- **Sistema:** open_app, open_program, close_program, system_status, computer_settings, computer_control
- **Web:** web_search, web_fetch, browser_control
- **Arquivos:** file_controller, read_file, write_file, file_edit, find_file, glob_search, file_processor
- **Código:** code_helper, dev_agent, execute_python, bash, text_search
- **Mídia:** youtube_video, screen_process, close_camera
- **Outros:** send_message, reminder, desktop_control, game_updater, flight_finder, manage_monitor, memory_save, memory_recall, weather_report

### Frontend
- Chat com streaming SSE
- Voice mode (Web Speech API + TTS)
- TaskChecklist com progresso visual
- PermissionDialog para confirmação de ferramentas
- Media player integrado
- Architecture page com diagrama de fluxo
- Explorer de arquivos
- Terminal integrado

## Providers Disponíveis

| Provider | Modelo | Status | Custo |
|---|---|---|---|
| OpenCode | deepseek-v4-flash-free | ✅ | $0 |
| Groq | llama-3.3-70b | ✅ | Free tier |
| Ollama | (modelos locais) | ✅ | Grátis |
| OpenClaude | (vários) | ⚠️ | Variável |
| MiMo | mimo-v2.5 | ❌ 402 | ¥1/MTok |
| Gemini | gemini-1.5-pro | ❌ 404 | - |
| OpenRouter | (vários) | ❌ 401 | - |

## Known Issues

- MiMo API key retorna 402 (funciona no MiMo Code CLI)
- Gemini API key inválida/quebrada
- OpenRouter API key expirada
- SettingsPage toggle state não sincroniza com App.tsx em tempo real

## Comandos Úteis

```bash
# Iniciar sistema
START-TOTAL.bat

# Parar sistema
STOP-TOTAL.bat

# Apenas backend
npm run dev:backend

# Apenas frontend
npm run dev:frontend

# Build frontend
npm run build

# Testes
npm run test

# Lint
npm run lint
```

## Estrutura do Projeto

```
C:\DEEP-OS\
├── backend/          # Python FastAPI backend
│   ├── core/         # Core modules (spiral_memory, lifecycle, etc.)
│   ├── agents/       # Agent loop
│   ├── browser/      # Browser automation (CDP)
│   ├── cron/         # Cron scheduler
│   ├── database/     # SQLite pool + triggers
│   ├── memory/       # Elastic memory, vector memory (FAISS)
│   └── routes/       # API routes
├── frontend/         # React + TypeScript (Vite)
├── skills/           # Agent skills
├── .memory/          # Memória do projeto (portável)
├── config.yaml       # Configuração principal
└── START-TOTAL.bat   # Iniciar sistema
```
