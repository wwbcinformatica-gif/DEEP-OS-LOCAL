import React, { useState, useRef, useEffect } from 'react';
import StatusIndicator from './StatusIndicator';

interface OllamaStatus {
  running: boolean;
  models?: string[];
}

interface StatusBarProps {
  prov: string;
  model: string;
  mood: string;
  ollSt?: OllamaStatus;
  termOpen: boolean;
  setTermOpen: (v: boolean) => void;
  thinkOpen?: boolean;
  setThinkOpen?: (v: boolean) => void;
  charonPanel?: boolean;
  setCharonPanel?: (v: boolean) => void;
  charonActive?: boolean;
  voiceName?: string;
  onCharonActive?: (active: boolean) => void;
  onCharonVoiceStatus?: (status: string) => void;
  onCharonTranscript?: (text: string) => void;
  onCharonTranscriptFull?: (speaker: string, text: string) => void;
  onCharonToolResult?: (tool: string, result: string) => void;
  onCharonSendText?: (fn: (text: string) => void) => void;
  stopGen?: () => void;
  loading?: boolean;
  theme: string;
  toggleTheme: () => void;
}

const WORKLET_CODE = `
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = [];
    this._size = 1024;
  }
  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];
    const ratio = 3;
    const downsampled = Math.floor(ch.length / ratio);
    const pcm16 = new Int16Array(downsampled);
    for (let i = 0; i < downsampled; i++) {
      const idx = i * ratio;
      const avg = (ch[idx] + ch[idx + 1] + ch[idx + 2]) / 3;
      const s = Math.max(-1, Math.min(1, avg));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    for (let i = 0; i < pcm16.length; i++) this._buf.push(pcm16[i]);
    while (this._buf.length >= this._size) {
      const chunk = new Int16Array(this._size);
      for (let i = 0; i < this._size; i++) chunk[i] = this._buf.shift();
      this.port.postMessage(chunk.buffer, [chunk.buffer]);
    }
    return true;
  }
}
registerProcessor('mic-proc', MicProcessor);
`;

const PLAYBACK_CODE = `
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ringSize = 480000;
    this._ring = new Float32Array(this._ringSize);
    this._writePos = 0;
    this._readPos = 0;
    this._avail = 0;
    this._prebuf = 30000;
    this._started = false;
    this._consecutiveZeroes = 0;
    this._threshold = 144000;
    this._lastChunkHash = 0;
    this._dupCount = 0;
    this.port.onmessage = (e) => {
      if (e.data && e.data.type === 'clear') {
        this._writePos = 0; this._readPos = 0; this._avail = 0;
        this._started = false; this._consecutiveZeroes = 0;
        this._lastChunkHash = 0; this._dupCount = 0;
        return;
      }
      const pcm16 = new Int16Array(e.data);
      // Deduplicacao: hash simples do chunk
      let hash = 0;
      const step = Math.max(1, Math.floor(pcm16.length / 16));
      for (let i = 0; i < pcm16.length; i += step) {
        hash = ((hash << 5) - hash + pcm16[i]) | 0;
      }
      if (hash !== 0 && hash === this._lastChunkHash) {
        this._dupCount++;
        if (this._dupCount > 2) return; // ignora 3+ duplicatas seguidas
      } else {
        this._dupCount = 0;
      }
      this._lastChunkHash = hash;
      for (let i = 0; i < pcm16.length; i++) {
        this._ring[this._writePos] = pcm16[i] / 32768;
        this._writePos = (this._writePos + 1) % this._ringSize;
        if (this._avail < this._ringSize) {
          this._avail++;
        } else {
          this._readPos = (this._readPos + 1) % this._ringSize;
        }
      }
      if (!this._started && this._avail >= this._prebuf) {
        this._started = true;
      }
    };
  }
  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || !output[0]) return true;
    const ch = output[0];
    if (!this._started) {
      for (let i = 0; i < ch.length; i++) ch[i] = 0;
      return true;
    }
    for (let i = 0; i < ch.length; i++) {
      if (this._avail > 0) {
        ch[i] = this._ring[this._readPos];
        this._readPos = (this._readPos + 1) % this._ringSize;
        this._avail--;
        this._consecutiveZeroes = 0;
      } else {
        this._consecutiveZeroes++;
        if (this._consecutiveZeroes > this._threshold) {
          this._started = false;
          this._consecutiveZeroes = 0;
        }
        ch[i] = 0;
      }
    }
    return true;
  }
}
registerProcessor('playback-proc', PlaybackProcessor);
`;

function getWsUrl(): string {
  const host = window.location.hostname || 'localhost';
  return `ws://${host}:8001/ws/voice`;
}

const StatusBar: React.FC<StatusBarProps> = ({
  prov,
  model,
  mood,
  ollSt,
  termOpen,
  setTermOpen,
  thinkOpen,
  setThinkOpen,
  charonPanel,
  setCharonPanel,
  charonActive,
  voiceName = 'Charon',
  onCharonActive,
  onCharonVoiceStatus,
  onCharonTranscript,
  onCharonTranscriptFull,
  onCharonToolResult,
  onCharonSendText,
  stopGen,
  loading,
  theme,
  toggleTheme,
}) => {
  const [voiceStatus, setVoiceStatusRaw] = useState('idle');
  const voiceStatusRef = useRef('idle');
  const setVoiceStatus = (status: string) => {
    voiceStatusRef.current = status;
    setVoiceStatusRaw(status);
  };
  const [processMsg, setProcessMsg] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const micCtxRef = useRef<AudioContext | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const micNodeRef = useRef<AudioWorkletNode | null>(null);
  const playNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const startedRef = useRef(false);
  const audioBufRef = useRef<Int16Array[]>([]);
  const audioFlushRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioLevelTimeRef = useRef(0);
  const lastResponseTimeRef = useRef(0);
  const heartbeatCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastAudioHashRef = useRef(0);
  const dupCountRef = useRef(0);

  // Expõe a função de envio de texto para o parent
  useEffect(() => {
    if (onCharonSendText) {
      const sendText = (text: string) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'text', text }));
        }
      };
      onCharonSendText(sendText);
    }
  }, [onCharonSendText]);

  // Notifica o parent sobre mudanças no status de voz
  useEffect(() => {
    onCharonVoiceStatus?.(voiceStatus);
  }, [voiceStatus, onCharonVoiceStatus]);

  // Setup playback worklet
  useEffect(() => {
    let mounted = true;
    (async () => {
      const ctx = new AudioContext({ sampleRate: 24000 });
      if (ctx.state === 'suspended') await ctx.resume();
      const blob = new Blob([PLAYBACK_CODE], { type: 'application/javascript' });
      const url = URL.createObjectURL(blob);
      await ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      if (!mounted) { ctx.close(); return; }
      const node = new AudioWorkletNode(ctx, 'playback-proc', {
        numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [1],
      });
      node.connect(ctx.destination);
      playCtxRef.current = ctx;
      playNodeRef.current = node;
    })();
    return () => {
      mounted = false;
      if (playNodeRef.current) { playNodeRef.current.disconnect(); playNodeRef.current = null; }
      if (playCtxRef.current) { playCtxRef.current.close().catch(() => {}); playCtxRef.current = null; }
    };
  }, []);

  // Audio buffer flush — junta chunks e envia ao worklet
  useEffect(() => {
    audioFlushRef.current = setInterval(() => {
      const buf = audioBufRef.current;
      if (buf.length < 1 || !playNodeRef.current || !playCtxRef.current) return;
      audioBufRef.current = [];
      const totalLen = buf.reduce((acc, c) => acc + c.length, 0);
      const merged = new Int16Array(totalLen);
      let offset = 0;
      for (const chunk of buf) { merged.set(chunk, offset); offset += chunk.length; }
      if (playCtxRef.current.state === 'suspended') playCtxRef.current.resume();
      playNodeRef.current.port.postMessage(merged.buffer, [merged.buffer]);
    }, 15);
    return () => { if (audioFlushRef.current) clearInterval(audioFlushRef.current); };
  }, []);

  // Setup WebSocket + mic
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    let stopped = false;

    const start = async () => {
      try {
        setVoiceStatus('connecting');
        const ws = new WebSocket(getWsUrl());
        wsRef.current = ws;

        let wsReady = false;

        ws.onopen = () => {
          ws.send(JSON.stringify({ type: 'start', voice: voiceName }));
          wsReady = true;
        };

        ws.onmessage = async (e) => {
          lastResponseTimeRef.current = Date.now();
          if (e.data instanceof Blob) {
            const buf = await e.data.arrayBuffer();
            const bytes = new Uint8Array(buf);
            if (bytes.length >= 2) {
              const pcm16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.length / 2);
              // Deduplicacao JS-level: hash do chunk
              let hash = 0;
              const step = Math.max(1, Math.floor(pcm16.length / 16));
              for (let i = 0; i < pcm16.length; i += step) {
                hash = ((hash << 5) - hash + pcm16[i]) | 0;
              }
              if (hash !== 0 && hash === lastAudioHashRef.current) {
                dupCountRef.current++;
                if (dupCountRef.current > 1) return; // ignora duplicatas
              } else {
                dupCountRef.current = 0;
              }
              lastAudioHashRef.current = hash;
              audioBufRef.current.push(pcm16);
            }
            setVoiceStatus('speaking');
            return;
          }
          try {
            const m = JSON.parse(e.data);
            if (m.type === 'connected') { setVoiceStatus('listening'); setProcessMsg(''); onCharonActive?.(true); }
            else if (m.type === 'status') { setProcessMsg(m.message || ''); }
            else if (m.type === 'transcript') { onCharonTranscriptFull?.(m.speaker || 'wbc', m.text || ''); }
            else if (m.type === 'tool_result') { setProcessMsg(''); onCharonToolResult?.(m.tool || 'tool', m.result || ''); }
            else if (m.type === 'turn_complete') {
              setVoiceStatus('listening'); setProcessMsg('');
              // Limpa buffer de audio entre turns para evitar "disco arranhado"
              audioBufRef.current = [];
              if (playNodeRef.current) playNodeRef.current.port.postMessage({ type: 'clear' });
            }
            else if (m.type === 'error') {
              console.error('[Charon] Backend error:', m.message);
              setVoiceStatus('error');
              setProcessMsg('');
              // Auto-reconnect rapido apos erro
              setTimeout(() => {
                if (!stopped && wsRef.current === ws) {
                  console.log('[Charon] Reconectando apos erro...');
                  startedRef.current = false;
                  wsRef.current = null;
                  start();
                }
              }, 2000);
            }
            else if (m.type === 'disconnected') { console.log('[Charon] Disconnected'); setVoiceStatus('idle'); setProcessMsg(''); onCharonActive?.(false); }
          } catch {}
        };

        ws.onerror = (ev) => {
          console.error('[Charon] WS error');
          if (!wsReady) setVoiceStatus('error');
        };

        ws.onclose = () => {
          console.log('[Charon] WS closed');
          if (!stopped) {
            setVoiceStatus('idle');
            onCharonActive?.(false);
            // Auto-reconnect after 3s
            if (!stopped) {
              setTimeout(() => {
                if (!stopped && wsRef.current === ws) {
                  console.log('[Charon] Reconnecting...');
                  startedRef.current = false;
                  wsRef.current = null;
                  start();
                }
              }, 3000);
            }
          }
        };

        // Wait for WebSocket to open (max 10s)
        let tries = 0;
        while (!wsReady && ws.readyState === WebSocket.CONNECTING && tries < 100) {
          await new Promise(r => setTimeout(r, 100));
          tries++;
        }
        if (!wsReady || ws.readyState !== WebSocket.OPEN) {
          setVoiceStatus('error');
          return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, sampleRate: 48000, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        streamRef.current = stream;

        const micCtx = new AudioContext({ sampleRate: 48000 });
        micCtxRef.current = micCtx;

        const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
        const url = URL.createObjectURL(blob);
        await micCtx.audioWorklet.addModule(url);
        URL.revokeObjectURL(url);

        const source = micCtx.createMediaStreamSource(stream);
        const node = new AudioWorkletNode(micCtx, 'mic-proc', {
          numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1,
        });
        micNodeRef.current = node;

        node.port.onmessage = (ev: MessageEvent) => {
          // Audio is already downsampled to 16kHz PCM16 in the worklet
          const pcm16 = new Int16Array(ev.data);
          const bytes = new Uint8Array(pcm16.buffer);
          if (ws.readyState === WebSocket.OPEN) ws.send(bytes);
          // Calculate audio level (throttled to 100ms)
          const now = performance.now();
          if (now - audioLevelTimeRef.current > 100) {
            audioLevelTimeRef.current = now;
            let sum = 0;
            for (let i = 0; i < pcm16.length; i++) sum += Math.abs(pcm16[i]);
            setAudioLevel(Math.min(1, (sum / pcm16.length / 0x8000) * 3));
          }
        };

        source.connect(node);

        // Heartbeat: verifica se o backend esta respondendo
        heartbeatCheckRef.current = setInterval(() => {
          if (stopped || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

          const timeSinceLastResponse = Date.now() - lastResponseTimeRef.current;
          // Usa voiceStatusRef para evitar closure desatualizado
          const currentStatus = voiceStatusRef.current;
          // Se nao recebeu nada por 45 segundos (qualquer status ativo), forca reconexao
          if (timeSinceLastResponse > 45000 && currentStatus !== 'idle' && currentStatus !== 'error' && currentStatus !== 'connecting') {
            console.log(`[Charon] Backend nao respondeu por 45s (status: ${currentStatus}). Forcando reconexao...`);
            ws.close();
          }
        }, 10000);
      } catch {
        setVoiceStatus('error');
      }
    };

    start();

    return () => {
      stopped = true;
      startedRef.current = false;
      if (heartbeatCheckRef.current) clearInterval(heartbeatCheckRef.current);
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
      if (micNodeRef.current) { micNodeRef.current.disconnect(); micNodeRef.current = null; }
      if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
      if (micCtxRef.current) { micCtxRef.current.close().catch(() => {}); micCtxRef.current = null; }
    };
  }, []);

  const interrupt = () => {
    console.log('[StatusBar] Interrupt clicked');
    // Limpa o buffer de audio e playback
    audioBufRef.current = [];
    if (playNodeRef.current) playNodeRef.current.port.postMessage({ type: 'clear' });
    // Fecha o WebSocket (desliga o Charon)
    if (wsRef.current) {
      try { wsRef.current.send(JSON.stringify({ type: 'stop' })); } catch {}
      try { wsRef.current.close(); } catch {}
      wsRef.current = null;
    }
    // Para o microfone
    if (micNodeRef.current) { micNodeRef.current.disconnect(); micNodeRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (micCtxRef.current) { micCtxRef.current.close().catch(() => {}); micCtxRef.current = null; }
    startedRef.current = false;
    setVoiceStatus('idle');
    onCharonActive?.(false);
    // Para a geração do chat se estiver rodando
    if (stopGen) {
      console.log('[StatusBar] Calling stopGen');
      stopGen();
    } else {
      console.log('[StatusBar] stopGen not provided');
    }
  };

  // Toggle ligar/desligar Charon
  const toggleCharon = () => {
    if (voiceStatusRef.current === 'idle' || voiceStatusRef.current === 'error') {
      // Ligar: reconectar WebSocket
      startedRef.current = false;
      wsRef.current = null;
      // Chama a função start novamente
      const startCharon = async () => {
        try {
          setVoiceStatus('connecting');
          const ws = new WebSocket(getWsUrl());
          wsRef.current = ws;

          let wsReady = false;

        ws.onopen = () => {
          ws.send(JSON.stringify({ type: 'start', voice: voiceName }));
          wsReady = true;
        };

          ws.onmessage = async (e) => {
            if (e.data instanceof Blob) {
              const buf = await e.data.arrayBuffer();
              const bytes = new Uint8Array(buf);
              if (bytes.length >= 2) {
                const pcm16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.length / 2);
                let hash = 0;
                const step = Math.max(1, Math.floor(pcm16.length / 16));
                for (let i = 0; i < pcm16.length; i += step) {
                  hash = ((hash << 5) - hash + pcm16[i]) | 0;
                }
                if (hash !== 0 && hash === lastAudioHashRef.current) {
                  dupCountRef.current++;
                  if (dupCountRef.current > 1) return;
                } else {
                  dupCountRef.current = 0;
                }
                lastAudioHashRef.current = hash;
                audioBufRef.current.push(pcm16);
              }
              setVoiceStatus('speaking');
              return;
            }
            try {
              const m = JSON.parse(e.data);
              if (m.type === 'connected') { setVoiceStatus('listening'); setProcessMsg(''); onCharonActive?.(true); }
              else if (m.type === 'status') { setProcessMsg(m.message || ''); }
              else if (m.type === 'transcript') { onCharonTranscriptFull?.(m.speaker || 'wbc', m.text || ''); }
              else if (m.type === 'tool_result') { setProcessMsg(''); onCharonToolResult?.(m.tool || 'tool', m.result || ''); }
              else if (m.type === 'turn_complete') {
                setVoiceStatus('listening'); setProcessMsg('');
                audioBufRef.current = [];
                if (playNodeRef.current) playNodeRef.current.port.postMessage({ type: 'clear' });
              }
              else if (m.type === 'error') { console.error('[Charon] Backend error:', m.message); setVoiceStatus('error'); setProcessMsg(''); }
              else if (m.type === 'disconnected') { console.log('[Charon] Disconnected'); setVoiceStatus('idle'); setProcessMsg(''); onCharonActive?.(false); }
            } catch {}
          };

          ws.onerror = (ev) => {
            console.error('[Charon] WS error');
            if (!wsReady) setVoiceStatus('error');
          };

          ws.onclose = () => {
            console.log('[Charon] WS closed');
            const wasActive = voiceStatusRef.current !== 'idle';
            // Limpar sempre o estado para permitir reconexao
            if (micNodeRef.current) { micNodeRef.current.disconnect(); micNodeRef.current = null; }
            if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
            if (micCtxRef.current) { try { micCtxRef.current.close(); } catch {} micCtxRef.current = null; }
            wsRef.current = null;
            startedRef.current = false;
            setVoiceStatus('idle');
            voiceStatusRef.current = 'idle';
            if (wasActive) onCharonActive?.(false);
          };

          // Wait for WebSocket to open (max 10s)
          let tries = 0;
          while (!wsReady && ws.readyState === WebSocket.CONNECTING && tries < 100) {
            await new Promise(r => setTimeout(r, 100));
            tries++;
          }
          if (!wsReady || ws.readyState !== WebSocket.OPEN) {
            setVoiceStatus('error');
            return;
          }

          const stream = await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, sampleRate: 48000, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          });
          streamRef.current = stream;

          const micCtx = new AudioContext({ sampleRate: 48000 });
          micCtxRef.current = micCtx;

          const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
          const url = URL.createObjectURL(blob);
          await micCtx.audioWorklet.addModule(url);
          URL.revokeObjectURL(url);

          const source = micCtx.createMediaStreamSource(stream);
          const node = new AudioWorkletNode(micCtx, 'mic-proc', {
            numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1,
          });
          micNodeRef.current = node;

          node.port.onmessage = (ev: MessageEvent) => {
            // Audio is already downsampled to 16kHz PCM16 in the worklet
            const pcm16 = new Int16Array(ev.data);
            const bytes = new Uint8Array(pcm16.buffer);
            if (ws.readyState === WebSocket.OPEN) ws.send(bytes);
            // Calculate audio level (throttled to 100ms)
            const now2 = performance.now();
            if (now2 - audioLevelTimeRef.current > 100) {
              audioLevelTimeRef.current = now2;
              let sum = 0;
              for (let i = 0; i < pcm16.length; i++) sum += Math.abs(pcm16[i]);
              setAudioLevel(Math.min(1, (sum / pcm16.length / 0x8000) * 3));
            }
          };

          source.connect(node);
        } catch {
          setVoiceStatus('error');
        }
      };
      startCharon();
    } else {
      // Desligar: usar a função interrupt
      interrupt();
    }
  };

  const vc: Record<string, string> = { idle: '#666', connecting: '#ff0', listening: '#0f0', speaking: '#0af', error: '#f44' };
  const vl: Record<string, string> = { idle: 'Off', connecting: 'Conectando', listening: 'Ouvindo', speaking: 'Falando', error: 'Erro' };
  const vColor = vc[voiceStatus] || '#666';
  const vLabel = vl[voiceStatus] || voiceStatus;

  return (
    <div className="status-bar">
      <div className="status-left" style={{ display: 'flex', flexDirection: 'row', gap: '12px', alignItems: 'center', whiteSpace: 'nowrap', minWidth: 0, overflow: 'hidden' }}>
        <span style={{ fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0 }}>
          openclaude
        </span>
        <span style={{ opacity: 0.5, whiteSpace: 'nowrap', flexShrink: 0 }}>|</span>
        <span style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>{prov}</span>
        <span style={{ opacity: 0.5, whiteSpace: 'nowrap', flexShrink: 0 }}>|</span>
        <span
          style={{
            whiteSpace: 'nowrap',
            flexShrink: 0,
            maxWidth: 140,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {model.split(':')[0]}
        </span>
        <span style={{ opacity: 0.5, whiteSpace: 'nowrap', flexShrink: 0 }}>|</span>
        <span style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>{mood}</span>
        <span style={{ opacity: 0.5, whiteSpace: 'nowrap', flexShrink: 0 }}>|</span>
        {/* Charon toggle + indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          <button
            onClick={toggleCharon}
            title={voiceStatus === 'idle' || voiceStatus === 'error' ? 'Ativar Charon (sempre ouvindo)' : 'Desligar Charon'}
            style={{
              background: voiceStatus === 'idle' || voiceStatus === 'error' ? 'transparent' : 'rgba(180,120,255,0.2)',
              border: '1px solid',
              borderColor: voiceStatus === 'idle' || voiceStatus === 'error' ? 'var(--line)' : '#b478ff',
              borderRadius: 4,
              fontSize: '10px',
              color: voiceStatus === 'idle' || voiceStatus === 'error' ? 'var(--muted)' : '#b478ff',
              cursor: 'pointer',
              padding: '2px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              whiteSpace: 'nowrap',
              fontWeight: 600,
              animation: voiceStatus === 'listening' ? 'pulse 2s infinite' : 'none',
            }}
          >
            <span style={{ fontSize: 8 }}>⚡</span>
            {voiceStatus === 'idle' || voiceStatus === 'error' ? 'Charon' : voiceStatus === 'listening' ? 'Ouvindo...' : voiceStatus === 'speaking' ? 'Falando...' : 'Conectando...'}
          </button>
          {voiceStatus !== 'idle' && voiceStatus !== 'error' && (
            <>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: vColor, animation: voiceStatus === 'listening' ? 'pulse 1s infinite' : 'none' }} />
              {processMsg && (
                <span style={{ fontSize: 9, color: '#b478ff', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={processMsg}>
                  {processMsg}
                </span>
              )}
              <div style={{ width: 35, height: 5, background: '#222', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${audioLevel * 100}%`, height: '100%', background: audioLevel > 0.6 ? '#f44' : audioLevel > 0.3 ? '#ff0' : '#0f0', transition: 'width 0.05s' }} />
              </div>
            </>
          )}
          {voiceStatus === 'error' && <span style={{ color: '#f44', fontSize: 9 }}>⚠</span>}
        </div>
      </div>
      <div className="status-right">
        <span
          style={{
            opacity: 0.45,
            marginRight: 8,
            letterSpacing: '0.3px',
          }}
        >
          Copyright \u00a9 Empresa: WBC 2026
        </span>
        {setCharonPanel && (
          <button
            onClick={() => {
              // Só permite toggle manual quando Charon NÃO está ativo
              if (!charonActive) {
                setCharonPanel(!charonPanel);
              }
            }}
            title={charonActive ? "Painel ativo com Charon" : "Contexto Charon"}
            style={{
              background: charonPanel ? 'rgba(180,120,255,0.15)' : 'transparent',
              border: '1px solid',
              borderColor: charonPanel ? '#b478ff' : 'var(--line)',
              borderRadius: 4,
              fontSize: '10px',
              color: charonPanel ? '#b478ff' : 'inherit',
              cursor: charonActive ? 'default' : 'pointer',
              padding: '2px 8px',
              display: 'flex',
              alignItems: 'center',
              whiteSpace: 'nowrap',
            }}
          >
            T {charonPanel ? 'on' : 'off'}
          </button>
        )}
        {setThinkOpen && (
          <button onClick={() => setThinkOpen(!thinkOpen)} title="Thinking" style={{ background: thinkOpen ? 'rgba(0,170,255,0.15)' : 'transparent', border: '1px solid', borderColor: thinkOpen ? '#0af' : 'var(--line)', borderRadius: 4, fontSize: '10px', color: thinkOpen ? '#0af' : 'inherit', cursor: 'pointer', padding: '2px 8px', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
            H {thinkOpen ? 'on' : 'off'}
          </button>
        )}
        <button
          onClick={toggleTheme}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: '13px',
            color: 'inherit',
            cursor: 'pointer',
            opacity: 0.8,
            lineHeight: 1,
          }}
          title={`switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          aria-label={`switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
        <StatusIndicator provider={prov} ollamaRunning={ollSt?.running} />
      </div>
    </div>
  );
};

export default StatusBar;