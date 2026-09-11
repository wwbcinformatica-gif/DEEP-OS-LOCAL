# ðŸ§  DEEP-OS-LOCAL

## ðŸ‘¨â€ðŸ’» Desenvolvedor

| Campo | Valor |
|-------|-------|
| **Nome** | Wilson Barbosa Coimbra |
| **Empresa** | WBC |
| **Projeto** | DEEP-OS-LOCAL |

Â© 2026 DEEP-OS-LOCAL â€” Desenvolvido por **Wilson Barbosa Coimbra** (empresa **WBC**). Todos os direitos reservados.


**Sistema Operacional de Agentes de IA** â€” antigo WBC-ZERO-G 5.0

Plataforma full-stack que orquestra mÃºltiplos agentes de IA especializados para automatizar tarefas de engenharia de software. Opera 100% local com suporte a mÃºltiplos provedores de LLM. Inclui o **Charon**, assistente de voz com 20 ferramentas via Gemini Live.

---

## ðŸ“ LocalizaÃ§Ã£o

```
C:\DEEP-OS-LOCAL\
```

---

## ðŸŒ€ Spiral Memory (DEEP-OS-LOCAL)

Sistema de memÃ³ria em espiral onde **dois modelos** trabalham em sincronia:

### Modelo A (Worker)
- Executa ferramentas, gera cÃ³digo, resolve a tarefa
- Modelo principal configurado em `config.yaml` (`model.default`)

### Modelo B (Keeper)  
- Monitora o contexto do Worker a cada N passos
- Extrai: arquivo atual, Ãºltima aÃ§Ã£o, erros, decisÃµes, progresso
- Gera um **snapshot compacto** da memÃ³ria de trabalho
- Reinjeta como mensagem de sistema no Worker

### Como funciona

```
Worker (Modelo A) â”€â”€executa ferramentasâ”€â”€â–¶ contexto cresce
                                              â”‚
                  Keeper (Modelo B) â—€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â”‚  (a cada 4 passos)
                       â–¼
         Extrai snapshot + sumariza
                       â”‚
         Injeta no prompt do Worker
                       â”‚
                      â—€â”€â”€â”€ espiral contÃ­nua
```

### Arquivos do Spiral Memory

| Arquivo | DescriÃ§Ã£o |
|---------|-----------|
| `backend/core/spiral_memory.py` | MÃ³dulo principal do Keeper |
| `backend/core/lifecycle.py` | Engine de ciclo de vida com callback de refresh |
| `backend/agents/loop.py` | IntegraÃ§Ã£o: Keeper conectado ao Worker |
| `backend/core/agent_config.py` | Config `SpiralMemoryConfig` |

### ConfiguraÃ§Ã£o (`config.yaml`)

```yaml
spiral_memory:
  enabled: true
  interval: 4
  keeper_provider: "ollama"
  keeper_model: "deepseek-r1:7b"
```

### TrÃªs nÃ­veis de sumarizaÃ§Ã£o

1. **Regras** (sempre ativo) â€” extraÃ§Ã£o determinÃ­stica de ferramentas, arquivos, erros
2. **Keeper LLM** (se `keeper_model` configurado) â€” usa Modelo B para sumarizaÃ§Ã£o semÃ¢ntica
3. **Fallback** â€” se Keeper LLM falhar, volta para regras

---

## ðŸ—ï¸ Arquitetura

```
C:\DEEP-OS-LOCAL\
â”œâ”€â”€ backend/          # FastAPI (Python) â€” servidor principal
â”‚   â”œâ”€â”€ agents/       # Orquestrador, loop, teams, fork
â”‚   â”œâ”€â”€ core/         # Lifecycle, LLM, RAG, prompts, seguranÃ§a, spiral_memory
â”‚   â”œâ”€â”€ routes/       # 28+ endpoints REST/WebSocket
â”‚   â”œâ”€â”€ tools/        # Bash, leitura/escrita, web search, fetch
â”‚   â”œâ”€â”€ memory/       # MemÃ³ria vetorial, elÃ¡stica, brain, reflexÃ£o
â”‚   â””â”€â”€ main.py       # Entrypoint FastAPI
â”œâ”€â”€ frontend/         # React + TypeScript + Vite + Tailwind
â”‚   â””â”€â”€ src/          # Chat, Terminal, Explorer, Editor, Plan, etc.
â”œâ”€â”€ .opencode/        # 25+ agentes e 20+ skills
â”œâ”€â”€ skills/           # Skills de desenvolvimento
â”œâ”€â”€ data/             # MemÃ³ria persistente, brain, FAQ
â””â”€â”€ docs/             # Docs e relatÃ³rios de auditoria
```

---

## ðŸ”§ Tech Stack

| Camada | Tecnologias |
|--------|-------------|
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic |
| Frontend | React 18, TypeScript 5, Vite 5, Tailwind 4, xterm.js |
| Banco | SQLite, MemÃ³ria Vetorial (embeddings) |
| LLMs | Ollama (local), OpenAI, Groq, Gemini, OpenRouter, MiMo |
| Protocolos | REST, WebSocket, MCP, SSE (streaming) |
| Modelos locais | qwen3:14b, deepseek-r1:7b/14b, nemomix-12b, qwen2.5-coder |

---

## ðŸš€ Como usar

### Iniciar
```bash
C:\DEEP-OS-LOCAL\START-TOTAL.bat
```

### Menu rÃ¡pido
```bash
C:\DEEP-OS-LOCAL\run.bat
```

### Acessos
| ServiÃ§o | URL |
|---------|-----|
| Frontend | http://localhost:5175 |
| Backend API | http://localhost:8001/docs |

---

## ðŸ¤– Agentes Especializados (25+)

Orchestrator, Architect, Coder, Debugger, Backend-Specialist, Frontend-Specialist, Security-Auditor, Penetration-Tester, Database-Architect, DevOps-Engineer, Test-Engineer, Game-Developer, Mobile-Developer, SEO-Specialist, Documentation-Writer, Performance-Optimizer, Project-Planner, QA-Automation-Engineer, Product-Manager, Product-Owner, e mais.

---

## ðŸ“ Skills (32+)

Clean Code, Architecture, Database Design, i18n, Vulnerability Scanner, WebApp Testing, Red Team Tactics, Frontend Design, Python Patterns, PowerShell Windows, Bash Linux, Code Review, Deployment Procedures, Plan Writing, e mais.

---

## âš™ï¸ Provedores Suportados

| Provider | Tipo | Modelo sugerido |
|----------|------|----------------|
| Ollama | Local | qwen3:14b, deepseek-r1:7b |
| Groq | Cloud | mixtral-8x7b, llama-3.1-70b |
| OpenAI | Cloud | gpt-4o |
| Gemini | Cloud | gemini-1.5-pro |
| OpenRouter | Cloud | vÃ¡rios |
| OpenClaude | Cloud/Self | deepseek-v4-flash |
| MiMo | Cloud | mimmo-7b-rl |

---

## ðŸŽ™ï¸ Charon â€” Assistente de Voz

O **Charon** Ã© o assistente de voz do DEEP-OS-LOCAL, baseado no **Gemini Live** (audio nativo) com **20 ferramentas** de funÃ§Ã£o.

### Como usar
- **Falar:** clique no microfone e fale diretamente com o Charon (ou diga "aurea" para ativar o modo de voz do chat central).
- **Digitar:** abra o painel Charon (botÃ£o "T" na barra de status) e digite â€” o texto entra no contexto e o Charon responde por voz.
- **Ligar/desligar:** botÃ£o "âš¡ Charon" na barra de status.
- **Interromper:** botÃ£o â¹ no HUD de voz, ou fale "para", "silencio", "cala boca".

### Ferramentas principais
| Ferramenta | O que faz |
|-----------|-----------|
| `file_controller` | Criar/listar/deletar/mover arquivos e pastas, abrir documentos e imagens |
| `computer_control` | Mouse, teclado, cliques, hotkeys, screenshot |
| `browser_control` | Navegar, buscar, clicar, digitar no navegador |
| `open_app` | Abrir qualquer aplicativo |
| `file_processor` | OCR, resumos, conversÃµes de PDF/docx/xlsx, transcriÃ§Ãµes |
| `web_search` / `web_fetch` | Pesquisar e baixar conteÃºdo da web |

### Comandos de voz Ãºteis
| Fale | O que acontece |
|------|----------------|
| "criar pasta X" | Cria pasta em Documents/Desktop |
| "tira print da tela" | Screenshot com data/hora (nunca sobrescreve) |
| "abre o arquivo config.py" | Abre arquivos no aplicativo padrÃ£o |
| "para de ler" / "cala boca" | Interrompe a fala atual |
| "repetir" / "ler novamente" | Repete a Ãºltima resposta |

> **Nota:** screenshots e resultados de processamento usam nomes com data/hora (`AAAAMMDD_HHMMSS`) para nunca sobrescrever arquivos anteriores. A listagem de pastas mostra sempre todas as pastas, limitando apenas os arquivos (atÃ© 100).

---

## ðŸ”„ Fluxo do Spiral Memory (implementado em Jul/2026)

1. Worker inicia tarefa com ferramentas
2. A cada 4 passos, Lifecycle Engine chama Keeper
3. Keeper varre tool_logs + mensagens recentes
4. Gera snapshot (regras OU LLM)
5. Injeta `[DEEP-OS-LOCAL MEMORY REFRESH]` no contexto do Worker
6. Worker continua de onde parou com memÃ³ria fresca

---

## ðŸ“Œ Notas

- O venv precisa ser recriado apÃ³s o rename: `python -m venv venv`
- MemÃ³ria de reflexÃµes e longo prazo em `data/memory/` (regenerÃ¡vel)
- O Spiral Memory Ã© ativado por padrÃ£o â€” desligar em `config.yaml: spiral_memory.enabled: false`

---

---


