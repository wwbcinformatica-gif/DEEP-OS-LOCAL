import React, { useState, useEffect } from 'react';

const TABS = [
  { id: 'connect', label: 'Conectar', icon: '🔗' },
  { id: 'assistant', label: 'Assistente', icon: '🤖' },
  { id: 'providers', label: 'Providers IA', icon: '🧠' },
  { id: 'knowledge', label: 'Base Conhecimento', icon: '📚' },
  { id: 'tools', label: 'Ferramentas', icon: '🛠️' },
  { id: 'campaign', label: 'Campanha Manual', icon: '📢' },
  { id: 'auto_group', label: 'Msg Auto Grupo', icon: '👥' },
  { id: 'auto_private', label: 'Msg Auto Privado', icon: '💬' },
];

const PROVIDERS = [
  { id: 'none', label: 'Nenhum', icon: '❌', color: '#ef4444' },
  { id: 'gemini', label: 'Gemini', icon: '💎', color: '#3b82f6' },
  { id: 'ollama', label: 'Ollama (Local)', icon: '🦙', color: '#10b981' },
  { id: 'openai', label: 'OpenAI', icon: '🤖', color: '#8b5cf6' },
];

interface ChatBotConfig {
  provider: string;
  ollama_url: string;
  ollama_model: string;
  gemini_model: string;
  gemini_api_key: string;
  openai_model: string;
  openai_api_key: string;
  assistant_name: string;
  assistant_personality: string;
  welcome_message: string;
}

export default function ChatBotPage() {
  const [activeTab, setActiveTab] = useState('providers');
  const [config, setConfig] = useState<ChatBotConfig>({
    provider: 'ollama',
    ollama_url: 'http://localhost:11434',
    // Defaults corrigidos: 'llama3' e 'gemini-2.0-flash' nao existem mais
    // (o segundo foi removido pela API do Google). Ver tools/MODELOS-PROVADOS.md.
    ollama_model: 'qwen2.5-coder:7b',
    gemini_model: 'gemini-2.5-flash',
    gemini_api_key: '',
    openai_model: 'gpt-4o-mini',
    openai_api_key: '',
    assistant_name: 'Assistente',
    assistant_personality: 'Voce e um assistente util e educado.',
    welcome_message: 'Ola! Como posso ajudar?',
  });
  const [testMessage, setTestMessage] = useState('ola');
  const [testResult, setTestResult] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);

  useEffect(() => {
    fetch('/api/chatbot/config')
      .then(r => r.json())
      .then(data => { if (data && data.provider) setConfig(data); })
      .catch(() => {});

    fetch('http://localhost:11434/api/tags')
      .then(r => r.json())
      .then(data => {
        if (data && data.models) {
          setOllamaModels(data.models.map((m: any) => m.name));
        }
      })
      .catch(() => {});
  }, []);

  const saveConfig = async () => {
    try {
      await fetch('/api/chatbot/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      alert('Configuracoes salvas!');
    } catch (e) {
      alert('Erro ao salvar');
    }
  };

  const testProvider = async () => {
    setIsTesting(true);
    setTestResult('Testando...');
    try {
      const res = await fetch('/api/chatbot/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: config.provider, message: testMessage }),
      });
      const data = await res.json();
      setTestResult(data.response || data.error || 'Sem resposta');
    } catch (e) {
      setTestResult('Erro ao conectar');
    }
    setIsTesting(false);
  };

  const connectWhatsApp = async () => {
    try {
      const res = await fetch('/api/chatbot/connect', { method: 'POST' });
      const data = await res.json();
      setTestResult(data.message || 'Conectando...');
      setConnected(true);
    } catch (e) {
      setTestResult('Erro ao conectar WhatsApp');
    }
  };

  const s = {
    content: { padding: '0', color: '#333', fontSize: '13px' } as React.CSSProperties,
    tabsBar: { display: 'flex', gap: '6px', padding: '12px 16px', background: '#fff', borderRadius: '10px', marginBottom: '16px', flexWrap: 'wrap', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' } as React.CSSProperties,
    tab: (active: boolean) => ({
      padding: '7px 14px', background: active ? '#10b981' : 'transparent', border: active ? 'none' : '1px solid #e5e7eb',
      borderRadius: '16px', color: active ? '#fff' : '#666', cursor: 'pointer', fontSize: '12px', fontWeight: active ? '600' : '400',
      display: 'flex', alignItems: 'center', gap: '5px', whiteSpace: 'nowrap' as const,
    }),
    card: { background: '#fff', borderRadius: '10px', padding: '16px', marginBottom: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' } as React.CSSProperties,
    cardTitle: { fontSize: '14px', fontWeight: '700', color: '#111', marginTop: 0, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' } as React.CSSProperties,
    cardSubtitle: { fontSize: '12px', color: '#888', marginBottom: '12px' } as React.CSSProperties,
    label: { fontSize: '10px', fontWeight: '700', color: '#999', textTransform: 'uppercase' as const, letterSpacing: '0.5px', marginBottom: '4px', display: 'block' } as React.CSSProperties,
    input: { width: '100%', padding: '8px 12px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '6px', color: '#333', fontSize: '13px', outline: 'none', marginBottom: '12px', boxSizing: 'border-box' as const } as React.CSSProperties,
    btnGreen: { padding: '8px 20px', background: '#10b981', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' } as React.CSSProperties,
    btnProvider: (active: boolean, color: string) => ({
      padding: '8px 16px', background: active ? color + '15' : '#f9fafb', border: `1px solid ${active ? color : '#e5e7eb'}`,
      borderRadius: '6px', color: active ? color : '#666', cursor: 'pointer', fontSize: '12px', fontWeight: active ? '600' : '400',
      display: 'flex', alignItems: 'center', gap: '5px',
    }),
    testResult: { marginTop: '8px', padding: '8px 12px', background: '#f9fafb', borderRadius: '6px', color: '#333', fontSize: '12px', border: '1px solid #e5e7eb' } as React.CSSProperties,
    placeholder: { padding: '30px', background: '#fff', borderRadius: '10px', textAlign: 'center' as const, color: '#999', boxShadow: '0 1px 3px rgba(0,0,0,0.06)', fontSize: '13px' } as React.CSSProperties,
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'connect':
        return (
          <div>
            <div style={s.card}>
              <h3 style={s.cardTitle}>WhatsApp</h3>
              <p style={s.cardSubtitle}>Conecte seu WhatsApp para automatizar atendimento</p>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: connected ? '#10b981' : '#ef4444' }} />
                <span style={{ color: '#333', fontSize: '12px' }}>{connected ? 'Conectado' : 'Desconectado'}</span>
              </div>
              <button onClick={connectWhatsApp} style={s.btnGreen}>Conectar WhatsApp</button>
            </div>
            {testResult && <div style={s.testResult}>{testResult}</div>}
          </div>
        );

      case 'assistant':
        return (
          <div>
            <div style={s.card}>
              <h3 style={s.cardTitle}>Configuracoes do Assistente</h3>
              <label style={s.label}>Nome do Assistente</label>
              <input style={s.input} value={config.assistant_name} onChange={e => setConfig({ ...config, assistant_name: e.target.value })} />
              <label style={s.label}>Personalidade</label>
              <textarea style={{ ...s.input, minHeight: '60px', resize: 'vertical' as const }} value={config.assistant_personality} onChange={e => setConfig({ ...config, assistant_personality: e.target.value })} />
              <label style={s.label}>Mensagem de Boas-vindas</label>
              <input style={s.input} value={config.welcome_message} onChange={e => setConfig({ ...config, welcome_message: e.target.value })} />
              <button onClick={saveConfig} style={s.btnGreen}>Salvar</button>
            </div>
          </div>
        );

      case 'providers':
        return (
          <div>
            <div style={s.card}>
              <h3 style={s.cardTitle}>Provider de IA</h3>
              <p style={s.cardSubtitle}>Escolha qual inteligencia artificial vai responder as mensagens dos clientes.</p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {PROVIDERS.map(p => (
                  <button key={p.id} onClick={() => setConfig({ ...config, provider: p.id })} style={s.btnProvider(config.provider === p.id, p.color)}>
                    <span>{p.icon}</span> {p.label}
                  </button>
                ))}
              </div>
            </div>

            {config.provider === 'ollama' && (
              <div style={s.card}>
                <h3 style={s.cardTitle}>Ollama (Local)</h3>
                <label style={s.label}>URL do Servidor</label>
                <input style={s.input} value={config.ollama_url} onChange={e => setConfig({ ...config, ollama_url: e.target.value })} />
                <label style={s.label}>Modelo</label>
                {ollamaModels.length > 0 ? (
                  <select
                    style={{ ...s.input, cursor: 'pointer' }}
                    value={config.ollama_model}
                    onChange={e => setConfig({ ...config, ollama_model: e.target.value })}
                  >
                    {ollamaModels.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                ) : (
                  <input style={s.input} value={config.ollama_model} onChange={e => setConfig({ ...config, ollama_model: e.target.value })} placeholder="Digite o nome do modelo" />
                )}
                {ollamaModels.length > 0 && (
                  <p style={{ fontSize: '10px', color: '#999', margin: '4px 0 0' }}>{ollamaModels.length} modelos encontrados no Ollama</p>
                )}
              </div>
            )}

            {config.provider === 'gemini' && (
              <div style={s.card}>
                <h3 style={s.cardTitle}>Gemini</h3>
                <label style={s.label}>API Key</label>
                <input style={s.input} type="password" value={config.gemini_api_key} onChange={e => setConfig({ ...config, gemini_api_key: e.target.value })} placeholder="AIzaSy..." />
                <label style={s.label}>Modelo</label>
                <input style={s.input} value={config.gemini_model} onChange={e => setConfig({ ...config, gemini_model: e.target.value })} />
              </div>
            )}

            {config.provider === 'openai' && (
              <div style={s.card}>
                <h3 style={s.cardTitle}>OpenAI</h3>
                <label style={s.label}>API Key</label>
                <input style={s.input} type="password" value={config.openai_api_key} onChange={e => setConfig({ ...config, openai_api_key: e.target.value })} placeholder="sk-..." />
                <label style={s.label}>Modelo</label>
                <input style={s.input} value={config.openai_model} onChange={e => setConfig({ ...config, openai_model: e.target.value })} />
              </div>
            )}

            <div style={s.card}>
              <h3 style={s.cardTitle}>Testar Provider</h3>
              <label style={s.label}>Mensagem de Teste</label>
              <input style={s.input} value={testMessage} onChange={e => setTestMessage(e.target.value)} />
              <button onClick={testProvider} style={s.btnGreen} disabled={isTesting}>{isTesting ? 'Testando...' : 'Testar'}</button>
              {testResult && <div style={s.testResult}>{testResult}</div>}
            </div>

            <button onClick={saveConfig} style={{ ...s.btnGreen, width: '100%', padding: '10px', marginTop: '4px' }}>Salvar configuracoes</button>
          </div>
        );

      case 'knowledge':
        return <div style={s.placeholder}>Base de Conhecimento - Em breve</div>;
      case 'tools':
        return <div style={s.placeholder}>Ferramentas - Em breve</div>;
      case 'campaign':
        return <div style={s.placeholder}>Campanha Manual - Em breve</div>;
      case 'auto_group':
        return <div style={s.placeholder}>Msg Auto Grupo - Em breve</div>;
      case 'auto_private':
        return <div style={s.placeholder}>Msg Auto Privado - Em breve</div>;
      default:
        return null;
    }
  };

  return (
    <div style={s.content}>
      <div style={s.tabsBar}>
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={s.tab(activeTab === tab.id)}>
            <span>{tab.icon}</span> {tab.label}
          </button>
        ))}
      </div>
      {renderContent()}
    </div>
  );
}
