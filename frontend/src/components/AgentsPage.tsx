import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { AGENTS_LIST, API_BASE } from '../lib/constants';
import type { AccentTheme, Mood } from '../lib/constants';
import { ACCENT_THEMES } from '../lib/constants';

type VoicePreset =
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

type SubTab = 'agents' | 'voz' | 'agente' | 'assistente';

const VOICE_OPTIONS = [
  { key: 'google-female' as const, label: 'Google PT-BR Feminino', desc: 'Voz clara e natural' },
  { key: 'francisca' as const, label: 'Francisca (Feminino)', desc: 'Voz feminina brasileira classica' },
  { key: 'maria' as const, label: 'Maria (Feminino)', desc: 'Voz feminina suave e natural' },
  { key: 'google-male' as const, label: 'Google PT-BR Masculino', desc: 'Voz masculina nativa' },
  { key: 'antonio' as const, label: 'Antonio (Masculino)', desc: 'Voz masculina brasileira profunda' },
  { key: 'daniel' as const, label: 'Daniel (Masculino)', desc: 'Voz masculina estavel e clara' },
  { key: 'jarvis-cinematic' as const, label: 'Jarvis Cinematic', desc: 'Tom grave, levemente cinematografico' },
  { key: 'edge-francisca' as const, label: 'Francisca Neural (Edge)', desc: 'Voz feminina natural Microsoft Neural' },
  { key: 'edge-thalita' as const, label: 'Thalita Neural (Edge)', desc: 'Voz feminina clara Microsoft Neural' },
  { key: 'dani-brandi' as const, label: 'Dani Brandi (Google)', desc: 'Voz feminina brasileira bonita e natural' },
  { key: 'eleven-natasha' as const, label: 'Natasha (ElevenLabs)', desc: 'Sensual, hipnotica e brincalhona' },
  { key: 'eleven-serafina' as const, label: 'Serafina (ElevenLabs)', desc: 'Sedutora sensual e charmosa' },
  { key: 'eleven-ivy' as const, label: 'Ivy (ElevenLabs)', desc: 'Suave, expressiva e calorosa' },
  { key: 'eleven-ingmar' as const, label: 'Ingmar (ElevenLabs)', desc: 'Masculina, misteriosa e envolvente' },
];

interface DropdownOption {
  label: string;
  value: string;
  group?: string;
}

function CustomDropdown({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: DropdownOption[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node) && !(e.target as HTMLElement).closest('[data-dropdown-portal]')) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleOpen = () => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
    }
    setOpen(!open);
  };

  const selected = options.find(o => o.value === value);
  const groups = [...new Set(options.map(o => o.group).filter(Boolean))];

  return (
    <>
      <div ref={ref} style={{ position: 'relative', width: '100%' }}>
        <div
          onClick={handleOpen}
          style={{
            width: '100%',
            background: 'var(--input-bg)',
            border: '1px solid var(--line-strong)',
            borderRadius: '4px',
            color: 'var(--ink)',
            padding: '5px 8px',
            fontSize: '11px',
            cursor: 'pointer',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>{selected?.label || value}</span>
          <span style={{ fontSize: '8px', color: 'var(--muted)' }}>{open ? '▲' : '▼'}</span>
        </div>
      </div>
      {open && ReactDOM.createPortal(
        <div
          data-dropdown-portal="true"
          style={{
            position: 'fixed',
            top: pos.top,
            left: pos.left,
            width: pos.width,
            background: 'var(--bg-2)',
            border: '1px solid var(--line-strong)',
            borderRadius: '4px',
            maxHeight: 480,
            overflowY: 'auto',
            zIndex: 99999,
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          {groups.length > 0 ? groups.map(group => (
            <div key={group}>
              <div style={{ padding: '6px 10px', fontSize: '11px', fontWeight: 700, color: 'var(--accent)', background: 'var(--bg-3)', borderTop: '1px solid var(--line)' }}>
                {group}
              </div>
              {options.filter(o => o.group === group).map(opt => (
                <div
                  key={opt.value}
                  onClick={(e) => { e.stopPropagation(); onChange(opt.value); setOpen(false); }}
                  style={{
                    padding: '8px 10px',
                    fontSize: '12px',
                    cursor: 'pointer',
                    background: opt.value === value ? 'var(--accent-soft)' : 'transparent',
                    color: opt.value === value ? 'var(--accent)' : 'var(--ink)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-3)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = opt.value === value ? 'var(--accent-soft)' : 'transparent')}
                >
                  {opt.label}
                </div>
              ))}
            </div>
          )) : options.map(opt => (
            <div
              key={opt.value}
              onClick={(e) => { e.stopPropagation(); onChange(opt.value); setOpen(false); }}
              style={{
                padding: '8px 10px',
                fontSize: '12px',
                cursor: 'pointer',
                background: opt.value === value ? 'var(--accent-soft)' : 'transparent',
                color: opt.value === value ? 'var(--accent)' : 'var(--ink)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-3)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = opt.value === value ? 'var(--accent-soft)' : 'transparent')}
            >
              {opt.label}
            </div>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}

const MODEL_OPTIONS: DropdownOption[] = [
  { group: 'Coding', label: 'qwen2.5-coder:14b (9GB)', value: 'qwen2.5-coder:14b' },
  { group: 'Coding', label: 'qwen2.5-coder:7b (4.7GB)', value: 'qwen2.5-coder:7b' },
  { group: 'Coding', label: 'deepseek-coder-v2 (8.9GB)', value: 'deepseek-coder-v2:latest' },
  { group: 'Coding', label: 'deepseek-coder:6.7b (3.8GB)', value: 'deepseek-coder:6.7b' },
  { group: 'Raciocinio', label: 'qwen3:14b (9.3GB)', value: 'qwen3:14b' },
  { group: 'Raciocinio', label: 'qwen3.5:9b (6.6GB)', value: 'qwen3.5:9b' },
  { group: 'Raciocinio', label: 'deepseek-r1 (5.2GB)', value: 'deepseek-r1:latest' },
  { group: 'Raciocinio', label: 'deepseek-r1:14b (9GB)', value: 'deepseek-r1:14b' },
  { group: 'Raciocinio', label: 'deepseek-r1:7b (4.7GB)', value: 'deepseek-r1:7b' },
  { group: 'Raciocinio', label: 'deepseek-r1:1.5b (1.1GB)', value: 'deepseek-r1:1.5b' },
  { group: 'Geral', label: 'qwen2.5:7b (4.7GB)', value: 'qwen2.5-7b:latest' },
  { group: 'Geral', label: 'llama-3.2:3b (2GB)', value: 'llama-3.2-3b:latest' },
  { group: 'Geral', label: 'gemma4:12b (7.6GB)', value: 'gemma4:12b' },
  { group: 'Geral', label: 'mistral-nemo:12b (7.1GB)', value: 'mistral-nemo:12b' },
  { group: 'Multimodal', label: 'qwen3-vl:8b (6.1GB)', value: 'qwen3-vl:8b' },
  { group: 'Multimodal', label: 'qwen2.5vl:7b (6GB)', value: 'qwen2.5vl:7b' },
  { group: 'Multimodal', label: 'llava (4.7GB)', value: 'llava:latest' },
  { group: 'Cloud (gratuito)', label: 'gpt-oss:120b-cloud', value: 'gpt-oss:120b-cloud' },
  { group: 'Cloud (gratuito)', label: 'kimi-k3:cloud', value: 'kimi-k3:cloud' },
  { group: 'Cloud (gratuito)', label: 'glm-5.2:cloud', value: 'glm-5.2:cloud' },
  { group: 'Cloud (gratuito)', label: 'glm-5.1:cloud', value: 'glm-5.1:cloud' },
  { group: 'Cloud (gratuito)', label: 'kimi-k2.7-code:cloud', value: 'kimi-k2.7-code:cloud' },
  { group: 'Cloud (gratuito)', label: 'minimax-m2:cloud', value: 'minimax-m2:cloud' },
];

interface Props {
  mood: Mood;
  setMood: (v: Mood) => void;
  sysPr: string;
  setSysPr: (v: string) => void;
  voicePreset: VoicePreset;
  setVoicePreset: (v: VoicePreset) => void;
  jarvisRate: number;
  setJarvisRate: (v: number) => void;
  voicePitch: number;
  setVoicePitch: (v: number) => void;
  deepSilenceSec: number;
  setDeepSilenceSec: (v: number) => void;
  accentTheme: AccentTheme;
  setAccentTheme: (v: AccentTheme) => void;
  customColor: string;
  setCustomColor: (v: string) => void;
  assistantName: string;
  setAssistantName: (v: string) => void;
  userName: string;
  setUserName: (v: string) => void;
  voiceName: string;
  setVoiceName: (v: string) => void;
  gpuEnabled: boolean;
  setGpuEnabled: (v: boolean) => void;
  charonFullTools: boolean;
  setCharonFullTools: (v: boolean) => void;
}

const base: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--font-size-base)',
  fontWeight: 600,
  color: 'var(--ink)',
};

function s(extra: React.CSSProperties = {}): React.CSSProperties {
  return { ...base, ...extra };
}

function inputStyle(): React.CSSProperties {
  return {
    background: 'transparent',
    border: '1px solid var(--line-strong)',
    borderRadius: '4px',
    color: 'var(--ink)',
    padding: '6px 10px',
    outline: 'none',
    ...base,
  };
}

function btnStyle(c: string = 'var(--muted)', b?: string): React.CSSProperties {
  return {
    background: 'transparent',
    border: `1px solid ${b || 'var(--line-strong)'}`,
    borderRadius: '4px',
    color: c,
    cursor: 'pointer',
    padding: '4px 10px',
    ...base,
    fontSize: '12px',
  };
}

export default function AgentsPage(props: Props) {
  const {
    mood, setMood, sysPr, setSysPr, voicePreset, setVoicePreset,
    jarvisRate, setJarvisRate, voicePitch, setVoicePitch,
    deepSilenceSec, setDeepSilenceSec, accentTheme, setAccentTheme,
    customColor, setCustomColor, assistantName, setAssistantName,
    userName, setUserName, voiceName, setVoiceName,
    gpuEnabled, setGpuEnabled, charonFullTools, setCharonFullTools,
  } = props;
  const [subTab, setSubTab] = useState<SubTab>('agents');
  const [toast, setToast] = useState('');

  const [maxTurns, setMaxTurns] = useState(25);
  const [maxToolSteps, setMaxToolSteps] = useState(100);
  const [toolset, setToolset] = useState('agent');
  const [imageInputMode, setImageInputMode] = useState('text');

  const [agentModels, setAgentModels] = useState<Record<string, string>>({
    jarvis: 'qwen2.5-coder:14b',
    architect: 'qwen2.5-coder:14b',
    debugger: 'qwen2.5-coder:14b',
    planner: 'qwen2.5-coder:14b',
    coder: 'qwen2.5-coder:14b',
  });

  useEffect(() => {
    fetch(`${API_BASE}/api/config`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        const a = data.agent || {};
        if (a.max_turns !== undefined) setMaxTurns(a.max_turns);
        if (a.max_tool_steps !== undefined) setMaxToolSteps(a.max_tool_steps);
        if (a.toolset) setToolset(a.toolset);
        if (a.image_input_mode) setImageInputMode(a.image_input_mode);
        const am = data.agent_models || {};
        setAgentModels((prev) => ({ ...prev, ...am }));
      })
      .catch(() => {});
  }, []);

  const card: React.CSSProperties = {
    border: '1px solid var(--line)',
    borderRadius: '4px',
    padding: '14px',
    background: 'var(--bg)',
  };
  const h3: React.CSSProperties = { ...base, fontSize: '11px', fontWeight: 700, color: 'var(--muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' };
  const selectStyle: React.CSSProperties = { ...inputStyle(), width: '100%', cursor: 'pointer' };
  const rangeStyle: React.CSSProperties = { flex: 1, accentColor: 'var(--accent)' };
  const labelStyle: React.CSSProperties = { ...base, fontSize: '11px', color: 'var(--muted)', marginBottom: '6px' };
  const grid2: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' };

  const Toggle = ({ value, onChange, label }: { value: boolean; onChange: () => void; label: string }) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
      <span style={s({ fontSize: '11px' })}>{label}</span>
      <div onClick={onChange} style={{ width: 34, height: 18, borderRadius: 9, cursor: 'pointer', position: 'relative', background: value ? 'var(--accent)' : 'var(--bg-3)', border: '1px solid var(--line-strong)', flexShrink: 0, transition: 'background 0.2s' }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: value ? 'var(--bg-2)' : 'var(--quiet)', position: 'absolute', top: 2, left: value ? 18 : 3, transition: 'all 0.2s', boxShadow: '0 1px 2px rgba(0,0,0,0.3)' }} />
      </div>
    </div>
  );

  const handleSave = async () => {
    fetch(`${API_BASE}/api/config/identity`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ assistant_name: assistantName, user_name: userName, custom_color: accentTheme === 'custom' ? customColor : '', voice: voiceName }) }).catch(() => {});
    fetch(`${API_BASE}/voice/disconnect-all`, { method: 'POST' }).catch(() => {});
    fetch(`${API_BASE}/api/config`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ section: 'agent', values: { max_turns: maxTurns, max_tool_steps: maxToolSteps, toolset, image_input_mode: imageInputMode, personality: mood, system_prompt: sysPr || '' } }) }).catch(() => {});
    fetch(`${API_BASE}/api/config`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ section: 'voice', values: { charon_toolset: charonFullTools } }) }).catch(() => {});
    fetch(`${API_BASE}/api/config/agent-models`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(agentModels) }).catch(() => {});
    setToast('Salvo!');
    setTimeout(() => setToast(''), 3000);
  };

  const handleReset = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/config/agent-models/reset`, { method: 'POST' });
      if (r.ok) {
        const data = await r.json();
        setAgentModels(data.agent_models);
      }
    } catch {}
    // Restaura identity para padrao
    setAssistantName('DEEP-OS');
    setUserName('');
    setVoiceName('Charon');
    fetch(`${API_BASE}/api/config/identity`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assistant_name: 'DEEP-OS', user_name: '', custom_color: '', voice: 'Charon' }),
    }).catch(() => {});
    fetch(`${API_BASE}/voice/disconnect-all`, { method: 'POST' }).catch(() => {});
    setToast('Restaurado para padrao!');
    setTimeout(() => setToast(''), 3000);
  };

  const SUB_TABS: { key: SubTab; label: string }[] = [
    { key: 'agents', label: 'Agentes' },
    { key: 'voz', label: 'Voz' },
    { key: 'agente', label: 'Agente' },
    { key: 'assistente', label: 'Assistente' },
  ];

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: '2px', marginBottom: '16px', borderBottom: '1px solid var(--line)', paddingBottom: 0 }}>
        {SUB_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setSubTab(t.key)}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderBottom: subTab === t.key ? '2px solid var(--accent)' : '2px solid transparent',
              background: subTab === t.key ? 'var(--bg-3)' : 'transparent',
              color: subTab === t.key ? 'var(--accent)' : 'var(--muted)',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '11px',
              fontFamily: 'var(--font-ui)',
              letterSpacing: '0.3px',
              borderRadius: '4px 4px 0 0',
              transition: 'all 0.15s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── AGENTES (grid) ── */}
      {subTab === 'agents' && (
        <>
          <h2 style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: 'var(--accent)', margin: '0 0 4px' }}>
            // agentes
          </h2>
          <p style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: '#9cdcfe', margin: '0 0 20px' }}>
            $ roteamento inteligente de tarefas
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '12px' }}>
            {AGENTS_LIST.map((a) => {
              const key = a.name.toLowerCase();
              return (
                <div key={a.name} style={{ border: '1px solid var(--line)', borderRadius: '4px', padding: '16px', background: 'var(--bg)' }}>
                  <h3 style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: a.color, margin: '0 0 6px' }}>
                    {'>'} {a.name}
                  </h3>
                  <p style={{ fontFamily: 'inherit', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', margin: '0 0 10px' }}>
                    {a.desc}
                  </p>
                  <CustomDropdown
                    value={agentModels[key] || 'qwen2.5-coder:14b'}
                    onChange={(v) => setAgentModels((prev) => ({ ...prev, [key]: v }))}
                    options={MODEL_OPTIONS}
                  />
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ── VOZ ── */}
      {subTab === 'voz' && (
        <div style={{ maxWidth: 600 }}>
          <div style={card}>
            <h3 style={h3}>Voz (Text-to-Speech)</h3>
            <p style={labelStyle}>Selecione uma voz em pt-BR para leitura</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                {[
                  { key: 'google-female' as const, label: 'Natural' },
                  { key: 'jarvis-cinematic' as const, label: 'Jarvis' },
                  { key: 'google-male' as const, label: 'Masculina' },
                ].map((v) => (
                  <button key={v.key} onClick={() => setVoicePreset(v.key)} style={{ flex: 1, padding: '8px 10px', borderRadius: 6, border: voicePreset === v.key ? '1px solid var(--accent)' : '1px solid var(--line-strong)', background: voicePreset === v.key ? 'var(--accent)' : 'transparent', color: voicePreset === v.key ? 'var(--selection-fg)' : 'var(--muted)', cursor: 'pointer', fontSize: '11px', fontWeight: 600 }}>
                    {v.label}
                  </button>
                ))}
              </div>
              <p style={{ ...s({ fontSize: '9px', color: 'var(--quiet)', margin: 0 }) }}>Edge TTS (streaming):</p>
              <div style={{ display: 'flex', gap: '6px' }}>
                {[
                  { key: 'edge-francisca' as const, label: 'Francisca' },
                  { key: 'edge-thalita' as const, label: 'Thalita' },
                ].map((v) => (
                  <button key={v.key} onClick={() => setVoicePreset(v.key)} style={{ flex: 1, padding: '6px 8px', borderRadius: 6, border: voicePreset === v.key ? '1px solid var(--accent)' : '1px solid var(--line-strong)', background: voicePreset === v.key ? 'var(--accent)' : 'transparent', color: voicePreset === v.key ? 'var(--selection-fg)' : 'var(--muted)', cursor: 'pointer', fontSize: '11px' }}>
                    {v.label}
                  </button>
                ))}
              </div>
              <p style={{ ...s({ fontSize: '9px', color: 'var(--quiet)', margin: 0 }) }}>Google Natural:</p>
              <div style={{ display: 'flex', gap: '6px' }}>
                {[
                  { key: 'dani-brandi' as const, label: 'Dani Brandi' },
                ].map((v) => (
                  <button key={v.key} onClick={() => setVoicePreset(v.key)} style={{ flex: 1, padding: '6px 8px', borderRadius: 6, border: voicePreset === v.key ? '1px solid var(--accent)' : '1px solid var(--line-strong)', background: voicePreset === v.key ? 'var(--accent)' : 'transparent', color: voicePreset === v.key ? 'var(--selection-fg)' : 'var(--muted)', cursor: 'pointer', fontSize: '11px' }}>
                    {v.label}
                  </button>
                ))}
              </div>
              <p style={{ ...s({ fontSize: '9px', color: 'var(--quiet)', margin: 0 }) }}>ElevenLabs (requer API key):</p>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {[
                  { key: 'eleven-natasha' as const, label: 'Natasha' },
                  { key: 'eleven-serafina' as const, label: 'Serafina' },
                  { key: 'eleven-ivy' as const, label: 'Ivy' },
                  { key: 'eleven-ingmar' as const, label: 'Ingmar' },
                ].map((v) => (
                  <button key={v.key} onClick={() => setVoicePreset(v.key)} style={{ flex: '1 0 45%', padding: '6px 8px', borderRadius: 6, border: voicePreset === v.key ? '1px solid var(--accent)' : '1px solid var(--line-strong)', background: voicePreset === v.key ? 'var(--accent)' : 'transparent', color: voicePreset === v.key ? 'var(--selection-fg)' : 'var(--muted)', cursor: 'pointer', fontSize: '11px' }}>
                    {v.label}
                  </button>
                ))}
              </div>
              <p style={{ ...s({ fontSize: '10px', color: 'var(--muted)', margin: 0 }) }}>{VOICE_OPTIONS.find((o) => o.key === voicePreset)?.desc}</p>
            </div>
            <div style={{ display: 'grid', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ ...s(), minWidth: '56px' }}>Velocidade</span>
                <input type="range" min="0" max="100" value={jarvisRate} onChange={(e) => setJarvisRate(+e.target.value)} style={rangeStyle} />
                <span style={s({ minWidth: '32px', textAlign: 'right' })}>{jarvisRate}%</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ ...s(), minWidth: '56px' }}>Tom</span>
                <input type="range" min="-50" max="50" value={voicePitch - 50} onChange={(e) => setVoicePitch(+e.target.value + 50)} style={rangeStyle} />
                <span style={s({ minWidth: '32px', textAlign: 'right' })}>{voicePitch > 50 ? '+' : ''}{voicePitch - 50}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ ...s(), minWidth: '56px' }} title="Tempo de silencio no modo Aurea antes de enviar o comando">Escuta</span>
                <input type="range" min="2" max="15" value={deepSilenceSec} onChange={(e) => setDeepSilenceSec(+e.target.value)} style={rangeStyle} />
                <span style={s({ minWidth: '32px', textAlign: 'right' })}>{deepSilenceSec}s</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── AGENTE ── */}
      {subTab === 'agente' && (
        <div style={{ ...grid2, maxWidth: 700 }}>
          <div style={{ ...card, gridColumn: '1 / -1' }}>
            <h3 style={h3}>Prompt Personalizado</h3>
            <p style={labelStyle}>Instrucao extra enviada ao modelo</p>
            <textarea value={sysPr} onChange={(e) => setSysPr(e.target.value)} rows={3} placeholder='ex: "Responda sempre em portugues..."' style={{ ...inputStyle(), width: '100%', resize: 'vertical', lineHeight: 1.5 }} />
          </div>
          <div style={card}>
            <h3 style={h3}>Agente</h3>
            <div style={labelStyle}>Max Turns</div>
            <input type="number" min="1" max="200" value={maxTurns} onChange={(e) => setMaxTurns(+e.target.value)} style={inputStyle()} />
            <div style={{ ...labelStyle, marginTop: '8px' }}>Max Tool Steps</div>
            <input type="number" min="1" max="500" value={maxToolSteps} onChange={(e) => setMaxToolSteps(+e.target.value)} style={inputStyle()} />
          </div>
          <div style={card}>
            <h3 style={h3}>Toolset</h3>
            <select value={toolset} onChange={(e) => setToolset(e.target.value)} style={selectStyle}>
              <option value="agent">Agent (completo)</option>
              <option value="developer">Developer</option>
              <option value="readonly">Read Only</option>
              <option value="minimal">Minimal</option>
            </select>
            <div style={{ ...labelStyle, marginTop: '8px' }}>Image Input Mode</div>
            <select value={imageInputMode} onChange={(e) => setImageInputMode(e.target.value)} style={selectStyle}>
              <option value="text">Text (descrito)</option>
              <option value="image">Image (base64)</option>
            </select>
          </div>
          <div style={card}>
            <h3 style={h3}>GPU (Ollama + Llamacpp)</h3>
            <Toggle value={gpuEnabled} onChange={() => setGpuEnabled(!gpuEnabled)} label={gpuEnabled ? 'GPU ativada (RTX 3060)' : 'GPU desativada'} />
          </div>
          <div style={card}>
            <h3 style={h3}>Charon Tools</h3>
            <select 
              value={charonFullTools} 
              onChange={(e) => setCharonFullTools(e.target.value)}
              style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid var(--line-strong)', background: 'var(--bg-3)', color: 'var(--ink)' }}
            >
              <option value="basic">Estabilidade Minima (19 tools)</option>
              <option value="medium">Equilibrio (22 tools) - Recomendado</option>
              <option value="full">Completa (25 tools)</option>
            </select>
            <span style={{ fontSize: 9, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
              Basico: mais estavel | Equilibrio: recomendado | Completa: todas as tools
            </span>
          </div>
        </div>
      )}

      {/* ── ASSISTENTE ── */}
      {subTab === 'assistente' && (
        <div style={{ ...grid2, maxWidth: 700 }}>
          <div style={{ ...card, gridColumn: '1 / -1' }}>
            <h3 style={h3}>Personalizar Assistente</h3>
            <p style={labelStyle}>Configure o nome do assistente, seu nome e a cor da interface</p>
          </div>
          <div style={card}>
            <h3 style={h3}>Nome do Assistente</h3>
            <input value={assistantName} onChange={(e) => setAssistantName(e.target.value)} placeholder="DEEP-OS" style={inputStyle()} />
            <span style={{ fontSize: 9, color: 'var(--muted)', marginTop: 4, display: 'block' }}>Nome exibido no titulo e nas respostas</span>
          </div>
          <div style={card}>
            <h3 style={h3}>Seu Nome</h3>
            <input value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="(opcional)" style={inputStyle()} />
            <span style={{ fontSize: 9, color: 'var(--muted)', marginTop: 4, display: 'block' }}>Para o assistente te chamar pelo nome</span>
          </div>
          <div style={{ ...card, gridColumn: '1 / -1' }}>
            <h3 style={h3}>Cor da Interface</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px' }}>
              <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--line-strong)', background: 'var(--bg-3)' }}>
                <input type="color" value={customColor} onChange={(e) => { setCustomColor(e.target.value); setAccentTheme('custom'); }} style={{ width: 32, height: 32, border: 'none', borderRadius: 4, cursor: 'pointer', background: 'transparent' }} />
                <span style={{ fontSize: '11px', color: 'var(--ink)' }}>Escolher cor personalizada</span>
              </label>
              <div style={{ width: 32, height: 32, borderRadius: 6, background: customColor, border: '2px solid var(--line-strong)' }} />
              <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{customColor}</span>
            </div>
            <p style={{ fontSize: 9, color: 'var(--muted)', marginTop: 8 }}>Ou selecione um tema na aba Aparencia</p>
          </div>
          <div style={{ ...card, gridColumn: '1 / -1' }}>
            <h3 style={h3}>Voz do Charon (Gemini Live)</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
              {[
                { key: 'Charon', label: 'Charon', desc: 'Masculina (padrao)' },
                { key: 'Puck', label: 'Puck', desc: 'Masculina' },
                { key: 'Fenrir', label: 'Fenrir', desc: 'Masculina' },
                { key: 'Orus', label: 'Orus', desc: 'Masculina' },
                { key: 'Kore', label: 'Kore', desc: 'Feminina' },
                { key: 'Leda', label: 'Leda', desc: 'Feminina' },
                { key: 'Aoede', label: 'Aoede', desc: 'Feminina' },
                { key: 'Zephyr', label: 'Zephyr', desc: 'Feminina' },
              ].map((v) => (
                <div key={v.key} onClick={() => setVoiceName(v.key)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', cursor: 'pointer', padding: '6px 8px', borderRadius: 6, background: voiceName === v.key ? 'var(--accent-soft)' : 'transparent', border: voiceName === v.key ? '1px solid var(--accent)' : '1px solid var(--line)', transition: 'all 0.15s', flex: '1 0 22%', maxWidth: '25%' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: voiceName === v.key ? 'var(--accent)' : 'var(--ink)' }}>{v.label}</span>
                  <span style={{ fontSize: '9px', color: 'var(--muted)' }}>{v.desc}</span>
                </div>
              ))}
            </div>
            <span style={{ fontSize: 9, color: 'var(--muted)', marginTop: 4, display: 'block' }}>Reinicie o Charon apos salvar para aplicar</span>
          </div>
          <div style={{ ...card, gridColumn: '1 / -1' }}>
            <h3 style={h3}>Preview</h3>
            <div style={{ padding: '12px', borderRadius: 6, background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', background: customColor, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '12px', fontWeight: 700 }}>
                  {assistantName ? assistantName.charAt(0).toUpperCase() : 'D'}
                </div>
                <span style={{ fontWeight: 700, color: customColor }}>{assistantName || 'DEEP-OS'}</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                {userName ? `Ola ${userName}, como posso ajudar?` : 'Como posso ajudar?'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Save/Reset buttons */}
      <div style={{ marginTop: '16px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button onClick={handleSave} style={btnStyle('var(--accent)', 'var(--accent)')}>
          Salvar configuracoes
        </button>
        <button onClick={handleReset} style={btnStyle()}>
          Restaurar padrao
        </button>
        {toast && (
          <span style={{ ...s({ color: 'var(--accent-2)', fontSize: '11px' }) }}>
            {toast}
          </span>
        )}
      </div>
    </div>
  );
}
