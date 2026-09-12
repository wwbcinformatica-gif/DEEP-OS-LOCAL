import React, { useState, useRef, useEffect, useCallback } from 'react';
import { renderMarkdown } from './markdownRenderer';
import {
  Conversation, TranscriptEntry,
  getConversations, createConversation, renameConversation, deleteConversation,
  getTranscripts, saveTranscripts, getActivityLog, saveActivityLog,
  conversationToMarkdown, baixarTexto,
  getWorkspaces, setConversationWorkspace, WORKSPACE_PADRAO,
  tenantGet, tenantSet, migrateLegacyData,
} from './chatStorage';

// NOTA: `TranscriptEntry` vem do chatStorage (linha de import acima).
//
// Havia aqui um `interface TranscriptEntry` LOCAL com os mesmos tres campos, o
// que sombreava o tipo importado e gerava o erro TS2440 "Import declaration
// conflicts with local declaration". Com o tipo duplicado, uma mudanca no
// formato gravado nao alcancava este arquivo. Um lugar so.

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
    // Migra dados antigos se existirem (efeito colateral necessario) — mas NAO
    // adota a conversa mais recente.
    //
    // Mesma regra do Jarvis: abrir o Charon e SESSAO NOVA. Antes ele abria na
    // conversa mais recente, o que alem de confundir agravava a corrida do
    // efeito de salvar (que gravava vazio por cima justamente dessa conversa
    // adotada automaticamente). As conversas antigas ficam no historico,
    // alcancaveis pela arvore.
    migrateLegacyData();
    return '';
  });
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [activityLog, setActivityLog] = useState<TranscriptEntry[]>([]);
  // Espelhos em ref do que o efeito de salvar acabou de gravar.
  //
  // Existem para o gravador do `beforeunload`/`pagehide`: aquele listener e
  // registrado UMA vez, entao ler `activeConvId`/`transcripts` do state pegaria
  // valores da primeira renderizacao (closure velha) — a mesma armadilha que ja
  // apareceu nos callbacks de microfone e de conexao.
  const activeConvIdRef = useRef<string>('');
  const transcriptsRef = useRef<TranscriptEntry[]>([]);
  const activityLogRef = useRef<TranscriptEntry[]>([]);
  const [showConvMenu, setShowConvMenu] = useState(false);

  // Load transcripts when active conversation changes
  //
  // ── CORRIDA QUE APAGAVA O HISTORICO DO CHARON ────────────────────────────
  //
  // BUG RELATADO: "quando clica no historico aparece 'Restaurando contexto: 300
  // falas desta conversa' mas nunca restaura o historico no painel central".
  //
  // O efeito de CARREGAR e o de SALVAR dependem os dois de `activeConvId`. Eles
  // rodam no MESMO commit, e nesse momento o estado `transcripts` ainda e o
  // ANTERIOR (a mudanca de estado so vale no render seguinte). Entao:
  //
  //   1. carregar: le os 300 registros da conversa e agenda o estado novo;
  //   2. salvar: grava o `transcripts` ATUAL — que na primeira montagem e `[]` —
  //      POR CIMA da conversa que acabou de ser lida.
  //
  // Ou seja: abrir o Charon (ou trocar de conversa) gravava vazio sobre o
  // historico. O painel ficava sem nada, e o dado ia embora de verdade.
  //
  // O JarvisPage ja tinha essa trava; o CharonPage nao tinha. Agora os dois tem.
  const carregandoConversaRef = useRef(false);

  useEffect(() => {
    if (activeConvId) {
      carregandoConversaRef.current = true;
      setTranscripts(getTranscripts(activeConvId));
      setActivityLog(getActivityLog(activeConvId));
      // Libera no proximo tick, depois que o React aplicou o estado novo.
      const t = setTimeout(() => { carregandoConversaRef.current = false; }, 0);
      return () => clearTimeout(t);
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

  // ── Estado de escolha do contexto ────────────────────────────────────────
  //
  // PEDIDO DO USUARIO: "quando clicar no menu charon eu escolho do lado direito
  // no workspace novo chat ou clico em algum historico registrado das conversas
  // anteriores para que ele ja comece com um novo contexto ou com aquele
  // contexto salvo do historico selecionado, igual aqui no nosso painel DSH".
  //
  // E ainda: "nao faz nenhuma das duas ate eu escolher" e "clicando em nova
  // conversa o charon deve iniciar com saudacao automatica".
  //
  // Ou seja: ao abrir a pagina o Charon NAO liga sozinho (nem cria conversa, nem
  // pede microfone, nem cumprimenta). Ele fica PARADO esperando uma das duas
  // escolhas:
  //   'novo'      -> "+ Novo chat"  -> sessao nova, com saudacao, sem historico
  //   'historico' -> clique numa sessao da arvore -> reenvia o historico e
  //                  reconecta, entao ele retoma aquele contexto
  //   'escolher'  -> ainda nao escolheu: nada de voz
  const [modoInicio, setModoInicio] = useState<'escolher' | 'novo' | 'historico'>('escolher');
  // Espelho em ref: o callback de conexao e criado uma vez e leria estado velho.
  const modoInicioRef = useRef<'escolher' | 'novo' | 'historico'>('escolher');

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
  // ── Arvore do historico (mesma do Jarvis, a pedido do usuario) ───────────
  // "no charon ter isso seria muito bom e tambem poder fazer download da session"
  const [wsExpandidos, setWsExpandidos] = useState<Record<string, boolean>>({});
  const [menuConversa, setMenuConversa] = useState<string | null>(null);
  const [renomeando, setRenomeando] = useState<string | null>(null);
  const [nomeTemp, setNomeTemp] = useState('');
  const [workspaceAtivo, setWorkspaceAtivo] = useState<string>(
    () => tenantGet('charon_workspace') || WORKSPACE_PADRAO
  );
  const [todosWorkspaces, setTodosWorkspaces] = useState<string[]>(() => getWorkspaces());
  const [editandoWorkspace, setEditandoWorkspace] = useState(false);
  const [novoWorkspace, setNovoWorkspace] = useState('');  // Espelho em ref: o callback de conexao precisa do valor atual, e ele e criado
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

    // NAO ha mais auto-start.
    //
    // ANTES: a pagina tentava ligar sozinha (timer de 1s + listener do primeiro
    // gesto), e por isso o Charon abria falando sem o usuario ter pedido nada.
    // O pedido atual e explicito: "nao faz nenhuma das duas ate eu escolher".
    //
    // Agora o Charon so conecta quando o usuario clica em "+ Novo chat" ou numa
    // sessao do historico — e esse clique e justamente o GESTO que o Firefox
    // exige para liberar AudioContext e microfone (nada de getUserMedia sem
    // gesto, senao o Firefox memoriza a negativa como bloqueio do site).
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
    rightListRef.current?.scrollTo({ top: rightListRef.current.scrollHeight, behavior: 'smooth' });
    activityRef.current?.scrollTo({ top: activityRef.current.scrollHeight, behavior: 'smooth' });
    if (activeConvId) {
      // NAO gravar enquanto a conversa esta sendo carregada.
      //
      // Sem esta guarda, este efeito rodava no MESMO commit do carregar — com o
      // `transcripts` anterior (vazio, na primeira montagem) — e gravava vazio
      // por cima do historico da conversa. Era a causa de "nunca restaura o
      // historico no painel central" (o dado era apagado, nao so escondido).
      if (carregandoConversaRef.current) return;
      saveTranscripts(activeConvId, transcripts);
      saveActivityLog(activeConvId, activityLog);
      // Espelhos para o desligamento da pagina (que nao pode ler state).
      activeConvIdRef.current = activeConvId;
      transcriptsRef.current = transcripts;
      activityLogRef.current = activityLog;
    }
  }, [transcripts, activityLog, activeConvId]);

  // Grava o historico ao FECHAR/recarregar a aba.
  //
  // O efeito acima cobre o uso normal, mas se o usuario fechar a aba no meio da
  // conversa (ou der F5) a ultima fala pode nao ter passado por ele. Aqui o
  // registro e regravado uma ultima vez. Importante: salvar e uma escrita
  // SINCRONA no localStorage, entao ela sobrevive ao `beforeunload` — diferente
  // de um fetch, que o navegador cancelaria.
  //
  // Usa REFS, nao state: um listener registrado uma vez leria valores velhos.
  useEffect(() => {
    const gravar = () => {
      const id = activeConvIdRef.current;
      if (!id) return;
      try {
        saveTranscripts(id, transcriptsRef.current);
        saveActivityLog(id, activityLogRef.current);
      } catch { /* fechando a pagina: nao ha o que fazer alem de ignorar */ }
    };
    window.addEventListener('beforeunload', gravar);
    window.addEventListener('pagehide', gravar);
    return () => {
      window.removeEventListener('beforeunload', gravar);
      window.removeEventListener('pagehide', gravar);
    };
  }, []);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && activeTab !== 'chat') setActiveTab('chat');
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [activeTab]);

  const now = () => new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  // ⚠️ NAO JUNTAR OS PEDACOS DE TRANSCRICAO.
  //
  // Eu tentei "melhorar" isto juntando os pedacos do mesmo falante, achando que
  // uma entrada por palavra era defeito. O USUARIO CORRIGIU: o formato
  // EMPILHADO e o que funciona e foi assim que ficou bom depois de varios dias
  // de ajuste. Nao mexer.
  //
  // (Mesma licao das outras: eu inferi um problema a partir do arquivo exportado
  // em vez de perguntar. O pedido dele era o painel CENTRAL no download, nao
  // mudar a transcricao.)
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
    // NAO ha nada a gravar aqui.
    //
    // Conferido: o efeito `useEffect(..., [transcripts, activityLog, activeConvId])`
    // ja grava a cada mudanca de fala, e `disconnectVoice` nao altera nenhum dos
    // tres — entao o historico ja esta no storage quando este botao e apertado.
    // Parar de ouvir NUNCA perdeu historia; o que apagava contexto era a
    // RECONEXAO vindo como sessao nova (ver `reconectarContextoAtual`).
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
    // Vai para o painel DIREITO (transcricao), nao para o log de atividades.
    //
    // PEDIDO DO USUARIO: "estes retornos -> SYSTEM - 19:33:08 Interrompido (voce
    // falou) - ouvindo voce; nao seria necessario entregar no painel central. se
    // quiser pode deixar esse retorno no painel direito".
    //
    // Faz sentido com a divisao que ele definiu: o painel central e para a
    // ENTREGA ORGANIZADA (ferramentas, buscas, resultados). Recado de status
    // como este e ruido ali, e no painel direito ele ate ajuda a entender POR QUE
    // o Charon parou de falar no meio de uma frase.
    //
    // Speaker 'sistema' tem tratamento proprio na renderizacao (cinza, discreto).
    setTranscripts(prev => [...prev, { speaker: 'sistema', text: `Interrompido (${motivo}) — ouvindo voce`, time: now() }]);
  };

  const toggleCharon = () => {
    if (isCharonActive) {
      // Parar de ouvir. NAO mexe no historico gravado — ver `disconnectVoice`.
      disconnectVoice();
      return;
    }
    // Apertar o Charon tambem e uma ESCOLHA de contexto. Mas, se ja existe uma
    // conversa em andamento, ele NAO pode voltar como sessao nova: isso jogaria
    // fora o contexto do Gemini (que vive no servidor DELE, por sessao) e ele
    // "esqueceria" tudo no meio da conversa — o usuario via isso como "o Charon
    // nao lembra de nada".
    if (modoInicioRef.current === 'escolher') {
      newConversation();
      return;
    }
    reconectarContextoAtual();
  };

  /**
   * Reabre a sessao PRESERVANDO o contexto da conversa atual.
   *
   * O botao "⚡ Charon ouvindo" (o cabecalho do painel direito) para e religa o
   * Charon. Religar como sessao nova faria ele esquecer a conversa — entao aqui
   * decidimos:
   *   - a conversa tem falas  -> manda o historico como contexto e ele retoma;
   *   - a conversa esta vazia -> sessao nova mesmo (ele cumprimenta).
   */
  const reconectarContextoAtual = () => {
    const convId = activeConvId;
    const salvo = convId ? getTranscripts(convId) : [];
    if (salvo.length > 0) {
      setTranscripts(salvo);
      setActivityLog(getActivityLog(convId));
      setRestaurarHistorico(true);
      restaurarHistoricoRef.current = true;
      modoInicioRef.current = 'historico';
      setModoInicio('historico');
      // `connectVoice` le `restaurarHistoricoRef` e envia o historico ao abrir.
      startedRef.current ? entrarNaConversa('Retomando o contexto desta conversa...')
                         : connectVoiceRef.current();
      return;
    }
    // Sem falas ainda: sessao nova na conversa que ja esta aberta.
    setRestaurarHistorico(false);
    restaurarHistoricoRef.current = false;
    modoInicioRef.current = 'novo';
    setModoInicio('novo');
    connectVoiceRef.current();
  };

  const sendText = (text: string) => {
    if (!text.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    // Auto-create conversation on first message
    if (!activeConvId) {
      const conv = createConversation(text.trim(), workspaceAtivo, assistantNameRef.current || 'Charon');
      setConversations(getConversations());
      setTodosWorkspaces(getWorkspaces());
      setActiveConvId(conv.id);
      modoInicioRef.current = 'novo';
      setModoInicio('novo');
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

  /**
   * Entra numa conversa: troca o contexto, limpa o que era da anterior e
   * RECONECTA (o estado da conversa vive no servidor do Gemini por sessao, entao
   * nao ha como "rebobinar": a unica troca confiavel de contexto e uma sessao
   * nova com o historico certo).
   */
  const entrarNaConversa = (motivo: string) => {
    setShowConvMenu(false);
    setTranscripts([]);
    setActivityLog([]);
    setError('');
    if (startedRef.current) {
      addActivity(motivo, 'system');
      disconnectVoice();
      // Pequeno atraso para o servidor fechar a sessao antiga antes de abrir a
      // nova (o backend tambem derruba sessoes antigas, mas isto evita corrida).
      setTimeout(() => connectVoiceRef.current(), 600);
    } else {
      connectVoiceRef.current();
    }
  };

  const switchConversation = (convId: string) => {
    const jaAtiva = convId === activeConvId;
    setActiveConvId(convId);
    // O usuario escolheu uma conversa do historico: o Charon deve lembrar dela.
    setRestaurarHistorico(true);
    restaurarHistoricoRef.current = true;
    modoInicioRef.current = 'historico';
    setModoInicio('historico');
    // Carrega o painel com o que estava salvo (o historico enviado ao Gemini e
    // lido do storage, entao precisa estar consistente na hora de conectar).
    setTranscripts(getTranscripts(convId));
    setActivityLog(getActivityLog(convId));
    entrarNaConversa(
      jaAtiva
        ? 'Recarregando o contexto desta conversa...'
        : 'Trocando de conversa — recarregando o contexto...',
    );
  };

  const newConversation = () => {
    // Nasce no workspace ativo (a raiz escolhida na arvore) e com o NOME DO
    // ASSISTENTE escolhido em Configuracoes > Identidade (pedido do usuario).
    // Se o nome ja existir, o chatStorage numera ("Charon 2").
    const conv = createConversation(undefined, workspaceAtivo, assistantNameRef.current || 'Charon');
    setConversations(getConversations());
    setTodosWorkspaces(getWorkspaces());
    setActiveConvId(conv.id);
    // Conversa nova = contexto novo: nada de restaurar nada, o Charon cumprimenta.
    setRestaurarHistorico(false);
    restaurarHistoricoRef.current = false;
    modoInicioRef.current = 'novo';
    setModoInicio('novo');
    entrarNaConversa('Novo chat — sessao nova, sem contexto anterior');
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
      // Apagou a conversa em uso: volta para a ESCOLHA de contexto, sem ligar
      // o Charon sozinho (mesma regra de quando a pagina abre).
      setActiveConvId('');
      setTranscripts([]);
      setActivityLog([]);
      modoInicioRef.current = 'escolher';
      setModoInicio('escolher');
      if (startedRef.current) {
        disconnectVoice();
        addActivity('Conversa excluida — escolha um contexto para continuar', 'system');
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
            </div>

            {/* ── EXPLORER: workspaces → sessoes do Charon ──────────────────
                Mesma arvore do Jarvis, a pedido do usuario. Aqui a "conversa"
                e a SESSAO de voz: a setinha na raiz abre as sessoes, e o "..."
                de cada uma permite renomear, excluir ou BAIXAR (exporta a
                transcricao em .md). */}
            <div style={{ borderBottom: '1px solid #1e1e1e', flexShrink: 0, maxHeight: '32vh', overflowY: 'auto' }}>
              {/* ── AS DUAS ESCOLHAS DE CONTEXTO ────────────────────────────
                  Pedido do usuario: "eu escolho do lado direito no workspace
                  novo chat ou clico em algum historico registrado das conversas
                  anteriores para que ele ja comece com um novo contexto ou com
                  aquele contexto salvo".

                  Antes o "+" era um caractere solto no canto da barra e passava
                  despercebido; agora a escolha e explicita e fica no topo da
                  arvore, junto dos workspaces (igual ao painel do DSH). */}
              <div
                onClick={newConversation}
                title="Comecar uma sessao nova, sem contexto anterior"
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  margin: '6px 8px', padding: '5px 8px', borderRadius: 4,
                  cursor: 'pointer',
                  background: modoInicio === 'novo' ? 'rgba(180,120,255,0.16)' : 'rgba(180,120,255,0.07)',
                  border: `1px solid ${modoInicio === 'novo' ? 'rgba(180,120,255,0.55)' : 'rgba(180,120,255,0.25)'}`,
                  color: '#c9a6ff', fontSize: 10, fontWeight: 600,
                }}>
                <span style={{ fontSize: 12, lineHeight: 1 }}>+</span>
                <span style={{ flex: 1 }}>Novo chat</span>
                <span style={{ fontSize: 8, color: '#7a6a95', fontWeight: 400 }}>sem contexto</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 8px 2px', fontSize: 8, color: '#5a5a5a', letterSpacing: 1, textTransform: 'uppercase' as const }}>
                <span>workspaces</span>
                <span style={{ marginLeft: 'auto', opacity: 0.7 }}>{conversations.length}</span>
                <button onClick={() => setEditandoWorkspace(v => !v)} title="Nova raiz (workspace)"
                  style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 11, padding: '0 2px', lineHeight: 1 }}>+</button>
              </div>

              {editandoWorkspace && (
                <div style={{ display: 'flex', gap: 4, padding: '2px 8px 4px' }}>
                  <input value={novoWorkspace} onChange={e => setNovoWorkspace(e.target.value)} autoFocus
                    onKeyDown={e => {
                      if (e.key === 'Enter' && novoWorkspace.trim()) {
                        const w = novoWorkspace.trim();
                        setWorkspaceAtivo(w); tenantSet('charon_workspace', w);
                        setTodosWorkspaces(prev => prev.includes(w) ? prev : [...prev, w].sort((a, b) => a.localeCompare(b, 'pt-BR')));
                        setWsExpandidos(p => ({ ...p, [w]: true }));
                        setNovoWorkspace(''); setEditandoWorkspace(false);
                      }
                      if (e.key === 'Escape') { setNovoWorkspace(''); setEditandoWorkspace(false); }
                    }}
                    placeholder="nome da raiz..."
                    style={{ flex: 1, background: '#0d0d0d', border: '1px solid #2a2a2a', borderRadius: 3, color: '#ccc', fontSize: 10, padding: '2px 5px', outline: 'none' }} />
                </div>
              )}

              {todosWorkspaces.map(ws => {
                const doWs = conversations.filter(c => (c.workspace || WORKSPACE_PADRAO) === ws);
                if (doWs.length === 0 && ws !== workspaceAtivo) return null;
                const aberto = wsExpandidos[ws] !== false;
                return (
                  <div key={ws}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '3px 8px', cursor: 'pointer' }}
                      onClick={() => setWsExpandidos(p => ({ ...p, [ws]: !aberto }))} title={`Workspace: ${ws}`}>
                      <span style={{ fontSize: 8, color: '#555', width: 8 }}>{aberto ? '\u25BE' : '\u25B8'}</span>
                      <span style={{ fontSize: 10, color: ws === workspaceAtivo ? '#b478ff' : '#999', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{ws}</span>
                      <span style={{ fontSize: 8, color: '#444' }}>{doWs.length}</span>
                    </div>

                    {aberto && doWs.map(conv => (
                      <div key={conv.id}>
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: 3, padding: '2px 8px 2px 20px',
                          background: conv.id === activeConvId ? 'rgba(180,120,255,0.12)' : 'transparent',
                          borderLeft: conv.id === activeConvId ? '2px solid #b478ff' : '2px solid transparent',
                        }}>
                          {renomeando === conv.id ? (
                            <input value={nomeTemp} onChange={e => setNomeTemp(e.target.value)} autoFocus
                              onClick={e => e.stopPropagation()}
                              onKeyDown={e => {
                                if (e.key === 'Enter') {
                                  if (nomeTemp.trim()) { renameConversation(conv.id, nomeTemp.trim()); setConversations(getConversations()); }
                                  setRenomeando(null);
                                }
                                if (e.key === 'Escape') setRenomeando(null);
                              }}
                              onBlur={() => setRenomeando(null)}
                              style={{ flex: 1, background: '#0d0d0d', border: '1px solid #2a2a2a', borderRadius: 3, color: '#ccc', fontSize: 10, padding: '1px 4px', outline: 'none' }} />
                          ) : (
                            <>
                              <span onClick={() => switchConversation(conv.id)} title={conv.name}
                                style={{ flex: 1, fontSize: 10, color: conv.id === activeConvId ? '#b478ff' : '#bbb', cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                                {conv.name}
                              </span>
                              <span style={{ fontSize: 8, color: '#3a3a3a', flexShrink: 0 }}>{formatConvTime(conv.updatedAt)}</span>
                              <button onClick={(e) => { e.stopPropagation(); setMenuConversa(menuConversa === conv.id ? null : conv.id); }}
                                title="Opcoes"
                                style={{ background: 'none', border: 'none', color: menuConversa === conv.id ? '#b478ff' : '#555', cursor: 'pointer', fontSize: 12, padding: '0 2px', lineHeight: 1, flexShrink: 0 }}>{'\u22EF'}</button>
                            </>
                          )}
                        </div>

                        {menuConversa === conv.id && renomeando !== conv.id && (
                          <div style={{ display: 'flex', gap: 6, padding: '3px 8px 3px 30px', background: 'rgba(255,255,255,0.02)' }}>
                            <button onClick={() => { setRenomeando(conv.id); setNomeTemp(conv.name); setMenuConversa(null); }}
                              style={{ background: 'none', border: 'none', color: '#c9a6ff', cursor: 'pointer', fontSize: 9, padding: 0 }}>{'\u270E'} Renomear</button>
                            <button onClick={(e) => { setMenuConversa(null); handleDeleteConversation(conv.id, e); }}
                              style={{ background: 'none', border: 'none', color: '#f77', cursor: 'pointer', fontSize: 9, padding: 0 }}>{'\u2715'} Excluir</button>
                            {/* Download da SESSAO — pedido do usuario. Exporta a
                                transcricao de voz inteira em Markdown. */}
                            <button onClick={() => {
                              const md = conversationToMarkdown(conv.id, conv.name);
                              if (!md) { alert('Esta sessao ainda nao tem transcricao para baixar.'); return; }
                              baixarTexto(conv.name, md);
                              addActivity('Sessao exportada', `${md.length} caracteres em Markdown`);
                              setMenuConversa(null);
                            }} style={{ background: 'none', border: 'none', color: '#7c9', cursor: 'pointer', fontSize: 9, padding: 0 }}>{'\u2B07'} Baixar sessao</button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })}

              {conversations.length === 0 && !editandoWorkspace && (
                <div style={{ padding: '2px 8px 6px', fontSize: 9, color: '#4a4a4a', lineHeight: 1.5 }}>
                  Nenhuma sessao ainda. O historico aparece aqui conforme voce fala com o Charon.
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
                  {modoInicio === 'escolher' ? (
                    // Tela de ESCOLHA: o Charon nao liga sozinho. Pedido do
                    // usuario: "nao faz nenhuma das duas ate eu escolher".
                    <div style={{ maxWidth: 460, textAlign: 'left' }}>
                      <p style={{ margin: '0 0 4px', fontSize: 14, fontWeight: 600, color: '#c9a6ff' }}>
                        Como voce quer comecar?
                      </p>
                      <p style={{ margin: '0 0 14px', fontSize: 12, opacity: 0.7, lineHeight: 1.5 }}>
                        O Charon esta parado esperando voce escolher. Ele so liga
                        depois da escolha — assim nao abre falando sozinho.
                      </p>
                      <button onClick={newConversation}
                        style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 8, padding: '10px 14px', background: 'rgba(180,120,255,0.14)', color: '#e0d0ff', border: '1px solid rgba(180,120,255,0.45)', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontWeight: 600 }}>
                        + Novo chat
                        <div style={{ fontSize: 11, fontWeight: 400, opacity: 0.75, marginTop: 3 }}>
                          Sessao nova, sem contexto anterior. Ele cumprimenta e comeca do zero.
                        </div>
                      </button>
                      <button onClick={() => { setActiveTab('chat'); setWsExpandidos(p => ({ ...p, [workspaceAtivo]: true })); }}
                        style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 14px', background: 'rgba(255,255,255,0.04)', color: '#ccc', border: '1px solid #333', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontWeight: 600 }}>
                        &#8635; Continuar uma conversa
                        <div style={{ fontSize: 11, fontWeight: 400, opacity: 0.75, marginTop: 3 }}>
                          Clique numa sessao da arvore ali em cima ({conversations.length} salvas).
                          O Charon recebe aquele historico e retoma de onde pararam.
                        </div>
                      </button>
                    </div>
                  ) : micError ? (
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
                    background: t.speaker === 'user' ? 'rgba(180,120,255,0.08)'
                      : t.speaker === 'sistema' ? 'rgba(255,255,255,0.03)'
                      : 'rgba(0,200,0,0.08)',
                    borderLeft: `3px solid ${t.speaker === 'user' ? '#b478ff'
                      : t.speaker === 'sistema' ? '#444'
                      : '#0c0'}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                      {/* Nota de sistema (ex.: "Interrompido — ouvindo voce").
                          Vem para o painel direito, discreta, para o usuario
                          entender por que o Charon parou de falar — sem poluir o
                          painel central, que e para a entrega organizada. */}
                      <span style={{ fontSize: 12 }}>{t.speaker === 'user' ? '👤' : t.speaker === 'sistema' ? 'ℹ️' : '⚡'}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: t.speaker === 'user' ? '#b478ff' : t.speaker === 'sistema' ? '#777' : '#0c0' }}>
                        {t.speaker === 'user' ? 'Voce' : t.speaker === 'sistema' ? 'Sistema' : 'Charon'}
                      </span>
                      <span style={{ fontSize: 10, color: '#666', marginLeft: 'auto' }}>{t.time}</span>
                    </div>
                    <div style={{ color: t.speaker === 'sistema' ? '#888' : '#ccc', fontSize: t.speaker === 'sistema' ? 11 : 12, fontStyle: t.speaker === 'sistema' ? 'italic' : 'normal', lineHeight: 1.6, fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace" }}>{renderMarkdown(t.text)}</div>
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
