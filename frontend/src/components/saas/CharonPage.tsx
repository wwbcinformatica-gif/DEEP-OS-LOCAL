import React, { useState, useRef, useEffect, useCallback } from 'react';
import { renderMarkdown } from './markdownRenderer';
import {
  Conversation, TranscriptEntry,
  getConversations, createConversation, renameConversation, deleteConversation,
  getTranscripts, saveTranscripts, getActivityLog, saveActivityLog,
  tenantGet, tenantSet, migrateLegacyData,
} from './chatStorage';

interface TranscriptEntry {
  speaker: string;
  text: string;
  time: string;
}

const VOICES = [
  { id: 'Charon', label: 'Charon', type: 'Masculino (padrao)' },
  { id: 'Puck', label: 'Puck', type: 'Masculino' },
  { id: 'Fenrir', label: 'Fenrir', type: 'Masculino' },
  { id: 'Orus', label: 'Orus', type: 'Masculino' },
  { id: 'Kore', label: 'Kore', type: 'Feminino' },
  { id: 'Leda', label: 'Leda', type: 'Feminino' },
  { id: 'Aoede', label: 'Aoede', type: 'Feminino' },
  { id: 'Zephyr', label: 'Zephyr', type: 'Feminino' },
];

const MIC_WORKLET = `
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

const PLAYBACK_WORKLET = `
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ringSize = 384000;
    this._ring = new Float32Array(this._ringSize);
    this._writePos = 0;
    this._readPos = 0;
    this._available = 0;
    this._prebuf = 36000;
    this._started = false;
    this._lastChunkHash = 0;
    this._dupCount = 0;
    this._underruns = 0;
    this.port.onmessage = (e) => {
      if (e.data && e.data.type === 'clear') {
        this._writePos = 0; this._readPos = 0; this._available = 0;
        this._started = false; this._lastChunkHash = 0; this._dupCount = 0;
        this._underruns = 0;
        return;
      }
      const pcm16 = new Int16Array(e.data);
      let hash = 0;
      const step = Math.max(1, Math.floor(pcm16.length / 16));
      for (let i = 0; i < pcm16.length; i += step) hash = ((hash << 5) - hash + pcm16[i]) | 0;
      // Dedup so descarta repeticoes EM SEQUENCIA. Antes o contador nunca era
      // zerado, entao audio real podia ser engolido e a fala ficava picada.
      if (hash !== 0 && hash === this._lastChunkHash) {
        this._dupCount++;
        if (this._dupCount > 6) return;
      } else {
        this._dupCount = 0;
      }
      this._lastChunkHash = hash;
      for (let i = 0; i < pcm16.length; i++) {
        this._ring[this._writePos] = pcm16[i] / 32768;
        this._writePos = (this._writePos + 1) % this._ringSize;
        if (this._available < this._ringSize) this._available++;
        else this._readPos = (this._readPos + 1) % this._ringSize;
      }
      if (!this._started && this._available >= this._prebuf) this._started = true;
    };
  }
  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || !output[0]) return true;
    const ch = output[0];
    if (!this._started) { for (let i = 0; i < ch.length; i++) ch[i] = 0; return true; }
    for (let i = 0; i < ch.length; i++) {
      if (this._available > 0) {
        ch[i] = this._ring[this._readPos];
        this._readPos = (this._readPos + 1) % this._ringSize;
        this._available--;
      } else {
        // Sub-run: o buffer esvaziou antes de chegar mais audio. Em vez de
        // seguir emitindo silencio (que engasga no meio da frase e corta a
        // cauda da ultima palavra), volta ao estado "aguardando" e so retoma
        // quando o prebuffer encher de novo. Sem isso, o fim da fala era
        // consumido em silencio e as ultimas letras sumiam.
        ch[i] = 0;
        this._underruns++;
        if (this._underruns > 4) {
          this._started = false;
          this._underruns = 0;
          this._lastChunkHash = 0;
          this._dupCount = 0;
          for (let j = i + 1; j < ch.length; j++) ch[j] = 0;
          return true;
        }
      }
    }
    this._underruns = 0;
    return true;
  }
}
registerProcessor('playback-proc', PlaybackProcessor);
`;

/**
 * Traduz o erro do getUserMedia/AudioContext numa causa provavel.
 *
 * Antes o erro era engolido ("Mic falhou (Chrome iOS?)") e o usuario ficava
 * sem saber o motivo. Cada caso abaixo pede uma acao diferente — por isso
 * vale distinguir em vez de mostrar mensagem generica.
 */
function _diagnosticoMic(err: unknown): { curto: string; detalhe: string } {
  const nome = (err as { name?: string })?.name || '';
  const msg = (err as { message?: string })?.message || String(err);

  const segura = typeof window !== 'undefined' && window.isSecureContext;

  if (!segura) {
    return {
      curto: 'conexao nao segura',
      detalhe:
        'O navegador so libera o microfone em HTTPS (ou localhost). ' +
        'Acesse por https://deep-os.tech — nao por IP nem http://.',
    };
  }

  switch (nome) {
    case 'NotAllowedError':
    case 'SecurityError':
      return {
        curto: 'permissao negada',
        detalhe:
          'O navegador bloqueou o microfone. Clique no icone de cadeado (ou no icone de ' +
          'microfone) na barra de enderecos, mude para "Permitir" e recarregue a pagina. ' +
          'Se voce negou uma vez, o navegador memoriza essa negativa e para de perguntar.',
      };
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return {
        curto: 'nenhum microfone encontrado',
        detalhe:
          'Nenhum microfone foi detectado. Conecte um e recarregue a pagina.',
      };
    case 'NotReadableError':
    case 'TrackStartError':
      return {
        curto: 'microfone em uso',
        detalhe:
          'Outro programa (Zoom, Teams, gravador) ou outra aba esta usando o microfone. ' +
          'Feche o outro programa/aba e tente de novo.',
      };
    case 'OverconstrainedError':
      return {
        curto: 'configuracao de audio nao suportada',
        detalhe:
          'O microfone nao aceita as opcoes pedidas (cancelamento de eco/ruido). ' +
          'Tente outro dispositivo de entrada no sistema.',
      };
    case 'AbortError':
      return {
        curto: 'captura interrompida',
        detalhe: 'A captura de audio foi interrompida pelo sistema. Tente de novo.',
      };
    case 'TypeError':
      return {
        curto: 'API de audio indisponivel',
        detalhe:
          'navigator.mediaDevices nao esta disponivel. Isso acontece em conexao nao segura ' +
          '(http://) ou em navegador antigo.',
      };
    default:
      return {
        curto: nome || 'erro desconhecido',
        detalhe: `${nome || 'Erro'}: ${msg}`,
      };
  }
}

function getWsUrl(): string {
  const host = window.location.hostname || 'localhost';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
  const base = (port === '443' || port === '80')
    ? `${proto}//${host}/ws/voice`
    : `${proto}//${host}:${port}/ws/voice`;
  // Envia o JWT para o backend isolar a identidade (nome do assistente) por tenant
  const token = tenantGet('saas_token') || localStorage.getItem('saas_token');
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

const CharonPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'config' | 'help'>('chat');
  const [conversations, setConversations] = useState<Conversation[]>(() => getConversations());
  const [activeConvId, setActiveConvId] = useState<string>(() => {
    const migrated = migrateLegacyData();
    if (migrated) return migrated;
    const convs = getConversations();
    return convs[0]?.id || '';
  });
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [activityLog, setActivityLog] = useState<TranscriptEntry[]>([]);
  const [showConvMenu, setShowConvMenu] = useState(false);

  // Load transcripts when active conversation changes
  useEffect(() => {
    if (activeConvId) {
      setTranscripts(getTranscripts(activeConvId));
      setActivityLog(getActivityLog(activeConvId));
    }
  }, [activeConvId]);
  const [inputText, setInputText] = useState('');
  const [voiceName, setVoiceName] = useState('Charon');
  const [userName, setUserName] = useState('');
  const [assistantName, setAssistantName] = useState('DEEP-OS');
  const [accentColor, setAccentColor] = useState('#b478ff');
  const [apiKey, setApiKey] = useState('');
  const [contextFilter, setContextFilter] = useState('');
  const [voiceStatus, setVoiceStatus] = useState<string>('idle');
  const [isCharonActive, setIsCharonActive] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Diagnostico do microfone (curto + detalhe acionavel). Separado de `error`
  // porque a UI trata os dois de forma diferente: aqui o texto e a conexao
  // estao OK, so o microfone falhou — da para tentar de novo sem reconectar.
  const [micError, setMicError] = useState<{ curto: string; detalhe: string } | null>(null);
  const [textareaHeight, setTextareaHeight] = useState(60);
  const textareaHeightRef = useRef(60);
  const [rightPanelWidth, setRightPanelWidth] = useState(280);
  const rightPanelWidthRef = useRef(280);

  const listRef = useRef<HTMLDivElement>(null);
  const rightListRef = useRef<HTMLDivElement>(null);
  const activityRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const micCtxRef = useRef<AudioContext | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const micNodeRef = useRef<AudioWorkletNode | null>(null);
  const playNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const startedRef = useRef(false);
  // Funcao de captura do microfone, guardada para o botao "Tentar de novo".
  // O Chrome precisa de gesto do usuario para liberar o mic — entao a
  // retentativa tem de partir de um clique, nao do auto-start.
  const adquirirMicRef = useRef<null | (() => Promise<boolean>)>(null);
  // Watchdog do microfone: retoma o AudioContext suspenso e readquire a track
  // quando o navegador revoga o acesso no meio da sessao.
  const micWatchdogRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Ultimo instante em que o usuario mexeu no microfone (para o watchdog).
  const lastSendTimeRef = useRef<number>(0);

  // ── Contexto da conversa (regra definida pelo usuario) ───────────────────
  //
  //   "sempre for aberto pela primeira vez a sessao deve ser nova, mas quando eu
  //    entro no novo historico ele deve lembrar de tudo"
  //
  // Ou seja: abrir o Charon NAO deve restaurar contexto (sessao nova, com
  // saudacao). So quando o usuario CLICA numa conversa do historico o contexto
  // daquela conversa deve ser enviado ao Gemini.
  //
  // Sem esta distincao o Charon ou nunca lembrava (como estava) ou lembrava
  // sempre — inclusive quando o usuario queria comecar do zero.
  const [restaurarHistorico, setRestaurarHistorico] = useState(false);
  // Espelho em ref: o callback de conexao precisa do valor atual, e ele e criado
  // uma vez (state ficaria congelado no valor da primeira renderizacao).
  const restaurarHistoricoRef = useRef(false);
  const lastAudioHashRef = useRef(0);
  const dupCountRef = useRef(0);
  const audioBufRef = useRef<Int16Array[]>([]);
  const audioFlushRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const connectVoiceRef = useRef<() => void>(() => {});
  const manualDisconnectRef = useRef(false);
  const voiceNameRef = useRef('Charon');
  const assistantNameRef = useRef('DEEP-OS');
  const userNameRef = useRef('');
  const contextFilterRef = useRef('');

  // ── Barge-in (interromper o Charon falando) ──────────────────────────────
  //
  // O Charon so deve calar quando o USUARIO fala — nao com qualquer ruido.
  // `charonFalandoRef` espelha o status num ref porque o callback do microfone
  // e criado uma vez e leria um `useState` desatualizado.
  const charonFalandoRef = useRef(false);
  // Instante em que a ultima interrupcao foi enviada (evita mandar 30 vezes).
  const ultimaInterrupcaoRef = useRef(0);
  // Contador de chunks seguidos com voz acima do limite. Exigir alguns chunks
  // (e nao um so) evita que um estalo, um teclado ou a propria voz do Charon
  // saindo no alto-falante interrompam a fala sozinhos.
  const chunksComVozRef = useRef(0);
  // Depois de interromper, descarta o audio que ja estava em transito na rede.
  // Sem isto os chunks enviados nos ~400ms anteriores chegam e o Charon continua
  // falando baixinho por cima do usuario — a interrupcao parecia "meio furada".
  const ignorarAudioAteRef = useRef(0);

  useEffect(() => {
    const savedKey = tenantGet('saas_api_key') || '';
    const savedVoice = tenantGet('charon_voice') || 'Charon';
    const savedFilter = tenantGet('charon_context_filter') || '';
    const savedHeight = parseInt(tenantGet('charon_textarea_height') || '60');
    const savedWidth = parseInt(tenantGet('charon_right_panel_width') || '340');
    setApiKey(savedKey);
    setVoiceName(savedVoice);
    setContextFilter(savedFilter);
    setTextareaHeight(savedHeight);
    textareaHeightRef.current = savedHeight;
    setRightPanelWidth(savedWidth);
    rightPanelWidthRef.current = savedWidth;
    contextFilterRef.current = savedFilter;
    // Carrega identity do tenant (JWT identifica o tenant no backend)
    const identityToken = tenantGet('saas_token') || localStorage.getItem('saas_token');
    fetch('/api/config/identity', {
      headers: identityToken ? { Authorization: `Bearer ${identityToken}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          const name = data.assistant_name || 'DEEP-OS';
          const user = data.user_name || '';
          const voice = data.voice || '';
          setAssistantName(name);
          setUserName(user);
          assistantNameRef.current = name;
          userNameRef.current = user;
          tenantSet('charon_assistant_name', name);
          tenantSet('charon_user_name', user);
          if (voice) {
            setVoiceName(voice);
            voiceNameRef.current = voice;
            tenantSet('charon_voice', voice);
          }
        }
      })
      .catch(() => {
        const savedAssistant = tenantGet('charon_assistant_name') || 'DEEP-OS';
        const savedUser = tenantGet('charon_user_name') || '';
        setAssistantName(savedAssistant);
        setUserName(savedUser);
        assistantNameRef.current = savedAssistant;
        userNameRef.current = savedUser;
      });

    // Auto-start: Charon ativa quando a pagina carrega.
    //
    // CUIDADO (Firefox): o Firefox exige GESTO do usuario para liberar audio
    // (AudioContext e getUserMedia). Se tentarmos conectar sozinhos no load,
    // o contexto fica 'suspended' e o microfone captura silencio — o Charon
    // aparece "ouvindo" mas nao recebe nada.
    //
    // Por isso, alem do timer, armamos um listener de primeira interacao:
    // no Firefox o clique/tecla do usuario e o que destrava o audio.
    // O timer so dispara se a pagina tiver foco e o navegador permitir.
    let autoStartFeito = false;

    const limparGatilhos = () => {
      window.removeEventListener('pointerdown', onPrimeiroGesto);
      window.removeEventListener('keydown', onPrimeiroGesto);
      window.removeEventListener('touchstart', onPrimeiroGesto);
    };

    function onPrimeiroGesto() {
      tentarAutoStart('gesto do usuario');
    }

    function tentarAutoStart(motivo: string) {
      if (autoStartFeito || startedRef.current) return;
      autoStartFeito = true;
      limparGatilhos();
      console.log('[Charon] Auto-start (', motivo, ')');
      connectVoiceRef.current().catch(() => {
        setError('Clique em "Charon" para ativar');
        setVoiceStatus('idle');
        startedRef.current = false;
      });
    }

    // No Firefox, so tentamos sozinhos se o navegador JA registrou interacao
    // do usuario nesta pagina. Caso contrario, esperamos o gesto.
    //
    // `navigator.userActivation.hasBeenActive` e a checagem correta (Firefox 79+,
    // Chrome 72+). Tentar getUserMedia sem isso faz o Firefox responder
    // NotAllowedError E MEMORIZAR a negativa como bloqueio do site — depois
    // disso ele nem pergunta mais, mesmo num clique posterior.
    const jaInteragiu = (() => {
      try {
        const ua = (navigator as any).userActivation;
        if (ua && typeof ua.hasBeenActive === 'boolean') return ua.hasBeenActive;
      } catch {}
      return false;
    })();

    const timerAuto = jaInteragiu
      ? setTimeout(() => tentarAutoStart('timer — usuario ja interagiu'), 1000)
      : null;

    window.addEventListener('pointerdown', onPrimeiroGesto, { once: true });
    window.addEventListener('keydown', onPrimeiroGesto, { once: true });
    window.addEventListener('touchstart', onPrimeiroGesto, { once: true });

    if (!jaInteragiu) {
      console.log(
        '[Charon] Sem interacao do usuario ainda — o microfone sera pedido no ' +
        'primeiro clique/tecla. (Evita bloquear o mic permanentemente: o Firefox ' +
        'memoriza uma negativa por falta de gesto.)'
      );
    }

    return () => {
      if (timerAuto) clearTimeout(timerAuto);
      limparGatilhos();
    };
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
    rightListRef.current?.scrollTo({ top: rightListRef.current.scrollHeight, behavior: 'smooth' });
    activityRef.current?.scrollTo({ top: activityRef.current.scrollHeight, behavior: 'smooth' });
    if (activeConvId) {
      saveTranscripts(activeConvId, transcripts);
      saveActivityLog(activeConvId, activityLog);
    }
  }, [transcripts, activityLog, activeConvId]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && activeTab !== 'chat') setActiveTab('chat');
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [activeTab]);

  const now = () => new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const addUserTranscript = useCallback((text: string) => {
    setTranscripts(prev => [...prev, { speaker: 'user', text, time: now() }]);
  }, []);

  const addCharonTranscript = useCallback((text: string) => {
    setTranscripts(prev => [...prev, { speaker: 'charon', text, time: now() }]);
  }, []);

  const addActivity = useCallback((text: string, speaker: string = 'system') => {
    setActivityLog(prev => [...prev, { speaker, text, time: now() }]);
  }, []);

  const renderActivity = (t: TranscriptEntry) => {
    const isWebSearch = t.text.startsWith('web_search:') && t.text.includes('Source:');
    
    // Detecta links de download no formato [texto](url) — api/download ou data:
    const hasDownloadLink = /\[.*?\]\((\/api\/download\?path=|data:).*?\)/.test(t.text);
    
    if (!isWebSearch) {
      // Renderiza links de download como botoes
      const renderTextWithDownloads = (text: string) => {
        const parts = text.split(/(\[.*?\]\((?:\/api\/download\?path=|data:).*?\))/g);
        return parts.map((part, i) => {
          const match = part.match(/\[(.*?)\]\(((?:\/api\/download\?path=|data:).*?)\)/);
          if (match) {
            const label = match[1];
            const url = match[2];
            return (
              <a
                key={i}
                href={url}
                download
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)',
                  color: '#000',
                  borderRadius: 6,
                  textDecoration: 'none',
                  fontSize: 11,
                  fontWeight: 600,
                  marginTop: 8,
                }}
                onClick={(e) => e.stopPropagation()}
              >
                📥 {label}
              </a>
            );
          }
          return <span key={i}>{part}</span>;
        });
      };
      
      return (
        <div key={t.time + t.text.slice(0, 20)} style={{ ...s.messageItem, borderLeft: t.speaker === 'tool' ? '2px solid #b478ff' : t.speaker === 'error' ? '2px solid #f44' : '2px solid #0c0', marginLeft: 4 }}>
          <div style={s.messageSpeaker}>
            {t.speaker === 'tool' ? '🔧 TOOL' : t.speaker === 'error' ? '❌ ERRO' : 'SYSTEM'} - {t.time}
          </div>
          <div style={{ ...s.messageText, whiteSpace: 'pre-wrap', wordBreak: 'break-word', overflowWrap: 'break-word', fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace", fontSize: 11, lineHeight: 1.6 }}>
            {hasDownloadLink ? renderTextWithDownloads(t.text) : t.text}
          </div>
        </div>
      );
    }
    const lines = t.text.split('\n');
    const header = lines[0] || '';
    const query = header.replace('web_search: Search results for: ', '');
    const results: { num: string; title: string; snippet: string; source: string }[] = [];
    let cur: { num: string; title: string; snippet: string; source: string } | null = null;
    for (const line of lines.slice(1)) {
      const numMatch = line.match(/^(\d+)\.\s+(.+)/);
      if (numMatch) {
        if (cur) results.push(cur);
        cur = { num: numMatch[1], title: numMatch[2], snippet: '', source: '' };
      } else if (line.startsWith('Source: ')) {
        if (cur) cur.source = line.replace('Source: ', '');
      } else if (cur && line.trim()) {
        cur.snippet += (cur.snippet ? ' ' : '') + line.trim();
      }
    }
    if (cur) results.push(cur);
    return (
      <div key={t.time + 'ws'} style={{ ...s.messageItem, borderLeft: '2px solid #b478ff', marginLeft: 4, padding: '8px 10px', background: '#1a1a2e', borderRadius: 6, marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: '#b478ff', fontWeight: 700 }}>🔍 WEB SEARCH</span>
          <span style={{ fontSize: 10, color: '#999' }}>•</span>
          <span style={{ fontSize: 10, color: '#ccc', fontStyle: 'italic' }}>"{query}"</span>
          <span style={{ fontSize: 9, color: '#666', marginLeft: 'auto' }}>{t.time}</span>
        </div>
        {results.map((r) => (
          <div key={r.num} style={{ padding: '6px 8px', marginBottom: 4, background: '#12121f', borderRadius: 4, border: '1px solid #222' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
              <span style={{ fontSize: 10, color: '#b478ff', fontWeight: 700, minWidth: 14 }}>{r.num}.</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: '#e0e0e0', fontWeight: 600, lineHeight: 1.3 }}>{r.title}</div>
                {r.snippet && <div style={{ fontSize: 10, color: '#999', marginTop: 2, lineHeight: 1.4 }}>{r.snippet}</div>}
                {r.source && <div style={{ fontSize: 9, color: '#b478ff', marginTop: 3, wordBreak: 'break-all' }}>🔗 {r.source}</div>}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const setupPlayback = useCallback(async () => {
    if (playCtxRef.current && playCtxRef.current.state !== 'closed') {
      // iOS: sempre resume se suspended
      if (playCtxRef.current.state === 'suspended') {
        await playCtxRef.current.resume().catch(() => {});
      }
      return;
    }
    // Fecha contexto anterior se existir (pode ter ficado em estado ruim)
    if (playCtxRef.current && playCtxRef.current.state === 'closed') {
      playCtxRef.current = null;
      playNodeRef.current = null;
    }
    try {
      const ctx = new AudioContext({ sampleRate: 24000 });
      if (ctx.state === 'suspended') {
        await ctx.resume().catch(() => {});
      }
      // iOS Safari: audioWorklet pode nao funcionar, usar fallback
      if (ctx.audioWorklet) {
        try {
          const blob = new Blob([PLAYBACK_WORKLET], { type: 'application/javascript' });
          const url = URL.createObjectURL(blob);
          await ctx.audioWorklet.addModule(url);
          URL.revokeObjectURL(url);
          const node = new AudioWorkletNode(ctx, 'playback-proc', {
            numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [1],
          });
          node.connect(ctx.destination);
          playCtxRef.current = ctx;
          playNodeRef.current = node;
          return;
        } catch (e) {
          console.warn('audioWorklet falhou, usando ScriptProcessor:', e);
        }
      }
      // Fallback: ScriptProcessorNode (compativel com iOS Safari)
      const processor = ctx.createScriptProcessor(4096, 0, 1);
      const playQueue: Float32Array[] = [];
      (processor as any).onaudioprocess = (e: AudioProcessingEvent) => {
        const output = e.outputBuffer.getChannelData(0);
        const chunk = playQueue.shift();
        if (chunk) {
          for (let i = 0; i < output.length; i++) output[i] = chunk[i] || 0;
        } else {
          for (let i = 0; i < output.length; i++) output[i] = 0;
        }
      };
      processor.connect(ctx.destination);
      playCtxRef.current = ctx;
      (playNodeRef as any).current = processor;
      (window as any).__charonPlayQueue = playQueue;
    } catch (e) {
      console.error('setupPlayback falhou:', e);
    }
  }, []);

  const connectVoice = useCallback(async () => {
    if (startedRef.current) return;
      startedRef.current = true;
      manualDisconnectRef.current = false;
      setVoiceStatus('connecting');
      setError(null);
      setMicError(null);
      // Limpa audio antigo ao reconectar
      if (playNodeRef.current) { try { playNodeRef.current.port.postMessage({ type: 'clear' }); } catch {} }
      audioBufRef.current = [];

    try {
      setupPlayback().catch(e => console.warn('setupPlayback falhou (continuando):', e));

      // Buffer intermediario: acumula chunks de audio e envia ao worklet a cada 20ms
      audioBufRef.current = [];
      if (audioFlushRef.current) clearInterval(audioFlushRef.current);
      audioFlushRef.current = setInterval(() => {
        const chunks = audioBufRef.current;
        if (chunks.length === 0) return;
        audioBufRef.current = [];
        let totalLen = 0;
        for (const c of chunks) totalLen += c.length;
        if (totalLen === 0) return;
        const merged = new Int16Array(totalLen);
        let offset = 0;
        for (const c of chunks) { merged.set(c, offset); offset += c.length; }
        // Auto-recupera AudioContext se travou
        if (!playCtxRef.current || playCtxRef.current.state === 'closed') {
          setupPlayback().catch(() => {});
          return;
        }
        if (playCtxRef.current.state === 'suspended') {
          playCtxRef.current.resume().catch(() => {});
        }
        if (playNodeRef.current) {
          try {
            if ((playNodeRef.current as any).port) {
              (playNodeRef.current as any).port.postMessage(merged.buffer, [merged.buffer]);
            } else {
              const playQueue = (window as any).__charonPlayQueue as Float32Array[] | undefined;
              if (playQueue) {
                const float32 = new Float32Array(merged.length);
                for (let i = 0; i < merged.length; i++) float32[i] = merged[i] / 32768;
                playQueue.push(float32);
              }
            }
          } catch (e) {
            console.warn('Audio send failed, recreating playback:', e);
            playNodeRef.current = null;
            playCtxRef.current = null;
            setupPlayback().catch(() => {});
          }
        }
      }, 20);

      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        // Historico SO vai quando o usuario escolheu uma conversa do historico.
        // Numa abertura normal (sessao nova) vai vazio, e o backend cumprimenta.
        const historico = historicoParaEnviar();
        ws.send(JSON.stringify({
          type: 'start',
          voice: voiceNameRef.current,
          assistant_name: assistantNameRef.current,
          user_name: userNameRef.current,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Sao_Paulo',
          locale: navigator.language || 'pt-BR',
          history: historico,
        }));
        if (historico.length) {
          addActivity(`Restaurando contexto: ${historico.length} falas desta conversa`, 'system');
        }
      };

      ws.onmessage = async (e) => {
        if (e.data instanceof Blob) {
          const buf = await e.data.arrayBuffer();
          const bytes = new Uint8Array(buf);
          // Audio em transito logo apos uma interrupcao: descarta para o Charon
          // nao continuar falando por cima do usuario.
          if (Date.now() < ignorarAudioAteRef.current) return;
          if (bytes.length >= 2) {
            const pcm16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.length / 2);
            audioBufRef.current.push(pcm16);
          }
          // Marca que o Charon esta falando: e o que habilita a deteccao de
          // barge-in pelo nivel do microfone.
          charonFalandoRef.current = true;
          setVoiceStatus('speaking');
          return;
        }
        try {
          const m = JSON.parse(e.data);
          if (m.type === 'connected') {
            setVoiceStatus('listening');
            setIsCharonActive(true);
          } else if (m.type === 'status') {
            setVoiceStatus('processing');
          } else if (m.type === 'transcript') {
            if (m.speaker === 'user') addUserTranscript(m.text);
            else addCharonTranscript(m.text);
          } else if (m.type === 'tool_result') {
            addActivity(`${m.tool}: ${m.result}`, 'tool');
          } else if (m.type === 'tool_start') {
            addActivity(`Executando: ${m.tool}...`, 'tool');
          } else if (m.type === 'interrupted') {
            // O Gemini (VAD do servidor) detectou a fala do usuario. Esvazia a
            // fila local na hora — o servidor ja parou de gerar, mas o audio
            // que o navegador ja tinha baixado continuaria tocando.
            charonFalandoRef.current = false;
            chunksComVozRef.current = 0;
            audioBufRef.current = [];
            if (playNodeRef.current) {
              try { playNodeRef.current.port.postMessage({ type: 'clear' }); } catch {}
            }
            setVoiceStatus('listening');
          } else if (m.type === 'turn_complete') {
            charonFalandoRef.current = false;
            chunksComVozRef.current = 0;
            setVoiceStatus('listening');
          } else if (m.type === 'error') {
            setError(m.message);
            setVoiceStatus('error');
            addActivity(`Erro: ${m.message}`, 'error');
          }
        } catch {}
      };

      ws.onerror = () => {
        setError('Erro de conexao');
        setVoiceStatus('error');
      };

      ws.onclose = () => {
        if (micNodeRef.current) { micNodeRef.current.disconnect(); micNodeRef.current = null; }
        if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
        if (micCtxRef.current) { try { micCtxRef.current.close(); } catch {} micCtxRef.current = null; }
        if (micWatchdogRef.current) { clearInterval(micWatchdogRef.current); micWatchdogRef.current = null; }
        if (audioFlushRef.current) { clearInterval(audioFlushRef.current); audioFlushRef.current = null; }
        audioBufRef.current = [];
        // Limpa o ring buffer do worklet para evitar audio antigo sobrepondo
        if (playNodeRef.current) { try { playNodeRef.current.port.postMessage({ type: 'clear' }); } catch {} }
        wsRef.current = null;
        startedRef.current = false;
        setIsCharonActive(false);
        setVoiceStatus('idle');
        // So reconecta automaticamente se nao foi desconexao manual (queda acidental)
        if (!manualDisconnectRef.current) {
          setTimeout(() => {
            if (!startedRef.current) connectVoice();
          }, 3000);
        }
      };

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('WebSocket timeout')), 8000);
        const origOpen = ws.onopen;
        ws.onopen = (ev) => { clearTimeout(timeout); (origOpen as any)?.(ev); resolve(); };
        ws.onerror = () => { clearTimeout(timeout); reject(new Error('WebSocket error - verifique conexao')); };
      });

      // NÃO declarar "ouvindo" antes de ter o microfone de fato — isso fazia a
      // interface dizer "Ouvindo... fale com o Charon" mesmo com o mic falhado.
      setVoiceStatus('connecting');

      // Guarda a funcao de captura para permitir "tentar de novo" por gesto
      // do usuario (o Chrome exige interacao para liberar o microfone).
      const adquirirMic = async (): Promise<boolean> => {
        try {
          if (!navigator.mediaDevices?.getUserMedia) {
            throw new DOMException('navigator.mediaDevices indisponivel', 'SecurityError');
          }

          const stream = await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          });
          streamRef.current = stream;

          // IMPORTANTE (Firefox): se `sampleRate` for diferente do que o
          // Firefox suporta, o contexto fica SUSPENSO e a captura entrega
          // silencio. O Chrome reamostra sozinho, o Firefox nao.
          //
          // Antes usavamos `new AudioContext({ sampleRate: micRate })` com a
          // taxa do dispositivo (44100). Aqui tentamos sem forcar a taxa e so
          // caímos para o valor pedido se a criacao falhar.
          let micCtx: AudioContext;
          try {
            micCtx = new AudioContext();
          } catch (e) {
            const micRate = stream.getAudioTracks()[0]?.getSettings()?.sampleRate || 48000;
            micCtx = new AudioContext({ sampleRate: micRate });
          }
          // Firefox exige gesto do usuario para sair de 'suspended'; sem isso
          // o mic "conecta" mas nunca envia audio.
          if (micCtx.state === 'suspended') {
            await micCtx.resume().catch(() => {});
          }
          if (micCtx.state !== 'running') {
            // Tenta mais uma vez apos um instante curto (o resume as vezes
            // resolve de forma assincrona no Firefox).
            await new Promise((r) => setTimeout(r, 120));
            await micCtx.resume().catch(() => {});
          }
          micCtxRef.current = micCtx;
          console.log('[Charon] AudioContext do mic:', micCtx.state, '| sampleRate real:', micCtx.sampleRate);

          const blob = new Blob([MIC_WORKLET], { type: 'application/javascript' });
          const url = URL.createObjectURL(blob);
          await micCtx.audioWorklet.addModule(url);
          URL.revokeObjectURL(url);

          const source = micCtx.createMediaStreamSource(stream);
          const node = new AudioWorkletNode(micCtx, 'mic-proc', {
            numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1,
          });
          micNodeRef.current = node;

          node.port.onmessage = (ev: MessageEvent) => {
            const pcm16 = new Int16Array(ev.data);
            const bytes = new Uint8Array(pcm16.buffer);
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(bytes);
              lastSendTimeRef.current = Date.now();
            }
            let sum = 0;
            for (let i = 0; i < pcm16.length; i++) sum += Math.abs(pcm16[i]);
            const nivel = sum / pcm16.length / 0x8000;
            setAudioLevel(Math.min(1, nivel * 3));

            // ── Barge-in: o usuario falou por cima do Charon ──────────────
            //
            // Reaproveita o nivel que ja era calculado para o medidor da tela.
            // Limite de 0.06 (~ -44 dBFS) e 3 chunks seguidos: baixo o bastante
            // para pegar fala normal, alto o bastante para ignorar ruido de
            // fundo. Exigir 3 chunks evita que um estalo ou o proprio audio do
            // Charon saindo no alto-falante disparem a interrupcao.
            if (charonFalandoRef.current) {
              if (nivel > 0.06) {
                chunksComVozRef.current += 1;
                if (chunksComVozRef.current >= 3) {
                  interromperCharon('voce falou');
                }
              } else {
                chunksComVozRef.current = 0;
              }
            }
          };

          source.connect(node);

          // So agora e verdade: microfone capturando
          setMicError(null);
          setVoiceStatus('listening');
          setIsCharonActive(true);
          console.log('[Charon] Microfone ativo. AudioContext state:', micCtx.state,
                      '| sampleRate:', micCtx.sampleRate);

          // ── Watchdog do microfone ──────────────────────────────────────
          // O playback ja tinha auto-recuperacao, o microfone NAO. Se o
          // AudioContext do mic for suspenso (troca de aba, economia de
          // energia, bloqueio de tela no celular), a captura para em silencio
          // e o Charon fica "ouvindo" sem receber nada.
          if (micWatchdogRef.current) clearInterval(micWatchdogRef.current);
          micWatchdogRef.current = setInterval(() => {
            if (ws.readyState !== WebSocket.OPEN) return;

            const ctx = micCtxRef.current;
            if (!ctx || ctx.state === 'closed') return;
            if (ctx.state === 'suspended') {
              console.warn('[Charon] AudioContext do microfone suspenso — retomando');
              addActivity('Microfone pausado pelo navegador — retomando', 'system');
              ctx.resume().catch(() => {});
            }

            // O navegador revoga a permissao ou o dispositivo some no meio da
            // sessao: a track dispara 'ended' e o mic morre calado.
            const track = streamRef.current?.getAudioTracks?.()[0];
            if (track && track.readyState === 'ended') {
              console.warn('[Charon] Track de audio encerrada — readquirindo microfone');
              addActivity('Microfone desconectado — reconectando', 'system');
              clearInterval(micWatchdogRef.current!);
              micWatchdogRef.current = null;
              const atual = adquirirMicRef.current;
              if (atual) atual().catch(() => {});
            }
          }, 2000);

          return true;
        } catch (micErr) {
          const motivo = _diagnosticoMic(micErr);
          console.warn('[Charon] Microfone indisponivel:', micErr);
          addActivity(`Microfone indisponivel - modo texto ativo (${motivo.curto})`, 'system');
          setMicError({ curto: motivo.curto, detalhe: motivo.detalhe });
          setVoiceStatus('mic-error');
          setIsCharonActive(false);
          return false;
        }
      };
      adquirirMicRef.current = adquirirMic;

      await adquirirMic();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro');
      setVoiceStatus('error');
      startedRef.current = false;
    }
  }, [setupPlayback, addUserTranscript, addCharonTranscript]);

  // Mantem o ref atualizado com a funcao connectVoice mais recente
  useEffect(() => {
    connectVoiceRef.current = connectVoice;
  }, [connectVoice]);

  // Atualiza voiceNameRef quando a voz muda (para WebSocket enviar a nova voz)
  useEffect(() => {
    voiceNameRef.current = voiceName;
  }, [voiceName]);

  const disconnectVoice = useCallback(() => {
    manualDisconnectRef.current = true;
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    if (micNodeRef.current) { micNodeRef.current.disconnect(); micNodeRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (micCtxRef.current) { try { micCtxRef.current.close(); } catch {} micCtxRef.current = null; }
    if (micWatchdogRef.current) { clearInterval(micWatchdogRef.current); micWatchdogRef.current = null; }
    if (audioFlushRef.current) { clearInterval(audioFlushRef.current); audioFlushRef.current = null; }
    audioBufRef.current = [];
    if (playNodeRef.current) { playNodeRef.current.port.postMessage({ type: 'clear' }); }
    startedRef.current = false;
    setIsCharonActive(false);
    setVoiceStatus('idle');
    setAudioLevel(0);
  }, []);

  /**
   * Faz o Charon parar de falar imediatamente para ouvir o usuario.
   *
   * POR QUE ISSO PRECISA EXISTIR NO NAVEGADOR
   * O Gemini Live ja detecta a fala do usuario no servidor, mas sozinho isso
   * nao basta: quando o Charon esta falando, ja existem SEGUNDOS de audio
   * baixados esperando na fila local (o `audioBufRef` + o ring do worklet de
   * reproducao). Mesmo que o servidor pare de mandar, o navegador continua
   * tocando o que ja recebeu — o Charon "nao para de falar".
   *
   * Por isso a interrupcao tem duas partes:
   *   1. esvaziar a fila e o ring locais (silencio imediato, sem esperar a rede);
   *   2. avisar o servidor (`type: 'interrupt'`) para ele descartar o turno e
   *      mandar `interrupt=True` ao Gemini.
   *
   * Usa apenas refs, entao nao sofre com closure desatualizada no callback do
   * microfone (que e registrado uma unica vez).
   */
  const interromperCharon = (motivo: string) => {
    const agora = Date.now();
    // Nao repetir a cada chunk: no maximo uma interrupcao por segundo.
    if (agora - ultimaInterrupcaoRef.current < 1000) return;
    ultimaInterrupcaoRef.current = agora;
    chunksComVozRef.current = 0;
    charonFalandoRef.current = false;

    // 1. Silencio local imediato
    audioBufRef.current = [];
    if (playNodeRef.current) {
      try { playNodeRef.current.port.postMessage({ type: 'clear' }); } catch {}
    }
    // Descarta o que ja estava vindo pela rede
    ignorarAudioAteRef.current = Date.now() + 400;

    // 2. Avisa o servidor
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify({ type: 'interrupt' })); } catch {}
    }

    setVoiceStatus('listening');
    addActivity(`Interrompido (${motivo}) — ouvindo voce`, 'system');
  };

  const toggleCharon = () => {
    if (isCharonActive) {
      disconnectVoice();
    } else {
      connectVoice();
    }
  };

  const sendText = (text: string) => {
    if (!text.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    // Auto-create conversation on first message
    if (!activeConvId) {
      const conv = createConversation(text.trim());
      setConversations(getConversations());
      setActiveConvId(conv.id);
    }
    wsRef.current.send(JSON.stringify({ type: 'text', text: text.trim() }));
    addUserTranscript(text.trim());
    setInputText('');
  };

  const handleSend = () => {
    const text = inputText.trim();
    if (!text) return;
    sendText(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleSaveVoice = async () => {
    tenantSet('charon_voice', voiceName);
    try {
      const idToken = tenantGet('saas_token') || localStorage.getItem('saas_token');
      await fetch('/api/config/identity', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          assistant_name: assistantName,
          user_name: userName,
          custom_color: '',
          voice: voiceName
        })
      });
      await fetch('/voice/disconnect-all', { method: 'POST' }).catch(() => {});
    } catch (e) {
      console.error('Erro ao salvar voz:', e);
    }
    alert('Voz salva! Aplicada na proxima vez que reiniciar o Charon.');
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      alert('Informe sua chave de API!');
      return;
    }
    try {
      const res = await fetch('/api/config/api-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key: apiKey }),
      });
      if (res.ok) {
        tenantSet('saas_api_key', apiKey);
        alert('Chave API salva no servidor!');
      } else {
        tenantSet('saas_api_key', apiKey);
        alert('Chave API salva localmente (servidor indisponivel)');
      }
    } catch {
      tenantSet('saas_api_key', apiKey);
      alert('Chave API salva localmente!');
    }
  };

  const handleSaveContextFilter = () => {
    tenantSet('charon_context_filter', contextFilter);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'context_filter', filter: contextFilter }));
    }
    alert('Filtro de contexto salvo!');
  };

const handleSaveIdentity = async () => {
    tenantSet('charon_assistant_name', assistantName);
    tenantSet('charon_user_name', userName);
    
    // Salva no backend config.yaml via API correta
    try {
      const idToken = tenantGet('saas_token') || localStorage.getItem('saas_token');
      await fetch('/api/config/identity', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          assistant_name: assistantName,
          user_name: userName,
          custom_color: '',
          voice: voiceName
        })
      });
      // Forca reconexao do Charon para usar novo identity
      await fetch('/voice/disconnect-all', { method: 'POST' }).catch(() => {});
    } catch (e) {
      console.error('Erro ao salvar identity:', e);
    }
    
    alert('Identidade salva! Aplicada na proxima vez que reiniciar o Charon.');
};

  // ─── Conversation management ───────────────────────────────────
  const switchConversation = (convId: string) => {
    const jaAtiva = convId === activeConvId;
    setActiveConvId(convId);
    setShowConvMenu(false);
    // O usuario escolheu uma conversa do historico de proposito: a partir daqui
    // o Charon deve lembrar dela.
    setRestaurarHistorico(true);
    restaurarHistoricoRef.current = true;

    // Se a sessao JA esta aberta, so trocar o estado da tela nao muda nada no
    // Gemini: o estado da conversa fica no servidor DELE e nao pode ser
    // "rebobinado". A unica forma confiavel de trocar de contexto e RECONECTAR
    // — assim a sessao nasce ja com o historico certo.
    //
    // Reabrir a conversa que ja esta ativa tambem reconecta: e o gesto natural
    // de "quero o contexto desta aqui".
    if (startedRef.current) {
      addActivity(
        jaAtiva
          ? 'Recarregando o contexto desta conversa...'
          : 'Trocando de conversa — recarregando o contexto...',
        'system',
      );
      disconnectVoice();
      // Pequeno atraso para o servidor fechar a sessao antiga antes de abrir a
      // nova (o backend tambem derruba sessoes antigas, mas isto evita corrida).
      setTimeout(() => connectVoiceRef.current(), 600);
    }
  };

  const newConversation = () => {
    const conv = createConversation();
    setConversations(getConversations());
    setActiveConvId(conv.id);
    setTranscripts([]);
    setActivityLog([]);
    setShowConvMenu(false);
    // Conversa nova = sessao nova: nada de restaurar nada.
    setRestaurarHistorico(false);
    restaurarHistoricoRef.current = false;
  };

  /** Transcripts da conversa ativa no formato que o backend espera. */
  const historicoParaEnviar = (): { speaker: string; text: string }[] => {
    if (!restaurarHistoricoRef.current || !activeConvId) return [];
    return getTranscripts(activeConvId).map(t => ({ speaker: t.speaker, text: t.text }));
  };

  const handleDeleteConversation = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Excluir esta conversa?')) return;
    deleteConversation(convId);
    const remaining = getConversations();
    setConversations(remaining);
    if (activeConvId === convId) {
      const next = remaining[0];
      if (next) {
        setActiveConvId(next.id);
        setTranscripts(getTranscripts(next.id));
        setActivityLog(getActivityLog(next.id));
      } else {
        const conv = createConversation();
        setConversations(getConversations());
        setActiveConvId(conv.id);
        setTranscripts([]);
        setActivityLog([]);
      }
    }
  };

  const handleRenameConversation = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const conv = conversations.find(c => c.id === convId);
    if (!conv) return;
    const newName = prompt('Renomear conversa:', conv.name);
    if (newName && newName.trim()) {
      renameConversation(convId, newName.trim());
      setConversations(getConversations());
    }
  };

  const formatConvTime = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 86400000 && d.getDate() === now.getDate()) {
      return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }
    if (diff < 604800000) {
      return d.toLocaleDateString('pt-BR', { weekday: 'short' });
    }
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  };

  const activeConv = conversations.find(c => c.id === activeConvId);

  const statusColor: Record<string, string> = { idle: '#666', connecting: '#ff0', listening: '#0c0', speaking: '#0af', processing: '#f80', error: '#f44' };
  const statusLabel: Record<string, string> = { idle: 'inativo', connecting: 'conectando', listening: 'ouvindo', speaking: 'falando', processing: 'processando', error: 'erro' };
  const sc = statusColor[voiceStatus] || '#666';
  const sl = statusLabel[voiceStatus] || voiceStatus;

  return (
    <div style={s.container} className="charon-page">
      <div style={s.tabs} className="charon-tabs">
        <button style={{ ...s.tab, ...(activeTab === 'chat' ? s.tabActive : {}) }} onClick={() => setActiveTab('chat')}>
          Chat
        </button>
        <button style={{ ...s.tab, ...(activeTab === 'config' ? s.tabActive : {}) }} onClick={() => setActiveTab('config')}>
          Configuracoes
        </button>
        <button style={{ ...s.tab, ...(activeTab === 'help' ? s.tabActive : {}) }} onClick={() => setActiveTab('help')}>
          Ajuda
        </button>
      </div>

      {activeTab === 'chat' && (
        <div style={s.chatLayout} className="charon-chat-layout">
          {/* LEFT PANEL — Log de Atividades (pesquisas, tools, relatorios) */}
          <div style={s.leftPanel} className="charon-left-panel">
            <div style={s.charonHeader}>
              <div style={s.charonTitleArea}>
                <span style={s.charonTitle}>ATIVIDADES</span>
                <button style={s.novoBtn} onClick={() => setActivityLog([])}>+ limpar</button>
              </div>
              <div style={s.modelArea}>
                <span style={{ ...s.greenDot, background: sc }} />
                <span style={{ fontSize: 10, color: '#999', marginLeft: 4 }}>{activityLog.length} registros</span>
              </div>
            </div>

            <div ref={activityRef} style={s.chatArea}>
              {activityLog.length === 0 ? (
                <div style={s.emptyState}>
                  Log de atividades vazio. Pesquisas, ferramentas e resultados do Charon aparecerao aqui.
                </div>
              ) : (
                activityLog.map((t, i) => (
                  <div key={i}>{renderActivity(t)}</div>
                ))
              )}
            </div>

            <div style={s.inputSection}>
              <div
                onPointerDown={(e) => {
                  e.preventDefault();
                  const startY = e.clientY;
                  const startH = textareaHeightRef.current;
                  const move = (ev: PointerEvent) => {
                    const delta = startY - ev.clientY;
                    textareaHeightRef.current = Math.max(36, Math.min(400, startH + delta));
                    setTextareaHeight(textareaHeightRef.current);
                    tenantSet('charon_textarea_height', String(textareaHeightRef.current));
                  };
                  const up = () => {
                    window.removeEventListener('pointermove', move);
                    window.removeEventListener('pointerup', up);
                  };
                  window.addEventListener('pointermove', move);
                  window.addEventListener('pointerup', up);
                }}
                style={{ height: 6, cursor: 'ns-resize', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, margin: '2px 0' }}
              >
                <div style={{ width: 40, height: 3, borderRadius: 2, background: '#444' }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <textarea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={isCharonActive ? 'Digite sua mensagem...' : 'Ative o Charon para enviar'}
                  disabled={!isCharonActive}
                  style={{ ...s.textarea, height: textareaHeight, resize: 'none', opacity: isCharonActive ? 1 : 0.5, background: isCharonActive ? '#1a1a2e' : 'rgba(255,255,255,0.03)' }}
                />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: sc, display: 'inline-block' }} />
                    <span style={{ fontSize: 11, color: sc, fontWeight: 600 }}>
                      {isCharonActive ? 'Charon ativo' : 'Charon inativo'}
                    </span>
                    {audioLevel > 0 && (
                      <div style={{ width: 40, height: 4, background: '#222', borderRadius: 2, overflow: 'hidden', marginLeft: 6 }}>
                        <div style={{ width: `${audioLevel * 100}%`, height: '100%', background: audioLevel > 0.6 ? '#f44' : audioLevel > 0.3 ? '#ff0' : '#0c0', transition: 'width 0.05s' }} />
                      </div>
                    )}
                  </div>
                  <button style={s.sendBtn} onClick={handleSend} disabled={!isCharonActive || !inputText.trim()}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* DRAG HANDLE — redimensiona painel lateral */}
          <div
            className="charon-drag-h"
            onPointerDown={(e) => {
              e.preventDefault();
              const startX = e.clientX;
              const startW = rightPanelWidthRef.current;
              const move = (ev: PointerEvent) => {
                const delta = startX - ev.clientX;
                rightPanelWidthRef.current = Math.max(200, Math.min(500, startW + delta));
                setRightPanelWidth(rightPanelWidthRef.current);
                tenantSet('charon_right_panel_width', String(rightPanelWidthRef.current));
              };
              const up = () => {
                window.removeEventListener('pointermove', move);
                window.removeEventListener('pointerup', up);
              };
              window.addEventListener('pointermove', move);
              window.addEventListener('pointerup', up);
            }}
            style={{ width: 5, cursor: 'ew-resize', alignItems: 'center', justifyContent: 'center', flexShrink: 0, background: '#111' }}
          >
            <div style={{ width: 3, height: 40, borderRadius: 2, background: '#333' }} />
          </div>

          {/* RIGHT PANEL — Voz (escuta + respostas do Charon) */}
          <div style={{ ...s.rightPanel, width: rightPanelWidth }} className="charon-right-panel">
            {/* Conversation selector bar */}
            <div style={{ padding: '4px 8px', borderBottom: '1px solid #222', display: 'flex', alignItems: 'center', gap: 4, position: 'relative' as const }}>
              <button onClick={newConversation} title="Nova conversa" style={{ background: 'none', border: 'none', color: '#b478ff', fontSize: 14, cursor: 'pointer', padding: '2px 4px', lineHeight: 1 }}>+</button>
              <button
                onClick={() => setShowConvMenu(!showConvMenu)}
                style={{
                  flex: 1, background: 'none', border: 'none', color: '#ccc',
                  fontSize: 11, textAlign: 'left', cursor: 'pointer',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                  padding: '2px 4px',
                }}
              >
                {activeConv?.name || 'Nova conversa'}
              </button>
              {/* Indicador de contexto: deixa claro se o Charon esta num assunto
                  novo ou se esta lembrando da conversa escolhida. Sem isto o
                  usuario nao tem como saber se o contexto foi carregado. */}
              <span
                title={restaurarHistorico
                  ? 'Charon esta lembrando desta conversa. Use + para comecar do zero.'
                  : 'Sessao nova. Abra o historico e clique numa conversa para o Charon lembrar dela.'}
                style={{
                  fontSize: 8, padding: '1px 5px', borderRadius: 8, flexShrink: 0,
                  background: restaurarHistorico ? 'rgba(180,120,255,0.18)' : 'rgba(102,102,102,0.15)',
                  color: restaurarHistorico ? '#c9a6ff' : '#777',
                  border: `1px solid ${restaurarHistorico ? 'rgba(180,120,255,0.4)' : '#333'}`,
                  whiteSpace: 'nowrap' as const,
                }}
              >
                {restaurarHistorico ? '\u21BA lembra da conversa' : 'sessao nova'}
              </span>
              <span style={{ fontSize: 9, color: '#666' }}>{transcripts.length}</span>
              {showConvMenu && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
                  background: '#1a1a2e', border: '1px solid #333', borderRadius: 6,
                  maxHeight: 200, overflowY: 'auto', boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
                }}>
                  {conversations.map(conv => (
                    <div
                      key={conv.id}
                      onClick={() => switchConversation(conv.id)}
                      style={{
                        padding: '6px 8px', cursor: 'pointer', display: 'flex',
                        alignItems: 'center', gap: 6,
                        background: conv.id === activeConvId ? 'rgba(180,120,255,0.15)' : 'transparent',
                        borderBottom: '1px solid #222',
                      }}
                    >
                      <span style={{ flex: 1, fontSize: 11, color: conv.id === activeConvId ? '#b478ff' : '#ccc', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                        {conv.name}
                      </span>
                      <span style={{ fontSize: 9, color: '#666', flexShrink: 0 }}>{formatConvTime(conv.updatedAt)}</span>
                      <button onClick={(e) => handleRenameConversation(conv.id, e)} title="Renomear" style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 10, padding: '0 2px' }}>✎</button>
                      <button onClick={(e) => handleDeleteConversation(conv.id, e)} title="Excluir" style={{ background: 'none', border: 'none', color: '#f44', cursor: 'pointer', fontSize: 10, padding: '0 2px' }}>✕</button>
                    </div>
                  ))}
                  {conversations.length === 0 && (
                    <div style={{ padding: '8px', textAlign: 'center', color: '#666', fontSize: 11 }}>
                      Nenhuma conversa ainda
                    </div>
                  )}
                </div>
              )}
            </div>
            {/* Charon status header */}
            <div style={s.rightHeader} onClick={toggleCharon} role="button">
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                <span style={{ color: '#b478ff', fontSize: 12 }}>&#9889;</span>
                <span style={{ fontSize: 12, color: '#b478ff', fontWeight: 600 }}>Charon</span>
                <span style={{
                  fontSize: 9,
                  padding: '1px 8px',
                  borderRadius: 4,
                  background: `${sc}33`,
                  color: sc,
                  fontWeight: 500,
                  marginLeft: 4,
                }}>
                  {sl}
                </span>
              </div>
            </div>
            <div ref={rightListRef} style={s.messagesList}>
              {transcripts.length === 0 ? (
                <div style={s.emptyState}>
                  {micError ? (
                    // Microfone falhou: a conexao esta OK, mas nao da para falar.
                    // Antes a UI dizia "Ouvindo... fale com o Charon" aqui — mentia.
                    <div style={{maxWidth: 420, textAlign: 'left'}}>
                      <p style={{margin: '0 0 6px', fontWeight: 600, color: '#f59e0b'}}>
                        🎤 Microfone indisponivel ({micError.curto})
                      </p>
                      <p style={{margin: '0 0 12px', fontSize: 13, lineHeight: 1.5, opacity: 0.9}}>
                        {micError.detalhe}
                      </p>
                      <p style={{margin: '0 0 12px', fontSize: 13, opacity: 0.75}}>
                        Voce pode continuar digitando abaixo — o Charon responde por texto.
                      </p>
                      <button
                        onClick={async () => {
                          const ok = await adquirirMicRef.current?.();
                          if (ok) addActivity('Microfone ativo', 'system');
                        }}
                        style={{padding: '8px 20px', background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontWeight: 600}}
                      >
                        Tentar microfone novamente
                      </button>
                    </div>
                  ) : isCharonActive ? 'Ouvindo... fale com o Charon' :
                   voiceStatus === 'connecting' ? 'Conectando...' :
                   voiceStatus === 'error' ? (
                     <div>
                       <p style={{margin: '0 0 8px'}}>Erro: {error || 'desconhecido'}</p>
                       <button onClick={toggleCharon} style={{padding: '8px 20px', background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontWeight: 600}}>
                         Tentar novamente
                       </button>
                     </div>
                   ) : (
                     <div>
                       <p style={{margin: '0 0 8px'}}>Clique para ativar o Charon</p>
                       <button onClick={toggleCharon} style={{padding: '10px 24px', background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, cursor: 'pointer', fontWeight: 600}}>
                         Conectar Charon
                       </button>
                     </div>
                   )}
                </div>
              ) : (
                transcripts.map((t, i) => (
                  <div key={i} style={{
                    marginBottom: 10,
                    padding: '8px 10px',
                    borderRadius: 6,
                    background: t.speaker === 'user' ? 'rgba(180,120,255,0.08)' : 'rgba(0,200,0,0.08)',
                    borderLeft: `3px solid ${t.speaker === 'user' ? '#b478ff' : '#0c0'}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                      <span style={{ fontSize: 12 }}>{t.speaker === 'user' ? '👤' : '⚡'}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: t.speaker === 'user' ? '#b478ff' : '#0c0' }}>
                        {t.speaker === 'user' ? 'Voce' : 'Charon'}
                      </span>
                      <span style={{ fontSize: 10, color: '#666', marginLeft: 'auto' }}>{t.time}</span>
                    </div>
                    <div style={{ color: '#ccc', fontSize: 12, lineHeight: 1.6, fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace" }}>{renderMarkdown(t.text)}</div>
                  </div>
                ))
              )}
            </div>
            <div style={s.rightFooter}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: sc }} />
                <span style={{ fontSize: 10, color: sc }}>
                  {isCharonActive ? 'Charon ativo' : 'Charon inativo'}
                </span>
              </div>
              <span style={{ fontSize: 10, color: '#999' }}>·</span>
              <span style={{ fontSize: 10, color: '#999' }}>Voz: {voiceName}</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'config' && (
        <div style={s.configPanel}>
          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Identidade</h3>
            <div style={s.configRow}>
              <div style={s.configField}>
                <label style={s.configLabel}>NOME DO ASSISTENTE</label>
                <input type="text" value={assistantName} onChange={(e) => setAssistantName(e.target.value)} style={s.configInput} />
              </div>
              <div style={s.configField}>
                <label style={s.configLabel}>SEU NOME</label>
                <input type="text" value={userName} onChange={(e) => setUserName(e.target.value)} style={s.configInput} />
              </div>
            </div>
            <button style={{ ...s.saveBtn, marginTop: 12 }} onClick={handleSaveIdentity}>Salvar Identidade</button>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Aparencia</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: 6, background: accentColor, border: '2px solid #333' }} />
              <input type="text" value={accentColor} onChange={(e) => setAccentColor(e.target.value)} style={{ ...s.configInput, width: 120 }} />
            </div>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Voz do Charon</h3>
            <div style={s.voiceGrid}>
              {VOICES.map((voice) => (
                <button
                  key={voice.id}
                  style={{
                    ...s.voiceCard,
                    borderColor: voiceName === voice.id ? accentColor : '#333',
                    background: voiceName === voice.id ? accentColor + '20' : '#1a1a2e',
                  }}
                  onClick={() => setVoiceName(voice.id)}
                >
                  <span style={s.voiceLabel}>{voice.label}</span>
                  <span style={s.voiceType}>{voice.type}</span>
                </button>
              ))}
            </div>
            <button style={{ ...s.saveBtn, marginTop: 12 }} onClick={handleSaveVoice}>Salvar</button>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Chave API</h3>
            <div style={s.configField}>
              <label style={s.configLabel}>Google Gemini</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="AIza..." style={{ ...s.configInput, flex: 1 }} />
                <button style={s.saveBtn} onClick={handleSaveApiKey}>Salvar</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'help' && (
        <div style={s.configPanel}>
          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Como Usar o Charon</h3>
            <div style={{ color: '#ccc', fontSize: 12, lineHeight: 1.8 }}>
              <p><strong style={{ color: '#b478ff' }}>1. Ativar o Charon:</strong></p>
              <p>Clique no botao verde "Charon" no menu lateral. O assistente vai conectar automaticamente.</p>
              
              <p><strong style={{ color: '#b478ff' }}>2. Falar com o Charon:</strong></p>
              <p>Clique no microfone e fale. O Charon vai ouvir e responder por voz.</p>
              
              <p><strong style={{ color: '#b478ff' }}>3. Digitar mensagem:</strong></p>
              <p>Use o campo de texto na parte inferior para digitar comandos.</p>
            </div>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Ferramentas Disponiveis</h3>
            <div style={{ color: '#ccc', fontSize: 12, lineHeight: 1.8 }}>
              <p><strong style={{ color: '#10b981' }}>Web:</strong></p>
              <ul style={{ margin: '4px 0 12px 20px' }}>
                <li><code>web_search</code> - Busca na web (noticias, precos, comparacoes)</li>
                <li><code>youtube_video</code> - Busca videos no YouTube (retorna link clicavel)</li>
              </ul>
              
              <p><strong style={{ color: '#10b981' }}>Sistema:</strong></p>
              <ul style={{ margin: '4px 0 12px 20px' }}>
                <li><code>system_status</code> - Status do sistema (CPU, RAM)</li>
                <li><code>weather_report</code> - Relatorio do tempo</li>
                <li><code>reminder</code> - Criar lembretes</li>
              </ul>
              
              <p><strong style={{ color: '#10b981' }}>Arquivos:</strong></p>
              <ul style={{ margin: '4px 0 12px 20px' }}>
                <li><code>file_controller</code> - Gerenciar arquivos</li>
                <li><code>file_processor</code> - Processar PDFs/imagens</li>
                <li><code>download_image</code> - Baixar imagens</li>
              </ul>
              
              <p><strong style={{ color: '#10b981' }}>Codigo:</strong></p>
              <ul style={{ margin: '4px 0 12px 20px' }}>
                <li><code>code_helper</code> - Escrever/editar codigo</li>
                <li><code>dev_agent</code> - Criar projetos completos</li>
                <li><code>bash</code> - Executar comandos</li>
              </ul>
            </div>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Configurar API Key (Gemini)</h3>
            <div style={{ color: '#ccc', fontSize: 12, lineHeight: 1.8 }}>
              <p><strong style={{ color: '#b478ff' }}>Passo 1:</strong> Acesse <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" style={{ color: '#60a5fa' }}>Google AI Studio</a></p>
              <p><strong style={{ color: '#b478ff' }}>Passo 2:</strong> Faca login com sua conta Google</p>
              <p><strong style={{ color: '#b478ff' }}>Passo 3:</strong> Clique em "Create API Key"</p>
              <p><strong style={{ color: '#b478ff' }}>Passo 4:</strong> Copie a chave gerada (comeca com AIza...)</p>
              <p><strong style={{ color: '#b478ff' }}>Passo 5:</strong> Cole na aba "Configuracoes" em "Chave API"</p>
              
              <div style={{ background: '#1a1a2e', padding: 12, borderRadius: 6, marginTop: 12, border: '1px solid #333' }}>
                <p style={{ margin: 0, color: '#f59e0b' }}><strong>Importante:</strong> A chave e gratuita para uso basico. Limite: 15 requisicoes/minuto.</p>
              </div>
            </div>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Exemplos de Comandos</h3>
            <div style={{ color: '#ccc', fontSize: 12, lineHeight: 1.8 }}>
              <div style={{ background: '#1a1a2e', padding: 8, borderRadius: 4, marginBottom: 8, fontFamily: 'monospace' }}>
                "Pesquise noticias sobre inteligencia artificial"
              </div>
              <div style={{ background: '#1a1a2e', padding: 8, borderRadius: 4, marginBottom: 8, fontFamily: 'monospace' }}>
                "Toque musica relaxante no YouTube"
              </div>
              <div style={{ background: '#1a1a2e', padding: 8, borderRadius: 4, marginBottom: 8, fontFamily: 'monospace' }}>
                "Como esta o tempo em Sao Paulo?"
              </div>
              <div style={{ background: '#1a1a2e', padding: 8, borderRadius: 4, marginBottom: 8, fontFamily: 'monospace' }}>
                "Crie um lembrete para amanha as 9h"
              </div>
              <div style={{ background: '#1a1a2e', padding: 8, borderRadius: 4, marginBottom: 8, fontFamily: 'monospace' }}>
                "Escreva um script em Python para calcular fibonacci"
              </div>
            </div>
          </div>

          <div style={s.configSection}>
            <h3 style={s.sectionTitle}>Models Locais (Ollama)</h3>
            <div style={{ color: '#ccc', fontSize: 12, lineHeight: 1.8 }}>
              <p>Para usar modelos locais (Bonsai, Qwen, etc), voce precisa:</p>
              <ol style={{ margin: '8px 0 12px 20px' }}>
                <li>Instalar o <a href="https://ollama.com" target="_blank" rel="noopener" style={{ color: '#60a5fa' }}>Ollama</a> na sua maquina</li>
                <li>Baixar um modelo: <code>ollama pull qwen2.5-coder:14b</code></li>
                <li>O Ollama precisa estar rodando em <code>localhost:11434</code></li>
              </ol>
              
              <div style={{ background: '#1a1a2e', padding: 12, borderRadius: 6, marginTop: 12, border: '1px solid #333' }}>
                <p style={{ margin: 0, color: '#f59e0b' }}><strong>VPS:</strong> Modelos locais nao funcionam no VPS (4GB RAM). Use Gemini cloud.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const s: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, color: '#fff', background: '#0a0a1a' },
  tabs: { display: 'flex', gap: 0, borderBottom: '1px solid #222', flexShrink: 0 },
  tab: { flex: 1, padding: '10px 16px', border: 'none', background: 'transparent', color: '#999', fontSize: 12, cursor: 'pointer', borderBottom: '2px solid transparent' },
  tabActive: { color: '#fff', borderBottom: '2px solid #b478ff', background: 'rgba(180,120,255,0.05)' },
  chatLayout: { display: 'flex', flex: 1, minHeight: 0 },
  leftPanel: { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 },
  charonHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid #222', flexShrink: 0 },
  charonTitleArea: { display: 'flex', alignItems: 'center', gap: 8 },
  charonTitle: { fontSize: 13, fontWeight: 'bold', color: '#b478ff' },
  novoBtn: { fontSize: 10, padding: '2px 8px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 3, color: '#ccc', cursor: 'pointer' },
  modelArea: { display: 'flex', alignItems: 'center', gap: 8 },
  modelSelect: { fontSize: 11, padding: '4px 8px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 3, color: '#ccc' },
  modelSelectWide: { fontSize: 11, padding: '4px 8px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 3, color: '#ccc', minWidth: 160 },
  greenDot: { width: 6, height: 6, borderRadius: '50%', background: '#0c0' },
  chatArea: { flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: 12, minHeight: 0 },
  emptyState: { color: '#666', textAlign: 'center', marginTop: 40, fontSize: 11 },
  inputSection: { padding: '0 16px 8px 16px', flexShrink: 0 },
  textarea: { width: '100%', height: 60, resize: 'none', padding: '8px', borderRadius: 4, border: '1px solid #333', background: '#1a1a2e', color: '#ccc', fontFamily: 'inherit', fontSize: 11, lineHeight: 1.4, boxSizing: 'border-box', outline: 'none' },
  inputButtons: { display: 'flex', justifyContent: 'flex-end', marginTop: 4 },
  sendBtn: { width: 28, height: 28, borderRadius: 4, border: '1px solid #333', background: '#1a1a2e', color: '#ccc', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  statusLine: { display: 'flex', alignItems: 'center', marginTop: 6 },
  messageItem: { marginBottom: 10, padding: '8px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.02)', overflowWrap: 'break-word', wordBreak: 'break-word' as const },
  messageSpeaker: { fontSize: 10, color: '#b478ff', fontWeight: 600, marginBottom: 4 },
  messageText: { color: '#ccc', whiteSpace: 'pre-wrap' as const, wordBreak: 'break-word' as const, overflowWrap: 'break-word' as const, fontSize: 12, lineHeight: 1.6, fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace" },
  rightPanel: { width: 240, display: 'flex', flexDirection: 'column', flexShrink: 0, borderLeft: '1px solid #222', minHeight: 0 },
  rightHeader: { padding: '8px 12px', borderBottom: '1px solid #222', flexShrink: 0 },
  messagesList: { flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: 10, minHeight: 0 },
  rightFooter: { padding: '6px 12px', borderTop: '1px solid #222', display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 },
  configPanel: { flex: 1, overflowY: 'auto', padding: 20 },
  configSection: { background: '#111', border: '1px solid #222', borderRadius: 8, padding: 16, marginBottom: 16 },
  sectionTitle: { fontSize: 14, fontWeight: '600', margin: '0 0 12px 0', color: '#fff' },
  configRow: { display: 'flex', gap: 16 },
  configField: { flex: 1, marginBottom: 12 },
  configLabel: { display: 'block', fontSize: 10, color: '#999', marginBottom: 4, textTransform: 'uppercase' as const },
  configInput: { width: '100%', padding: '8px 12px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 4, color: '#ccc', fontSize: 12, boxSizing: 'border-box', outline: 'none' },
  voiceGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 },
  voiceCard: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, padding: '10px 8px', border: '2px solid #333', borderRadius: 6, cursor: 'pointer', transition: 'all 0.2s' },
  voiceLabel: { fontSize: 12, fontWeight: '600', color: '#fff' },
  voiceType: { fontSize: 10, color: '#999' },
  saveBtn: { padding: '6px 16px', background: '#b478ff', border: 'none', borderRadius: 4, color: '#fff', fontSize: 11, fontWeight: '600', cursor: 'pointer' },
};

export default CharonPage;
