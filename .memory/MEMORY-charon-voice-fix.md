# Charon (Gemini Live API) - Correções e Implementações

**Data:** 2026-08-12
**Status:** Concluído

## Problema: Áudio Engasgando/Arranhando

### Causa
O Gemini Live API envia áudio em chunks pequenos e irregulares via WebSocket. O AudioWorklet original processava cada chunk individualmente, causando:
- Buffer underflow (falta de áudio para reproduzir)
- Timing irregular entre chunks
- Artefatos de áudio (crackling/scratching)

### Solução Implementada

#### 1. Ring Buffer Aumentado
- **Antes:** 24.000 samples (1 segundo)
- **Depois:** 192.000 samples (8 segundos)
- **Por quê:** Absorve variações de timing do Gemini

#### 2. Pre-Buffer (Aguardar antes de tocar)
- **Adicionado:** 12.000 samples (0.5 segundos)
- **Comportamento:** Áudio só começa a tocar quando o buffer atinge 12k samples
- **Efeito:** Elimina engasgos no início da fala

#### 3. Buffer Intermediário no Frontend
- **Antes:** Cada chunk WebSocket ia direto ao Worklet
- **Depois:** Chunks são acumulados em buffer e enviados a cada 20ms
- **Junção:** Múltiplos chunks pequenos → um chunk maior
- **Redução de overhead:** Menos mensagens postMessage por segundo

#### 4. Normalização Correta
- **Antes:** `pcm16[i] / 0x8000` (valor errado)
- **Depois:** `pcm16[i] / 32768` (normalização PCM 16-bit correta)

### Código do Worklet (playback-proc)
```javascript
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ringSize = 192000;      // 8 segundos
    this._ring = new Float32Array(this._ringSize);
    this._writePos = 0;
    this._readPos = 0;
    this._avail = 0;
    this._prebuf = 12000;         // 0.5s antes de tocar
    this._started = false;
    // ...
  }
}
```

### Buffer Intermediário (Frontend)
```javascript
// Acumula chunks por 20ms antes de enviar ao worklet
audioFlushRef.current = setInterval(() => {
  const buf = audioBufRef.current;
  if (buf.length === 0) return;
  audioBufRef.current = [];
  const merged = new Int16Array(totalLen);
  // ... junta todos os chunks
  playNodeRef.current.port.postMessage(merged.buffer, [merged.buffer]);
}, 20);
```

## Google Search para Charon

### Problema
Charon não tinha ferramentas configuradas (`tools=[]`). Não conseguia pesquisar na internet.

### Solução
Adicionado `GoogleSearch` como tool na LiveConnectConfig:
```python
tools=[types.Tool(google_search=types.GoogleSearch())]
```

### System Instruction Atualizada
```
"Voce e o Charon, assistente de voz do DEEP-OS. 
Fale em portugues brasileiro. Seja direto e util. 
Voce tem acesso ao Google Search — use para pesquisar 
qualquer assunto quando pedido."
```

## Botão Interrupt (Parar Charon)

### Comportamento
1. Limpa buffer de áudio imediatamente
2. Envia `{ type: 'stop' }` para o backend
3. Fecha o WebSocket (interrompe sessão Gemini)
4. Para o microfone (desconecta tracks)
5. **NÃO reconecta automaticamente** (antes reconectava em 1s)

### Código
```javascript
const interrupt = () => {
  audioBufRef.current = [];
  if (playNodeRef.current) playNodeRef.current.port.postMessage({ type: 'clear' });
  if (wsRef.current) {
    try { wsRef.current.send(JSON.stringify({ type: 'stop' })); } catch {}
    try { wsRef.current.close(); } catch {}
    wsRef.current = null;
  }
  // ... para microfone
  startedRef.current = false;
  setVoiceStatus('idle');
  onCharonActive?.(false);
};
```

## CharonPanel (Painel de Contexto)

### Funcionalidade
- Mostra transcripts da conversa em tempo real
- Status do Charon (ouvindo/falando/inativo)
- Não abre WebSocket próprio (herda do StatusBar)
- Toggle pelo botão "T" na status bar
- Largura: 340px quando ativo

### Integração
- `onCharonTranscriptFull` callback do StatusBar → App.tsx → CharonPanel
- Transcripts armazenados em `charonTranscripts` state

## Arquivos Modificados
- `backend/routes/voice_ws.py` - Google Search tool + system instruction
- `frontend/src/components/StatusBar.tsx` - Audio worklet, buffer, interrupt
- `frontend/src/components/CharonPanel.tsx` - Painel de contexto
- `frontend/src/App.tsx` - State management, integração

## Referência
- WBC-Mark-L (desktop PyQt) como base
- Gemini Live API docs
- AudioWorklet API

---

## Sessão 6 — 20 Ferramentas Implementadas (2026-08-12)

### O que foi feito
Portadas todas as 20 ferramentas do WBC-Mark-L para o Charon do DEEP-OS.

### Ferramentas (20 total)
1. `open_app` — Abrir aplicativos
2. `web_search` — Busca web (search/news/research/price/compare)
3. `system_status` — Métricas do sistema (CPU/RAM/GPU)
4. `weather_report` — Relatório do tempo
5. `send_message` — Enviar mensagens (WhatsApp/Telegram)
6. `reminder` — Lembretes agendados
7. `youtube_video` — Controle YouTube
8. `screen_process` — Captura de tela/webcam
9. `close_camera` — Fechar câmera
10. `computer_settings` — Configurações do PC
11. `browser_control` — Controle do navegador
12. `file_controller` — Gerenciar arquivos/pastas
13. `desktop_control` — Controle da área de trabalho
14. `code_helper` — Auxiliar de código
15. `dev_agent` — Criar projetos completos
16. `computer_control` — Controle direto (type/click/hotkeys)
17. `game_updater` — Steam/Epic Games
18. `flight_finder` — Buscar voos
19. `file_processor` — Processar arquivos (PDF/Word/CSV)
20. `manage_monitor` — Monitoramento em background

### Dependências Instaladas
- `send2trash` — Para delete seguro de arquivos
- `playwright` — Para browser_control
- `sounddevice` — Para screen_processor

### Arquivos Criados/Modificados
- `C:\DEEP-OS\config.py` — NOVO — Helper de compatibilidade com actions
- `C:\DEEP-OS\backend\routes\voice_ws.py` — REESCRITO — 20 TOOL_DECLARATIONS + _execute_tool + receive_loop com tool_call handler

### Como funciona
1. Usuário fala via microfone
2. Gemini Live API recebe áudio e decide qual ferramenta chamar
3. Gemini responde com `tool_call` (nome + argumentos)
4. `_receive_loop` detecta `response.tool_call`
5. `_execute_tool` executa a action correspondente
6. Resultado é retornado para Gemini via `send_tool_response()`
7. Gemini gera resposta em áudio com o resultado
8. Áudio volta ao frontend via WebSocket

### Teste
```python
import asyncio, websockets, json
async def test():
    async with websockets.connect("ws://localhost:8001/ws/voice") as ws:
        await ws.send(json.dumps({"type": "start", "voice": "Charon"}))
        await ws.send(json.dumps({"type": "text", "text": "Abra o Chrome"}))
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                print(f"[Audio: {len(msg)} bytes]")
            else:
                print(json.loads(msg))
asyncio.run(test())
```
