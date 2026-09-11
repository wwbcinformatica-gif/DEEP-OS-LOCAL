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

interface Message {
  id: string;
  role: 'user' | 'jarvis';
  content: string;
  timestamp: Date;
  tools?: ToolCall[];
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
  { id: 'gemini', label: 'Google Gemini', keyField: 'gemini', models: [
    { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (limitado)' },
    { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
    { id: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
  ]},
  { id: 'openrouter', label: 'OpenRouter (gratis/variados)', keyField: 'openrouter', models: [
    { id: 'openrouter/auto', label: 'Auto (melhor modelo)' },
    { id: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B (grátis)' },
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
];

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
      content: 'Olá! Sou o Jarvis, seu assistente inteligente. Posso ouvir você, executar tarefas e usar ferramentas. Como posso ajudar?',
      timestamp: new Date(),
    },
  ]);
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);

  // Load transcripts when active conversation changes
  useEffect(() => {
    if (activeConvId) {
      setTranscripts(getTranscripts(activeConvId));
    }
  }, [activeConvId]);

  // Save transcripts when they change
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
    if (typeof window !== 'undefined') {
      synthRef.current = window.speechSynthesis;
    }
  }, []);

  const startListening = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Seu navegador não suporta reconhecimento de voz. Use Chrome.');
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
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  };

  const speak = async (text: string) => {
    const voiceOpt = VOICE_OPTIONS.find(v => v.key === selectedVoice) || VOICE_OPTIONS[0];
    const clean = text.replace(/\*\*/g, '').replace(/[#>*_`]/g, '').trim();
    if (!clean) return;

    if (voiceOpt.type === 'edge') {
      try {
        synthRef.current?.cancel();
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
        audio.onended = () => { setIsSpeaking(false); URL.revokeObjectURL(audio.src); };
        audio.onerror = () => { setIsSpeaking(false); URL.revokeObjectURL(audio.src); };
        await audio.play().catch((e) => {
          console.warn('Audio play bloqueado, tentando browser TTS:', e);
          speakBrowser(clean, voiceOpt);
        });
        return;
      } catch (e) {
        console.warn('Edge TTS falhou, usando browser:', e);
      }
    }

    speakBrowser(clean, voiceOpt);
  };

  const speakBrowser = (text: string, voiceOpt: any) => {
    if (!synthRef.current) {
      synthRef.current = window.speechSynthesis;
    }
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
    if (synthRef.current) {
      synthRef.current.cancel();
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsSpeaking(false);
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

    const jarvisMsg: Message = {
      id: String(Date.now() + 1),
      role: 'jarvis',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      tools: [],
    };
    setMessages(prev => [...prev, jarvisMsg]);

    try {
      const token = tenantGet('saas_token') || localStorage.getItem('saas_token');
      const activeKey = selectedProvider === 'gemini' ? apiKey : (apiKeys[selectedProvider] || tenantGet(`${selectedProvider}_api_key`) || '');
      console.log('[Jarvis] Provider:', selectedProvider, 'Key:', activeKey ? '***' : 'VAZIA');
      const resp = await fetch('/chat/stream', {
        method: 'POST',
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

      if (!resp.ok) {
        throw new Error(`Erro ${resp.status}: ${resp.statusText}`);
      }

      const reader = resp.body?.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = '';
      let buffer = '';

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
                setMessages(prev => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.id === jarvisMsg.id) {
                    updated[updated.length - 1] = { ...last, content: fullAnswer };
                  }
                  return updated;
                });
              } else if (event.type === 'tool_start') {
                const tools = [...(jarvisMsg.tools || [])];
                tools.push({
                  name: event.tool_name || 'unknown',
                  params: event.params || {},
                  status: 'running',
                });
                setMessages(prev => {
                  const updated = [...prev];
                  const idx = updated.findIndex(m => m.id === jarvisMsg.id);
                  if (idx >= 0) updated[idx] = { ...updated[idx], tools };
                  return updated;
                });
              } else if (event.type === 'tool_end') {
                setMessages(prev => {
                  const updated = [...prev];
                  const idx = updated.findIndex(m => m.id === jarvisMsg.id);
                  if (idx >= 0) {
                    const tools = [...(updated[idx].tools || [])];
                    const lastTool = tools.length - 1;
                    if (lastTool >= 0) {
                      tools[lastTool] = { ...tools[lastTool], result: event.result, status: 'done' };
                    }
                    updated[idx] = { ...updated[idx], tools };
                  }
                  return updated;
                });
              } else if (event.type === 'error') {
                fullAnswer += `\n\n❌ Erro: ${event.message}`;
                setMessages(prev => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.id === jarvisMsg.id) {
                    updated[updated.length - 1] = { ...last, content: fullAnswer };
                  }
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
        if (idx >= 0) {
          updated[idx] = { ...updated[idx], content: fullAnswer, isStreaming: false };
        }
        return updated;
      });

      if (fullAnswer) speak(fullAnswer);

    } catch (err: any) {
      setMessages(prev => {
        const updated = [...prev];
        const idx = updated.findIndex(m => m.id === jarvisMsg.id);
        if (idx >= 0) {
          updated[idx] = {
            ...updated[idx],
            content: `Desculpe, ocorreu um erro: ${err.message}. Verifique se o backend está rodando e se sua chave de API está configurada.`,
            isStreaming: false,
          };
        }
        return updated;
      });
    }

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
    // Auto-resize textarea
    const target = e.target;
    setTimeout(() => {
      target.style.height = 'auto';
      target.style.height = Math.min(target.scrollHeight, 150) + 'px';
    }, 0);
  };

  // ─── Conversation management ───────────────────────────────────
  const switchConversation = (convId: string) => {
    setActiveConvId(convId);
    setShowConvMenu(false);
  };

  const newConversation = () => {
    const conv = createConversation();
    setConversations(getConversations());
    setActiveConvId(conv.id);
    setTranscripts([]);
    setMessages([{
      id: '1',
      role: 'jarvis',
      content: 'Olá! Sou o Jarvis, seu assistente inteligente. Como posso ajudar?',
      timestamp: new Date(),
    }]);
    setShowConvMenu(false);
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
      } else {
        const conv = createConversation();
        setConversations(getConversations());
        setActiveConvId(conv.id);
        setTranscripts([]);
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

  return (
    <div style={styles.container} className="jarvis-container">
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.jarvisIcon}>🤖</div>
          <div>
            <h1 style={styles.title}>Jarvis</h1>
            <p style={styles.subtitle}>Assistente Inteligente com Voz e Ferramentas</p>
          </div>
        </div>
        {/* Conversation selector */}
        <div style={{ position: 'relative' as const, display: 'flex', alignItems: 'center', gap: 4 }}>
          <button onClick={newConversation} title="Nova conversa" style={{ background: 'none', border: '1px solid #333', color: '#00d9ff', fontSize: 13, cursor: 'pointer', padding: '4px 8px', borderRadius: 4 }}>+</button>
          <button
            onClick={() => setShowConvMenu(!showConvMenu)}
            style={{
              background: 'rgba(255,255,255,0.05)', border: '1px solid #333', borderRadius: 4,
              color: '#ccc', fontSize: 11, textAlign: 'left', cursor: 'pointer',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
              padding: '4px 8px', maxWidth: 180,
            }}
          >
            {activeConv?.name || 'Nova conversa'}
          </button>
          {showConvMenu && (
            <div style={{
              position: 'absolute', top: '100%', right: 0, zIndex: 100,
              background: '#1a1a2e', border: '1px solid #333', borderRadius: 6,
              maxHeight: 200, overflowY: 'auto', boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
              minWidth: 200,
            }}>
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => switchConversation(conv.id)}
                  style={{
                    padding: '6px 8px', cursor: 'pointer', display: 'flex',
                    alignItems: 'center', gap: 6,
                    background: conv.id === activeConvId ? 'rgba(0,217,255,0.15)' : 'transparent',
                    borderBottom: '1px solid #222',
                  }}
                >
                  <span style={{ flex: 1, fontSize: 11, color: conv.id === activeConvId ? '#00d9ff' : '#ccc', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
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
        <div style={{ ...styles.headerRight, flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <select
              value={selectedProvider}
              onChange={(e) => {
                setSelectedProvider(e.target.value);
                const prov = PROVIDERS.find(p => p.id === e.target.value);
                if (prov) setSelectedModel(prov.models[0].id);
              }}
              style={styles.modelSelect}
            >
              {PROVIDERS.map(p => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              style={styles.modelSelect}
            >
              {(PROVIDERS.find(p => p.id === selectedProvider)?.models || []).map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            <button style={styles.settingsBtn} onClick={() => setShowSettings(!showSettings)} title="Configurações">
              ⚙️
            </button>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div style={{
          background: 'var(--saas-bg-card)',
          border: '1px solid var(--saas-border)',
          borderRadius: 8,
          padding: 16,
          marginBottom: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          {PROVIDERS.map(prov => (
            <div key={prov.id}>
              <label style={{ fontSize: 12, color: 'var(--saas-text-muted)', display: 'block', marginBottom: 4 }}>
                🔑 {prov.label} API Key
              </label>
              <input
                type="password"
                value={prov.keyField === 'gemini' ? apiKey : (apiKeys[prov.keyField] || '')}
                onChange={(e) => {
                  if (prov.keyField === 'gemini') {
                    setApiKey(e.target.value);
                  } else {
                    setApiKeys({ ...apiKeys, [prov.keyField]: e.target.value });
                  }
                }}
                placeholder={prov.id === 'gemini' ? 'AIza...' : prov.id === 'openrouter' ? 'sk-or-v1-...' : 'sk-...'}
                style={styles.apiInput}
              />
              <button onClick={() => {
                const key = prov.keyField === 'gemini' ? apiKey : (apiKeys[prov.keyField] || '');
                if (prov.keyField === 'gemini') {
                  tenantSet('saas_api_key', key);
                  setApiKey(key);
                  fetch('/api/config/api-key', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gemini_api_key: key }) }).catch(() => {});
                } else {
                  tenantSet(`${prov.keyField}_api_key`, key);
                  setApiKeys({ ...apiKeys, [prov.keyField]: key });
                }
                alert(`Chave ${prov.label} salva!`);
              }} style={styles.saveKeyBtn}>Salvar {prov.label}</button>
            </div>
          ))}

          {/* Instancia */}
          {instances.length > 0 && (
            <div>
              <label style={{ fontSize: 12, color: 'var(--saas-text-muted)', display: 'block', marginBottom: 4 }}>Instância</label>
              <select
                value={selectedInstanceId}
                onChange={(e) => {
                  const id = e.target.value;
                  setSelectedInstanceId(id);
                  tenantSet('jarvis_instance_id', id);
                  if (id) {
                    const inst = instances.find(i => i.id === id);
                    if (inst) {
                      setSelectedModel(inst.model);
                      setSelectedProvider(inst.provider);
                      setInstanceConfig(inst);
                    }
                  } else {
                    setInstanceConfig(null);
                  }
                }}
                style={styles.apiInput}
              >
                <option value="">— Padrão —</option>
                {instances.map(inst => (
                  <option key={inst.id} value={inst.id}>{inst.name} ({inst.model})</option>
                ))}
              </select>
            </div>
          )}

          {/* Voz */}
          <div>
            <label style={{ fontSize: 12, color: 'var(--saas-text-muted)', display: 'block', marginBottom: 4 }}>🎙️ Voz</label>
            <select
              value={selectedVoice}
              onChange={(e) => {
                setSelectedVoice(e.target.value);
                tenantSet('jarvis_voice', e.target.value);
              }}
              style={styles.apiInput}
            >
              {VOICE_OPTIONS.map(v => (
                <option key={v.key} value={v.key}>{v.label} — {v.desc}</option>
              ))}
            </select>
          </div>

          {/* Velocidade */}
          <div>
            <label style={{ fontSize: 12, color: 'var(--saas-text-muted)', display: 'block', marginBottom: 4 }}>
              🔊 Velocidade da voz: {voiceRate.toFixed(1)}x
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#666' }}>Lento</span>
              <input
                type="range"
                min="0.5"
                max="3"
                step="0.1"
                value={voiceRate}
                onChange={(e) => {
                  const rate = parseFloat(e.target.value);
                  setVoiceRate(rate);
                  tenantSet('jarvis_voice_rate', String(rate));
                }}
                style={{ flex: 1 }}
              />
              <span style={{ fontSize: 11, color: '#666' }}>Rápido</span>
            </div>
          </div>

          {/* Tom */}
          <div>
            <label style={{ fontSize: 12, color: 'var(--saas-text-muted)', display: 'block', marginBottom: 4 }}>
              🎵 Tom da voz: {voicePitch}%
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#666' }}>Grave</span>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={voicePitch}
                onChange={(e) => {
                  const pitch = parseInt(e.target.value);
                  setVoicePitch(pitch);
                  tenantSet('jarvis_voice_pitch', String(pitch));
                }}
                style={{ flex: 1 }}
              />
              <span style={{ fontSize: 11, color: '#666' }}>Agudo</span>
            </div>
          </div>

          <div style={{ fontSize: 11, color: 'var(--saas-text-muted)' }}>
            Provedor: {selectedProvider} | Modelo: {selectedModel}
          </div>
        </div>
      )}

      {/* Chat Area */}
      <div style={styles.chatContainer}>
        <div style={styles.messagesArea}>
          {messages.map(msg => (
            <div
              key={msg.id}
              style={{
                ...styles.message,
                ...(msg.role === 'jarvis' ? styles.messageJarvis : styles.messageUser),
              }}
            >
              {msg.role === 'jarvis' && (
                <div style={styles.avatarJarvis}>J</div>
              )}
              <div style={styles.messageContent}>
                <p style={styles.messageText}>
                  {msg.content}
                  {msg.isStreaming && <span style={styles.cursor}>▌</span>}
                </p>

                {/* Tool Calls */}
                {msg.tools && msg.tools.length > 0 && (
                  <div style={styles.toolsContainer}>
                    {msg.tools.map((tool, i) => (
                      <div key={i} style={{
                        ...styles.toolCard,
                        borderColor: tool.status === 'running' ? '#f59e0b' :
                                   tool.status === 'done' ? '#10b981' : '#ef4444',
                      }}>
                        <div style={styles.toolHeader}>
                          <span style={styles.toolIcon}>🔧</span>
                          <span style={styles.toolName}>{tool.name}</span>
                          <span style={{
                            ...styles.toolStatus,
                            color: tool.status === 'running' ? '#f59e0b' :
                                  tool.status === 'done' ? '#10b981' : '#ef4444',
                          }}>
                            {tool.status === 'running' ? '⏳ Executando...' :
                             tool.status === 'done' ? '✅ Concluído' : '❌ Erro'}
                          </span>
                        </div>
                        {tool.result && (
                          <pre style={styles.toolResult}>{tool.result}</pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <span style={styles.messageTime}>
                  {msg.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              {msg.role === 'user' && (
                <div style={styles.avatarUser}>W</div>
              )}
            </div>
          ))}

          {isTyping && (
            <div style={{...styles.message, ...styles.messageJarvis}}>
              <div style={styles.avatarJarvis}>J</div>
              <div style={styles.messageContent}>
                <div style={styles.typingIndicator}>
                  <span style={styles.typingDot}></span>
                  <span style={styles.typingDot}></span>
                  <span style={styles.typingDot}></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div style={styles.inputArea}>
          <button
            style={{
              ...styles.voiceBtn,
              background: isListening ? '#ef4444' : 'var(--saas-bg-card)',
              color: isListening ? '#fff' : 'var(--saas-text)',
            }}
            onClick={isListening ? stopListening : startListening}
            title={isListening ? 'Parar de ouvir' : 'Ouvir voz'}
          >
            {isListening ? '⏹' : '🎤'}
          </button>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? 'Ouvindo...' : 'Digite sua mensagem...'}
            rows={1}
            style={{
              ...styles.textarea,
              borderColor: isListening ? '#ef4444' : 'var(--saas-border)',
            }}
            disabled={isTyping}
          />

          <button
            style={styles.sendBtn}
            onClick={handleSendMessage}
            disabled={!input.trim() || isTyping}
          >
            {isTyping ? '⏳' : 'Enviar'}
          </button>

          <button
            onClick={stopSpeaking}
            disabled={!isSpeaking}
            style={{
              ...styles.voiceBtn,
              background: isSpeaking ? '#ef4444' : 'var(--saas-bg-card)',
              color: isSpeaking ? '#fff' : '#666',
              opacity: isSpeaking ? 1 : 0.4,
              cursor: isSpeaking ? 'pointer' : 'default',
            }}
            title={isSpeaking ? 'Parar voz' : 'Jarvis não está falando'}
          >
            {isSpeaking ? '🔇' : '🔈'}
          </button>
        </div>
      </div>
    </div>
  );
};

const OllamaStatus: React.FC = () => {
  const [status, setStatus] = useState<'loading' | 'online' | 'offline'>('loading');

  useEffect(() => {
    fetch('http://localhost:11434/api/tags')
      .then(r => r.ok ? setStatus('online') : setStatus('offline'))
      .catch(() => setStatus('offline'));
  }, []);

  return (
    <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
      <div style={{
        width: '10px', height: '10px', borderRadius: '50%',
        background: status === 'online' ? '#10b981' : status === 'loading' ? '#f59e0b' : '#ef4444',
      }}/>
      <span style={{fontSize: '13px', color: 'var(--saas-text-muted)'}}>
        {status === 'online' ? 'Ollama conectado' :
         status === 'loading' ? 'Verificando...' : 'Ollama offline (instale em ollama.com)'}
      </span>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    padding: '16px 24px 0 24px',
    color: 'var(--saas-text)',
    overflowY: 'auto',
    overflowX: 'hidden',
    WebkitOverflowScrolling: 'touch',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
    flexShrink: 0,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  jarvisIcon: {
    width: '40px',
    height: '40px',
    background: 'linear-gradient(135deg, var(--saas-accent), #00ff88)',
    borderRadius: '10px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '20px',
  },
  title: { fontSize: '20px', fontWeight: 'bold', margin: 0 },
  subtitle: { fontSize: '12px', color: 'var(--saas-text-muted)', margin: 0 },
  headerRight: { display: 'flex', gap: '8px', alignItems: 'center' },
  modelSelect: {
    padding: '5px 8px',
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 6,
    color: 'var(--saas-text-muted)',
    fontSize: 11,
    cursor: 'pointer',
  },
  settingsBtn: {
    padding: '5px 8px',
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 6,
    cursor: 'pointer',
    fontSize: '13px',
    color: 'var(--saas-text-muted)',
  },
  apiInput: {
    width: '100%',
    padding: '8px 12px',
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: 6,
    color: 'var(--saas-text)',
    fontSize: 13,
    boxSizing: 'border-box',
  },
  saveKeyBtn: {
    marginTop: 4,
    padding: '4px 10px',
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 4,
    color: 'var(--saas-text-muted)',
    fontSize: 10,
    cursor: 'pointer',
  },
  chatContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '12px',
    marginBottom: '8px',
  },
  messagesArea: {
    flex: 1,
    padding: '20px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  message: { display: 'flex', gap: '12px', maxWidth: '85%' },
  messageJarvis: { alignSelf: 'flex-start' },
  messageUser: { alignSelf: 'flex-end', flexDirection: 'row-reverse' },
  avatarJarvis: {
    width: '36px', height: '36px',
    background: 'linear-gradient(135deg, var(--saas-accent), #00ff88)',
    borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '14px', fontWeight: 'bold', color: '#000', flexShrink: 0,
  },
  avatarUser: {
    width: '36px', height: '36px',
    background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
    borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '14px', fontWeight: 'bold', color: '#fff', flexShrink: 0,
  },
  messageContent: {
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: '12px',
    padding: '12px 16px',
  },
  messageText: { margin: 0, fontSize: '14px', lineHeight: 1.6, whiteSpace: 'pre-wrap' },
  cursor: { animation: 'blink 1s infinite', color: 'var(--saas-accent)' },
  toolsContainer: { marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' },
  toolCard: {
    padding: '10px 12px',
    background: 'var(--saas-bg-card)',
    border: '1px solid',
    borderRadius: '8px',
  },
  toolHeader: { display: 'flex', alignItems: 'center', gap: '8px' },
  toolIcon: { fontSize: '14px' },
  toolName: { fontSize: '13px', fontWeight: '600', color: 'var(--saas-text)' },
  toolStatus: { fontSize: '12px', marginLeft: 'auto' },
  toolResult: {
    marginTop: '8px',
    padding: '8px',
    background: 'var(--saas-bg-input)',
    borderRadius: '6px',
    fontSize: '11px',
    fontFamily: 'monospace',
    color: 'var(--saas-text-muted)',
    overflow: 'auto',
    maxHeight: '150px',
    whiteSpace: 'pre-wrap',
  },
  messageTime: { fontSize: '11px', color: 'var(--saas-text-muted)', marginTop: '4px', display: 'block' },
  typingIndicator: { display: 'flex', gap: '4px', padding: '4px 0' },
  typingDot: {
    width: '8px', height: '8px', background: 'var(--saas-text-muted)',
    borderRadius: '50%', animation: 'pulse 1.4s infinite',
  },
  inputArea: {
    display: 'flex', gap: '6px', padding: '8px 0 16px 0',
    background: 'transparent',
  },
  voiceBtn: {
    padding: '8px', border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 6, cursor: 'pointer', fontSize: '14px',
    transition: 'all 0.2s', flexShrink: 0,
    background: 'transparent',
  },
  sendBtn: {
    padding: '8px 14px', background: 'transparent',
    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 6,
    color: 'var(--saas-text-muted)',
    fontSize: '12px', cursor: 'pointer', flexShrink: 0,
  },
  stopSpeakBtn: {
    padding: '12px', background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '8px', color: '#ef4444', fontSize: '12px', cursor: 'pointer',
  },
  textarea: {
    flex: 1,
    padding: '12px 16px',
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: '8px',
    color: 'var(--saas-text)',
    fontSize: '14px',
    resize: 'vertical' as const,
    minHeight: '44px',
    maxHeight: '150px',
    lineHeight: 1.5,
    fontFamily: 'inherit',
    outline: 'none',
    overflow: 'auto',
  },
};

export default JarvisPage;
