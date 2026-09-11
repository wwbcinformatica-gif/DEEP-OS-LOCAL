# DEEP-OS — Completed Features & Patterns
_Extracted from MEMORY.md §Discovered durable knowledge. Completed implementation patterns no longer in active development._

## Completed Feature Patterns

### Chat dual-mode routing
Messages go to either `handle_task_stream()` (tool-calling loop with plan mode support) or `handle_question_stream()` (simple RAG-augmented streaming) based on keyword detection via `is_task_message()` in `backend/routes/chat.py:284`.

### Textarea resize
Implemented via custom drag handler with mousedown/mousemove listeners (min 36px, max 400px) rather than native CSS resize, for cleaner UX with visual grab handle.

### Cloud tool calling blacklist
Blacklist approach over whitelist because cloud model tool-calling support changes frequently; maintaining a negative list is more practical than a positive list that breaks whenever a model is added.

### VS Code visual standard
All UI must match VS Code exactly — colors (#1e1e1e editor, #252526 sidebar, #2d2d2d cards), sizes (11px labels, 12px buttons, 13px body). All colors via CSS variables in styles.css for theme switching.

### Font hierarchy
`:root` uses `var(--font-ui)` (Segoe UI/system-ui sans-serif) for all UI. Monospace (`var(--font-mono)`) only for code/terminal contexts. Tokens: `--font-size-xs(11px)/sm(12px)/base(13px)/md(14px)/lg(15px)`.

### Dynamic Checklist UX (2026-06-21, IMPLEMENTED)
Agent MUST present reasoning + markdown checkbox plan BEFORE executing any tool. Two rendering paths: backend `task_checklist` JSON events + frontend markdown checkbox parsing. Pre-execution plan is a behavioral constraint. `TASK_CHECKLIST_PROMPT` rewritten with rigid protocol. Checklist repositioned in `ChatPanel.tsx` to appear right before streaming area.

### CSS variable source of truth
`:root` in styles.css defines all theme tokens. Components must reference variables, not hardcoded values.

### Print format toggle (A4/Cupom)
Implemented in `Pdv.jsx` lines 489-498 — two buttons toggle `printFormato` state (persisted to `localStorage`). `PrintPreview.jsx` renders differently based on `formato === 'cupom'`.

### PlanMessage OpenCode-style architecture
Uses `var(--accent)` for all color styling — automatically adapts to any accent theme. Structure: header bar → progress bar → problem table → checkbox list → risk box → action buttons.

### Top bar layout structure
`display: flex; justifyContent: space-between` with three zones: (1) page navigation tabs, (2) inline components, (3) layout controls + window controls. All buttons use inline SVG icons with `fill="currentColor"`.

### React audio file handling pattern
`URL.createObjectURL(file)` for each uploaded File, `URL.revokeObjectURL()` on component unmount and track removal. Audio element with `timeupdate` event for progress tracking, `ended` event for auto-advance.

### SettingsPage tab refactor pattern
`useState<Tab>('geral')` for active tab, content conditionally rendered via `{activeTab === 'x' && (...)}`. Tab button styling: `borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent'`.

## Completed WBC-ZERO-G Features

### Voice wake words for hands-free control
VoiceAssistant.tsx component uses Web Speech API with `continuous=true` for wake word detection. Commands: "ok mic", "ok voz", "ok jarvis", "desativa mic/voz/jarvis", "pare/silencio", "ajuda". Button "VOZ" in ChatPanel next to microphone icon.

### Word-boundary matching for voice commands
Replaced substring matching (`includes()`) with regex word boundaries `(^|\s)word(\s|$)` via `hasWord()`. Multi-word phrases use ordered word-by-word matching via `hasPhrase()`. Critical fix — false triggers made the system unusable.

### Built-in player over system player
User observed that opening Windows Media Player via bash breaks accessibility (window switching). Backend media API serves files for built-in mini player — keeping everything in-app.

### No auto-speak — voice on demand
User explicitly said responses should not be read aloud automatically. Model executes silently; only reads when user says "ler tudo". **Exception**: Execution plans ("PLANO DE EXECUCAO") should be spoken aloud for accessibility.

### Continuous listening during idle
User requires microphone to stay active during model idle state. The `onend` handler always restarts recognition without conditional checks.

### Voice confirmation over click confirmation
For accessibility, plan approval and tool confirmation must work by voice ("sim, pode fazer") in addition to click buttons. Critical for users who cannot use mouse/keyboard.

### Refs-based recognition stability
Speech recognition callbacks must read from refs, not state, to avoid stale closures and infinite recreation loops. All values accessed inside `onresult`/`onerror`/`onend` go through refs.

### 5-second debounce before sending voice
User requires a 5-second debounce window before sending voice to the model. Allows user to correct misheard speech. Accumulate text, show countdown, send after silence. User can say "confirma" to send early or "cancela" to discard.

### Keep-alive interval for continuous listening
`setInterval` every 1.5s checking `!wakeRecognitionRef.current` is the PRIMARY mechanism for keeping mic alive. `utterance.onend` and `recognition.onend` are secondary — Chrome doesn't always fire them.

### Voice speed from slider
TTS rate must use the settings slider. Mapping: `rate = 0.5 + (sliderValue / 100) * 1.5`. Same pattern for pitch.

### Conversational model behavior
After completing a task, model should ask "O que voce quer fazer?" and wait for next command.

### Built-in player only — never system player
Model must use `media_search` action instead of bash `start` command to open media files. **Updated**: Now supports player choice via `payload.player` parameter.

### Text accumulation pattern for voice
Web Speech API `isFinal` results fire incrementally. Must accumulate all text until `onend` fires, then process complete sentence. Processing each `isFinal` individually causes phrases to be cut short.

### Inline voice status display
Voice status shown as inline `<span>` next to VOZ button, not absolute-positioned tooltip. Shows: debouncing text + countdown, interim transcription, confidence %, or "ouvindo...". Tooltip caused layout issues.

### echoOLlama/llmrtc evaluation (COMPLETED)
User shared two repos. echoOLlama: Python/FastAPI + Ollama + faster_whisper + OpenedAI TTS (WebSocket). llmrtc: TypeScript SDK + WebRTC + multi-provider + VAD + tool calling + playbooks. llmrtc chosen for integration — created voice server on port 8787.

## Completed WBC-PDV Features
- **Three-Pillar Adaptive Architecture (2026-06-21, COMPLETED)**: Elastic Memory + Anti-Loop Protection + Context Compression (see MEMORY-wbc-legacy-architecture.md)
- **Lifecycle state machine (2026-06-21, COMPLETED)**: 16 states formal state machine (see MEMORY-wbc-legacy-architecture.md)
- **Crisis Resolution Architecture (2026-06-21, COMPLETED)**: Contextualized Frustration Nudge + Graceful Failure + Anti-Pattern Memory + Atomic Write + Iteration Break (see MEMORY-wbc-legacy-architecture.md)

## Legacy System References
- See MEMORY-pdv-legacy.md (38 entries) — WBC-PDV Firebird/PostgreSQL migration, Supabase integration, deployment, legacy patterns
- See MEMORY-mercado-pago-legacy-fixes.md (18 entries) — Mercado Pago API reference + legacy Python tkinter/electron/Firebird fixes (all completed)
- See MEMORY-historical-completed-fixes.md (6 entries) — Task checklist bug, Admin.jsx fixes, CSS specificity, documentation consolidation, Produtos.jsx focus, UserFormModal fix
- See MEMORY-pdv-ui-patterns.md (33 entries) — WBC-ZERO-G 5.0 platform refs, PDV UI patterns, fiscal/caixa/permission patterns, completed component fixes
