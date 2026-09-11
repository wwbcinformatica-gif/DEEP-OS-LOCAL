# Atualizações - DEEP-OS

Registro de todas as alterações e implementações realizadas no projeto.

---

## 2026-08-27 — Customise Assistant + Correções

### Nova Feature: Personalizar Assistente (Config > Assistente)

**Backend:**
- `config.yaml` — Adicionada seção `identity` com campos `assistant_name`, `user_name`, `custom_color`
- `routes/config.py` — Novos endpoints:
  - `GET /api/config/identity` — retorna nome do assistente, nome do usuário e cor
  - `PUT /api/config/identity` — salva os dados de identidade
  - Modelo `IdentityConfig` para validação

**Frontend:**
- `lib/constants.ts` — Tipo `AccentTheme` expandido com `'custom'`
- `App.tsx`:
  - States: `assistantName`, `userName`, `customColor`
  - Função `applyAccentTheme()` agora aceita cor customizada via parâmetro
  - Fetch do identity na inicialização (`GET /api/config/identity`)
  - Persistência em localStorage + backend
- `components/SettingsPage.tsx`:
  - Nova aba "Assistente" com campos:
    - Nome do Assistente (input)
    - Seu Nome (input)
    - Cor da Interface (input type="color" + preview)
  - Preview visual do assistente personalizado
- `components/PageRenderer.tsx` — Props atualizadas com `assistantName`, `userName`, `customColor`
- `components/ChatPanel.tsx`:
  - Avatar do bot agora mostra a primeira letra do `assistantName`
  - Header do chat mostra o nome do assistente

### Correção: Charon usa identidade configurada

**Problema:** Charon estava hardcoded com "Wilson" e "Wilson Barbosa Coimbra"

**Correções:**
- `backend/routes/voice_ws.py`:
  - Nova função `_load_identity()` — lê identity do `config.yaml`
  - `_build_system_instruction()` agora usa `assistant_name` e `user_name` do config
  - System prompt dinâmico em vez de hardcoded
- `CHARON_CONTEXT.md` — Removido nome hardcoded do desenvolvedor

---

## 2026-08-26 — Módulo de Voz para OpenCode

### Implementação completa do sistema de entrada por voz

**Arquivos criados em `C:\OPENCODE\opencode\voice\`:**
- `voice-input.ts` — Módulo principal de reconhecimento de voz
- `voice-ui.tsx` — Interface do usuário para controles de voz
- `voice-config.ts` — Configurações de voz
- `voice-commands.ts` — Processador de comandos de voz
- `voice-feedback.ts` — Feedback visual/sonoro
- `voice-history.ts` — Histórico de transcrições
- `voice-settings.ts` — Painel de configurações
- `voice-test.html` — Página de teste
- `install-voice.ps1` — Script de instalação
- `start-voice.bat` — Script de inicialização

**Plugins:**
- `.opencode/tools/voice.ts` — Tool de voz para o agente
- `.opencode/plugins/voice-plugin.ts` — Plugin de integração

---

## 2026-08-26 — Correção do Mark-LI start.bat

### Problema
- Python 3.11-32 estava desinstalado
- Venv corrompido
- `requirements.txt` com PyQt6 (incompatível)

**Correções:**
- Venv recriado com Python 3.11 64-bit via `py -3.11 -m venv`
- Todas as dependências reinstaladas incluindo PyQt5
- `requirements.txt` atualizado: PyQt6 → PyQt5
- `start.bat` atualizado para usar `py -3.11`

---

## Estrutura Atual do Projeto

```
C:\DEEP-OS\
├── backend/
│   ├── routes/
│   │   ├── config.py         ← endpoints de config (inclui identity)
│   │   ├── voice_ws.py       ← Charon com identity dinâmico
│   │   └── ...
│   └── core/
│       └── prompts.py        ← MOOD_INSTRUCTIONS
├── frontend/
│   └── src/
│       ├── App.tsx           ← states de identity
│       ├── lib/constants.ts  ← AccentTheme com 'custom'
│       └── components/
│           ├── SettingsPage.tsx  ← aba Assistente
│           ├── ChatPanel.tsx     ← avatar + header dinâmico
│           └── PageRenderer.tsx  ← props atualizadas
├── config.yaml               ← seção identity
└── CHARON_CONTEXT.md         ← contexto dinâmico
```

---

## Configuração

### Identity (config.yaml)
```yaml
identity:
  assistant_name: DEEP-OS
  user_name: ""
  custom_color: ""
```

### Como alterar
1. Acesse **Config > Assistente** no frontend
2. Altere o nome do assistente, seu nome e/ou cor
3. Clique em **Salvar configurações**
4. Reinicie o backend para aplicar no Charon
