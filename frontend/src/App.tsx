import React, { useState, useEffect, useRef, useMemo, lazy, Suspense } from 'react';
import { useTheme } from './hooks/useTheme';
import { setSoundEnabled, playSound } from './lib/soundFx';
import { showToast } from './components/Toast';
import type {
  Msg,
  Provider,
  Mood,
  HistItem,
  ExpItem,
  TLog,
  FileTab,
  Theme,
  AccentTheme,
  Page,
  KnowItem,
} from './lib/constants';
import { API_BASE, ACCENT_THEMES, DEFAULT_ACCENT_THEME } from './lib/constants';
import ExplorerPanel from './components/ExplorerPanel';
import EditorPanel from './components/EditorPanel';
import ChatPanel from './components/ChatPanel';
import StatusBar from './components/StatusBar';
import TerminalPanel from './components/TerminalPanel';
import MiniMonitors from './components/MiniMonitors';
import ConfigModal from './components/ConfigModal';
import CharonPanel from './components/CharonPanel';
import ErrorBoundary from './components/ErrorBoundary';
import PageRenderer from './components/PageRenderer';
import MusicPlayer, { type MusicPlayerHandle } from './components/MusicPlayer';
import ToastContainer from './components/Toast';
import MediaPlayDialog from './components/MediaPlayDialog';

// Lazy load SaaS components
const SaaSApp = lazy(() => import('./components/saas/SaaSApp'));

// Detecta modo SaaS pela porta, variavel de ambiente ou dominio
const isSaaSMode = () => {
  // Variavel de ambiente do Vite (build:saas)
  if (import.meta.env.VITE_SaaS_MODE === 'true') return true;
  // Porta 5176 = modo SaaS (dev)
  if (window.location.port === '5176') return true;
  // URL com /saas
  if (window.location.pathname.includes('/saas')) return true;
  // Dominio deep-os.tech = sempre SaaS
  if (window.location.hostname.includes('deep-os.tech')) return true;
  return false;
};

// ─── Accent theme CSS application ─────────────────────────────────────

// Detecta JSON de protocolo interno (task_plan, task_progress) que nao deve ser exibido
function isInternalJson(s: string) {
  if (!s || typeof s !== 'string') return false;
  const trimmed = s.trim();
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === 'object' && parsed.type !== 'action_card'
      && ['task_plan', 'task_progress'].includes(parsed.type);
  } catch { /* not json */ }
  return false;
}

// Remove JSON de protocolo interno e raciocinio interno do modelo
function stripInternalJson(s: string) {
  if (!s) return s;
  let cleaned = s.replace(/\{"type"\s*:\s*"(task_plan|task_progress)"[^}]*\}/g, '');
  // Remove bloco de raciocinio em ingles (MiMo V2.5)
  // Procura linha em branco separando thinking (ASCII) de resposta (PT-BR)
  const lines = cleaned.split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === '' && i > 0) {
      const preBlock = lines.slice(0, i).join('\n').trim();
      if (!preBlock) continue;
      const asciiRatio = [...preBlock].filter(c => c.charCodeAt(0) < 128).length / Math.max(preBlock.length, 1);
      if (asciiRatio > 0.85) {
        const postBlock = lines.slice(i).join('\n').trim();
        if (postBlock) {
          cleaned = postBlock;
          break;
        }
      }
    }
  }
  return cleaned.trim().replace(/\n{3,}/g, '\n\n');
}
function lightenHex(hex: string, amount: number): string {
  const r = Math.min(255, parseInt(hex.slice(1, 3), 16) + amount);
  const g = Math.min(255, parseInt(hex.slice(3, 5), 16) + amount);
  const b = Math.min(255, parseInt(hex.slice(5, 7), 16) + amount);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

function applyAccentTheme(themeKey: AccentTheme, customColor?: string) {
  let hex: string;
  if (themeKey === 'custom' && customColor) {
    hex = customColor;
  } else {
    const t = ACCENT_THEMES.find((t) => t.key === themeKey) || ACCENT_THEMES[0];
    hex = t.color;
  }
  // Convert hex to RGB for rgba usage
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  const root = document.documentElement;
  root.style.setProperty('--accent', hex);
  root.style.setProperty('--accent-soft', `rgba(${r},${g},${b},0.12)`);
  root.style.setProperty('--accent-line', `rgba(${r},${g},${b},0.35)`);
  // --accent-2: lighter variant for secondary text/detail (opposite of hover)
  root.style.setProperty('--accent-2', lightenHex(hex, 60));
  root.style.setProperty('--status-bg', hex);
  root.style.setProperty('--line-strong', `rgba(${r},${g},${b},0.25)`);
  // For light accent colors use dark text on status bar and selection
  root.style.setProperty('--status-fg', brightness > 160 ? '#000000' : '#ffffff');
  root.style.setProperty('--selection-fg', brightness > 140 ? '#000000' : '#ffffff');
}

// ─── Apply saved accent theme BEFORE first render (no flash) ───────
(function initAccentSync() {
  try {
    const saved = JSON.parse(localStorage.getItem('wbc2') || '{}');
    const themeKey = saved.accentTheme || DEFAULT_ACCENT_THEME;
    const customColor = saved.customColor || '';
    applyAccentTheme(themeKey, customColor);
  } catch {}
})();

// ─── Loading spinner para SaaS ─────────────────────────────────────
const LoadingSpinner = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    background: '#0f0f1a',
    color: '#00d9ff',
    fontSize: '18px'
  }}>
    <div>Carregando DEEP-OS SaaS...</div>
  </div>
);

// ─── SaaS Wrapper com Suspense ─────────────────────────────────────
function SaaSWrapper() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <SaaSApp />
    </Suspense>
  );
}

export default function App() {
  // Detecta modo SaaS e renderiza componente apropriado
  const saas = isSaaSMode();
  console.log('[App] isSaaSMode:', saas, 'pathname:', window.location.pathname, 'host:', window.location.hostname);
  if (saas) {
    return <SaaSWrapper />;
  }

  const { theme, toggleTheme } = useTheme();

  // ── Chat state ────────────────────────────────────────────────────────
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [stream, setStream] = useState('');
  const [thinking, setThink] = useState('');
  const [thinkOn, setThinkOn] = useState(false);
  const [thinkOpen, setThinkOpen] = useState(true);
  const [charonPanel, setCharonPanel] = useState(true);
  const [charonTranscripts, setCharonTranscripts] = useState<{speaker: string; text: string; time: string}[]>([]);
  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  const [deepSilenceSec, setDeepSilenceSec] = useState(30);
  const [charonActive, setCharonActive] = useState(false);
  const [charonVoiceStatus, setCharonVoiceStatus] = useState<string>('idle');
  const charonSendTextRef = useRef<((text: string) => void) | null>(null);
  const savedProvRef = useRef<{ prov: Provider; model: string } | null>(null);

  // Sincroniza voiceModeRef com o state
  useEffect(() => { voiceModeRef.current = voiceMode; }, [voiceMode]);

  // Quando WBC liga: troca provider local por cloud
  // Quando WBC desliga: restaura provider local
  useEffect(() => {
    const LOCAL_PROVIDERS: Provider[] = ['ollama', 'llamacpp'];
    if (charonActive && LOCAL_PROVIDERS.includes(prov)) {
      savedProvRef.current = { prov, model };
      setProv('opencode');
      setModel('deepseek-v4-flash-free');
    } else if (!charonActive && savedProvRef.current) {
      setProv(savedProvRef.current.prov);
      setModel(savedProvRef.current.model);
      savedProvRef.current = null;
    }
  }, [charonActive]);

  // Quando Charon ativa: abre o painel. Quando desativa: fecha o painel
  // (pula no primeiro render para nao sobrescrever layout salvo)
  useEffect(() => {
    if (layoutLoadedRef.current) setCharonPanel(charonActive);
  }, [charonActive]);

  // Handler para resultados de tools do Charon
  const handleCharonToolResult = (tool: string, result: string) => {
    const toolConfig: Record<string, { label: string; icon: string; color: string }> = {
      'file_controller': { label: 'Gerenciador de Arquivos', icon: '📁', color: '#4fc3f7' },
      'web_search': { label: 'Busca Web', icon: '🔍', color: '#81c784' },
      'open_app': { label: 'Aplicativo', icon: '🚀', color: '#ffb74d' },
      'computer_control': { label: 'Controle do PC', icon: '💻', color: '#e57373' },
      'browser_control': { label: 'Navegador', icon: '🌐', color: '#64b5f6' },
      'code_helper': { label: 'Código', icon: '📝', color: '#ba68c8' },
      'send_message': { label: 'Mensagem', icon: '💬', color: '#4db6ac' },
      'system_status': { label: 'Sistema', icon: '⚙️', color: '#90a4ae' },
      'weather_report': { label: 'Tempo', icon: '🌤️', color: '#ffd54f' },
      'reminder': { label: 'Lembrete', icon: '⏰', color: '#ff8a65' },
      'desktop_control': { label: 'Área de Trabalho', icon: '🖥️', color: '#a1887f' },
      'computer_settings': { label: 'Configurações', icon: '🔧', color: '#78909c' },
      'youtube_video': { label: 'YouTube', icon: '🎬', color: '#ef5350' },
      'game_updater': { label: 'Jogos', icon: '🎮', color: '#7e57c2' },
      'flight_finder': { label: 'Voos', icon: '✈️', color: '#29b6f6' },
      'file_processor': { label: 'Processador', icon: '📋', color: '#66bb6a' },
    };

    const config = toolConfig[tool] || { label: tool, icon: '⚡', color: '#b478ff' };
    
    // Formata o resultado baseado no conteúdo
    let formattedResult = result;
    
    // Se for listagem de arquivos, formata como lista
    if (tool === 'file_controller' && result.includes('itens')) {
      formattedResult = result
        .replace(/Pastas:\s*/, '**Pastas:**\n')
        .replace(/Arquivos:\s*/, '\n**Arquivos:**\n')
        .replace(/,\s*/g, '\n');
    }
    
    // Se for status do sistema, formata melhor
    if (tool === 'system_status') {
      formattedResult = result.replace(/CPU|RAM|GPU/g, (match) => `**${match}**`);
    }

    const msg = {
      from: 'bot' as const,
      text: `charon_tool:${config.icon}:${config.label}:${config.color}:${formattedResult}`,
      time: Date.now(),
    };
    
    setMsgs(prev => [...prev, msg]);
  };
  const [toolLogs, setLogs] = useState<TLog[]>([]);
  const [checklistSteps, setChecklistSteps] = useState<{ label: string; status: string; error?: string }[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0); // Contador de geração para descartar eventos antigos
  const latestExpPath = useRef('');
  const latestExpRoot = useRef('');
  const pendingRead = useRef<{ path: string; root: string }[]>([]);
  const taskIdRef = useRef(''); // Para continuar tarefas
  const sessionIdRef = useRef(`session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const messageQueueRef = useRef<Array<{text: string; images?: string[]}>>([]);
  const [pendingToolConfirm, setPendingToolConfirm] = useState<{
    confirmId: string;
    tool: string;
    label: string;
    risk_level?: string;
    params: Record<string, any>;
    taskId: string;
  } | null>(null);

  // ── Provider ──────────────────────────────────────────────────────────
  const [prov, setProv] = useState<Provider>('mimo');
  const [model, setModel] = useState('mimo-v2.5');
  const [oModels, setOModels] = useState<{ value: string; label: string }[]>([]);
  const [orModels, setOrModels] = useState<{ value: string; label: string }[]>([]);
  const [llamacppModels, setLlamacppModels] = useState<{ value: string; label: string; available: boolean }[]>([]);
  const [ollSt, setOllSt] = useState<{ running: boolean; models: string[] } | undefined>(undefined);
  const [customM, setCustomM] = useState('');
  const [showCust, setShowCust] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [orApiKey, setOrApiKey] = useState('');
  const [groqApiKey, setGroqApiKey] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [geminiApiKey, setGeminiApiKey] = useState('');
  const [mimoApiKey, setMimoApiKey] = useState('');
  const [nvidiaApiKey, setNvidiaApiKey] = useState('');
  const [initDone, setInitDone] = useState(false);

  // ── Settings ──────────────────────────────────────────────────────────
  const [mood, setMood] = useState<Mood>('opencode');
  const [temp, setTemp] = useState(0.7);
  const [sysPr, setSysPr] = useState('');
  const [snd, setSnd] = useState(false);
  const [bright, setBright] = useState(100);
  const [fsize, setFsize] = useState(13);
  const [voicePreset, setVoicePreset] = useState<
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
    | 'dani-brandi'
  >('jarvis-cinematic');
  const [jarvisRate, setJarvisRate] = useState(50);
  const [voicePitch, setVoicePitch] = useState(50);
  // (reserved)
  const [accentTheme, setAccentTheme] = useState<AccentTheme>(DEFAULT_ACCENT_THEME);
  const [customColor, setCustomColor] = useState('#D6EAF8');
  const [assistantName, setAssistantName] = useState('DEEP-OS');
  const [userName, setUserName] = useState('');
  const [voiceName, setVoiceName] = useState('Charon');
  const [gpuEnabled, setGpuEnabled] = useState(true);
  const [charonFullTools, setCharonFullTools] = useState('medium');

  const [planData, setPlanData] = useState<any>(null);
  const planTaskIdRef = useRef('');
  const planOrigTextRef = useRef('');

  // ── Media Play Dialog ─────────────────────────────────────────────────
  const [mediaPlayDialog, setMediaPlayDialog] = useState<{
    fileName: string;
    isVideo: boolean;
    filePath?: string;
  } | null>(null);

  // ── Layout ────────────────────────────────────────────────────────────
  const [expW, setExpW] = useState(240);
  const [chatW, setChatW] = useState(480);
  const [chatH, setChatH] = useState(0); // 0 = fill available height
  const [termH, setTermH] = useState(220);
  const [termOpen, setTermOpen] = useState(true);
  const dragging = useRef<'exp' | 'chat' | 'chat-h' | 'chat-charon' | null>(null);

  // ── Navigation ────────────────────────────────────────────────────────
  const [page, setPage] = useState<Page>('monitor');
  const [view, setView] = useState<'page' | 'file'>('page');
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpSections, setHelpSections] = useState<Record<string, boolean>>({});
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const helpRef = useRef<HTMLDivElement>(null);

  const toggleHelpSection = (key: string) => {
    setHelpSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // ── File tabs ─────────────────────────────────────────────────────────
  const [tabs, setTabs] = useState<FileTab[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);

  // ── Explorer ──────────────────────────────────────────────────────────
  const [expRoot, setExpRoot] = useState('');
  const [expTree, setExpTree] = useState<ExpItem[]>([]);
  const [expPath, setExpPath] = useState<string[]>([]);
  const [currentDir, setCurrentDir] = useState('');
  const [histSearch, setHistSearch] = useState('');
  const [histItens, setHistItens] = useState<HistItem[]>([]);

  // ── Knowledge ─────────────────────────────────────────────────────────
  const [knows, setKnows] = useState<KnowItem[]>([]);

  // ── Refs ──────────────────────────────────────────────────────────────
  const fileScrollRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLPreElement>(null);
  const fileContentRef = useRef('');
  const musicPlayerRef = useRef<MusicPlayerHandle>(null);

  // ─── Layout persistence ──────────────────────────────────────────────
  const LAYOUT_KEY = 'wbc2_layout';
  const layoutLoadedRef = useRef(false);

  // Load layout from localStorage on mount
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}');
      if (typeof saved.page === 'string') setPage(saved.page as Page);
      if (saved.view === 'page' || saved.view === 'file') setView(saved.view);
      if (typeof saved.expW === 'number') setExpW(saved.expW);
      if (typeof saved.chatW === 'number') setChatW(saved.chatW);
      if (typeof saved.chatH === 'number') setChatH(saved.chatH);
      if (typeof saved.termH === 'number') setTermH(saved.termH);
      if (typeof saved.termOpen === 'boolean') setTermOpen(saved.termOpen);
      if (typeof saved.charonPanel === 'boolean') setCharonPanel(saved.charonPanel);
      if (typeof saved.thinkOpen === 'boolean') setThinkOpen(saved.thinkOpen);
    } catch {}
    layoutLoadedRef.current = true;
  }, []);

  // Save layout to localStorage on change
  useEffect(() => {
    if (!initDone) return;
    try {
      localStorage.setItem(
        LAYOUT_KEY,
        JSON.stringify({ page, view, expW, chatW, chatH, termH, termOpen, charonPanel, thinkOpen }),
      );
    } catch {}
  }, [initDone, page, view, expW, chatW, termH, termOpen, charonPanel, thinkOpen]);

  // ─── Effects ──────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let themeFromBackend: string | null = null;
      let sysPrFromBackend: string = '';
      let identityFromBackend: { assistant_name?: string; user_name?: string; voice?: string } = {};
      try {
        const [themeRes, configRes, identityRes] = await Promise.all([
          fetch(`${API_BASE}/api/config/accent-theme`),
          fetch(`${API_BASE}/api/config/agent`),
          fetch(`${API_BASE}/api/config/identity`),
        ]);
        if (themeRes.ok) {
          const data = await themeRes.json();
          if (data.accent_theme) themeFromBackend = data.accent_theme;
        }
        if (configRes.ok) {
          const data = await configRes.json();
          if (data.system_prompt) sysPrFromBackend = data.system_prompt;
        }
        if (identityRes.ok) {
          identityFromBackend = await identityRes.json();
        }
      } catch {
        /* backend offline */
      }
      if (cancelled) return;

      // Load ALL saved settings from localStorage
      let saved: any = {};
      try {
        saved = JSON.parse(localStorage.getItem('wbc2') || '{}');
      } catch {}

      // User's last choice (localStorage) takes precedence over backend default
      const theme = saved.accentTheme || themeFromBackend || DEFAULT_ACCENT_THEME;
      const custom = saved.customColor || '';

      setAccentTheme(theme as AccentTheme);
      if (custom) setCustomColor(custom);
      setAssistantName(saved.assistantName || identityFromBackend.assistant_name || 'DEEP-OS');
      setUserName(saved.userName || identityFromBackend.user_name || '');
      setVoiceName(saved.voiceName || identityFromBackend.voice || 'Charon');
      if (saved.prov) setProv(saved.prov);
      if (saved.model) setModel(saved.model);
      if (saved.mood) setMood(saved.mood);
      if (saved.temp !== undefined) setTemp(saved.temp);
      setSysPr(saved.sysPr || sysPrFromBackend);
      if (saved.snd !== undefined) setSnd(saved.snd);
      if (saved.bright !== undefined) setBright(saved.bright);
      if (saved.fsize !== undefined) setFsize(saved.fsize);
      if (saved.voicePreset) setVoicePreset(saved.voicePreset);
      if (saved.jarvisRate !== undefined) setJarvisRate(saved.jarvisRate);
      if (saved.voicePitch !== undefined) setVoicePitch(saved.voicePitch);
      if (saved.apiKey) setApiKey(saved.apiKey);
      if (saved.orApiKey) setOrApiKey(saved.orApiKey);
      if (saved.groqApiKey) setGroqApiKey(saved.groqApiKey);
      if (saved.openaiApiKey) setOpenaiApiKey(saved.openaiApiKey);
      if (saved.geminiApiKey) setGeminiApiKey(saved.geminiApiKey);
      if (saved.mimoApiKey) setMimoApiKey(saved.mimoApiKey);
      if (saved.nvidiaApiKey) setNvidiaApiKey(saved.nvidiaApiKey);

      if (!cancelled) setInitDone(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Welcome message — reflects current provider/model after init
  useEffect(() => {
    if (!initDone) return;
    // Removida a mensagem inicial de "Pronto. Mimo..." a pedido do usuario
  }, [initDone]);

  useEffect(() => {
    if (!initDone) return;
    // Merge with existing localStorage to preserve extended settings (agent/developer/display)
    let existing: any = {};
    try {
      existing = JSON.parse(localStorage.getItem('wbc2') || '{}');
    } catch {}
    localStorage.setItem(
      'wbc2',
      JSON.stringify({
        ...existing,
        prov,
        model,
        mood,
        temp,
        sysPr,
        snd,
        bright,
        fsize,
        voicePreset,
        jarvisRate,
        voicePitch,
        apiKey,
        orApiKey,
        groqApiKey,
        openaiApiKey,
        geminiApiKey,
        nvidiaApiKey,
        accentTheme,
        assistantName,
        userName,
        voiceName,
      }),
    );
  }, [
    initDone,
    prov,
    model,
    mood,
    temp,
    sysPr,
    snd,
    bright,
    fsize,
    voicePreset,
    jarvisRate,
    voicePitch,
    apiKey,
    orApiKey,
    groqApiKey,
    openaiApiKey,
    geminiApiKey,
    nvidiaApiKey,
    accentTheme,
    assistantName,
    userName,
    voiceName,
  ]);

  // Sync accent theme to backend config.yaml whenever it changes
  useEffect(() => {
    if (!initDone) return;
    fetch(`${API_BASE}/api/config/accent-theme`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme: accentTheme }),
    }).catch(() => {});
  }, [initDone, accentTheme]);

  // Carrega estado da GPU do backend
  useEffect(() => {
    if (!initDone) return;
    fetch(`${API_BASE}/ollama/gpu`)
      .then((r) => r.json())
      .then((d) => {
        if (d.gpu_enabled !== undefined) setGpuEnabled(d.gpu_enabled);
      })
      .catch(() => {});
    // Carrega config do Charon toolset
    fetch(`${API_BASE}/api/config/voice`)
      .then((r) => r.json())
      .then((d) => {
        if (d.charon_toolset !== undefined) setCharonFullTools(d.charon_toolset);
      })
      .catch(() => {});
  }, [initDone]);

  // Sincroniza toggle GPU com backend (Ollama + Llamacpp)
  useEffect(() => {
    if (!initDone) return;
    // Salvar no Ollama
    fetch(`${API_BASE}/ollama/gpu`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gpu_enabled: gpuEnabled, gpu_layers: -1 }),
    }).catch(() => {});
    // Salvar no Llamacpp
    fetch(`${API_BASE}/llamacpp/gpu`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gpu_enabled: gpuEnabled, gpu_layers: 999 }),
    }).catch(() => {});
  }, [initDone, gpuEnabled]);

  // Apply accent theme CSS variables
  useEffect(() => {
    try {
      applyAccentTheme(accentTheme, customColor);
    } catch (e) {
      console.warn('Nao foi possivel aplicar o tema de destaque', e);
    }
  }, [accentTheme, customColor]);

  // Atualiza a variável CSS global quando o tamanho da fonte mudar
  useEffect(() => {
    try {
      document.documentElement.style.setProperty('--base-font-size', `${fsize}px`);
    } catch (e) {
      // não bloqueia a aplicação se falhar
      console.warn('Não foi possível aplicar --base-font-size', e);
    }
  }, [fsize]);

  useEffect(() => {
    fetchHist();
    // Tenta workspace API primeiro, fallback para /status
    const tryFetchRoot = (attempt = 0) => {
      fetch(`${API_BASE}/api/workspace`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.workspace) {
            setExpRoot(data.workspace);
            loadDir('', data.workspace);
            return;
          }
          // Fallback: /status
          return fetch(`${API_BASE}/status`).then((r) => r.json());
        })
        .then((d) => {
          if (d?.base_dir && !localStorage.getItem('wbc2_expRoot')) {
            setExpRoot(d.base_dir);
            loadDir('', d.base_dir);
          }
        })
        .catch(() => {
          if (attempt < 10) setTimeout(() => tryFetchRoot(attempt + 1), 1000);
        });
    };
    tryFetchRoot();
  }, []);

  useEffect(() => {
    setSoundEnabled(snd);
  }, [snd]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
        setHelpOpen(false);
      }
    };
    if (helpOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [helpOpen]);

  useEffect(() => {
    if (prov === 'ollama') {
      fetch(`${API_BASE}/ollama/status`)
        .then((r) => r.json())
        .then((d) => {
          setOllSt(d);
          // Apenas modelos Ollama instalados
          if (d.running && d.models?.length) {
            setOModels(d.models.map((m: string) => ({ value: m, label: m })));
          }
        })
        .catch(() => {});
    }
    if (prov === 'llamacpp') {
      fetch(`${API_BASE}/llamacpp/models`)
        .then((r) => r.json())
        .then((d) => {
          if (d.models?.length) {
            setLlamacppModels(d.models.map((m: any) => ({
              value: m.id,
              label: m.available ? `${m.label}${m.has_vision ? ' 👁️' : ''}` : `${m.label} (não encontrado)`,
              available: m.available,
              has_vision: m.has_vision,
            })));
          }
        })
        .catch(() => {});
    }
    if (prov === 'openrouter' && orApiKey) {
      fetch(`${API_BASE}/openrouter/models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: orApiKey }),
      })
        .then((r) => r.json())
        .then((d) => {
          if (d.models?.length) setOrModels(d.models);
        })
        .catch(() => {});
    }
  }, [prov, orApiKey]);

  // ─── API helpers ──────────────────────────────────────────────────────
  const fetchHist = async () => {
    try {
      const r = await fetch(`${API_BASE}/history`);
      if (r.ok) setHistItens((await r.json()).history || []);
    } catch {}
  };

  const loadHist = async (id: number) => {
    try {
      const r = await fetch(`${API_BASE}/history`);
      if (!r.ok) return;
      const data = await r.json();
      const all: HistItem[] = data.history || [];
      const item = all.find((h: HistItem) => h.id === id);
      if (!item) return;
      const ts = new Date(item.created_at).toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
      });
      setMsgs([
        { from: 'user', text: item.question, time: ts },
        { from: 'bot', text: isInternalJson(item.answer) ? '' : stripInternalJson(item.answer), time: ts },
      ]);
    } catch {}
  };

  const delHist = async (id: number) => {
    try {
      await fetch(`${API_BASE}/history/${id}`, { method: 'DELETE' });
      fetchHist();
    } catch {}
  };

  const loadDir = (dirPath: string, rootOverride?: string) => {
    setCurrentDir(dirPath);
    const p = new URLSearchParams();
    p.set('path', dirPath);
    const root = rootOverride ?? expRoot;
    if (root) p.set('root', root);
    fetch(`${API_BASE}/explorer?${p}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.type === 'directory') setExpTree(d.items || []);
      })
      .catch(() => {});
  };

  const refreshExplorer = (root?: string) => {
    const base = root || expRoot;
    if (!base) return;
    loadDir(currentDir || '');
  };

  const toggleDir = (path: string) => {
    setExpPath((prev) => [...prev, path]);
    loadDir(path);
  };

  const goUpDir = () => {
    if (!currentDir) return;
    const parent = currentDir.split(/[\\/]/).slice(0, -1).join('/');
    if (!parent || parent === currentDir) {
      // Volta pra raiz
      setCurrentDir('');
      loadDir('');
    } else {
      setExpPath((prev) => prev.slice(0, -1));
      loadDir(parent);
    }
  };

  const saveFile = async (tabId: string): Promise<boolean> => {
    const tab = tabs.find((t) => t.id === tabId);
    if (!tab) return false;
    try {
      const resp = await fetch(`${API_BASE}/explorer/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: tab.path, content: tab.content, root: expRoot }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setTabs((prev) => prev.map((t) => (t.id === tabId ? { ...t, dirty: false } : t)));
      // Refresh explorer apos salvar
      setTimeout(() => refreshExplorer(), 300);
      return true;
    } catch (e: any) {
      alert(`Erro ao salvar: ${e.message}`);
      return false;
    }
  };

  const saveCurrentFile = () => {
    if (activeTab) saveFile(activeTab);
  };

  const setTabContent = (id: string, content: string) => {
    setTabs((prev) =>
      prev.map((t) =>
        t.id === id ? { ...t, content, dirty: t.content !== content ? true : t.dirty } : t,
      ),
    );
  };

  const openFile = (item: ExpItem) => {
    const path = item.path;
    const name = path.split(/[\\/]/).pop() || path;
    const fileExtension = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';

    // ── Bloquear .docx/.pdf: abrir nativamente no Windows ──────────────
    if (fileExtension === 'docx' || fileExtension === 'pdf') {
      const fullUrl = `${API_BASE}/api/explorer/open-external?path=${encodeURIComponent(path)}&root=${encodeURIComponent(expRoot)}`;
      fetch(fullUrl).catch(() => {});
      return;
    }

    const tabId = `file::${path}`;
    if (tabs.find((t) => t.id === tabId)) {
      setActiveTab(tabId);
      setView('file');
      return;
    }
    const p = new URLSearchParams();
    p.set('path', path);
    if (expRoot) p.set('root', expRoot);
    fetch(`${API_BASE}/explorer/read?${p}`)
      .then((r) => r.json())
      .then((d) => {
        const content = d.type === 'text' ? d.content : '[Arquivo binário]';
        const name = path.split(/[\\/]/).pop() || path;
        const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
        setTabs((prev) => [...prev, { id: tabId, name, path, content, ext, dirty: false }]);
        setActiveTab(tabId);
        setView('file');
      })
      .catch((e: any) => {
        const name = path.split(/[\\/]/).pop() || path;
        setTabs((prev) => [
          ...prev,
          { id: tabId, name, path, content: `[Erro: ${e.message}]`, ext: 'err' },
        ]);
        setActiveTab(tabId);
        setView('file');
      });
  };

  const closeTab = async (id: string) => {
    const tab = tabs.find((t) => t.id === id);
    if (tab?.dirty) {
      const confirm = window.confirm(`"${tab.name}" foi alterado. Deseja salvar antes de fechar?`);
      if (confirm) {
        const saved = await saveFile(id);
        if (!saved) return; // Se falhou ao salvar, nao fecha
      }
    }
    setTabs((prev) => {
      const next = prev.filter((t) => t.id !== id);
      if (activeTab === id) {
        setActiveTab(next.length ? next[next.length - 1].id : null);
        if (!next.length) setView('page');
      }
      return next;
    });
  };

  // ─── Chat ─────────────────────────────────────────────────────────────
  const projectLabel = useMemo(() => {
    if (!expRoot) return 'projeto';
    const parts = expRoot.split(/[\\/]/).filter(Boolean);
    return parts[parts.length - 1] || 'projeto';
  }, [expRoot]);

  const newChat = () => {
    setMsgs([]);
    setStream('');
    setThink('');
    setThinkOn(false);
    setLogs([]);
    setChecklistSteps([]);
  };

  const stopGen = () => {
    console.log('[App] stopGen called, abortRef:', abortRef.current);
    abortRef.current?.abort();
    setLoading(false);
    // Parar llama-server no backend se provider for llamacpp
    if (prov === 'llamacpp') {
      fetch(`${API_BASE}/llamacpp/stop`, { method: 'POST' }).catch(() => {});
    }
  };

  const send = async (text?: string, images?: string[]) => {
    const fm = text ?? input;
    if (!fm.trim() && (!images || images.length === 0)) return;

    // Clear pending tool confirmation if user sends a regular message
    if (!fm.startsWith('/approve-tool') && !fm.startsWith('/reject-tool')) {
      setPendingToolConfirm(null);
    }

    // Detecta "continue" e reusa o task_id anterior
    const isContinue = fm.trim().toLowerCase() === 'continue' && taskIdRef.current;
    const effectiveTaskId = isContinue ? taskIdRef.current : '';

    // Valida chave de API antes de enviar (para providers que exigem)
    if (prov !== 'ollama') {
      const keyToSend =
        prov === 'opencode'
          ? apiKey
          : prov === 'openclaude'
            ? apiKey || orApiKey
            : prov === 'openrouter'
              ? orApiKey
              : prov === 'groq'
                ? groqApiKey
                : prov === 'openai'
                  ? openaiApiKey
                  : prov === 'gemini'
                    ? geminiApiKey
                    : prov === 'nvidia'
                      ? nvidiaApiKey
                      : '__backend_env__';
      if (!keyToSend) {
        setMsgs((c) => [
          ...c,
          {
            from: 'bot',
            text: `⚠️ Provedor "${prov}" precisa de chave de API.\nCrie o arquivo backend/.env com a chave ou troque para "ollama".`,
            time: Date.now(),
          },
        ]);
        return;
      }
    }

    // Don't show internal commands in chat
    if (!fm.startsWith('/approve-plan') && !fm.startsWith('/reject-plan')) {
      const msg: Msg = { from: 'user', text: fm, time: Date.now() };
      if (images && images.length > 0) msg.images = images;
      setMsgs((c) => [...c, msg]);
    }
    setInput('');

    // Se ja esta processando, adicionar na fila local
    if (loading) {
      messageQueueRef.current.push({ text: fm, images });
      setMsgs((c) => [
        ...c,
        {
          from: 'bot',
          text: `📋 Mensagem enfileirada (${messageQueueRef.current.length} na fila)`,
          time: Date.now(),
        },
      ]);
      return;
    }

    setLoading(true);
    setStream('');
    setThink('');
    setThinkOn(false);
    setLogs([]);
    setChecklistSteps([]);
    setThinkOpen(true);
    playSound('agent_thinking');
    // Incrementar geração para descartar eventos da requisição antiga
    const thisGeneration = ++generationRef.current;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    let full = '';
    try {
      // Store original text for plan approval flow
      if (!isContinue && !planTaskIdRef.current) {
        planOrigTextRef.current = fm;
      }

      const bodyData: any = {
        user: isContinue ? 'continue' : fm,
        provider: prov,
        model,
        mood,
        temperature: temp,
        system_prompt: sysPr,
        root: expRoot,
        path: expPath.join('/'),
        api_key:
          prov === 'opencode'
            ? apiKey
            : prov === 'openclaude'
              ? apiKey || orApiKey
              : prov === 'openrouter'
                ? orApiKey
                : prov === 'groq'
                  ? groqApiKey
                  : prov === 'openai'
                    ? openaiApiKey
                    : prov === 'gemini'
                      ? geminiApiKey
                      : prov === 'mimo'
                        ? mimoApiKey
                        : prov === 'nvidia'
                          ? nvidiaApiKey
                          : '',
        task_id: effectiveTaskId,
        mode: 'auto',
        plan_strategy: 'never',
        images: images || [],
        session_id: sessionIdRef.current,
      };
      // If this is a plan approval re-send, set the flag
      if (planTaskIdRef.current && fm.startsWith('/approve-plan')) {
        bodyData.plan_approved = true;
        bodyData.task_id = planTaskIdRef.current;
      }
      const resp = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        signal: ctrl.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyData),
      });
      if (resp.status === 401)
        throw new Error('Autenticacao falhou (401). Verifique a chave de API no backend/.env');
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            // Descartar eventos de requisições anteriores
            if (thisGeneration !== generationRef.current) return;
            if (ev.type === 'plan') {
              if (ev.auto_executed) {
                // LOW plans execute silently — no toast or plan card
              } else {
                // Store plan info for approval
                planTaskIdRef.current = ev.task_id || '';
                planOrigTextRef.current = '';
                // Add plan message to chat (will be rendered by PlanMessage inline)
                const nowStr = new Date().toLocaleTimeString('pt-BR', {
                  hour: '2-digit',
                  minute: '2-digit',
                });
                setMsgs((c) => [
                  ...c,
                  {
                    from: 'bot',
                    text: '📋 Plano de execução aguardando aprovação.',
                    time: nowStr,
                    planData: ev.data,
                    planTaskId: ev.task_id || '',
                    planStatus: 'pending',
                  },
                ]);
                setLoading(false);
                setStream('');
                return;
              }
            }
            if (ev.type === 'thinking_start') setThinkOn(true);
            else if (ev.type === 'thinking') {
              setThinkOn(true);
              setThink(ev.content || '');
            } else if (ev.type === 'token') {
              full += ev.content || '';
              setStream(voiceModeRef.current ? stripInternalJson(full) : full);
            } else if (ev.type === 'tool_start') {
              const logId = `${ev.tool}_${Date.now()}`;
              setLogs((p) => [...p, { id: logId, tool: ev.tool, status: 'running', params: ev.params, startedAt: Date.now() }]);
              const toolParams = ev.params || {};
              const paramStr = Object.values(toolParams).slice(0, 1).join('') || '';
              setStream(`> ${ev.tool}(${paramStr.length > 60 ? paramStr.slice(0, 60) + '...' : paramStr})`);
              if (planTaskIdRef.current) {
                setMsgs((c) =>
                  c.map((m) =>
                    m.planTaskId === planTaskIdRef.current
                      ? { ...m, planStatus: 'executing' as const }
                      : m,
                  ),
                );
              }
            } else if (ev.type === 'tool_end') {
              const endedAt = Date.now();
              setLogs((p) => {
                const idx = [...p].reverse().findIndex((l) => l.tool === ev.tool && l.status === 'running');
                if (idx === -1) return p;
                const realIdx = p.length - 1 - idx;
                const next = [...p];
                const startedAt = next[realIdx].startedAt || endedAt;
                next[realIdx] = {
                  ...next[realIdx],
                  status: ev.result?.error ? 'error' : 'done',
                  result: ev.result,
                  endedAt,
                  duration: endedAt - startedAt,
                };
                return next;
              });
              // NÃO setStream('') aqui — evita que o auto-speak dispare a cada ferramenta
              // O stream será limpo apenas no evento 'done' final
            } else if (ev.type === 'tool_error')
              setLogs((p) => [
                ...p,
                { tool: 'erro', status: 'error', result: { error: ev.error } },
              ]);
            else if (ev.type === 'tool_confirm') {
              setPendingToolConfirm({
                confirmId: ev.confirm_id,
                tool: ev.tool,
                label: ev.label,
                risk_level: ev.risk_level || 'high',
                params: ev.params || {},
                taskId: ev.task_id || '',
              });
              if (ev.task_id) taskIdRef.current = ev.task_id;
              setMsgs((c) => [
                ...c,
                {
                  from: 'bot',
                  text: `⚠️ Ação "${ev.label}" requer confirmação`,
                  time: Date.now(),
                },
              ]);
            } else if (ev.type === 'queued') {
              // Mensagem enfileirada - processamento anterior em andamento
              setMsgs((c) => [
                ...c,
                {
                  from: 'bot',
                  text: `📋 ${ev.message || 'Mensagem enfileirada'}`,
                  time: Date.now(),
                },
              ]);
              // Manter loading ativo e esperar
            } else if (ev.type === 'task_checklist') {
              setChecklistSteps(ev.steps || []);
            } else if (ev.type === 'task_progress') {
              const idx = ev.step_index as number;
              const st = ev.status as string;
              setChecklistSteps((prev) => {
                if (idx < 0 || idx >= prev.length) return prev;
                const next = [...prev];
                next[idx] = { ...next[idx], status: st };
                return next;
              });
            } else if (ev.type === 'action') {
              // AI action commands for media player, explorer, etc.
              const act = ev.action as string;
              const payload = ev.payload || {};
              if (act === 'media_play') {
                // Show dialog to choose where to play
                setMediaPlayDialog({
                  fileName: payload.name || '',
                  isVideo: payload.isVideo || false,
                  filePath: payload.path || payload.url || '',
                });
              } else if (act === 'media_pause' && musicPlayerRef.current) {
                musicPlayerRef.current.playPause();
              } else if (act === 'media_next' && musicPlayerRef.current) {
                musicPlayerRef.current.next();
              } else if (act === 'media_prev' && musicPlayerRef.current) {
                musicPlayerRef.current.prev();
              } else if (act === 'media_stop' && musicPlayerRef.current) {
                musicPlayerRef.current.stop();
                showToast('Reproducao parada', 'info');
              } else if (act === 'media_list') {
                const tracks = musicPlayerRef.current?.getTracks() || [];
                // Send back to next AI turn
                const listText = tracks.length > 0
                  ? tracks.map((t, i) => `${i + 1}. ${t.isVideo ? '[VIDEO]' : '[AUDIO]'} ${t.name}`).join('\n')
                  : 'Nenhuma midia carregada no player.';
                showToast(`Musicas: ${tracks.length} arquivos`, 'info');
              } else if (act === 'explorer_cd') {
                if (payload.path) {
                  setExpRoot(payload.path);
                  loadDir(payload.path);
                  showToast(`Navegando: ${payload.path}`, 'info');
                }
              } else if (act === 'open_file') {
                if (payload.path) {
                  // Check if it's a media file
                  const ext = payload.path.split('.').pop()?.toLowerCase() || '';
                  const isMedia = /\.(mp3|wav|ogg|flac|m4a|aac|mp4|wmv|avi|mkv|webm|mov)$/i.test(ext);
                  if (isMedia) {
                    // Show dialog for media files
                    const name = payload.path.split(/[\\/]/).pop() || payload.path;
                    const isVideo = /\.(mp4|wmv|avi|mkv|webm|mov)$/i.test(ext);
                    setMediaPlayDialog({
                      fileName: name,
                      isVideo,
                      filePath: payload.path,
                    });
                  } else {
                    openFile({ path: payload.path } as any);
                    showToast(`Abrindo: ${payload.path}`, 'info');
                  }
                }
              } else if (act === 'run_terminal') {
                if (payload.command) {
                  setTermOpen(true);
                  showToast(`Terminal: ${payload.command}`, 'info');
                }
              }
            } else if (ev.type === 'done') {
              full = ev.answer || full;
              // Salva o raciocinio antes de limpar (para preservar quando Jarvis off)
              const savedThinking = thinking;
              setThinkOn(false);
              setChecklistSteps((prev) => {
                if (prev.length === 0) return prev;
                const total = prev.length;
                return prev.map((step) => ({ ...step, status: 'done' }));
              });
              // Skip adding message if this is a pending tool confirmation
              if (ev.pending_confirm) {
                setLoading(false);
              } else if (planTaskIdRef.current) {
                playSound('agent_success');
                setMsgs((c) =>
                  c.map((m) =>
                    m.planTaskId === planTaskIdRef.current
                      ? { ...m, planStatus: 'done' as const }
                      : m,
                  ),
                );
                planTaskIdRef.current = '';
              } else {
                playSound('agent_success');
                // Quando Jarvis off: mostra raciocinio completo. Quando on: mostra so resumo
                const displayText = voiceModeRef.current ? stripInternalJson(full) : full;
                setMsgs((c) => [
                  ...c,
                  {
                    from: 'bot',
                    text: displayText || '(resposta vazia)',
                    time: Date.now(),
                    // Salva raciocinio apenas quando Jarvis esta desativado
                    thinking: !voiceModeRef.current && savedThinking ? savedThinking : undefined,
                  },
                ]);
              }
              // setStream DEPOIS de setMsgs para o auto-speak detectar a mensagem nova
              setStream('');
              fetchHist();
              // Salva task_id para continuar depois
              if (ev.task_id) taskIdRef.current = ev.task_id;
              else taskIdRef.current = '';
              // Refresh no explorador apos qualquer resposta (captura mudancas de arquivos)
              setTimeout(() => refreshExplorer(), 400);
            } else if (ev.type === 'error') {
              setLoading(false);
              const isLoop = ev.message?.toLowerCase().includes('loop');
              setMsgs((c) => [
                ...c,
                {
                  from: 'bot',
                  text: `! ${ev.message || 'Erro'}`,
                  time: Date.now(),
                  isLoopError: isLoop,
                },
              ]);
              setStream('');
            }
          } catch {}
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError')
        setMsgs((c) => [...c, { from: 'bot', text: `! ${e.message}`, time: Date.now() }]);
    } finally {
      // Só limpar estado se ainda estamos na mesma geração
      if (thisGeneration === generationRef.current) {
        setLoading(false);
        setStream('');
        setThinkOn(false);

        // Processar proxima mensagem da fila
        if (messageQueueRef.current.length > 0) {
          const next = messageQueueRef.current.shift()!;
          setTimeout(() => send(next.text, next.images), 100);
        }
      }
      if (thisGeneration === generationRef.current) {
        abortRef.current = null;
      }
    }
  };

  const analyzeFile = (tab: FileTab) =>
    send(
      `[Arquivo: ${tab.path}]\n\n\`\`\`${tab.ext}\n${tab.content.slice(0, 4000)}\n\`\`\`\n\nAnalise este arquivo:`,
    );

  // ─── Terminal ─────────────────────────────────────────────────────────
  // ─── Memo ─────────────────────────────────────────────────────────────
  const curTab = view === 'file' ? tabs.find((t) => t.id === activeTab) : undefined;

  // ─── Drag resize ──────────────────────────────────────────────────────
  useEffect(() => {
    let rafId = 0;
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      if (rafId) return; // throttled — skip frame if one is already pending
      rafId = requestAnimationFrame(() => {
        rafId = 0;
        if (dragging.current === 'exp') setExpW(Math.max(160, Math.min(400, e.clientX)));
        else if (dragging.current === 'chat-charon') {
          const charonW = Math.max(200, Math.min(window.innerWidth - e.clientX, 600));
          setChatW(charonW);
        }
        else if (dragging.current === 'chat-h')
          setChatH(
            Math.max(
              200,
              Math.min(window.innerHeight - 32 - 24, window.innerHeight - e.clientY - 24),
            ),
          );
      });
    };
    const onUp = () => {
      if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
      dragging.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  // Responsivo: ajusta larguras iniciais baseado no tamanho da tela (so se nao houver layout salvo)
  useEffect(() => {
    if (!initDone) return;
    try {
      const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}');
      if (typeof saved.expW === 'number' || typeof saved.chatW === 'number') return;
    } catch {}
    const w = window.innerWidth;
    if (w < 900) {
      setExpW(180);
      setChatW(Math.max(320, Math.round(w * 0.4)));
    } else if (w < 1200) {
      setExpW(200);
      setChatW(Math.max(360, Math.round(w * 0.35)));
    }
  }, [initDone]);

  // ─── Keyboard shortcuts ──────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey) {
        switch (e.key.toLowerCase()) {
          case 'n':
            e.preventDefault();
            newChat();
            showToast('Novo chat criado', 'success');
            break;
          case 't':
            e.preventDefault();
            setTermOpen((prev) => !prev);
            showToast(termOpen ? 'Terminal fechado' : 'Terminal aberto', 'info');
            break;
          case 's':
            e.preventDefault();
            saveCurrentFile();
            showToast('Arquivo salvo', 'success');
            break;
        }
      }
      if (e.key === 'Escape' && loading) {
        e.preventDefault();
        stopGen();
        showToast('Geração cancelada', 'info');
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !loading) {
        e.preventDefault();
        send();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const drag = (which: 'exp' | 'chat' | 'chat-h' | 'chat-charon') => (e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = which;
    document.body.style.cursor =
      which === 'chat-h' ? 'row-resize' : 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const DragH = (dir: 'h' | 'v', onDown: (e: React.MouseEvent) => void) => (
    <div onMouseDown={onDown} className={dir === 'h' ? 'drag-handle-h' : 'drag-handle-v'} />
  );

  // ─── Plan Mode Handlers ──────────────────────────────────────────────
  const handleApprovePlan = (taskId: string) => {
    if (!taskId) return;
    // Update message status
    setMsgs((c) =>
      c.map((m) => (m.planTaskId === taskId ? { ...m, planStatus: 'approved' as const } : m)),
    );
    // Send approval as new message
    setInput('');
    planTaskIdRef.current = taskId;
    send(`/approve-plan ${taskId}`);
  };

  const handleRejectPlan = (taskId: string) => {
    if (!taskId) return;
    // Update message status
    setMsgs((c) =>
      c.map((m) => (m.planTaskId === taskId ? { ...m, planStatus: 'rejected' as const } : m)),
    );
    planTaskIdRef.current = '';
    showToast('Plano rejeitado', 'error');
  };

  const handleCancelPlan = () => {
    setPlanData(null);
    planTaskIdRef.current = '';
    planOrigTextRef.current = '';
  };

  const handleApproveTool = () => {
    if (!pendingToolConfirm) return;
    const { taskId } = pendingToolConfirm;
    setPendingToolConfirm(null);
    setInput('');
    send(`/approve-tool ${taskId}`);
  };

  const handleRejectTool = () => {
    if (!pendingToolConfirm) return;
    const { taskId, tool } = pendingToolConfirm;
    setPendingToolConfirm(null);
    showToast(`Ação "${tool}" rejeitada`, 'info');
    send(`/reject-tool ${taskId}`);
  };

  // ─── Media Play Handlers ──────────────────────────────────────────────
  const handleMediaInternalPlay = () => {
    if (!mediaPlayDialog) return;
    if (musicPlayerRef.current) {
      const fd = mediaPlayDialog;
      if (fd.filePath && fd.filePath.startsWith('http')) {
        // URL online - adiciona direto
        musicPlayerRef.current.addByUrl(fd.fileName, fd.filePath, fd.isVideo);
        musicPlayerRef.current.playFile(fd.fileName);
      } else if (fd.filePath) {
        // Arquivo local - converte para URL via backend
        const streamUrl = `${API_BASE}/api/media/stream?path=${encodeURIComponent(fd.filePath)}&root=${encodeURIComponent(expRoot)}`;
        musicPlayerRef.current.addByUrl(fd.fileName, streamUrl, fd.isVideo);
        musicPlayerRef.current.playFile(fd.fileName);
      }
      showToast(`Tocando no player interno: ${fd.fileName}`, 'info');
    }
    setMediaPlayDialog(null);
  };

  const handleMediaExternalPlay = () => {
    if (!mediaPlayDialog) return;
    // Open file with system default player via backend API
    if (mediaPlayDialog.filePath && !mediaPlayDialog.filePath.startsWith('http')) {
      fetch(`${API_BASE}/api/explorer/open-external?path=${encodeURIComponent(mediaPlayDialog.filePath)}&root=${encodeURIComponent(expRoot)}`)
        .then(() => showToast(`Abrindo no reprodutor padrão: ${mediaPlayDialog.fileName}`, 'info'))
        .catch(() => showToast('Erro ao abrir arquivo', 'error'));
    } else if (mediaPlayDialog.filePath && mediaPlayDialog.filePath.startsWith('http')) {
      // For URLs, open in browser
      window.open(mediaPlayDialog.filePath, '_blank');
      showToast(`Abrindo no navegador: ${mediaPlayDialog.fileName}`, 'info');
    } else {
      showToast('Caminho do arquivo não disponível', 'error');
    }
    setMediaPlayDialog(null);
  };

  const handleMediaCancel = () => {
    setMediaPlayDialog(null);
  };

  // ─── JSX ──────────────────────────────────────────────────────────────
  const safeBright = Math.max(20, Math.min(150, bright));

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg)',
        color: 'var(--ink)',
        display: 'flex',
        flexDirection: 'column',
        filter: `brightness(${safeBright}%)`,
        fontSize: `${fsize}px`,
        fontFamily: 'inherit',
      }}
    >
      {/* TOP BAR */}
      <div
        style={{
          height: 32,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 14px',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', flexShrink: 0 }}>
            ◈
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--accent)',
              flexShrink: 0,
              letterSpacing: '0.3px',
            }}
          >
            {projectLabel}
          </span>
          {expRoot && (
            <>
              <span style={{ fontSize: 10, color: 'var(--quiet)' }}>/</span>
              <span
                style={{
                  fontSize: 11,
                  color: 'var(--muted)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: 300,
                }}
                title={expRoot}
              >
                {projectLabel}
              </span>
            </>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <MiniMonitors />
          <div ref={helpRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setHelpOpen((p) => !p)}
              style={{
                background: helpOpen ? 'var(--accent-soft)' : 'transparent',
                border: '1px solid var(--line)',
                borderRadius: 4,
                padding: '3px 10px',
                fontSize: 11,
                color: 'var(--muted)',
                cursor: 'pointer',
                fontFamily: 'inherit',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              ❔ Ajuda
            </button>
            {helpOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: 6,
                  width: 400,
                  maxHeight: '80vh',
                  overflowY: 'auto',
                  background: 'var(--bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 6,
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  zIndex: 1000,
                  padding: '16px 18px',
                  color: 'var(--ink)',
                  fontSize: 12,
                  lineHeight: 1.6,
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12, color: 'var(--accent)' }}>
                  DEEP-OS — Guia Completo
                </div>

                {/* Helper para seção colapsável */}
                {(() => {
                  const sections: { key: string; title: string; color: string; items: JSX.Element }[] = [
                    {
                      key: 'chat', title: 'COMANDOS DE CHAT', color: 'var(--cyan)',
                      items: <>
                        {[
                          ['/goal <texto>', 'Definir objetivo de longo prazo'],
                          ['/run <comando>', 'Executar comando no terminal'],
                          ['/clear', 'Limpar contexto da conversa'],
                          ['/status', 'Ver status do sistema'],
                          ['/stop', 'Parar execucao atual'],
                          ['/help', 'Mostrar esta ajuda'],
                          ['/review', 'Revisao de codigo'],
                          ['/build', 'Build do projeto'],
                          ['/test', 'Executar testes'],
                          ['/deploy', 'Deploy da aplicacao'],
                          ['/logs', 'Ver logs do sistema'],
                          ['/cancel', 'Cancelar tarefa'],
                        ].map(([cmd, desc]) => (
                          <div key={cmd} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--accent)', fontFamily: 'monospace', minWidth: 160, whiteSpace: 'nowrap' }}>{cmd}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'voice', title: 'COMANDOS DE VOZ (PT-BR)', color: 'var(--green, #4caf50)',
                      items: <>
                        {[
                          ['"novo contexto"', 'Limpar conversa atual'],
                          ['"limpar contexto"', 'Limpar conversa atual'],
                          ['"limpa tudo"', 'Limpar tudo'],
                          ['"parar" / "cancelar"', 'Interromper execucao'],
                          ['"ajuda" / "help"', 'Mostrar ajuda'],
                          ['"status"', 'Ver status do sistema'],
                        ].map(([cmd, desc]) => (
                          <div key={cmd} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--green, #4caf50)', fontFamily: 'monospace', minWidth: 160, whiteSpace: 'nowrap' }}>{cmd}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'media', title: 'COMANDOS DE VOZ - MIDIA', color: 'var(--yellow, #ffc107)',
                      items: <>
                        {[
                          ['"pausa" / "pausar musica"', 'Pausar reproducao'],
                          ['"retomar" / "tocar musica"', 'Continuar reproducao'],
                          ['"proxima musica"', 'Proxima faixa'],
                          ['"musica anterior"', 'Faixa anterior'],
                          ['"parar musica"', 'Parar e fechar midia'],
                          ['"tocar no media"', 'Abrir no player interno MEDIA'],
                          ['"fechar arquivo"', 'Fechar arquivo aberto'],
                          ['"fechar video"', 'Fechar video reproduzindo'],
                          ['"fechar tudo"', 'Fechar todos os arquivos'],
                        ].map(([cmd, desc]) => (
                          <div key={cmd} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--yellow, #ffc107)', fontFamily: 'monospace', fontSize: 11, minWidth: 200, whiteSpace: 'nowrap' }}>{cmd}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'charon', title: 'CHARON - ASSISTENTE DE VOZ', color: 'var(--purple, #b478ff)',
                      items: <>
                        <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5, marginBottom: 8 }}>
                          O Charon e o assistente de voz do DEEP-OS (voz natural Gemini Live).
                        </div>
                        {[
                          ['"deep ..." (ativacao)', 'Diga "deep" antes de um comando'],
                          ['Falar normalmente', 'Converse direto com o Charon'],
                          ['"criar pasta X"', 'Cria pasta via file_controller'],
                          ['"tira print da tela"', 'Salva screenshot no Desktop'],
                          ['"abre o arquivo X"', 'Abre arquivos no app padrao'],
                          ['"para de ler"', 'Interrompe a fala atual'],
                          ['"repetir"', 'Repete a ultima resposta'],
                          ['"fechar aba"', 'Fecha aba do navegador'],
                          ['Botao "charon"', 'Liga/desliga o Charon'],
                          ['Botao "T"', 'Abre/fecha painel do Charon'],
                        ].map(([cmd, desc]) => (
                          <div key={cmd} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--purple, #b478ff)', fontFamily: 'monospace', fontSize: 11, minWidth: 170, whiteSpace: 'nowrap' }}>{cmd}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'tools', title: 'FERRAMENTAS DO CHARON', color: 'var(--purple, #b478ff)',
                      items: <>
                        {[
                          ['youtube_video(query)', 'Abrir video no YouTube'],
                          ['open_app(app_name)', 'Abrir aplicativo'],
                          ['weather_report(city', 'Relatorio do tempo'],
                          ['browser_control(action)', 'Controlar navegador'],
                          ['computer_control(action)', 'Controlar PC'],
                          ['computer_settings(action)', 'Configuracoes do sistema'],
                          ['file_controller(action)', 'Gerenciar arquivos'],
                          ['code_helper(instruction)', 'Revisar codigo'],
                          ['dev_agent(instruction)', 'Agente autonomo'],
                          ['file_processor(instruction)', 'Processar arquivos'],
                          ['system_status()', 'Metricas CPU/RAM/GPU'],
                          ['reminder(date, time)', 'Agendar lembrete'],
                          ['web_search(query)', 'Pesquisar na internet'],
                          ['send_message(receiver)', 'Enviar mensagem'],
                          ['screen_process(angle)', 'Capturar tela/webcam'],
                        ].map(([func, desc]) => (
                          <div key={func} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--purple, #b478ff)', fontFamily: 'monospace', fontSize: 11, minWidth: 180, whiteSpace: 'nowrap' }}>{func}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'agents', title: 'MENCIONAR AGENTES', color: 'var(--magenta, #e040fb)',
                      items: <>
                        {[
                          ['@general', 'Assistente geral full-stack'],
                          ['@coder', 'Programador especialista'],
                          ['@architect', 'Arquiteto de software'],
                          ['@debugger', 'Especialista em debugging'],
                          ['@planner', 'Planejador de tarefas'],
                        ].map(([agent, desc]) => (
                          <div key={agent} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--magenta, #e040fb)', fontFamily: 'monospace', minWidth: 120, whiteSpace: 'nowrap' }}>{agent}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'personalize', title: 'PERSONALIZACAO', color: 'var(--accent)',
                      items: <>
                        {[
                          ['Nome do Assistente', 'Altere o nome no chat'],
                          ['Seu Nome', 'Como o assistente te chama'],
                          ['Cor da Interface', 'Cor personalizada do app'],
                          ['Voz do Charon', '8 vozes Gemini Live'],
                        ].map(([cmd, desc]) => (
                          <div key={cmd} style={{ marginBottom: 3, display: 'flex', gap: 8 }}>
                            <code style={{ color: 'var(--accent)', fontFamily: 'monospace', fontSize: 11, minWidth: 140, whiteSpace: 'nowrap' }}>{cmd}</code>
                            <span style={{ color: 'var(--muted)' }}>{desc}</span>
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'tips', title: 'DICAS', color: 'var(--cyan)',
                      items: <>
                        {[
                          'Ative "auto" para enviar por voz automaticamente',
                          'Clique no microfone para falar comandos',
                          'Use "continue" para retomar tarefa interrompida',
                          'O agente mostra checkboxes antes de executar',
                          'Mude provedor/modelo em Config',
                        ].map((tip, i) => (
                          <div key={i} style={{ marginBottom: 3, color: 'var(--muted)' }}>
                            {'\u2022'} {tip}
                          </div>
                        ))}
                      </>
                    },
                    {
                      key: 'config', title: 'CONFIGURACAO INICIAL', color: 'var(--cyan)',
                      items: <>
                        <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.6 }}>
                          <div style={{ marginBottom: 4 }}>{'\u2460'} Rode <code style={{ color: 'var(--accent)' }}>START-TOTAL.bat</code></div>
                          <div style={{ marginBottom: 4 }}>{'\u2461'} Acesse <code style={{ color: 'var(--accent)' }}>http://localhost:5175</code></div>
                          <div style={{ marginBottom: 4 }}>{'\u2462'} Configure 1 provedor em Config</div>
                          <div style={{ marginBottom: 4 }}>{'\u2463'} Teste: "ola, tudo bem?"</div>
                          <div style={{ marginBottom: 4 }}>{'\u2464'} Para voz, clique no microfone</div>
                        </div>
                      </>
                    },
                  ];

                  return sections.map(s => (
                    <div key={s.key} style={{ marginBottom: 2 }}>
                      <div
                        onClick={() => toggleHelpSection(s.key)}
                        style={{
                          fontWeight: 700, fontSize: 11, color: s.color,
                          cursor: 'pointer', padding: '4px 0', display: 'flex',
                          alignItems: 'center', gap: 6, userSelect: 'none',
                        }}
                      >
                        <span style={{ fontSize: 8, transition: 'transform 0.2s', transform: helpSections[s.key] ? 'rotate(90deg)' : 'rotate(0deg)' }}>{'\u25B6'}</span>
                        {s.title}
                      </div>
                      {helpSections[s.key] && (
                        <div style={{ paddingLeft: 12, paddingBottom: 4 }}>
                          {s.items}
                        </div>
                      )}
                    </div>
                  ));
                })()}

                <div
                  style={{
                    borderTop: '1px solid var(--line)',
                    marginTop: 12,
                    paddingTop: 10,
                    fontSize: 11,
                    color: 'var(--muted)',
                  }}
                >
                  <div style={{ marginBottom: 4 }}>
                    <b style={{ color: 'var(--ink)' }}>DEEP-OS v1.0</b> — Agent OS
                  </div>
                  <div>Desenvolvedor: Wilson Barbosa Coimbra</div>
                  <div>Copyright \u00a9 Empresa: WBC 2026</div>
                </div>
              </div>
            )}
          </div>
          <span style={{ fontSize: 10, color: 'var(--quiet)', letterSpacing: '1px' }}>
            AGENT OS v1.0
          </span>
        </div>
      </div>

      {/* ── Top Navigation Bar (VS Code style) ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg)',
          minHeight: '32px',
          flexShrink: 0,
        }}
      >
        {/* Config button - opens modal */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0', padding: '0 4px', order: -1 }}>
          <button
            onClick={() => setConfigModalOpen(true)}
            style={{
              padding: '6px 14px',
              fontSize: '11px',
              fontWeight: 600,
              border: '1px solid var(--line)',
              cursor: 'pointer',
              borderRadius: '4px',
              background: 'var(--bg-2)',
              color: 'var(--cyan)',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>\u2699</span> Config
          </button>
        </div>

        {/* Music Player */}
        <MusicPlayer ref={musicPlayerRef} />

        {/* Layout controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '0 4px' }}>
          <button
            onClick={() => setExpW(expW > 0 ? 0 : 240)}
            style={{ background: 'none', border: 'none', color: expW > 0 ? 'var(--accent)' : 'var(--muted)', cursor: 'pointer', padding: '4px 6px', fontSize: '12px' }}
            title="Toggle Explorer"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="2" width="4" height="12" rx="1" fill="none" stroke="currentColor" strokeWidth="1.2"/>
              <rect x="6" y="2" width="9" height="12" rx="1" fill="none" stroke="currentColor" strokeWidth="1.2"/>
            </svg>
          </button>
          <button
            onClick={() => setCharonPanel(!charonPanel)}
            style={{ background: 'none', border: 'none', color: charonPanel ? 'var(--accent)' : 'var(--muted)', cursor: 'pointer', padding: '4px 6px', fontSize: '12px' }}
            title="Toggle Charon"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="2" width="9" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.2"/>
              <rect x="11" y="4" width="4" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.2"/>
            </svg>
          </button>
          <div style={{ width: 1, height: 20, background: 'var(--line)', margin: '0 6px' }} />
          <button style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: '4px 6px', fontSize: '12px' }} title="Minimizar">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="7" width="10" height="1" /></svg>
          </button>
          <button style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: '4px 6px', fontSize: '12px' }} title="Maximizar">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="3" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
          </button>
          <button style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: '4px 6px', fontSize: '12px' }} title="Fechar">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M4.5 3L8 6.5L11.5 3L13 4.5L9.5 8L13 11.5L11.5 13L8 9.5L4.5 13L3 11.5L6.5 8L3 4.5L4.5 3Z" /></svg>
          </button>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* EXPLORER */}
        <div
          style={{
            width: expW,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            borderRight: '1px solid var(--line)',
            overflow: 'hidden',
            minHeight: 0,
          }}
        >
          <ExplorerPanel
            expRoot={expRoot}
            setExpRoot={setExpRoot}
            expTree={expTree}
            setExpTree={setExpTree}
            expPath={expPath}
            toggleDir={toggleDir}
            openFile={openFile}
            histItens={histItens}
            loadHist={loadHist}
            delHist={delHist}
            histSearch={histSearch}
            setHistSearch={setHistSearch}
            apiBase={API_BASE}
            currentDir={currentDir}
            goUpDir={goUpDir}
            loadDir={loadDir}
            onInjectChat={(text) => setInput(text)}
            onWorkspaceChange={async (path) => {
              try {
                const r = await fetch(`${API_BASE}/api/workspace`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ path }),
                });
                if (!r.ok) {
                  const err = await r.json();
                  alert(`Workspace inválido: ${err.detail}`);
                  return false;
                }
                localStorage.setItem('wbc2_expRoot', path);
                // Limpa o chat ao trocar de projeto para evitar confusao de contexto
                newChat();
                return true;
              } catch {
                alert('Erro ao conectar ao servidor');
                return false;
              }
            }}
          />
        </div>

        {DragH('h', drag('exp'))}

        {/* CHAT — takes remaining space */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          <ChatPanel
            msgs={msgs}
            input={input}
            setInput={setInput}
            loading={loading}
            stream={stream}
            thinking={thinking}
            thinkOn={thinkOn}
            thinkOpen={thinkOpen}
            setThinkOpen={setThinkOpen}
            toolLogs={toolLogs}
            prov={prov}
            model={model}
            setProv={setProv}
            setModel={setModel}
            oModels={oModels}
            orModels={orModels}
            llamacppModels={llamacppModels}
            curTab={curTab}
            chatW={chatW}
            send={send}
            newChat={newChat}
            stopGen={stopGen}
            analyzeFile={analyzeFile}
            voicePreset={voicePreset}
            jarvisRate={jarvisRate}
            voicePitch={voicePitch}
            voiceMode={voiceMode}
            setVoiceMode={setVoiceMode}
            charonActive={charonActive}
            onConfirmPlan={handleApprovePlan}
            onRejectPlan={handleRejectPlan}
            pendingToolConfirm={pendingToolConfirm}
            onApproveTool={handleApproveTool}
            onRejectTool={handleRejectTool}
            checklistSteps={checklistSteps}
            assistantName={assistantName}
          />
        </div>

        {/* DRAG HANDLE - Chat/Charon */}
        {charonPanel && (
          <div
            onMouseDown={drag('chat-charon')}
            className="drag-handle-h"
          />
        )}

        {/* CHARON PANEL (right side) */}
        {charonPanel && (
          <div
            style={{
              width: chatW,
              flexShrink: 0,
              display: 'flex',
              flexDirection: 'column',
              borderLeft: '1px solid var(--line)',
              background: 'var(--bg)',
              overflow: 'hidden',
              minHeight: 0,
            }}
          >
            <CharonPanel
              visible={charonPanel}
              onClose={() => {
                if (!charonActive) {
                  setCharonPanel(false);
                }
              }}
              transcripts={charonTranscripts}
              voiceName={voiceName}
              voiceStatus={charonVoiceStatus}
              onSendText={(text) => {
                setCharonTranscripts(prev => [...prev, { speaker: 'user', text, time: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }]);
                charonSendTextRef.current?.(text);
              }}
            />
          </div>
        )}
      </div>

      {/* STATUS BAR */}
      <StatusBar
        prov={prov}
        model={model}
        mood={mood}
        ollSt={ollSt}
        termOpen={termOpen}
        setTermOpen={setTermOpen}
        thinkOpen={thinkOpen}
        setThinkOpen={setThinkOpen}
        charonPanel={charonPanel}
        setCharonPanel={setCharonPanel}
        charonActive={charonActive}
        voiceName={voiceName}
        onCharonActive={setCharonActive}
        onCharonVoiceStatus={setCharonVoiceStatus}
        onCharonToolResult={handleCharonToolResult}
        onCharonTranscriptFull={(speaker, text) => {
          setCharonTranscripts(prev => [...prev, { speaker, text, time: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }]);
        }}
        onCharonSendText={(fn) => { charonSendTextRef.current = fn; }}
        stopGen={stopGen}
        loading={loading}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <ToastContainer />

      {/* Media Play Dialog */}
      {mediaPlayDialog && (
        <MediaPlayDialog
          fileName={mediaPlayDialog.fileName}
          isVideo={mediaPlayDialog.isVideo}
          onInternalPlay={handleMediaInternalPlay}
          onExternalPlay={handleMediaExternalPlay}
          onCancel={handleMediaCancel}
        />
      )}

      {/* Config Modal */}
      <ConfigModal
        open={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
        prov={prov}
        model={model}
        apiKey={apiKey}
        orApiKey={orApiKey}
        knows={knows}
        setKnows={setKnows}
        mood={mood} setMood={setMood}
        temp={temp} setTemp={setTemp}
        sysPr={sysPr} setSysPr={setSysPr}
        snd={snd} setSnd={setSnd}
        bright={bright} setBright={setBright}
        fsize={fsize} setFsize={setFsize}
        geminiApiKey={geminiApiKey} setGeminiApiKey={setGeminiApiKey}
        mimoApiKey={mimoApiKey} setMimoApiKey={setMimoApiKey}
        nvidiaApiKey={nvidiaApiKey} setNvidiaApiKey={setNvidiaApiKey}
        voicePreset={voicePreset} setVoicePreset={setVoicePreset}
        jarvisRate={jarvisRate} setJarvisRate={setJarvisRate}
        voicePitch={voicePitch} setVoicePitch={setVoicePitch}
        accentTheme={accentTheme} setAccentTheme={setAccentTheme}
        customColor={customColor} setCustomColor={setCustomColor}
        assistantName={assistantName} setAssistantName={setAssistantName}
        userName={userName} setUserName={setUserName}
        voiceName={voiceName} setVoiceName={setVoiceName}
        gpuEnabled={gpuEnabled} setGpuEnabled={setGpuEnabled}
        charonFullTools={charonFullTools} setCharonFullTools={setCharonFullTools}
        ollSt={ollSt}
        oModels={oModels}
        orModels={orModels}
        llamacppModels={llamacppModels}
        customM={customM} setCustomM={setCustomM}
        showCust={showCust} setShowCust={setShowCust}
        expRoot={expRoot}
        groqApiKey={groqApiKey} setGroqApiKey={setGroqApiKey}
        openaiApiKey={openaiApiKey} setOpenaiApiKey={setOpenaiApiKey}
        deepSilenceSec={deepSilenceSec} setDeepSilenceSec={setDeepSilenceSec}
        loading={loading}
        thinking={thinking}
        thinkOn={thinkOn}
        thinkOpen={thinkOpen}
        setThinkOpen={setThinkOpen}
        toolLogs={toolLogs}
        termOpen={termOpen}
        setTermOpen={setTermOpen}
      />
    </div>
  );
}
