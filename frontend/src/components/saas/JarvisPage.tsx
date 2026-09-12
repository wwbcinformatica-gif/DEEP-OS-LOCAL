import React, { useState, useRef, useEffect } from 'react';
import {
  Conversation, TranscriptEntry,
  getConversations, createConversation, renameConversation, deleteConversation,
  getTranscripts, saveTranscripts, getActivityLog, saveActivityLog,
  tenantGet, tenantSet,
} from './chatStorage';

interface ToolCall {
  name: string;
  params: any;
  result?: string;
  status: 'running' | 'done' | 'error';
}

interface ProcessEntry {
  id: string;
  type: 'thinking' | 'tool_start' | 'tool_end' | 'tool_error' | 'info';
  label: string;
  detail?: string;
  timestamp: Date;
  status?: 'running' | 'done' | 'error';
}

interface Message {
  id: string;
  role: 'user' | 'jarvis';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

const VOICE_OPTIONS = [
  { key: 'google-female', label: 'Google PT-BR Feminino', desc: 'Voz clara e natural', type: 'browser' },
  { key: 'francisca', label: 'Francisca (Feminino)', desc: 'Voz feminina brasileira', type: 'browser' },
  { key: 'maria', label: 'Maria (Feminino)', desc: 'Voz feminina suave', type: 'browser' },
  { key: 'google-male', label: 'Google PT-BR Masculino', desc: 'Voz masculina nativa', type: 'browser' },
  { key: 'antonio', label: 'Antonio (Masculino)', desc: 'Voz masculina profunda', type: 'browser' },
  { key: 'daniel', label: 'Daniel (Masculino)', desc: 'Voz masculina estavel', type: 'browser' },
  { key: 'jarvis-cinematic', label: 'Jarvis Cinematic', desc: 'Tom grave cinematografico (Edge TTS)', type: 'edge', voice: 'pt-BR-AntonioNeural' },
  { key: 'edge-francisca', label: 'Francisca Neural (Edge)', desc: 'Voz feminina natural (Edge TTS)', type: 'edge', voice: 'pt-BR-FranciscaNeural' },
  { key: 'edge-thalita', label: 'Thalita Neural (Edge)', desc: 'Voz feminina clara (Edge TTS)', type: 'edge', voice: 'pt-BR-ThalitaMultilingualNeural' },
  { key: 'dani-brandi', label: 'Dani Brandi (Google)', desc: 'Voz feminina brasileira natural', type: 'edge', voice: 'pt-BR-FranciscaNeural' },
];

const BROWSER_VOICE_MAP: Record<string, string[]> = {
  'google-female': ['google', 'female', 'pt'],
  francisca: ['francisca', 'pt'],
  maria: ['maria', 'pt'],
  'google-male': ['google', 'male', 'pt'],
  antonio: ['antonio', 'pt'],
  daniel: ['daniel', 'pt'],
};

const PROVIDERS = [
  { id: 'ollama', label: 'Ollama (local)', keyField: '', models: [], dynamic: true },
  { id: 'llamacpp', label: 'llama.cpp (GGUF local)', keyField: '', models: [], dynamic: true },
  { id: 'gemini', label: 'Google Gemini', keyField: 'gemini', models: [
    { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (limitado)' },
    { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
    { id: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
  ]},
  { id: 'openrouter', label: 'OpenRouter (gratis/variados)', keyField: 'openrouter', models: [
    { id: 'openrouter/auto', label: 'Auto (melhor modelo)' },
    { id: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B (gratis)' },
    { id: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
    { id: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  ]},
  { id: 'groq', label: 'Groq (gratis/rapido)', keyField: 'groq', models: [
    { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B Versatile' },
    { id: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B Instant' },
  ]},
  { id: 'mimo', label: 'MiMo', keyField: 'mimo', models: [
    { id: 'mimo-v2.5', label: 'MiMo V2.5' },
  ]},
  { id: 'zhipu', label: 'Zhipu AI (GLM)', keyField: 'zhipu', models: [
    { id: 'glm-5.3-flash', label: 'GLM-5.3-Flash (novo)' },
    { id: 'glm-5.3', label: 'GLM-5.3' },
    { id: 'glm-5.2', label: 'GLM-5.2' },
  ]},
];

const LANG_LABELS: Record<string, string> = {
  python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript',
  jsx: 'JSX', tsx: 'TSX', java: 'Java', cpp: 'C++', c: 'C',
  go: 'Go', rust: 'Rust', ruby: 'Ruby', php: 'PHP',
  html: 'HTML', css: 'CSS', sql: 'SQL', bash: 'Bash',
  json: 'JSON', yaml: 'YAML', markdown: 'Markdown', shell: 'Shell',
};

function highlightCode(code: string, lang: string): React.ReactNode {
  const lines = code.split('\n');
  return lines.map((line, i) => {
    let highlighted = line
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/(\/\/.*$|#.*$)/gm, '<span style="color:#6a9955">$1</span>')
      .replace(/(["'`])((?:(?!\1)[^\\]|\\.)*)(\1)/g, '<span style="color:#ce9178">$1$2$3</span>')
      .replace(/\b(import|from|export|default|const|let|var|function|return|if|else|for|while|class|extends|new|this|async|await|try|catch|throw|def|print|self|True|False|None|in|not|and|or|is|with|as|elif|except|lambda|yield|raise|pass|break|continue|switch|case|do|type|interface|enum|struct|pub|fn|mut|use|mod|crate|match|loop|unsafe|impl|trait|where|async|move|ref|dyn|abstract|final|static|synchronized|volatile|transient|native|public|private|protected|internal|override|readonly|optional|nullable)\b/g, '<span style="color:#569cd6">$1</span>')
      .replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#b5cea8">$1</span>');
    return (
      <div key={i} style={{ display: 'flex' }}>
        <span style={{ userSelect: 'none', color: '#555', minWidth: 32, textAlign: 'right', paddingRight: 12, fontSize: 12 }}>{i + 1}</span>
        <span dangerouslySetInnerHTML={{ __html: highlighted }} />
      </div>
    );
  });
}

function renderMarkdown(text: string): React.ReactNode {
  // Normalize: ensure line breaks before markdown markers
  let normalized = text
    .replace(/---/g, '\n---\n')
    .replace(/(#{1,6})\s/g, '\n$1 ')
    .replace(/\|([^\n]*\|)/g, (m) => '\n' + m)
    .replace(/(?<!\n)([-*+])\s+(?=[^\s])/g, '\n$1 ')
    .replace(/(?<!\n)(\d+\.)\s+(?=[^\s])/g, '\n$1 ');

  const lines = normalized.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Skip empty
    if (trimmed === '') { i++; continue; }

    // Code block
    if (trimmed.startsWith('```')) {
      const lang = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      elements.push(
        <div key={elements.length} style={{ margin: '8px 0', borderRadius: 8, overflow: 'hidden', border: '1px solid #2a2a3e', background: '#0d0d1a' }}>
          {lang && <div style={{ padding: '4px 12px', background: '#16162a', borderBottom: '1px solid #2a2a3e', fontSize: 11, color: '#888', fontWeight: 600 }}>{LANG_LABELS[lang] || lang.toUpperCase()}</div>}
          <pre style={{ margin: 0, padding: '12px 8px', overflowX: 'auto', fontSize: 12.5, lineHeight: 1.65, fontFamily: "'Cascadia Code', 'Fira Code', monospace", color: '#d4d4d4' }}>
            <code>{highlightCode(codeLines.join('\n'), lang)}</code>
          </pre>
        </div>
      );
      continue;
    }

    // Table
    if (trimmed.includes('|') && i + 1 < lines.length && lines[i + 1].trim().includes('---')) {
      const headers = trimmed.split('|').map(c => c.trim()).filter(Boolean);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().includes('|') && !lines[i].trim().startsWith('```')) {
        rows.push(lines[i].trim().split('|').map(c => c.trim()).filter(Boolean));
        i++;
      }
      elements.push(
        <div key={elements.length} style={{ margin: '8px 0', overflowX: 'auto', borderRadius: 6, border: '1px solid #2a2a3e' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: "'Cascadia Code', 'Fira Code', monospace" }}>
            <thead><tr>{headers.map((h, hi) => (
              <th key={hi} style={{ padding: '6px 10px', background: '#16162a', borderBottom: '1px solid #2a2a3e', color: '#00d9ff', fontWeight: 700, textAlign: 'left', fontSize: 11 }}>{renderInline(h)}</th>
            ))}</tr></thead>
            <tbody>{rows.map((row, ri) => (
              <tr key={ri}>{row.map((cell, ci) => (
                <td key={ci} style={{ padding: '5px 10px', borderBottom: '1px solid #1a1a2e', color: '#ccc', background: ri % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>{renderInline(cell)}</td>
              ))}</tr>
            ))}</tbody>
          </table>
        </div>
      );
      continue;
    }

    // HR
    if (/^\s*[-*_]{3,}\s*$/.test(trimmed)) {
      elements.push(<hr key={elements.length} style={{ border: 'none', borderTop: '1px solid #2a2a3e', margin: '10px 0' }} />);
      i++; continue;
    }

    // Header
    const hm = trimmed.match(/^(#{1,6})\s+(.+)/);
    if (hm) {
      const lvl = hm[1].length;
      const sz = lvl <= 1 ? 18 : lvl <= 2 ? 15 : 13;
      const clr = lvl <= 2 ? '#00d9ff' : '#b478ff';
      elements.push(<div key={elements.length} style={{ fontSize: sz, fontWeight: 700, color: clr, marginTop: lvl <= 2 ? 12 : 8, marginBottom: 4, fontFamily: "'Inter', sans-serif" }}>{renderInline(hm[2])}</div>);
      i++; continue;
    }

    // Unordered list
    if (/^\s*[-*+]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\s*[-*+]\s+/, ''));
        i++;
      }
      elements.push(
        <div key={elements.length} style={{ margin: '4px 0' }}>
          {items.map((item, li) => (
            <div key={li} style={{ display: 'flex', gap: 6, padding: '2px 0', paddingLeft: 8 }}>
              <span style={{ color: '#b478ff', flexShrink: 0 }}>{'\u25CF'}</span>
              <span>{renderInline(item)}</span>
            </div>
          ))}
        </div>
      );
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\s*\d+\.\s+/, ''));
        i++;
      }
      elements.push(
        <div key={elements.length} style={{ margin: '4px 0' }}>
          {items.map((item, li) => (
            <div key={li} style={{ display: 'flex', gap: 6, padding: '2px 0', paddingLeft: 8 }}>
              <span style={{ color: '#00d9ff', flexShrink: 0, fontWeight: 700, fontSize: 12 }}>{li + 1}.</span>
              <span>{renderInline(item)}</span>
            </div>
          ))}
        </div>
      );
      continue;
    }

    // Paragraph
    elements.push(
      <div key={elements.length} style={{ margin: '3px 0', lineHeight: 1.75, color: '#ccc' }}>
        {renderInline(trimmed)}
      </div>
    );
    i++;
  }

  return elements;
}

function renderInline(text: string): React.ReactNode {
  // Split by bold and inline code
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: '#e0e0e0', fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} style={{ background: '#1a1a2e', padding: '1px 5px', borderRadius: 4, fontSize: 12, color: '#e06c75', fontFamily: "'Cascadia Code', 'Fira Code', monospace" }}>{part.slice(1, -1)}</code>;
    }
    return <span key={i}>{part}</span>;
  });
}

function renderMessageContent(content: string): React.ReactNode {
  return renderMarkdown(content);
}

const JarvisPage: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>(() => getConversations());
  const [activeConvId, setActiveConvId] = useState<string>(() => {
    const convs = getConversations();
    return convs[0]?.id || '';
  });
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [showConvMenu, setShowConvMenu] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'jarvis',
      content: 'Ola! Sou o Jarvis, seu assistente inteligente. Posso ouvir voce, executar tarefas e usar ferramentas. Como posso ajudar?',
      timestamp: new Date(),
    },
  ]);
  const [processLog, setProcessLog] = useState<ProcessEntry[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash');
  const [selectedProvider, setSelectedProvider] = useState('gemini');
  const [apiKey, setApiKey] = useState('');
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showSettings, setShowSettings] = useState(false);
  const [voiceRate, setVoiceRate] = useState(parseFloat(tenantGet('jarvis_voice_rate') || '1.3'));
  const [voicePitch, setVoicePitch] = useState(parseInt(tenantGet('jarvis_voice_pitch') || '50'));
  const [selectedVoice, setSelectedVoice] = useState(tenantGet('jarvis_voice') || 'jarvis-cinematic');
  const [instances, setInstances] = useState<any[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState(tenantGet('jarvis_instance_id') || '');
  const [instanceConfig, setInstanceConfig] = useState<any>(null);
  const [dynamicModels, setDynamicModels] = useState<{id: string, label: string, hasVision?: boolean}[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [gpuMode, setGpuMode] = useState<Record<string, boolean>>({
    ollama: tenantGet('jarvis_gpu_ollama') !== 'false',
    llamacpp: tenantGet('jarvis_gpu_llamacpp') !== 'false',
  });
  const textareaHeightRef = useRef(60);
  const [textareaHeight, setTextareaHeight] = useState(60);
  const rightPanelWidthRef = useRef(280);
  const [rightPanelWidth, setRightPanelWidth] = useState(280);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const processListRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (activeConvId) {
      setTranscripts(getTranscripts(activeConvId));
    }
  }, [activeConvId]);

  useEffect(() => {
    if (activeConvId && transcripts.length > 0) {
      saveTranscripts(activeConvId, transcripts);
    }
  }, [transcripts, activeConvId]);

  useEffect(() => {
    const savedKey = tenantGet('saas_api_key') || '';
    setApiKey(savedKey);
    const keys: Record<string, string> = {};
    ['gemini', 'openrouter', 'openai', 'groq', 'nvidia', 'mimo', 'openclaude', 'opencode'].forEach(p => {
      const k = tenantGet(`${p}_api_key`) || '';
      if (k) keys[p] = k;
    });
    setApiKeys(keys);
    fetch('/api/config/api-keys').then(r => r.ok ? r.json() : null).then(data => {
      if (!data) return;
      const envToField: Record<string, string> = { gemini: 'gemini', openrouter: 'openrouter', openai: 'openai', groq: 'groq', nvidia: 'nvidia', mimo: 'mimo', openclaude: 'openclaude', opencode: 'opencode' };
      Object.entries(envToField).forEach(([name, field]) => {
        if (data[name]?.has_key && !keys[field]) {
          keys[field] = '***saved***';
          tenantSet(`${field}_api_key`, '***saved***');
        }
      });
      setApiKeys({ ...keys });
    }).catch(() => {});
    const savedInst = tenantGet('jarvis_instance_id') || '';
    fetch('/api/instances').then(r => r.ok ? r.json() : null).then(data => {
      if (data?.instances) {
        setInstances(data.instances);
        if (savedInst) {
          const inst = data.instances.find((i: any) => i.id === savedInst);
          if (inst) {
            setSelectedModel(inst.model);
            setSelectedProvider(inst.provider);
            setInstanceConfig(inst);
          }
        }
      }
    }).catch(() => {});

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showSettings) setShowSettings(false);
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [showSettings]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    processListRef.current?.scrollTo({ top: processListRef.current.scrollHeight, behavior: 'smooth' });
  }, [processLog]);

  useEffect(() => {
    if (selectedProvider === 'ollama') {
      setLoadingModels(true);
      fetch('/ollama/models').then(r => r.ok ? r.json() : { models: [] }).then(data => {
        const visionPatterns = /vl|vision|llava|gemma4/i;
        const models = (data.models || []).map((m: string) => ({
          id: m,
          label: m,
          hasVision: visionPatterns.test(m),
        }));
        setDynamicModels(models);
        if (models.length > 0 && !models.find((m: any) => m.id === selectedModel)) {
          setSelectedModel(models[0].id);
        }
        setLoadingModels(false);
      }).catch(() => { setDynamicModels([]); setLoadingModels(false); });
    } else if (selectedProvider === 'llamacpp') {
      setLoadingModels(true);
      fetch('/llamacpp/models').then(r => r.ok ? r.json() : { models: [] }).then(data => {
        const models = (data.models || []).map((m: any) => ({
          id: m.id || m.file,
          label: m.label || m.id || m.file,
          hasVision: m.has_vision || false,
        }));
        setDynamicModels(models);
        if (models.length > 0 && !models.find((m: any) => m.id === selectedModel)) {
          setSelectedModel(models[0].id);
        }
        setLoadingModels(false);
      }).catch(() => { setDynamicModels([]); setLoadingModels(false); });
    } else {
      setDynamicModels([]);
    }
  }, [selectedProvider]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      synthRef.current = window.speechSynthesis;
    }
  }, []);

  const addProcess = (type: ProcessEntry['type'], label: string, detail?: string, status?: ProcessEntry['status']) => {
    setProcessLog(prev => [...prev, {
      id: String(Date.now()) + Math.random().toString(36).slice(2, 6),
      type, label, detail, timestamp: new Date(), status,
    }]);
  };

  const updateLastProcess = (patch: Partial<ProcessEntry>) => {
    setProcessLog(prev => {
      const updated = [...prev];
      if (updated.length > 0) {
        updated[updated.length - 1] = { ...updated[updated.length - 1], ...patch };
      }
      return updated;
    });
  };

  const toggleGpu = async (provider: string) => {
    const newVal = !gpuMode[provider];
    setGpuMode(prev => ({ ...prev, [provider]: newVal }));
    tenantSet(`jarvis_gpu_${provider}`, String(newVal));
    try {
      await fetch(`/${provider}/gpu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_gpu: newVal }),
      });
    } catch (e) {}
  };

  const startListening = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Seu navegador nao suporta reconhecimento de voz. Use Chrome.');
      return;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.onresult = (event: any) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      setInput(transcript);
      if (event.results[event.results.length - 1].isFinal) {
        handleSendMessageDirect(transcript);
      }
    };
    recognitionRef.current = recognition;
    recognition.start();
  };

  const stopListening = () => {
    if (recognitionRef.current) recognitionRef.current.stop();
  };

  const speak = async (text: string) => {
    const voiceOpt = VOICE_OPTIONS.find(v => v.key === selectedVoice) || VOICE_OPTIONS[0];
    let clean = text
      .replace(/\*\*/g, '')
      .replace(/[#>*_`~\[\]{}|\\]/g, '')
      .replace(/-{3,}/g, '')
      .replace(/_{3,}/g, '')
      .replace(/\.{3,}/g, '')
      .replace(/•/g, '')
      .replace(/sdkjf|ã|©|®|™|°/g, '')
      .replace(/[\u{1F300}-\u{1F9FF}]/gu, '')
      .replace(/[\u{2600}-\u{26FF}]/gu, '')
      .replace(/[\u{2700}-\u{27BF}]/gu, '')
      .replace(/[\u{FE00}-\u{FE0F}]/gu, '')
      .replace(/[\u{200D}]/gu, '')
      .replace(/[\u{20E3}]/gu, '')
      .replace(/[\u{E0020}-\u{E007F}]/gu, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!clean) return;
    if (voiceOpt.type === 'edge') {
      try {
        synthRef.current?.cancel();
        addProcess('info', 'Gerando audio com Edge TTS...');
        const res = await fetch('/api/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: clean, voice: voiceOpt.voice }),
        });
        if (!res.ok) throw new Error(`TTS falhou: ${res.status}`);
        const blob = await res.blob();
        if (blob.size < 100) throw new Error('TTS retornou audio vazio');
        const audio = new Audio(URL.createObjectURL(blob));
        audio.volume = 1.0;
        audioRef.current = audio;
        setIsSpeaking(true);
        audio.onended = () => { setIsSpeaking(false); URL.revokeObjectURL(audio.src); updateLastProcess({ status: 'done' }); };
        audio.onerror = () => { setIsSpeaking(false); URL.revokeObjectURL(audio.src); updateLastProcess({ status: 'error' }); };
        await audio.play().catch(() => speakBrowser(clean, voiceOpt));
        return;
      } catch (e) { console.warn('Edge TTS falhou:', e); }
    }
    speakBrowser(clean, voiceOpt);
  };

  const speakBrowser = (text: string, voiceOpt: any) => {
    if (!synthRef.current) synthRef.current = window.speechSynthesis;
    if (!synthRef.current) return;
    synthRef.current.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'pt-BR';
    utterance.rate = voiceRate;
    utterance.pitch = 0.5 + (voicePitch / 100) * 1.0;
    const voices = window.speechSynthesis?.getVoices() || [];
    const keywords = BROWSER_VOICE_MAP[voiceOpt.key] || ['pt'];
    const normalized = (v: SpeechSynthesisVoice) => `${v.name.toLowerCase()} ${v.lang.toLowerCase()}`;
    const foundVoice = voices.find(v => keywords.every(kw => normalized(v).includes(kw))) || voices.find(v => v.lang.startsWith('pt')) || voices[0];
    if (foundVoice) utterance.voice = foundVoice;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    synthRef.current.speak(utterance);
  };

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stopSpeaking = () => {
    if (synthRef.current) synthRef.current.cancel();
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.currentTime = 0; audioRef.current = null; }
    setIsSpeaking(false);
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsTyping(false);
    addProcess('info', 'Geracao interrompida pelo usuario', undefined);
    setMessages(prev => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last && last.role === 'jarvis' && last.isStreaming) {
        updated[updated.length - 1] = { ...last, isStreaming: false, content: last.content || 'Geracao interrompida.' };
      }
      return updated;
    });
  };

  const clearMessages = () => {
    setMessages([{
      id: '1',
      role: 'jarvis',
      content: 'Ola! Sou o Jarvis, seu assistente inteligente. Como posso ajudar?',
      timestamp: new Date(),
    }]);
    setProcessLog([]);
  };

  const handleSendMessageDirect = async (text: string) => {
    if (!text.trim()) return;

    const userMessage: Message = {
      id: String(Date.now()),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    addProcess('thinking', 'Analisando pergunta...', `"${text.slice(0, 60)}${text.length > 60 ? '...' : ''}"`);

    const jarvisMsg: Message = {
      id: String(Date.now() + 1),
      role: 'jarvis',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, jarvisMsg]);

    try {
      const token = tenantGet('saas_token') || localStorage.getItem('saas_token');
      const activeKey = selectedProvider === 'gemini' ? apiKey : (apiKeys[selectedProvider] || tenantGet(`${selectedProvider}_api_key`) || '');
      addProcess('info', `Conectando com ${selectedProvider}...`, `Modelo: ${selectedModel}`);

      abortControllerRef.current = new AbortController();
      const resp = await fetch('/chat/stream', {
        method: 'POST',
        signal: abortControllerRef.current.signal,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          user: text,
          provider: selectedProvider,
          model: selectedModel,
          api_key: activeKey,
          temperature: instanceConfig?.temperature ?? 0.7,
          system_prompt: instanceConfig?.system_prompt || '',
          session_id: `saas-${tenantGet('saas_user') || localStorage.getItem('saas_user') || 'default'}`,
        }),
      });

      if (!resp.ok) throw new Error(`Erro ${resp.status}: ${resp.statusText}`);

      addProcess('thinking', 'Modelo processando...', 'Aguardando resposta');

      const reader = resp.body?.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = '';
      let buffer = '';
      let tokenCount = 0;

      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const event = JSON.parse(line);

              if (event.type === 'token') {
                fullAnswer += event.content || '';
                tokenCount++;
                setMessages(prev => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.id === jarvisMsg.id) {
                    updated[updated.length - 1] = { ...last, content: fullAnswer };
                  }
                  return updated;
                });
                if (tokenCount === 1) {
                  updateLastProcess({ label: 'Gerando resposta...', detail: 'Tokens recebidos' });
                }
              } else if (event.type === 'tool_start') {
                const toolName = event.tool || event.tool_name || 'desconhecida';
                const params = typeof event.params === 'string' ? event.params : JSON.stringify(event.params || {}, null, 0);
                addProcess('tool_start', `Ferramenta: ${toolName}`, params.slice(0, 150), 'running');
              } else if (event.type === 'tool_end') {
                const toolName = event.tool || event.tool_name || '';
                const result = typeof event.result === 'string' ? event.result : JSON.stringify(event.result || {}, null, 0);
                addProcess('tool_end', `Concluida: ${toolName}`, result.slice(0, 150), 'done');
              } else if (event.type === 'error') {
                addProcess('tool_error', `Erro: ${event.message}`, undefined, 'error');
                fullAnswer += `\n\nErro: ${event.message}`;
                setMessages(prev => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.id === jarvisMsg.id) updated[updated.length - 1] = { ...last, content: fullAnswer };
                  return updated;
                });
              } else if (event.type === 'done') {
                fullAnswer = event.answer || fullAnswer;
              }
            } catch (e) {}
          }
        }
      }

      setMessages(prev => {
        const updated = [...prev];
        const idx = updated.findIndex(m => m.id === jarvisMsg.id);
        if (idx >= 0) updated[idx] = { ...updated[idx], content: fullAnswer, isStreaming: false };
        return updated;
      });

      addProcess('info', 'Resposta concluida', `${tokenCount} tokens, ${fullAnswer.length} caracteres`);
      updateLastProcess({ status: 'done' });

      if (fullAnswer) speak(fullAnswer);

    } catch (err: any) {
      addProcess('tool_error', `Erro: ${err.message}`, undefined, 'error');
      setMessages(prev => {
        const updated = [...prev];
        const idx = updated.findIndex(m => m.id === jarvisMsg.id);
        if (idx >= 0) {
          updated[idx] = {
            ...updated[idx],
            content: `Desculpe, ocorreu um erro: ${err.message}. Verifique se o backend esta rodando e se sua chave de API esta configurada.`,
            isStreaming: false,
          };
        }
        return updated;
      });
    }

    abortControllerRef.current = null;
    setIsTyping(false);
  };

  const handleSendMessage = async () => {
    handleSendMessageDirect(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
    const target = e.target as HTMLTextAreaElement;
    setTimeout(() => {
      target.style.height = 'auto';
      target.style.height = Math.min(target.scrollHeight, 150) + 'px';
    }, 0);
  };

  const switchConversation = (convId: string) => {
    setActiveConvId(convId);
    setShowConvMenu(false);
  };

  const newConversation = () => {
    const conv = createConversation();
    setConversations(getConversations());
    setActiveConvId(conv.id);
    setTranscripts([]);
    setProcessLog([]);
    setMessages([{
      id: '1',
      role: 'jarvis',
      content: 'Ola! Sou o Jarvis, seu assistente inteligente. Como posso ajudar?',
      timestamp: new Date(),
    }]);
    setShowConvMenu(false);
  };

  const handleDeleteConversation = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (conversations.length <= 1) return;
    deleteConversation(convId);
    const updated = getConversations();
    setConversations(updated);
    if (activeConvId === convId) setActiveConvId(updated[0]?.id || '');
  };

  const handleRenameConversation = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const name = prompt('Novo nome da conversa:');
    if (name && name.trim()) {
      renameConversation(convId, name.trim());
      setConversations(getConversations());
    }
  };

  const activeConv = conversations.find(c => c.id === activeConvId);
  const formatConvTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  const formatProcessTime = (d: Date) => {
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  };

  const processIcon = (type: ProcessEntry['type'], status?: string) => {
    if (type === 'thinking') return '\u{1F4AD}';
    if (type === 'tool_start') return status === 'running' ? '\u23F3' : '\u2699\uFE0F';
    if (type === 'tool_end') return '\u2705';
    if (type === 'tool_error') return '\u274C';
    return '\u2139\uFE0F';
  };

  const activeToolCount = processLog.filter(p => p.type === 'tool_start' && p.status === 'running').length;

  return (
    <div style={s.container}>
      <div style={s.chatLayout}>
        <div style={s.leftPanel}>
          <div style={s.convBar}>
            <button onClick={newConversation} title="Nova conversa" style={s.convNewBtn}>+</button>
            <button onClick={() => setShowConvMenu(!showConvMenu)} style={s.convMenuBtn}>{activeConv?.name || 'Nova conversa'}</button>
            <span style={{ fontSize: 9, color: '#666' }}>{messages.length}</span>
            {showConvMenu && (
              <div style={s.convDropdown}>
                {conversations.map(conv => (
                  <div key={conv.id} onClick={() => switchConversation(conv.id)} style={{ ...s.convItem, background: conv.id === activeConvId ? 'rgba(0,217,255,0.15)' : 'transparent' }}>
                    <span style={{ flex: 1, fontSize: 11, color: conv.id === activeConvId ? '#00d9ff' : '#ccc', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{conv.name}</span>
                    <span style={{ fontSize: 9, color: '#666' }}>{formatConvTime(conv.updatedAt)}</span>
                    <button onClick={(e) => handleRenameConversation(conv.id, e)} style={s.convActionBtn}>{'\u270E'}</button>
                    <button onClick={(e) => handleDeleteConversation(conv.id, e)} style={{ ...s.convActionBtn, color: '#f44' }}>{'\u2715'}</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', borderBottom: '1px solid #222', flexShrink: 0, gap: 6 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ color: '#00d9ff', fontSize: 12 }}>{'\uD83E\uDD16'}</span>
              <span style={{ fontSize: 12, color: '#00d9ff', fontWeight: 600 }}>Jarvis</span>
              <button style={s.settingsBtn} onClick={() => setShowSettings(true)}>{'\u2699\uFE0F'}</button>
              <button style={s.settingsBtn} onClick={clearMessages} title="Limpar chat">{'\uD83D\uDDD1\uFE0F'}</button>
            </div>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <select value={selectedProvider} onChange={(e) => { setSelectedProvider(e.target.value); const prov = PROVIDERS.find(p => p.id === e.target.value); if (prov && prov.models.length > 0) setSelectedModel(prov.models[0].id); }} style={s.modelSelect}>
                {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
              <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} style={s.modelSelectWide}>
                {((dynamicModels.length > 0 ? dynamicModels : (PROVIDERS.find(p => p.id === selectedProvider)?.models || []))).map(m => (
                  <option key={m.id} value={m.id}>{(m as any).hasVision ? '\uD83D\uDC41 ' : ''}{m.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={s.messagesArea}>
            {messages.length === 0 ? (
              <div style={s.emptyState}>Jarvis pronto. Como posso ajudar?</div>
            ) : messages.map(msg => (
              <div key={msg.id} style={{
                marginBottom: 10, padding: '10px 14px', borderRadius: 8,
                background: msg.role === 'user' ? 'rgba(0,217,255,0.06)' : 'rgba(180,120,255,0.04)',
                borderLeft: `3px solid ${msg.role === 'user' ? '#00d9ff' : '#b478ff'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 13 }}>{msg.role === 'user' ? '\uD83D\uDC64' : '\uD83E\uDD16'}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: msg.role === 'user' ? '#00d9ff' : '#b478ff' }}>
                    {msg.role === 'user' ? 'Voce' : 'Jarvis'}
                  </span>
                  <span style={{ fontSize: 10, color: '#555', marginLeft: 'auto' }}>
                    {msg.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <div style={{ color: '#ddd', wordBreak: 'break-word', overflowWrap: 'break-word', fontSize: 13, lineHeight: 1.7, fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace" }}>
                  {renderMessageContent(msg.content)}{msg.isStreaming && <span style={{ animation: 'blink 1s infinite', color: '#00d9ff' }}>{'\u258C'}</span>}
                </div>
              </div>
            ))}
            {isTyping && (
              <div style={{ marginBottom: 10, padding: '10px 14px', borderRadius: 8, background: 'rgba(180,120,255,0.04)', borderLeft: '3px solid #b478ff' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 13 }}>{'\uD83E\uDD16'}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#b478ff' }}>Jarvis</span>
                </div>
                <div style={{ display: 'flex', gap: 6, padding: '6px 0' }}>
                  <span style={{ width: 7, height: 7, background: '#b478ff', borderRadius: '50%', animation: 'pulse 1.4s infinite' }} />
                  <span style={{ width: 7, height: 7, background: '#b478ff', borderRadius: '50%', animation: 'pulse 1.4s infinite 0.2s' }} />
                  <span style={{ width: 7, height: 7, background: '#b478ff', borderRadius: '50%', animation: 'pulse 1.4s infinite 0.4s' }} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div style={s.inputSection}>
            <div onPointerDown={(e) => { e.preventDefault(); const startY = e.clientY; const startH = textareaHeightRef.current; const move = (ev: PointerEvent) => { const delta = startY - ev.clientY; textareaHeightRef.current = Math.max(36, Math.min(300, startH + delta)); setTextareaHeight(textareaHeightRef.current); }; const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); }; window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); }} style={{ height: 6, cursor: 'ns-resize', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, margin: '2px 0' }}>
              <div style={{ width: 40, height: 3, borderRadius: 2, background: '#444' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
                placeholder={isListening ? 'Ouvindo...' : 'Digite sua mensagem...'}
                style={{ ...s.textarea, height: textareaHeight, borderColor: isListening ? '#ef4444' : '#333' }}
                disabled={isTyping} />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <button onClick={isListening ? stopListening : startListening} style={{ ...s.iconBtn, background: isListening ? '#ef4444' : '#1a1a2e', color: isListening ? '#fff' : '#ccc' }} title={isListening ? 'Parar' : 'Microfone'}>
                    {isListening ? '\u23F9' : '\uD83C\uDF99'}
                  </button>
                  <button onClick={stopSpeaking} disabled={!isSpeaking} style={{ ...s.iconBtn, background: isSpeaking ? '#ef4444' : '#1a1a2e', color: isSpeaking ? '#fff' : '#666', opacity: isSpeaking ? 1 : 0.4 }} title={isSpeaking ? 'Parar voz' : 'Falante'}>
                    {isSpeaking ? '\uD83D\uDD07' : '\uD83D\uDD08'}
                  </button>
                  <button onClick={stopGeneration} disabled={!isTyping} style={{ ...s.iconBtn, background: isTyping ? '#ef4444' : '#1a1a2e', color: isTyping ? '#fff' : '#666', opacity: isTyping ? 1 : 0.4 }} title="Parar geracao">
                    {'\u23F9'}
                  </button>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: isTyping ? '#f59e0b' : '#0c0', display: 'inline-block' }} />
                  <span style={{ fontSize: 10, color: isTyping ? '#f59e0b' : '#0c0', fontWeight: 600 }}>
                    {isTyping ? 'Processando...' : 'Jarvis ativo'}
                  </span>
                </div>
                <button style={s.sendBtn} onClick={handleSendMessage} disabled={!input.trim() || isTyping}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div onPointerDown={(e) => { e.preventDefault(); const startX = e.clientX; const startW = rightPanelWidthRef.current; const move = (ev: PointerEvent) => { const delta = startX - ev.clientX; rightPanelWidthRef.current = Math.max(200, Math.min(500, startW + delta)); setRightPanelWidth(rightPanelWidthRef.current); }; const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); }; window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); }} style={{ width: 5, cursor: 'ew-resize', alignItems: 'center', justifyContent: 'center', flexShrink: 0, background: '#111' }}>
          <div style={{ width: 3, height: 40, borderRadius: 2, background: '#333' }} />
        </div>

        <div style={{ ...s.rightPanel, width: rightPanelWidth }}>
          <div style={s.rightHeader}>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#b478ff' }}>{'\u2699\uFE0F'} Processos</span>
            <span style={{ fontSize: 9, color: '#666', marginLeft: 'auto' }}>
              {activeToolCount > 0 ? <span style={{ color: '#f59e0b' }}>{activeToolCount} ativo{activeToolCount > 1 ? 's' : ''}</span> : 'Idle'}
            </span>
          </div>
          <div ref={processListRef} style={s.processList}>
            {processLog.length === 0 ? (
              <div style={s.emptyState}>Nenhum processo ainda. Envie uma mensagem para ver a atividade do modelo aqui.</div>
            ) : processLog.map(entry => (
              <div key={entry.id} style={{
                ...s.processItem,
                borderLeftColor: entry.type === 'tool_error' ? '#ef4444' : entry.type === 'tool_end' ? '#10b981' : entry.type === 'tool_start' ? '#f59e0b' : entry.type === 'thinking' ? '#b478ff' : '#444',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                  <span style={{ fontSize: 10 }}>{processIcon(entry.type, entry.status)}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: entry.type === 'tool_error' ? '#ef4444' : entry.type === 'tool_end' ? '#10b981' : entry.type === 'tool_start' ? '#f59e0b' : entry.type === 'thinking' ? '#b478ff' : '#888' }}>
                    {entry.label}
                  </span>
                  <span style={{ fontSize: 8, color: '#555', marginLeft: 'auto' }}>{formatProcessTime(entry.timestamp)}</span>
                </div>
                {entry.detail && (
                  <div style={{ fontSize: 9, color: '#777', lineHeight: 1.3, fontFamily: "'Cascadia Code', monospace", whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {entry.detail}
                  </div>
                )}
                {entry.status === 'running' && (
                  <div style={{ marginTop: 3, height: 2, background: '#222', borderRadius: 1, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: '60%', background: entry.type === 'tool_start' ? '#f59e0b' : '#b478ff', animation: 'processBar 1.5s ease-in-out infinite' }} />
                  </div>
                )}
              </div>
            ))}
          </div>
          <div style={s.rightFooter}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: isTyping ? '#f59e0b' : '#0c0' }} />
            <span style={{ fontSize: 10, color: isTyping ? '#f59e0b' : '#0c0' }}>{isTyping ? 'Ativo' : 'Pronto'}</span>
            <span style={{ fontSize: 10, color: '#555', marginLeft: 'auto' }}>{processLog.length} eventos</span>
          </div>
        </div>
      </div>

      {showSettings && (
        <div style={s.modalOverlay} onClick={() => setShowSettings(false)}>
          <div style={s.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={s.modalHeader}>
              <span style={{ fontSize: 14, fontWeight: 700, color: '#00d9ff' }}>{'\u2699\uFE0F'} Configuracoes do Jarvis</span>
              <button onClick={() => setShowSettings(false)} style={s.modalClose}>{'\u2715'}</button>
            </div>
            <div style={s.modalBody}>
              <div style={s.settingsSection}>
                <div style={s.sectionTitle}>Chaves de API</div>
                {PROVIDERS.filter(p => !p.dynamic).map(prov => (
                  <div key={prov.id} style={s.settingsRow}>
                    <label style={s.settingsLabel}>{prov.label}</label>
                    <div style={{ display: 'flex', gap: 6, flex: 1 }}>
                      <input type="password" value={prov.keyField === 'gemini' ? apiKey : (apiKeys[prov.keyField] || '')}
                        onChange={(e) => { if (prov.keyField === 'gemini') setApiKey(e.target.value); else setApiKeys({ ...apiKeys, [prov.keyField]: e.target.value }); }}
                        style={s.configInput} placeholder="sk-..." />
                      <button onClick={() => {
                        const key = prov.keyField === 'gemini' ? apiKey : (apiKeys[prov.keyField] || '');
                        if (prov.keyField === 'gemini') { tenantSet('saas_api_key', key); setApiKey(key); fetch('/api/config/api-key', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gemini_api_key: key }) }).catch(() => {}); }
                        else { tenantSet(`${prov.keyField}_api_key`, key); setApiKeys({ ...apiKeys, [prov.keyField]: key }); }
                        const envKeyMap: Record<string, string> = { gemini: 'GEMINI_API_KEY', openrouter: 'OPENROUTER_API_KEY', openai: 'OPENAI_API_KEY', groq: 'GROQ_API_KEY', nvidia: 'NVIDIA_API_KEY', mimo: 'MIMO_API_KEY', openclaude: 'OPENCLAUDE_API_KEY', opencode: 'OPENCODE_API_KEY' };
                        const envPayload: Record<string, string> = {};
                        Object.keys(envKeyMap).forEach(pk => { envPayload[envKeyMap[pk]] = pk === 'gemini' ? (pk === prov.keyField ? key : (apiKeys['gemini'] || tenantGet('saas_api_key') || '')) : pk === prov.keyField ? key : (apiKeys[pk] || tenantGet(`${pk}_api_key`) || ''); });
                        fetch('/api/config/api-keys', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(envPayload) }).catch(() => {});
                      }} style={s.saveBtn}>Salvar</button>
                    </div>
                  </div>
                ))}
              </div>

              <div style={s.settingsSection}>
                <div style={s.sectionTitle}>Locais (GPU / CPU)</div>
                {['ollama', 'llamacpp'].map(prov => (
                  <div key={prov} style={s.settingsRow}>
                    <label style={s.settingsLabel}>{prov === 'ollama' ? 'Ollama' : 'llama.cpp'}</label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                      <button onClick={() => toggleGpu(prov)} style={{ ...s.toggleBtn, background: gpuMode[prov] ? '#10b981' : '#333', color: gpuMode[prov] ? '#fff' : '#999' }}>
                        {gpuMode[prov] ? 'GPU' : 'CPU'}
                      </button>
                      <span style={{ fontSize: 10, color: '#666' }}>{gpuMode[prov] ? 'Aceleracao por GPU' : 'Processamento na CPU'}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div style={s.settingsSection}>
                <div style={s.sectionTitle}>Voz</div>
                <div style={s.settingsRow}>
                  <label style={s.settingsLabel}>Voz</label>
                  <select value={selectedVoice} onChange={(e) => { setSelectedVoice(e.target.value); tenantSet('jarvis_voice', e.target.value); }} style={{ ...s.configInput, flex: 1 }}>
                    {VOICE_OPTIONS.map(v => <option key={v.key} value={v.key}>{v.label} - {v.desc}</option>)}
                  </select>
                </div>
                <div style={s.settingsRow}>
                  <label style={s.settingsLabel}>Velocidade: {voiceRate.toFixed(1)}x</label>
                  <input type="range" min="0.5" max="3" step="0.1" value={voiceRate}
                    onChange={(e) => { const rate = parseFloat(e.target.value); setVoiceRate(rate); tenantSet('jarvis_voice_rate', String(rate)); }}
                    style={{ flex: 1 }} />
                </div>
                <div style={s.settingsRow}>
                  <label style={s.settingsLabel}>Tom: {voicePitch}%</label>
                  <input type="range" min="0" max="100" step="5" value={voicePitch}
                    onChange={(e) => { const pitch = parseInt(e.target.value); setVoicePitch(pitch); tenantSet('jarvis_voice_pitch', String(pitch)); }}
                    style={{ flex: 1 }} />
                </div>
              </div>

              <div style={s.settingsSection}>
                <div style={s.sectionTitle}>Instancia</div>
                {instances.length > 0 ? (
                  <div style={s.settingsRow}>
                    <label style={s.settingsLabel}>Instancia</label>
                    <select value={selectedInstanceId} onChange={(e) => {
                      const id = e.target.value;
                      setSelectedInstanceId(id);
                      tenantSet('jarvis_instance_id', id);
                      if (id) {
                        const inst = instances.find(i => i.id === id);
                        if (inst) { setSelectedModel(inst.model); setSelectedProvider(inst.provider); setInstanceConfig(inst); }
                      } else { setInstanceConfig(null); }
                    }} style={{ ...s.configInput, flex: 1 }}>
                      <option value="">Padrao</option>
                      {instances.map(inst => <option key={inst.id} value={inst.id}>{inst.name} ({inst.model})</option>)}
                    </select>
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: '#666' }}>Nenhuma instancia configurada.</div>
                )}
              </div>

              <div style={{ fontSize: 10, color: '#555', marginTop: 8, borderTop: '1px solid #222', paddingTop: 8 }}>
                Provedor ativo: {selectedProvider} | Modelo: {selectedModel}
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
  chatLayout: { display: 'flex', flex: 1, minHeight: 0 },
  leftPanel: { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 },
  convBar: { padding: '4px 8px', borderBottom: '1px solid #222', display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, position: 'relative' as const },
  convNewBtn: { background: 'none', border: 'none', color: '#00d9ff', fontSize: 14, cursor: 'pointer', padding: '2px 4px', lineHeight: 1 },
  convMenuBtn: { flex: 1, background: 'none', border: 'none', color: '#ccc', fontSize: 11, textAlign: 'left', cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, padding: '2px 4px' },
  convDropdown: { position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100, background: '#1a1a2e', border: '1px solid #333', borderRadius: 6, maxHeight: 200, overflowY: 'auto', boxShadow: '0 4px 16px rgba(0,0,0,0.5)' },
  convItem: { padding: '6px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, borderBottom: '1px solid #222' },
  convActionBtn: { background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 10, padding: '0 2px' },
  modelSelect: { fontSize: 11, padding: '4px 8px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 3, color: '#ccc' },
  modelSelectWide: { fontSize: 11, padding: '4px 8px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 3, color: '#ccc', minWidth: 140 },
  settingsBtn: { background: 'none', border: '1px solid #333', color: '#ccc', fontSize: 12, cursor: 'pointer', padding: '2px 6px', borderRadius: 3 },
  messagesArea: { flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: 12, minHeight: 0 },
  emptyState: { color: '#555', textAlign: 'center', marginTop: 40, fontSize: 11, fontStyle: 'italic' },
  inputSection: { padding: '0 12px 8px 12px', flexShrink: 0 },
  textarea: { width: '100%', resize: 'none', padding: '8px', borderRadius: 4, border: '1px solid #333', background: '#1a1a2e', color: '#ccc', fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace", fontSize: 11, lineHeight: 1.4, boxSizing: 'border-box', outline: 'none' },
  iconBtn: { width: 28, height: 28, borderRadius: 4, border: '1px solid #333', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 },
  sendBtn: { width: 28, height: 28, borderRadius: 4, border: '1px solid #333', background: '#1a1a2e', color: '#ccc', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  rightPanel: { width: 280, display: 'flex', flexDirection: 'column', flexShrink: 0, borderLeft: '1px solid #222', minHeight: 0, background: '#08081a' },
  rightHeader: { padding: '8px 12px', borderBottom: '1px solid #1a1a2e', flexShrink: 0, display: 'flex', alignItems: 'center' },
  processList: { flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: 8, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 4 },
  processItem: { padding: '6px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)', borderLeft: '2px solid #444', fontSize: 10 },
  rightFooter: { padding: '6px 12px', borderTop: '1px solid #1a1a2e', display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 },
  modalOverlay: { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  modalContent: { background: '#0d0d1a', border: '1px solid #333', borderRadius: 12, width: '90%', maxWidth: 560, maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  modalHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #222', flexShrink: 0 },
  modalClose: { background: 'none', border: 'none', color: '#999', fontSize: 18, cursor: 'pointer', padding: '0 4px' },
  modalBody: { padding: 16, overflowY: 'auto', flex: 1 },
  settingsSection: { marginBottom: 16 },
  sectionTitle: { fontSize: 12, fontWeight: 700, color: '#00d9ff', marginBottom: 8, borderBottom: '1px solid #222', paddingBottom: 4 },
  settingsRow: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 },
  settingsLabel: { fontSize: 11, color: '#999', minWidth: 100, flexShrink: 0 },
  configInput: { flex: 1, padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', borderRadius: 4, color: '#ccc', fontSize: 11, outline: 'none', boxSizing: 'border-box' },
  saveBtn: { padding: '4px 12px', background: '#00d9ff', border: 'none', borderRadius: 3, color: '#000', fontSize: 10, fontWeight: 600, cursor: 'pointer', flexShrink: 0 },
  toggleBtn: { padding: '4px 14px', border: '1px solid #444', borderRadius: 4, fontSize: 11, fontWeight: 700, cursor: 'pointer', minWidth: 50, textAlign: 'center' as const },
};

export default JarvisPage;
