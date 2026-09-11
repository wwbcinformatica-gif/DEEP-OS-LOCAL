import React, { useRef, useEffect, useState, useCallback } from 'react';
import type { Msg, TLog, FileTab, Provider, Mood } from '../lib/constants';
import { API_BASE, MODELS, PROVIDERS, SETTINGS_KEY } from '../lib/constants';
import MarkdownBlock from './MarkdownBlock';
import PlanMessage from './PlanMessage';
import PermissionDialog from './PermissionDialog';
import ActionCard, { parseActionCard } from './ActionCard';
import StatusIndicator from './StatusIndicator';
import TaskChecklist from './TaskChecklist';
import CharonToolMessage from './CharonToolMessage';

interface ChatPanelProps {
  msgs: Msg[];
  input: string;
  setInput: (v: string) => void;
  loading: boolean;
  stream: string;
  thinking: string;
  thinkOn: boolean;
  thinkOpen: boolean;
  setThinkOpen: (v: boolean) => void;
  toolLogs: TLog[];
  prov: Provider;
  model: string;
  setProv: (v: Provider) => void;
  setModel: (v: string) => void;
  oModels: { value: string; label: string }[];
  orModels: { value: string; label: string }[];
  llamacppModels: { value: string; label: string; available: boolean; has_vision?: boolean }[];
  curTab: FileTab | undefined;
  chatW: number;
  send: (text?: string, images?: string[]) => void;
  newChat: () => void;
  stopGen: () => void;
  analyzeFile: (tab: FileTab) => void;
  voicePreset:
    | 'google-female'
    | 'francisca'
    | 'maria'
    | 'google-male'
    | 'antonio'
    | 'daniel'
    | 'jarvis-cinematic'
    | 'edge-francisca'
    | 'edge-thalita'
    | 'eleven-natasha'
    | 'eleven-serafina'
    | 'eleven-ivy'
    | 'eleven-ingmar'
    | 'dani-brandi';
  jarvisRate: number;
  voicePitch: number;
  voiceMode: boolean;
  setVoiceMode: (v: boolean) => void;
  charonActive?: boolean;
  onConfirmPlan: (taskId: string) => void;
  onRejectPlan: (taskId: string) => void;
  pendingToolConfirm: {
    confirmId: string;
    tool: string;
    label: string;
    risk_level?: string;
    params: Record<string, any>;
    taskId: string;
  } | null;
  onApproveTool: () => void;
  onRejectTool: () => void;
  checklistSteps: { label: string; status: string; error?: string }[];
  assistantName?: string;
}

export default function ChatPanel({
  msgs,
  input,
  setInput,
  loading,
  stream,
  thinking,
  thinkOn,
  thinkOpen,
  setThinkOpen,
  toolLogs,
  prov,
  model,
  setProv,
  setModel,
  oModels,
  orModels,
  llamacppModels,
  curTab,
  chatW,
  send,
  newChat,
  stopGen,
  analyzeFile,
  voicePreset,
  jarvisRate,
  voicePitch,
  voiceMode,
  setVoiceMode,
  charonActive,
  onConfirmPlan,
  onRejectPlan,
  pendingToolConfirm,
  onApproveTool,
  onRejectTool,
  checklistSteps,
  assistantName,
}: ChatPanelProps) {
  const chatEnd = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [msgs, stream]);

  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isJarvisVoice, setIsJarvisVoice] = useState(false);
  const [isDeepMode, setIsDeepMode] = useState(false);

  const [wakeWordActive, setWakeWordActive] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [autoSend, setAutoSend] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
      return saved.autoSend ?? true;
    } catch { return true; }
  });
  const [autoSendCountdown, setAutoSendCountdown] = useState(0);

  const autoSendRef = useRef(autoSend);
  useEffect(() => { autoSendRef.current = autoSend; }, [autoSend]);

  const inputValueRef = useRef('');
  const isSpeakingRef = useRef(false);
  const isDeepModeRef = useRef(false);
  const userWantsListeningRef = useRef(false);
  const deepAtivoRef = useRef(false);
  const deepSessionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deepSilenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deepInputRef = useRef('');
  const lastSpokenTimeRef = useRef(0);
  const handleSendRef = useRef<(text?: string) => void>(() => {});
  const isRestartingRef = useRef(false);
  const isStartingRef = useRef(false);
  const autoSendTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);



  // ─── @ Mention & / Command popover ────────────────────────────────
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [commandQuery, setCommandQuery] = useState<string | null>(null);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [plusMenuFilter, setPlusMenuFilter] = useState('');

  const AGENTS = [
    { id: 'mimo', label: '@mimo', desc: 'MiMo-V2.5 rapido e gratis', icon: 'M' },
    { id: 'coder', label: '@coder', desc: 'Programador especialista', icon: '>' },
    { id: 'writer', label: '@writer', desc: 'Escritor/documentador', icon: '#' },
    { id: 'helper', label: '@helper', desc: 'Assistente geral', icon: '?' },
    { id: 'planner', label: '@planner', desc: 'Planejador estrategico', icon: '~' },
    { id: 'reviewer', label: '@reviewer', desc: 'Revisor de codigo', icon: '!' },
    { id: 'debugger', label: '@debugger', desc: 'Especialista em debugging', icon: '&' },
    { id: 'architect', label: '@architect', desc: 'Arquiteto de software', icon: '^' },
    { id: 'analyst', label: '@analyst', desc: 'Analista de dados', icon: '%' },
  ];

  const SKILLS = [
    { id: 'web_search', label: '@web_search', desc: 'Pesquisar na internet', icon: '*' },
    { id: 'file_picker', label: '@file_picker', desc: 'Navegar arquivos', icon: '/' },
    { id: 'terminal_run', label: '@terminal_run', desc: 'Executar no terminal', icon: '$' },
    { id: 'code_review', label: '@code_review', desc: 'Revisar codigo', icon: '>' },
    { id: 'test_runner', label: '@test_runner', desc: 'Executar testes', icon: 'T' },
    { id: 'doc_generator', label: '@doc_generator', desc: 'Gerar documentacao', icon: 'D' },
    { id: 'refactor', label: '@refactor', desc: 'Refatorar codigo', icon: 'R' },
    { id: 'explore', label: '@explore', desc: 'Explorar projeto', icon: 'E' },
    { id: 'plan', label: '@plan', desc: 'Criar plano de execucao', icon: 'P' },
    // ── Browser-Harness Skills ──────────────────────────────────────────────
    { id: 'browser_open', label: '@browser_open', desc: 'Abrir site no navegador', icon: 'B' },
    { id: 'browser_search', label: '@browser_search', desc: 'Pesquisar no navegador', icon: 'S' },
    { id: 'browser_click', label: '@browser_click', desc: 'Clicar em elemento da pagina', icon: 'C' },
    { id: 'browser_type', label: '@browser_type', desc: 'Digitar no navegador', icon: 'T' },
    { id: 'browser_scrape', label: '@browser_scrape', desc: 'Extrair dados de pagina', icon: 'X' },
    { id: 'browser_form', label: '@browser_form', desc: 'Preencher formulario', icon: 'F' },
    { id: 'browser_screenshot', label: '@browser_screenshot', desc: 'Capturar tela', icon: 'I' },
    { id: 'browser_pdf', label: '@browser_pdf', desc: 'Salvar pagina como PDF', icon: 'P' },
    { id: 'browser_record', label: '@browser_record', desc: 'Gravar sessao do navegador', icon: 'G' },
    { id: 'browser_cookies', label: '@browser_cookies', desc: 'Gerenciar cookies', icon: 'K' },
    { id: 'browser_download', label: '@browser_download', desc: 'Gerenciar downloads', icon: 'W' },
  ];

  const SLASH_COMMANDS = [
    { cmd: '/goal', desc: 'Definir objetivo de longo prazo', icon: '?' },
    { cmd: '/run', desc: 'Executar comando/scriptId', icon: '>' },
    { cmd: '/clear', desc: 'Limpar contexto atual', icon: 'X' },
    { cmd: '/help', desc: 'Ver comandos disponiveis', icon: '?' },
    { cmd: '/status', desc: 'Status do sistema', icon: 'i' },
    { cmd: '/stop', desc: 'Parar execucao', icon: '!' },
    { cmd: '/Charon', desc: 'Ativar/falar com o Charon (voz) - 20 ferramentas', icon: 'V' },
  ];

  const PLUS_ACTIONS = [
    { id: 'goal', label: '/goal', desc: 'Definir objetivo', icon: '?' },
    { id: 'run', label: '/run', desc: 'Executar comando', icon: '>' },
    { id: 'clear', label: '/clear', desc: 'Limpar contexto', icon: 'X' },
    { id: 'web_search', label: '@web_search', desc: 'Pesquisar web', icon: '*' },
    { id: 'terminal', label: '@terminal_run', desc: 'Abrir terminal', icon: '$' },
    { id: 'browser_open', label: '@browser_open', desc: 'Abrir site', icon: 'B' },
    { id: 'browser_search', label: '@browser_search', desc: 'Pesquisar no navegador', icon: 'S' },
    { id: 'browser_screenshot', label: '@browser_screenshot', desc: 'Capturar tela', icon: 'I' },
    { id: 'help', label: '/help', desc: 'Ajuda', icon: '?' },
  ];

  // Parse input for @ and / triggers
  useEffect(() => {
    const val = input;
    const cursorPos = val.length;
    const textBeforeCursor = val.slice(0, cursorPos);

    // Check for @ mention
    const atMatch = textBeforeCursor.match(/@(\w*)$/);
    if (atMatch) {
      setMentionQuery(atMatch[1].toLowerCase());
      setCommandQuery(null);
      setShowPlusMenu(false);
      return;
    }

    // Check for / command (only at start of input)
    const slashMatch = textBeforeCursor.match(/^\/(\w*)$/);
    if (slashMatch) {
      setCommandQuery(slashMatch[1].toLowerCase());
      setMentionQuery(null);
      setShowPlusMenu(false);
      return;
    }

    setMentionQuery(null);
    setCommandQuery(null);
  }, [input]);

  const insertMention = (label: string) => {
    const atIdx = input.lastIndexOf('@');
    if (atIdx >= 0) {
      setInput(input.slice(0, atIdx) + label + ' ');
    }
    setMentionQuery(null);
  };

  const insertCommand = (cmd: string) => {
    setInput(cmd + ' ');
    setCommandQuery(null);
  };

  const filteredMentions = mentionQuery !== null ? [
    ...AGENTS.filter(a => a.id.includes(mentionQuery) || a.label.toLowerCase().includes(mentionQuery)),
    ...SKILLS.filter(s => s.id.includes(mentionQuery) || s.label.toLowerCase().includes(mentionQuery)),
  ] : [];

  const filteredCommands = commandQuery !== null
    ? SLASH_COMMANDS.filter(c => c.cmd.includes('/' + commandQuery))
    : SLASH_COMMANDS;

  const filteredPlusActions = plusMenuFilter
    ? PLUS_ACTIONS.filter(a => a.label.toLowerCase().includes(plusMenuFilter) || a.desc.toLowerCase().includes(plusMenuFilter))
    : PLUS_ACTIONS;

  // Close popovers on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-popover]')) {
        setShowPlusMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);
  // ── Wake word com fuzzy matching ──
  const WAKE_WORDS = ['deep', 'diep', 'dip', 'deap', 'deepa', 'dipi', 'depe', 'drip'];

  const normalizePhonetic = (word: string): string => {
    let w = word.toLowerCase().trim()
      .replace(/[áàâãä]/g, 'a').replace(/[éèêë]/g, 'e')
      .replace(/[íìîï]/g, 'i').replace(/[óòôõö]/g, 'o')
      .replace(/[úùûü]/g, 'u').replace(/[ç]/g, 'c')
      .replace(/[^a-z0-9]/g, '');
    const phoneticMap: Record<string, string> = {
      'parei': 'pare', 'pár': 'pare', 'pári': 'pare', 'párê': 'pare', 'pae': 'pare',
      'pára': 'para', 'stope': 'stop', 'estope': 'stop', 'estop': 'stop',
      'cansela': 'cancela', 'kansela': 'cancela',
      'dipi': 'deep', 'depe': 'deep', 'deap': 'deep', 'deepa': 'deep', 'diep': 'deep',
      'jeep': 'deep', 'drip': 'deep',
      'depp': 'deep', 'dep': 'deep', 'deeo': 'deep', 'deef': 'deep',
    };
    return phoneticMap[w] || w;
  };

  const levenshtein = (a: string, b: string): number => {
    const m = a.length, n = b.length;
    if (m === 0) return n; if (n === 0) return m;
    const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
    for (let i = 0; i <= m; i++) dp[i][0] = i;
    for (let j = 0; j <= n; j++) dp[0][j] = j;
    for (let i = 1; i <= m; i++)
      for (let j = 1; j <= n; j++)
        dp[i][j] = Math.min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+(a[i-1]===b[j-1]?0:1));
    return dp[m][n];
  };

  const fuzzyMatch = (word: string, candidates: string[], cutoff = 0.6): boolean => {
    const w = normalizePhonetic(word);
    if (!w) return false;
    for (const c of candidates) {
      if (w === c) return true;
      const dist = levenshtein(w, c);
      const maxLen = Math.max(w.length, c.length);
      if (maxLen === 0) continue;
      if (1 - dist / maxLen >= cutoff) return true;
    }
    return false;
  };

  const detectWakeWord = (transcript: string): boolean => {
    for (const word of transcript.toLowerCase().split(/\s+/))
      if (fuzzyMatch(word, WAKE_WORDS, 0.65)) return true;
    return false;
  };

  const STOP_WORDS = ['stop', 'pare', 'para', 'parar', 'cancela', 'cancelar', 'parou', 'chega'];

  const detectStopWord = (transcript: string): boolean => {
    for (const word of transcript.toLowerCase().split(/\s+/))
      if (fuzzyMatch(word, STOP_WORDS, 0.75)) return true;
    return false;
  };

  const safeRestart = () => {
    if (isRestartingRef.current || isStartingRef.current) return;
    if (!userWantsListeningRef.current) return;
    if (isSpeakingRef.current) return;
    isRestartingRef.current = true;
    try { recognitionRef.current?.stop(); } catch {}
    setTimeout(() => {
      isRestartingRef.current = false;
      if (userWantsListeningRef.current && !isSpeakingRef.current) {
        try {
          isStartingRef.current = true;
          recognitionRef.current?.start();
          setIsListening(true);
        } catch (e) {
          isStartingRef.current = false;
        }
      }
    }, 250);
  };

  const deepDesativar = () => {
    deepAtivoRef.current = false;
    setWakeWordActive(false);
    deepInputRef.current = '';
    setInput('');
    inputValueRef.current = '';
    if (deepSilenceTimerRef.current) { clearTimeout(deepSilenceTimerRef.current); deepSilenceTimerRef.current = null; }
    if (deepSessionTimerRef.current) { clearTimeout(deepSessionTimerRef.current); deepSessionTimerRef.current = null; }
    safeRestart();
  };

  const deepEnviarComando = () => {
    if (deepSilenceTimerRef.current) { clearTimeout(deepSilenceTimerRef.current); deepSilenceTimerRef.current = null; }
    if (deepSessionTimerRef.current) { clearTimeout(deepSessionTimerRef.current); deepSessionTimerRef.current = null; }
    const text = deepInputRef.current.trim();
    if (text) handleSendRef.current(text);
    deepAtivoRef.current = false;
    setWakeWordActive(false);
    deepInputRef.current = '';
    // Para o recognition para nao escutar a propria resposta do TTS
    try { recognitionRef.current?.stop(); } catch {}
    setIsListening(false);
    // Reinicia a escuta apos o TTS terminar (finishSpeaking chama safeRestart)
    // ou apos 8s como safety net se o TTS nao estiver ativo
    setTimeout(() => {
      if (isDeepModeRef.current && userWantsListeningRef.current && !isSpeakingRef.current) {
        safeRestart();
      }
    }, 8000);
  };

  const deepAtivar = (comandoInicial?: string) => {
    deepAtivoRef.current = true;
    setWakeWordActive(true);
    deepInputRef.current = comandoInicial || '';
    if (deepSilenceTimerRef.current) { clearTimeout(deepSilenceTimerRef.current); deepSilenceTimerRef.current = null; }
    if (deepSessionTimerRef.current) clearTimeout(deepSessionTimerRef.current);
    deepSessionTimerRef.current = setTimeout(() => deepDesativar(), 30000);
    if (comandoInicial) {
      setInput(comandoInicial);
      inputValueRef.current = comandoInicial;
      deepSilenceTimerRef.current = setTimeout(() => deepEnviarComando(), 5000);
    }
  };

  const handleDeepResult = (event: SpeechRecognitionEvent) => {
    let finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; i++)
      if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
    const transcript = finalTranscript.trim();
    if (!transcript) return;

    const lower = transcript.toLowerCase();

    // Comando: parar leitura
    if (lower.includes('parar leitura') || lower.includes('para leitura') || lower.includes('cala boca') || lower.includes('silencio')) {
      stopJarvis();
      if (isDeepModeRef.current) deepDesativar();
      return;
    }

    // Comando: repetir leitura
    const REPEAT_WORDS = ['ler novamente', 'repetir', 'repete', 'leia de novo', 'repita', 'fala de novo'];
    if (REPEAT_WORDS.some(w => lower.includes(w)) && lower.length < 60) {
      const lastBotMsg = [...msgs].reverse().find(m => m.from === 'bot');
      if (lastBotMsg?.text) { lastSpokenMsgRef.current = ''; speakText(lastBotMsg.text); }
      if (isDeepModeRef.current) deepDesativar();
      return;
    }

    // Modo Deep
    if (isDeepModeRef.current) {
      if (!deepAtivoRef.current) {
        if (detectWakeWord(transcript)) {
          if (detectStopWord(transcript)) { deepDesativar(); return; }
          const words = transcript.toLowerCase().split(/\s+/);
          const wakeIdx = words.findIndex(w => fuzzyMatch(w, WAKE_WORDS, 0.6));
          const afterDeep = wakeIdx >= 0 ? words.slice(wakeIdx + 1).join(' ') : '';
          const cleanCmd = afterDeep ? transcript.replace(/^.*?(deep|diep|dip|deap|deepa|dipi|depe|drip)\s*/i, '').trim() : '';
          deepAtivar(cleanCmd || undefined);
        }
        return;
      }
      // Estado ativo: capturando comando
      const words = transcript.toLowerCase().split(/\s+/).filter(w => w.length > 0);
      const lastWord = words[words.length - 1] || '';
      if (detectStopWord(transcript) && (words.length <= 3 || fuzzyMatch(lastWord, STOP_WORDS, 0.75))) {
        deepDesativar(); return;
      }
      const prev = deepInputRef.current;
      const newPart = prev ? prev + ' ' + transcript : transcript;
      deepInputRef.current = newPart;
      setInput(newPart);
      inputValueRef.current = newPart;
      if (deepSilenceTimerRef.current) clearTimeout(deepSilenceTimerRef.current);
      deepSilenceTimerRef.current = setTimeout(() => deepEnviarComando(), 5000);
      if (deepSessionTimerRef.current) clearTimeout(deepSessionTimerRef.current);
      deepSessionTimerRef.current = setTimeout(() => deepDesativar(), 30000);
      return;
    }

    // Modo normal
    setInput(transcript);
    inputValueRef.current = transcript;

    const PAUSE_WORDS = ['pause', 'pausa', 'aguarde', 'espere', 'espera', 'pera', 'perai', 'wait'];
    const pauseLower = transcript.toLowerCase().trim();
    if (PAUSE_WORDS.some(w => pauseLower === w || pauseLower.startsWith(w + ' ') || pauseLower.endsWith(' ' + w))) {
      if (autoSendTimerRef.current) { clearTimeout(autoSendTimerRef.current); autoSendTimerRef.current = null; }
      setAutoSendCountdown(0);
      if (userWantsListeningRef.current) setTimeout(() => { safeRestart(); }, 300);
      return;
    }

    const CANCEL_WORDS = ['cancela', 'cancelar', 'cancel', 'pare', 'parar', 'stop', 'para', 'esquece', 'ignora'];
    const cancelLower = transcript.toLowerCase().trim();
    if (CANCEL_WORDS.some(w => cancelLower === w || cancelLower.startsWith(w + ' ') || cancelLower.endsWith(' ' + w))) {
      if (autoSendTimerRef.current) { clearTimeout(autoSendTimerRef.current); autoSendTimerRef.current = null; }
      setAutoSendCountdown(0);
      setInput(''); inputValueRef.current = '';
      if (userWantsListeningRef.current) setTimeout(() => { safeRestart(); }, 300);
      return;
    }

    if (autoSendRef.current) {
      if (autoSendTimerRef.current) clearTimeout(autoSendTimerRef.current);
      setAutoSendCountdown(10);
      const countdownInterval = setInterval(() => {
        setAutoSendCountdown(prev => { if (prev <= 1) { clearInterval(countdownInterval); return 0; } return prev - 1; });
      }, 1000);
      autoSendTimerRef.current = setTimeout(() => {
        autoSendTimerRef.current = null;
        clearInterval(countdownInterval);
        setAutoSendCountdown(0);
        const text = inputValueRef.current.trim();
        if (text) handleSendRef.current(text);
      }, 10000);
    }
  };

  const buildRecognition = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || (window as any).mozSpeechRecognition || (window as any).msSpeechRecognition;
    if (!SpeechRecognition) return null;
    const r = new SpeechRecognition();
    r.lang = 'pt-BR';
    r.continuous = false;
    r.interimResults = false;
    r.onresult = (event: SpeechRecognitionEvent) => handleDeepResult(event);
    r.onerror = () => {
      isStartingRef.current = false;
      if (userWantsListeningRef.current && !isSpeakingRef.current) setTimeout(() => { safeRestart(); }, 500);
      else setIsListening(false);
    };
    r.onend = () => {
      isStartingRef.current = false;
      if (userWantsListeningRef.current && !isSpeakingRef.current) setTimeout(() => { safeRestart(); }, 200);
      else if (!isSpeakingRef.current) setIsListening(false);
    };
    return r;
  };

  const toggleDeepMode = () => {
    // Deep Mode desabilitado quando Charon esta ativo (conflito de microfone)
    if (charonActive) {
      console.log('[ChatPanel] Deep Mode desabilitado - Charon esta ativo');
      return;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || (window as any).mozSpeechRecognition || (window as any).msSpeechRecognition;
    if (!SpeechRecognition) { setSpeechSupported(false); return; }
    if (!recognitionRef.current) {
      const r = buildRecognition();
      if (!r) return;
      recognitionRef.current = r;
    }
    const recognition = recognitionRef.current as any;
    if (isDeepMode) {
      userWantsListeningRef.current = false;
      isDeepModeRef.current = false;
      setIsDeepMode(false);
      deepAtivoRef.current = false;
      setWakeWordActive(false);
      if (deepSilenceTimerRef.current) { clearTimeout(deepSilenceTimerRef.current); deepSilenceTimerRef.current = null; }
      if (deepSessionTimerRef.current) { clearTimeout(deepSessionTimerRef.current); deepSessionTimerRef.current = null; }
      try { recognition.stop(); } catch {}
      setIsListening(false);
    } else {
      userWantsListeningRef.current = true;
      isDeepModeRef.current = true;
      setIsDeepMode(true);
      deepAtivoRef.current = false;
      setWakeWordActive(false);
      try { recognition.start(); setIsListening(true); } catch (e) {
        console.warn('Erro ao iniciar modo deep:', e);
        setIsDeepMode(false); isDeepModeRef.current = false;
      }
    }
    try { window.speechSynthesis?.cancel?.(); } catch {}
  };

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
      saved.autoSend = autoSend;
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(saved));
    } catch {}
  }, [autoSend]);

  // Inicializa SpeechRecognition
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || (window as any).mozSpeechRecognition || (window as any).msSpeechRecognition;
    setSpeechSupported(!!SpeechRecognition);
    if (!SpeechRecognition) return;
    const r = buildRecognition();
    if (r) recognitionRef.current = r;
    return () => { try { recognitionRef.current?.abort(); } catch {} };
  }, []);

  // Atualiza handleSendRef sempre que handleSend mudar
  useEffect(() => {
    handleSendRef.current = handleSend;
  });



  const safeStartListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || (window as any).mozSpeechRecognition || (window as any).msSpeechRecognition;
    if (!SpeechRecognition) return;
    if (!recognitionRef.current) {
      const r = buildRecognition();
      if (!r) return;
      recognitionRef.current = r;
    }
    const recognition = recognitionRef.current as any;
    try {
      userWantsListeningRef.current = true;
      recognition.start();
      setIsListening(true);
    } catch (e) {
      console.warn('Erro ao iniciar reconhecimento:', e);
    }
  };

  const toggleMic = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || (window as any).mozSpeechRecognition || (window as any).msSpeechRecognition;
    if (!SpeechRecognition) { setSpeechSupported(false); setIsListening(false); return; }
    if (!recognitionRef.current) {
      const r = buildRecognition();
      if (!r) { setIsListening(false); return; }
      recognitionRef.current = r;
    }
    const recognition = recognitionRef.current as any;
    if (isListening) {
      userWantsListeningRef.current = false;
      isDeepModeRef.current = false;
      setIsDeepMode(false);
      deepAtivoRef.current = false;
      setWakeWordActive(false);
      if (deepSilenceTimerRef.current) { clearTimeout(deepSilenceTimerRef.current); deepSilenceTimerRef.current = null; }
      if (deepSessionTimerRef.current) { clearTimeout(deepSessionTimerRef.current); deepSessionTimerRef.current = null; }
      try { recognition.stop(); } catch {}
      setIsListening(false);
    } else {
      userWantsListeningRef.current = true;
      stopJarvis();
      try { recognition.start(); setIsListening(true); } catch (e) {
        console.warn('Erro ao iniciar reconhecimento:', e);
        setIsListening(false);
      }
    }
  };

  const SpeechRecognitionCtor =
    typeof window !== 'undefined'
      ? (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition ||
        (window as any).mozSpeechRecognition ||
        (window as any).msSpeechRecognition
      : undefined;

  // ─── Jarvis Voice (Text-to-Speech) ────────────────────────────

  const lastSpeakId = useRef(0);

  // Extrai apenas o texto limpo para o Jarvis falar
  const stripMarkdown = (text: string): string => {
    return text
      .replace(/<think>[\s\S]*?<\/think>/g, '') // remove thinking do modelo
      .replace(/```[\s\S]*?```/g, '') // blocos de codigo
      .replace(/`([^`]+)`/g, '$1') // inline code
      .replace(/\*\*([^*]+)\*\*/g, '$1') // **bold**
      .replace(/\*([^*]+)\*/g, '$1') // *italic*
      .replace(/~~([^~]+)~~/g, '$1') // ~~strikethrough~~
      .replace(/#{1,6}\s/g, '') // headings #
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links [text](url)
      .replace(/>\s/g, '') // blockquotes
      .replace(/[-*+]\s/g, '') // list markers
      .replace(/[\u{1F600}-\u{1F64F}]/gu, '') // emoticons
      .replace(/[\u{1F300}-\u{1F5FF}]/gu, '') // symbols & pictographs
      .replace(/[\u{1F680}-\u{1F6FF}]/gu, '') // transport & map
      .replace(/[\u{1F1E0}-\u{1F1FF}]/gu, '') // flags
      .replace(/[\u{2600}-\u{26FF}]/gu, '') // misc symbols
      .replace(/[\u{2700}-\u{27BF}]/gu, '') // dingbats
      .replace(/[\u{FE00}-\u{FE0F}]/gu, '') // variation selectors
      .replace(/[\u{1F900}-\u{1F9FF}]/gu, '') // supplemental symbols
      .replace(/[\u{200D}]/gu, '') // zero width joiner
      .replace(/[\u{20E3}]/gu, '') // combining enclosing keycap
      .replace(/[^\S\n]+/g, ' ') // multiplos espacos
      .replace(/\n{2,}/g, '. ') // paragrafos
      .trim();
  };

  const EDGE_VOICES: Record<string, string> = {
    'jarvis-cinematic': 'pt-BR-AntonioNeural',
    'edge-francisca': 'pt-BR-FranciscaNeural',
    'edge-thalita': 'pt-BR-ThalitaMultilingualNeural',
    'dani-brandi': 'pt-BR-FranciscaNeural',
  };

  // Fala o texto INTEIRO (sem resumir) - mantem todo o contexto
  const speakText = useCallback(
    async (text: string) => {
      const id = ++lastSpeakId.current;
      try {
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel?.();

        const clean = stripMarkdown(text);
        if (!clean) return;

        // Pausa o microfone para não gravar a própria voz (anti-eco)
        isSpeakingRef.current = true;
        if (recognitionRef.current && isListening) {
          try { recognitionRef.current.stop(); } catch {}
          setIsListening(false);
        }

        await new Promise((resolve) => setTimeout(resolve, 0));
        if (id !== lastSpeakId.current) { isSpeakingRef.current = false; return; }

        if (voicePreset in EDGE_VOICES) {
          if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            audioRef.current.src = '';
            audioRef.current = null;
          }

          const response = await fetch(`${API_BASE}/api/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: clean, voice: EDGE_VOICES[voicePreset] }),
          });

          if (!response.ok) {
            throw new Error(`TTS backend falhou: ${response.status}`);
          }
        if (id !== lastSpeakId.current) { isSpeakingRef.current = false; return; }

          const mimeType = 'audio/mpeg';
          const mediaSource = new MediaSource();
          const audio = new Audio();
          audioRef.current = audio;
          audio.src = URL.createObjectURL(mediaSource);

          let appendInProgress = false;
          let streamEnded = false;

          mediaSource.addEventListener('sourceopen', async () => {
            const sourceBuffer = mediaSource.addSourceBuffer(mimeType);
            const reader = response.body!.getReader();

            sourceBuffer.addEventListener('updateend', () => {
              appendInProgress = false;
              if (streamEnded && mediaSource.readyState === 'open') {
                mediaSource.endOfStream();
              }
            });

            const pump = async () => {
              try {
                while (true) {
                  const { done, value } = await reader.read();
                  if (done) {
                    streamEnded = true;
                    if (!appendInProgress && mediaSource.readyState === 'open') {
                      mediaSource.endOfStream();
                    }
                    return;
                  }
                  if (id !== lastSpeakId.current) {
                    streamEnded = true;
                    reader.cancel();
                    return;
                  }
                  if (sourceBuffer.updating) {
                    await new Promise((r) =>
                      sourceBuffer.addEventListener('updateend', r, { once: true }),
                    );
                  }
                  if (id !== lastSpeakId.current) return;
                  if (mediaSource.readyState === 'open') {
                    appendInProgress = true;
                    sourceBuffer.appendBuffer(value);
                  }
                }
              } catch (err) {
                console.warn('Erro no streaming TTS:', err);
              }
            };

            pump();

            setTimeout(() => {
              if (id === lastSpeakId.current) {
                audio.play().catch((err) => console.warn('Erro TTS:', err));
              }
            }, 300);
          });

          const finishSpeaking = () => {
            URL.revokeObjectURL(audio.src);
            if (audioRef.current === audio) audioRef.current = null;
            isSpeakingRef.current = false;
            if (userWantsListeningRef.current && !isListening) {
              setTimeout(() => { safeRestart(); }, 300);
            }
          };
          audio.onended = finishSpeaking;
          audio.onerror = finishSpeaking;
          return;
        }

        // Browser speech synthesis path
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.lang = 'pt-BR';
        utterance.volume = 1.0;
        utterance.rate = 0.5 + (jarvisRate / 100) * 1.5;
        utterance.pitch = 0.5 + (voicePitch / 100) * 1.0;

        const voices = Array.isArray(window.speechSynthesis.getVoices?.())
          ? window.speechSynthesis.getVoices()
          : [];
        const searchMap: Record<string, string[]> = {
          'google-female': ['google', 'female', 'pt'],
          francisca: ['francisca', 'pt'],
          maria: ['maria', 'pt'],
          'google-male': ['google', 'male', 'pt'],
          antonio: ['antonio', 'pt'],
          daniel: ['daniel', 'pt'],
        };
        const keywords = searchMap[voicePreset] || ['pt'];
        const normalized = (voice: SpeechSynthesisVoice) =>
          `${String(voice.name || '').toLowerCase()} ${String(voice.lang || '').toLowerCase()}`;
        const selectedVoice =
          voices.find((v) => keywords.every((keyword) => normalized(v).includes(keyword))) ||
          voices.find((v) =>
            String(v.lang || '')
              .toLowerCase()
              .startsWith('pt'),
          ) ||
          voices[0];
        if (selectedVoice) utterance.voice = selectedVoice;

        utterance.onend = () => {
          isSpeakingRef.current = false;
          if (userWantsListeningRef.current && !isListening) {
            setTimeout(() => { safeRestart(); }, 300);
          }
        };
        utterance.onerror = () => {
          isSpeakingRef.current = false;
        };

        if (id !== lastSpeakId.current) { isSpeakingRef.current = false; return; }
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        console.warn('Falha ao reproduzir Jarvis:', e);
        isSpeakingRef.current = false;
      }
    },
    [jarvisRate, voicePitch, voicePreset, isListening],
  );

  const stopJarvis = () => {
    lastSpeakId.current++;
    isSpeakingRef.current = false;
    window.speechSynthesis.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.src = '';
      audioRef.current = null;
    }
  };



  const toggleJarvis = () => {
    if (voiceMode) {
      stopJarvis();
      setVoiceMode(false);
    } else {
      setVoiceMode(true);
    }
  };

  // Disparo automático quando o stream chegar ao fim
  const prevStreamRef = useRef(stream);
  const lastSpokenMsgRef = useRef('');
  useEffect(() => {
    const finished = prevStreamRef.current && !stream;
    if (finished && voiceMode && stream === '' && msgs.length > 0) {
      const lastBotMsg = [...msgs].reverse().find((m) => m.from === 'bot');
      if (lastBotMsg && lastBotMsg.text) {
        const now = Date.now();
        const isNewMsg = lastBotMsg.text !== lastSpokenMsgRef.current;
        const cooldownOk = now - lastSpokenTimeRef.current > 3000;
        if (isNewMsg || cooldownOk) {
          lastSpokenMsgRef.current = lastBotMsg.text;
          lastSpokenTimeRef.current = now;
          speakText(lastBotMsg.text);
        }
      }
    }
    prevStreamRef.current = stream;
  }, [stream, voiceMode, msgs, speakText]);

  // Quando ativa o ear e ja tem mensagem nao falada, fala agora
  useEffect(() => {
    if (voiceMode && msgs.length > 0 && !isSpeakingRef.current) {
      const lastBotMsg = [...msgs].reverse().find((m) => m.from === 'bot');
      if (lastBotMsg && lastBotMsg.text && lastBotMsg.text !== lastSpokenMsgRef.current) {
        const now = Date.now();
        const cooldownOk = now - lastSpokenTimeRef.current > 3000;
        if (cooldownOk) {
          lastSpokenMsgRef.current = lastBotMsg.text;
          lastSpokenTimeRef.current = now;
          speakText(lastBotMsg.text);
        }
      }
    }
  }, [voiceMode]);



  const handleSend = (text?: string) => {
    lastSpeakId.current++;
    lastSpokenMsgRef.current = '';
    if (autoSendTimerRef.current) { clearTimeout(autoSendTimerRef.current); autoSendTimerRef.current = null; }
    setAutoSendCountdown(0);
    let msg = text ?? input;
    if (imagePreviews.length > 0) {
      const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
      if (saved.imageInputMode === 'image') {
        send(msg, imagePreviews);
      } else {
        const imgMd = imagePreviews.map((b64) => `![image](${b64})`).join('\n');
        msg = msg ? `${msg}\n\n${imgMd}` : imgMd;
        send(msg);
      }
    } else {
      send(msg);
    }
    setImagePreviews([]);
  };

  // ─── Textarea resize ──────────────────────────────────
  const [textareaH, setTextareaH] = useState(120);
  const dragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartH = useRef(0);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    dragStartY.current = e.clientY;
    dragStartH.current = textareaH;
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const delta = dragStartY.current - ev.clientY;
      setTextareaH(Math.max(36, Math.min(400, dragStartH.current + delta)));
    };
    const onUp = () => {
      dragging.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [textareaH]);

  // ─── Image upload (paste / drag-drop) ──────────────────
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);

  const MAX_IMG_DIM = 1024;
  const MAX_IMG_QUALITY = 0.7;

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const compressImage = async (b64: string): Promise<string> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width <= MAX_IMG_DIM && height <= MAX_IMG_DIM) {
          resolve(b64);
          return;
        }
        const ratio = Math.min(MAX_IMG_DIM / width, MAX_IMG_DIM / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
        const c = document.createElement('canvas');
        c.width = width;
        c.height = height;
        const ctx = c.getContext('2d');
        if (!ctx) {
          resolve(b64);
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        resolve(c.toDataURL('image/jpeg', MAX_IMG_QUALITY));
      };
      img.onerror = reject;
      img.src = b64;
    });
  };

  const handleImageInput = async (file: File) => {
    const b64 = await fileToBase64(file);
    const compressed = await compressImage(b64);
    setImagePreviews((prev) => [...prev, compressed]);
  };

  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.items);
    const imageItems = items.filter((item) => item.type.indexOf('image') !== -1);
    if (imageItems.length === 0) return;
    e.preventDefault();
    for (const item of imageItems) {
      const file = item.getAsFile();
      if (!file) continue;
      await handleImageInput(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const files = Array.from(e.dataTransfer.files);
    const imageFiles = files.filter((f) => f.type.indexOf('image') !== -1);
    for (const file of imageFiles) {
      await handleImageInput(file);
    }
  };

  // ─── Limpar provedor local (liberar RAM) ─────────────────
  const cleanProvider = async () => {
    // Para o llama-server se estiver rodando
    if (prov === 'llamacpp') {
      try {
        await fetch(`${API_BASE}/llamacpp/stop`, { method: 'POST' });
        console.log('[ChatPanel] llama-server parado via /llamacpp/stop');
      } catch (e) {
        console.warn('[ChatPanel] Erro ao parar llamacpp:', e);
      }
    }
    // Para o ollama se estiver rodando
    if (prov === 'ollama') {
      try {
        await fetch(`${API_BASE}/ollama/stop`, { method: 'POST' });
        console.log('[ChatPanel] ollama parado via /ollama/stop');
      } catch (e) {
        console.warn('[ChatPanel] Erro ao parar ollama:', e);
      }
    }
  };

  // ─── Plan pending detection ──────────────────────────────
  const pendingPlan = msgs.find((m) => m.planData && m.planStatus === 'pending');

  // ─── Modelos ────────────────────────────────────────────

  const loadedModels =
    prov === 'ollama' && oModels.length
      ? oModels
      : prov === 'llamacpp' && llamacppModels.length
        ? llamacppModels.map(m => ({
            value: m.value,
            label: m.available ? m.label : `${m.label} (indisponível)`,
          }))
        : prov === 'openrouter' && orModels.length
          ? orModels
          : MODELS[prov] || [];

  const models = loadedModels.some((m) => m.value === model)
    ? loadedModels
    : [{ value: model, label: model }, ...loadedModels];

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--bg)',
      }}
    >
      {/* header */}
      <div className="panel-header">
        <span className="panel-title" style={{ color: 'var(--pink)' }}>
          {assistantName || 'CHAT'}
        </span>
        <div style={{ display: 'flex', gap: '4px' }}>
          {loading && (
            <button className="btn btn-red" onClick={stopGen}>
              ■ stop
            </button>
          )}
          <button className="btn" onClick={newChat}>
            + novo
          </button>
          {(prov === 'llamacpp' || prov === 'ollama') && (
            <button className="btn" onClick={cleanProvider} title="Limpar modelo da memoria RAM">
              🧹 limpar
            </button>
          )}
        </div>
      </div>

      {/* provider / model row */}
      <div
        style={{
          display: 'flex',
          gap: '4px',
          padding: '5px 12px',
          borderBottom: '1px solid var(--line)',
        }}
      >
        <select
          value={prov}
          onChange={(e) => {
            const p = e.target.value as Provider;
            setProv(p);
            const ms = MODELS[p];
            if (ms?.length) setModel(ms[0].value);
          }}
          className="select-input"
          style={{ flex: 1, padding: '3px 5px', fontSize: '11px' }}
        >
          {PROVIDERS.map(
            (p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ),
          )}
        </select>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="select-input"
          style={{ flex: 2, padding: '3px 5px', fontSize: '11px' }}
        >
          {models.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
        <div style={{ alignSelf: 'center', flexShrink: 0 }}>
          <StatusIndicator provider={prov} />
        </div>
      </div>

      {/* messages */}
      <div
        style={{
          flex: 1,
          padding: '12px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        {msgs.map((m, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: m.from === 'bot' ? 'column' : 'row',
              gap: '8px',
              alignItems: m.from === 'bot' ? 'flex-start' : 'flex-start',
              justifyContent: m.from === 'user' ? 'flex-end' : 'flex-start',
              width: '100%',
            }}
          >
            {m.from === 'bot' && (
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--accent)',
                  color: 'var(--selection-fg)',
                  flexShrink: 0,
                  fontWeight: 700,
                  fontSize: '9px',
                  letterSpacing: '-0.3px',
                }}
              >
                {(assistantName || 'OC').charAt(0).toUpperCase()}
              </div>
            )}
            <div
              style={{
                position: m.from === 'bot' ? 'relative' : 'static',
                maxWidth: m.from === 'bot' ? '100%' : '85%',
                padding: m.planData ? '0' : '4px 8px',
                paddingTop: m.from === 'bot' && !m.planData ? '20px' : undefined,
                borderRadius: '4px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                background: 'transparent',
                border: 'none',
              }}
            >
              {m.permissionData ? (
                <PermissionDialog
                  title={m.permissionData.title}
                  description={m.permissionData.description}
                  patterns={m.permissionData.patterns}
                  onAllowOnce={() => handleSend(`/allow-once ${m.permissionData!.permissionId}`)}
                  onAllowAlways={() => handleSend(`/allow-always ${m.permissionData!.permissionId}`)}
                  onReject={() => handleSend(`/reject ${m.permissionData!.permissionId}`)}
                />
              ) : m.planData ? (
                <PlanMessage msg={m} onConfirm={onConfirmPlan} onReject={onRejectPlan} />
              ) : m.text.startsWith('charon_tool:') ? (
                (() => {
                  const parts = m.text.split(':');
                  const icon = parts[1];
                  const label = parts[2];
                  const color = parts[3];
                  const content = parts.slice(4).join(':');
                  return (
                    <CharonToolMessage
                      icon={icon}
                      label={label}
                      color={color}
                      content={content}
                    />
                  );
                })()
              ) : (() => {
                const actionCardData = parseActionCard(m.text);
                if (actionCardData) {
                  return (
                    <ActionCard
                      data={actionCardData}
                      onAction={(action) => handleSend(action)}
                    />
                  );
                }
                return (
                  <>
                    {m.thinking && (
                      <details style={{ marginBottom: 6, fontSize: 11, color: 'var(--muted)' }}>
                        <summary style={{ cursor: 'pointer', color: 'var(--accent)', fontWeight: 600, fontSize: 11, userSelect: 'none' }}>
                          Raciocínio
                        </summary>
                        <div style={{
                          marginTop: 4,
                          padding: '8px 10px',
                          background: 'rgba(128,128,128,0.08)',
                          borderRadius: 4,
                          borderLeft: '3px solid var(--accent)',
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'monospace',
                          fontSize: 11,
                          lineHeight: 1.5,
                          maxHeight: 300,
                          overflowY: 'auto',
                        }}>
                          {m.thinking}
                        </div>
                      </details>
                    )}
                    <MarkdownBlock text={m.text} />
                    {m.isLoopError && (
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      <button
                        onClick={() => handleSend('continue')}
                        style={{
                          padding: '6px 14px',
                          border: 'none',
                          borderRadius: '4px',
                          background: 'var(--accent)',
                          color: 'var(--selection-fg)',
                          cursor: 'pointer',
                          fontWeight: 600,
                          fontSize: '12px',
                          fontFamily: 'inherit',
                        }}
                      >
                        ▶ Continuar
                      </button>
                      <button
                        onClick={newChat}
                        style={{
                          padding: '6px 14px',
                          border: '1px solid var(--line)',
                          borderRadius: '4px',
                          background: 'transparent',
                          color: 'var(--muted)',
                          cursor: 'pointer',
                          fontWeight: 600,
                          fontSize: '12px',
                          fontFamily: 'inherit',
                        }}
                      >
                        + Novo Chat
                      </button>
                    </div>
                  )}
                  {m.images && m.images.length > 0 && (
                    <div
                      style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}
                    >
                      {m.images.map((img, idx) => (
                        <img
                          key={idx}
                          src={img.startsWith('data:') ? img : `data:image/jpeg;base64,${img}`}
                          style={{
                            maxWidth: 240,
                            maxHeight: 240,
                            borderRadius: '4px',
                            objectFit: 'contain',
                            border: '1px solid var(--line)',
                          }}
                          alt={`image-${idx}`}
                        />
                      ))}
                    </div>
                  )}
                </>
                );
              })()}
              {m.time && (
                <span style={{ fontSize: '10px', color: 'var(--muted)', alignSelf: 'flex-end' }}>
                  {typeof m.time === 'number'
                    ? new Date(m.time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
                    : m.time}
                </span>
              )}
              {m.from === 'bot' && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(m.text);
                    setCopiedIdx(i);
                    setTimeout(() => setCopiedIdx(null), 2000);
                  }}
                  style={{
                    position: 'absolute',
                    top: '4px',
                    right: '4px',
                    border: '1px solid var(--line)',
                    borderRadius: '3px',
                    background: 'var(--bg)',
                    color: 'var(--muted)',
                    cursor: 'pointer',
                    fontSize: '9px',
                    fontFamily: 'var(--font-ui)',
                    padding: '1px 5px',
                    lineHeight: '1.4',
                    transition: 'color 0.15s',
                  }}
                >
                  {copiedIdx === i ? 'Copiado! ✓' : 'copiar'}
                </button>
              )}
            </div>
            {m.from === 'user' && (
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--blue)',
                  color: 'var(--selection-fg)',
                  flexShrink: 0,
                  fontWeight: 700,
                  fontSize: '10px',
                }}
              >
                U
              </div>
            )}
          </div>
        ))}

        {/* Texto streaming em tempo real */}
        {loading && stream && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', width: '100%' }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--accent)', color: 'var(--selection-fg)', flexShrink: 0, fontWeight: 700, fontSize: '9px' }}>
              OC
            </div>
            <div style={{
              flex: 1,
              fontSize: '13px',
              lineHeight: 1.5,
              color: '#cccccc',
              padding: '6px 0',
              whiteSpace: 'pre-wrap' as const,
              fontFamily: 'var(--font-mono), "Cascadia Code", "Fira Code", Consolas, monospace',
              fontWeight: 400,
            }}>
              {stream}
              {stream.startsWith('>') && <span style={{ animation: 'blink 0.8s step-end infinite', color: '#808080' }}> ...</span>}
              {!stream.startsWith('>') && <span style={{ animation: 'blink 0.8s step-end infinite', color: 'var(--accent)' }}>|</span>}
            </div>
          </div>
        )}

        {/* Task Checklist - sequencia de tarefas como no VS Code */}
        {loading && checklistSteps.length > 0 && (
          <div style={{ width: '100%', paddingLeft: 32 }}>
            <TaskChecklist steps={checklistSteps} />
          </div>
        )}

        {/* Bolinhas de processo - dots animados quando carregando sem stream */}
        {loading && !stream && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', width: '100%' }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--accent)', color: 'var(--selection-fg)', flexShrink: 0, fontWeight: 700, fontSize: '9px' }}>
              OC
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '8px 12px', background: 'var(--bg-2)', borderRadius: '8px', border: '1px solid var(--line)' }}>
              {[0, 1, 2].map((i) => (
                <span key={i} style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--accent)',
                  animation: `dotPulse 1.4s ease-in-out infinite`,
                  animationDelay: `${i * 0.2}s`,
                }} />
              ))}
              <span style={{ fontSize: '10px', color: 'var(--muted)', marginLeft: 4 }}>
                {thinkOn ? 'pensando...' : 'processando...'}
              </span>
            </div>
          </div>
        )}

        <div ref={chatEnd} />
      </div>

      {/* input */}
      <div style={{ padding: '10px 12px', borderTop: '1px solid var(--line)' }}>
        {pendingPlan && (
          <div
            style={{
              display: 'flex',
              gap: '6px',
              marginBottom: '8px',
              padding: '8px 10px',
              borderRadius: '4px',
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              alignItems: 'center',
            }}
          >
            <span
              style={{
                flex: 1,
                fontSize: '11px',
                color: 'var(--muted)',
                fontFamily: 'var(--font-ui)',
              }}
            >
              Plano pendente — {pendingPlan.planData?.steps?.length || 0} etapa(s)
            </span>
            <button
              onClick={() => onConfirmPlan(pendingPlan.planTaskId || '')}
              style={{
                padding: '6px 14px',
                border: 'none',
                borderRadius: '4px',
                background: 'var(--accent)',
                color: 'var(--selection-fg)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '11px',
                fontFamily: 'inherit',
              }}
            >
              ✓ Aceitar
            </button>
            <button
              onClick={() => onRejectPlan(pendingPlan.planTaskId || '')}
              style={{
                padding: '6px 14px',
                border: '1px solid var(--line)',
                borderRadius: '4px',
                background: 'transparent',
                color: 'var(--muted)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '11px',
                fontFamily: 'inherit',
              }}
            >
              ✕ Rejeitar
            </button>
          </div>
        )}

        {pendingToolConfirm && (
          <div
            style={{
              display: 'flex',
              gap: '6px',
              marginBottom: '8px',
              padding: '8px 10px',
              borderRadius: '4px',
              background: pendingToolConfirm.risk_level === 'critical' ? 'rgba(239,68,68,0.1)' : 'var(--accent-soft)',
              border: `1px solid ${pendingToolConfirm.risk_level === 'critical' ? 'rgba(239,68,68,0.4)' : 'var(--accent-line)'}`,
              alignItems: 'center',
            }}
          >
            <span style={{ fontSize: '13px', flexShrink: 0 }}>
              {pendingToolConfirm.risk_level === 'critical' ? '🔴' : '⚠️'}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink)', fontFamily: 'var(--font-ui)' }}>
                {pendingToolConfirm.risk_level === 'critical' ? 'RISCO CRITICO' : 'Confirmacao'}
                {pendingToolConfirm.tool && <span style={{ fontWeight: 400, color: 'var(--muted)', marginLeft: 4 }}>({pendingToolConfirm.tool})</span>}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--muted)', fontFamily: 'var(--font-ui)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {pendingToolConfirm.label}
              </div>
              {pendingToolConfirm.params && Object.keys(pendingToolConfirm.params).length > 0 && (
                <div style={{ fontSize: '10px', color: 'var(--muted)', fontFamily: 'var(--font-ui)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {Object.entries(pendingToolConfirm.params)
                    .filter(([k]) => k !== 'root')
                    .map(([k, v]) => `${k}: ${typeof v === 'string' ? (v.length > 40 ? v.slice(0, 40) + '...' : v) : JSON.stringify(v)}`)
                    .join(' · ')}
                </div>
              )}
            </div>
            <button
              onClick={onApproveTool}
              style={{
                padding: '6px 14px',
                border: 'none',
                borderRadius: '4px',
                background: 'var(--accent)',
                color: 'var(--selection-fg)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '11px',
                fontFamily: 'inherit',
                flexShrink: 0,
              }}
            >
              ✓ Executar
            </button>
            <button
              onClick={onRejectTool}
              style={{
                padding: '6px 14px',
                border: '1px solid var(--line)',
                borderRadius: '4px',
                background: 'transparent',
                color: 'var(--muted)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '11px',
                fontFamily: 'inherit',
                flexShrink: 0,
              }}
            >
              ✕ Cancelar
            </button>
          </div>
        )}

        {curTab && (
          <button
            onClick={() => analyzeFile(curTab)}
            style={{
              width: '100%',
              textAlign: 'left',
              marginBottom: '8px',
              fontSize: '12px',
              padding: '6px 10px',
              border: '1px solid var(--line)',
              borderRadius: '4px',
              background: 'var(--bg-2)',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontWeight: 600,
              fontFamily: 'inherit',
              transition: 'border-color 0.15s',
            }}
          >
            $ analisar: {curTab.name}
          </button>
        )}

        {imagePreviews.length > 0 && (
          <div
            style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8, padding: '4px 0' }}
          >
            {imagePreviews.map((img, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img
                  src={img}
                  alt={`preview ${i}`}
                  style={{
                    width: 60,
                    height: 60,
                    objectFit: 'cover',
                    borderRadius: 4,
                    border: '1px solid var(--line)',
                  }}
                />
                <button
                  onClick={() => setImagePreviews((prev) => prev.filter((_, j) => j !== i))}
                  style={{
                    position: 'absolute',
                    top: -6,
                    right: -6,
                    width: 18,
                    height: 18,
                    borderRadius: '50%',
                    border: '1px solid var(--line)',
                    background: 'var(--bg)',
                    color: 'var(--muted)',
                    cursor: 'pointer',
                    fontSize: 10,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: 'inherit',
                    padding: 0,
                  }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        <div
          style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          {/* Textarea em cima */}
          <div style={{ width: '100%', position: 'relative' }}>
            {/* @ Mention Popover */}
            {mentionQuery !== null && filteredMentions.length > 0 && (
              <div data-popover style={{
                position: 'absolute',
                bottom: '100%',
                left: 0,
                right: 0,
                marginBottom: 4,
                background: 'var(--bg-2)',
                border: '1px solid var(--line)',
                borderRadius: 6,
                maxHeight: 240,
                overflowY: 'auto',
                zIndex: 100,
                boxShadow: '0 -4px 12px rgba(0,0,0,0.3)',
              }}>
                {filteredMentions.filter(m => AGENTS.some(a => a.id === m.id)).length > 0 && (
                  <div style={{ padding: '6px 10px', fontSize: '10px', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.5px' }}>
                    AGENTES
                  </div>
                )}
                {filteredMentions.filter(m => AGENTS.some(a => a.id === m.id)).map((item) => (
                  <div key={item.id} onClick={() => insertMention(item.label)} style={{
                    padding: '7px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                    fontSize: '12px', color: 'var(--ink)', fontFamily: 'var(--font-ui)',
                    borderBottom: '1px solid var(--line)',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--accent-soft)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <span style={{ width: 20, textAlign: 'center', color: 'var(--accent)', fontWeight: 700, fontSize: '11px' }}>{item.icon}</span>
                    <span style={{ fontWeight: 600 }}>{item.label}</span>
                    <span style={{ color: 'var(--muted)', fontSize: '11px', flex: 1 }}>{item.desc}</span>
                  </div>
                ))}
                {filteredMentions.filter(m => SKILLS.some(s => s.id === m.id)).length > 0 && (
                  <div style={{ padding: '6px 10px', fontSize: '10px', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.5px', borderTop: '1px solid var(--line)' }}>
                    SKILLS
                  </div>
                )}
                {filteredMentions.filter(m => SKILLS.some(s => s.id === m.id)).map((item) => (
                  <div key={item.id} onClick={() => insertMention(item.label)} style={{
                    padding: '7px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                    fontSize: '12px', color: 'var(--ink)', fontFamily: 'var(--font-ui)',
                    borderBottom: '1px solid var(--line)',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--accent-soft)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <span style={{ width: 20, textAlign: 'center', color: 'var(--teal)', fontWeight: 700, fontSize: '11px' }}>{item.icon}</span>
                    <span style={{ fontWeight: 600 }}>{item.label}</span>
                    <span style={{ color: 'var(--muted)', fontSize: '11px', flex: 1 }}>{item.desc}</span>
                  </div>
                ))}
              </div>
            )}

            {/* / Command Popover */}
            {commandQuery !== null && filteredCommands.length > 0 && (
              <div data-popover style={{
                position: 'absolute',
                bottom: '100%',
                left: 0,
                right: 0,
                marginBottom: 4,
                background: 'var(--bg-2)',
                border: '1px solid var(--line)',
                borderRadius: 6,
                maxHeight: 240,
                overflowY: 'auto',
                zIndex: 100,
                boxShadow: '0 -4px 12px rgba(0,0,0,0.3)',
              }}>
                <div style={{ padding: '6px 10px', fontSize: '10px', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.5px' }}>
                  COMANDOS
                </div>
                {filteredCommands.map((cmd) => (
                  <div key={cmd.cmd} onClick={() => insertCommand(cmd.cmd)} style={{
                    padding: '7px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                    fontSize: '12px', color: 'var(--ink)', fontFamily: 'var(--font-ui)',
                    borderBottom: '1px solid var(--line)',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--accent-soft)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <span style={{ width: 20, textAlign: 'center', color: 'var(--accent)', fontWeight: 700, fontSize: '11px' }}>{cmd.icon}</span>
                    <span style={{ fontWeight: 600, color: 'var(--accent)' }}>{cmd.cmd}</span>
                    <span style={{ color: 'var(--muted)', fontSize: '11px', flex: 1 }}>{cmd.desc}</span>
                  </div>
                ))}
              </div>
            )}

            {/* + Quick Actions Popover */}
            {showPlusMenu && (
              <div data-popover style={{
                position: 'absolute',
                bottom: '100%',
                left: 0,
                marginBottom: 4,
                background: 'var(--bg-2)',
                border: '1px solid var(--line)',
                borderRadius: 6,
                width: 220,
                zIndex: 100,
                boxShadow: '0 -4px 12px rgba(0,0,0,0.3)',
              }}>
                <input
                  value={plusMenuFilter}
                  onChange={(e) => setPlusMenuFilter(e.target.value.toLowerCase())}
                  placeholder="Filtrar acoes..."
                  autoFocus
                  style={{
                    width: '100%', padding: '6px 10px', border: 'none', borderBottom: '1px solid var(--line)',
                    background: 'transparent', color: 'var(--ink)', fontSize: '12px', fontFamily: 'var(--font-ui)',
                    outline: 'none', boxSizing: 'border-box',
                  }}
                />
                {filteredPlusActions.map((action) => (
                  <div key={action.id} onClick={() => {
                    setInput(action.label + ' ');
                    setShowPlusMenu(false);
                    setPlusMenuFilter('');
                  }} style={{
                    padding: '7px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                    fontSize: '12px', color: 'var(--ink)', fontFamily: 'var(--font-ui)',
                    borderBottom: '1px solid var(--line)',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--accent-soft)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <span style={{ width: 20, textAlign: 'center', color: 'var(--accent)', fontWeight: 700, fontSize: '11px' }}>{action.icon}</span>
                    <span style={{ fontWeight: 600 }}>{action.label}</span>
                    <span style={{ color: 'var(--muted)', fontSize: '11px', flex: 1 }}>{action.desc}</span>
                  </div>
                ))}
              </div>
            )}

            <div
              onMouseDown={onDragStart}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: 6,
                cursor: 'ns-resize',
                zIndex: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Arraste para redimensionar"
            >
              <div style={{ width: 32, height: 2, borderRadius: 1, background: 'var(--line)' }} />
            </div>
            <textarea
              value={input}
              onChange={(e) => { setInput(e.target.value); inputValueRef.current = e.target.value; }}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  setMentionQuery(null);
                  setCommandQuery(null);
                  setShowPlusMenu(false);
                } else if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                  if (mentionQuery !== null || commandQuery !== null) {
                    e.preventDefault();
                  }
                }
              }}
              onPaste={handlePaste}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onContextMenu={(e) => e.stopPropagation()}
              placeholder="Digite sua mensagem..."
              disabled={false}
              style={{
                width: '100%',
                height: textareaH,
                resize: 'none',
                padding: '10px',
                paddingTop: 12,
                borderRadius: 6,
                border: '1px solid var(--line)',
                background: 'var(--bg)',
                color: 'var(--ink)',
                fontFamily: 'inherit',
                fontSize: '13px',
                lineHeight: 1.4,
              }}
            />
          </div>

          {/* Botões embaixo */}
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center', justifyContent: 'space-between' }}>
            {/* Esquerda: Jarvis + Mic + Aurea */}
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              {/* TOGGLE JARVIS VOICE */}
              <button
                onClick={toggleJarvis}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 4,
                  border: `1px solid ${voiceMode ? 'var(--accent)' : 'var(--line)'}`,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: voiceMode ? 'var(--accent)' : 'transparent',
                  color: voiceMode ? 'var(--selection-fg)' : 'var(--muted)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '12px',
                  transition: 'all 0.2s ease',
                }}
                title={voiceMode ? 'Jarvis Ativo - clique para desligar' : 'Jarvis Desligado - clique para ativar'}
              >
                {voiceMode ? '🔊' : '🔇'}
              </button>

              {/* MICROFONE - desabilitado quando Charon ativo */}
              <button
                onClick={charonActive ? undefined : toggleMic}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 4,
                  border: '1px solid var(--line)',
                  cursor: charonActive ? 'not-allowed' : SpeechRecognitionCtor ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: charonActive ? 'rgba(100,100,100,0.1)' : isListening && !isDeepMode ? '#e53e3e' : 'transparent',
                  color: charonActive ? '#666' : isListening && !isDeepMode ? '#fff' : 'var(--muted)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '16px',
                  transition: 'all 0.2s ease',
                  opacity: charonActive ? 0.4 : 1,
                }}
                title={charonActive ? 'Desabilitado - Charon esta ativo' : !SpeechRecognitionCtor ? 'Reconhecimento de voz não suportado' : isListening && !isDeepMode ? 'Gravando... clique para parar' : 'Clique para falar'}
                disabled={!SpeechRecognitionCtor || charonActive}
              >
                {isListening && !isDeepMode ? '🔴' : '🎙️'}
              </button>

              {/* MODO DEEP - desabilitado quando Charon ativo */}
              <button
                onClick={charonActive ? undefined : toggleDeepMode}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 4,
                  border: `1px solid ${charonActive ? 'var(--line)' : isDeepMode ? 'var(--accent)' : 'var(--line)'}`,
                  cursor: charonActive ? 'not-allowed' : SpeechRecognitionCtor ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: charonActive ? 'rgba(100,100,100,0.1)' : isDeepMode ? (wakeWordActive ? '#e53e3e' : '#2d8659') : 'transparent',
                  color: charonActive ? '#666' : isDeepMode ? '#fff' : 'var(--muted)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '-0.5px',
                  transition: 'all 0.2s ease',
                  opacity: charonActive ? 0.4 : 1,
                }}
                title={charonActive ? 'Desabilitado - Charon esta ativo' : !SpeechRecognitionCtor ? 'Reconhecimento de voz não suportado' : isDeepMode ? (wakeWordActive ? 'Ouvindo comando... (fale sua tarefa)' : 'Aguardando palavra "deep"...') : 'Modo Deep — escuta permanente, diga "deep" para comandar'}
                disabled={!SpeechRecognitionCtor || charonActive}
              >
                {isDeepMode ? (wakeWordActive ? '🔴' : '👂') : 'A'}
              </button>

            </div>
            {/* Direita: Auto-send + Plus + Enviar */}
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              {/* AUTO-SEND TOGGLE */}
              <button
                onClick={() => setAutoSend(!autoSend)}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 4,
                  border: `1px solid ${autoSend ? 'var(--accent)' : 'var(--line)'}`,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: autoSend ? 'var(--accent)' : 'transparent',
                  color: autoSend ? 'var(--selection-fg)' : 'var(--muted)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '12px',
                  transition: 'all 0.2s ease',
                }}
                title={autoSend ? 'Envio Automatico ATIVO - voz envia apos 10s de silencio' : 'Envio Automatico DESATIVADO - voz so preenche o campo'}
              >
                {autoSend ? '⚡' : '✋'}
              </button>

              <button
                data-popover
                onClick={() => setShowPlusMenu(!showPlusMenu)}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 6,
                  border: `1px solid ${showPlusMenu ? 'var(--accent)' : 'var(--line)'}`,
                  color: showPlusMenu ? 'var(--accent)' : 'var(--muted)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: showPlusMenu ? 'var(--accent-soft)' : 'transparent',
                  fontSize: '16px',
                  fontWeight: 600,
                  fontFamily: 'inherit',
                  transition: 'all 0.15s ease',
                }}
                title="Acoes rapidas (+)"
              >
                +
              </button>

              <button
                onClick={() => handleSend()}
                disabled={false}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 6,
                  border: `1px solid var(--accent)`,
                  color: 'var(--accent)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: 'transparent',
                }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
