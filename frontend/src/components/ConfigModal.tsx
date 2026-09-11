import React, { useState } from 'react';
import type { Provider, Mood, AccentTheme } from '../lib/constants';
import KnowledgePage from './KnowledgePage';
import AgentsPage from './AgentsPage';
import ArchitecturePage from './ArchitecturePage';
import MCPPage from './MCPPage';
import MonitorPanel from './MonitorPanel';
import SettingsPage from './SettingsPage';
import TerminalPanel from './TerminalPanel';

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

interface ConfigModalProps {
  open: boolean;
  onClose: () => void;
  prov: Provider;
  model: string;
  apiKey: string;
  orApiKey: string;
  knows: any[];
  setKnows: (v: any) => void;
  // Settings props
  mood: Mood; setMood: (v: Mood) => void;
  temp: number; setTemp: (v: number) => void;
  sysPr: string; setSysPr: (v: string) => void;
  snd: boolean; setSnd: (v: boolean) => void;
  bright: number; setBright: (v: number) => void;
  fsize: number; setFsize: (v: number) => void;
  geminiApiKey: string; setGeminiApiKey: (v: string) => void;
  mimoApiKey: string; setMimoApiKey: (v: string) => void;
  nvidiaApiKey: string; setNvidiaApiKey: (v: string) => void;
  voicePreset: VoicePreset; setVoicePreset: (v: VoicePreset) => void;
  jarvisRate: number; setJarvisRate: (v: number) => void;
  voicePitch: number; setVoicePitch: (v: number) => void;
  accentTheme: AccentTheme; setAccentTheme: (v: AccentTheme) => void;
  customColor: string; setCustomColor: (v: string) => void;
  assistantName: string; setAssistantName: (v: string) => void;
  userName: string; setUserName: (v: string) => void;
  voiceName: string; setVoiceName: (v: string) => void;
  gpuEnabled: boolean; setGpuEnabled: (v: boolean) => void;
  charonFullTools: boolean; setCharonFullTools: (v: boolean) => void;
  ollSt: any;
  oModels: any;
  orModels: any;
  llamacppModels: any;
  customM: string; setCustomM: (v: string) => void;
  showCust: boolean; setShowCust: (v: boolean) => void;
  groqApiKey: string; setGroqApiKey: (v: string) => void;
  openaiApiKey: string; setOpenaiApiKey: (v: string) => void;
  deepSilenceSec: number; setDeepSilenceSec: (v: number) => void;
  expRoot: string;
  loading?: boolean;
  thinking?: string;
  thinkOn?: boolean;
  thinkOpen?: boolean; setThinkOpen?: (v: boolean) => void;
  toolLogs?: any[];
  // Terminal props
  termOpen: boolean;
  setTermOpen: (v: boolean) => void;
}

const tabs = [
  { id: 'settings', label: 'Configuracoes' },
  { id: 'knowledge', label: 'Conhecimento' },
  { id: 'agents', label: 'Agentes' },
  { id: 'architecture', label: 'Arquitetura' },
  { id: 'mcp', label: 'MCP' },
  { id: 'monitor', label: 'Monitor' },
  { id: 'terminal', label: 'Terminal' },
];

export default function ConfigModal(props: ConfigModalProps) {
  const { open, onClose, prov, model, apiKey, orApiKey, knows, setKnows, termOpen, setTermOpen, expRoot } = props;
  const [activeTab, setActiveTab] = useState('settings');

  if (!open) return null;

  const renderContent = () => {
    switch (activeTab) {
      case 'settings':
        return (
          <SettingsPage
            prov={prov}
            setProv={() => {}}
            model={model}
            setModel={() => {}}
            mood={props.mood} setMood={props.setMood}
            temp={props.temp} setTemp={props.setTemp}
            sysPr={props.sysPr} setSysPr={props.setSysPr}
            snd={props.snd} setSnd={props.setSnd}
            bright={props.bright} setBright={props.setBright}
            fsize={props.fsize} setFsize={props.setFsize}
            apiKey={apiKey} setApiKey={() => {}}
            orApiKey={orApiKey} setOrApiKey={() => {}}
            groqApiKey={props.groqApiKey} setGroqApiKey={props.setGroqApiKey}
            openaiApiKey={props.openaiApiKey} setOpenaiApiKey={props.setOpenaiApiKey}
            geminiApiKey={props.geminiApiKey} setGeminiApiKey={props.setGeminiApiKey}
            mimoApiKey={props.mimoApiKey} setMimoApiKey={props.setMimoApiKey}
            nvidiaApiKey={props.nvidiaApiKey} setNvidiaApiKey={props.setNvidiaApiKey}
            oModels={props.oModels}
            orModels={props.orModels}
            llamacppModels={props.llamacppModels}
            customM={props.customM} setCustomM={props.setCustomM}
            showCust={props.showCust} setShowCust={props.setShowCust}
            voicePreset={props.voicePreset} setVoicePreset={props.setVoicePreset}
            jarvisRate={props.jarvisRate} setJarvisRate={props.setJarvisRate}
            voicePitch={props.voicePitch} setVoicePitch={props.setVoicePitch}
            deepSilenceSec={props.deepSilenceSec} setDeepSilenceSec={props.setDeepSilenceSec}
            ollSt={props.ollSt}
            accentTheme={props.accentTheme} setAccentTheme={props.setAccentTheme}
            customColor={props.customColor} setCustomColor={props.setCustomColor}
            assistantName={props.assistantName} setAssistantName={props.setAssistantName}
            userName={props.userName} setUserName={props.setUserName}
            voiceName={props.voiceName} setVoiceName={props.setVoiceName}
            gpuEnabled={props.gpuEnabled} setGpuEnabled={props.setGpuEnabled}
            charonFullTools={props.charonFullTools} setCharonFullTools={props.setCharonFullTools}
          />
        );
      case 'knowledge':
        return <KnowledgePage knows={knows} setKnows={setKnows} prov={prov} model={model} apiKey={apiKey} orApiKey={orApiKey} />;
      case 'agents':
        return (
          <AgentsPage
            mood={props.mood} setMood={props.setMood}
            sysPr={props.sysPr} setSysPr={props.setSysPr}
            voicePreset={props.voicePreset} setVoicePreset={props.setVoicePreset}
            jarvisRate={props.jarvisRate} setJarvisRate={props.setJarvisRate}
            voicePitch={props.voicePitch} setVoicePitch={props.setVoicePitch}
            deepSilenceSec={props.deepSilenceSec} setDeepSilenceSec={props.setDeepSilenceSec}
            accentTheme={props.accentTheme} setAccentTheme={props.setAccentTheme}
            customColor={props.customColor} setCustomColor={props.setCustomColor}
            assistantName={props.assistantName} setAssistantName={props.setAssistantName}
            userName={props.userName} setUserName={props.setUserName}
            voiceName={props.voiceName} setVoiceName={props.setVoiceName}
            gpuEnabled={props.gpuEnabled} setGpuEnabled={props.setGpuEnabled}
            charonFullTools={props.charonFullTools} setCharonFullTools={props.setCharonFullTools}
          />
        );
      case 'architecture':
        return <ArchitecturePage />;
      case 'mcp':
        return <MCPPage />;
      case 'monitor':
        return <MonitorPanel />;
      case 'terminal':
        return (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <TerminalPanel termOpen={true} setTermOpen={setTermOpen} expRoot={expRoot} />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          width: '90vw',
          maxWidth: 1200,
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 18px',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-2)',
          flexShrink: 0,
        }}>
          <div>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent)' }}>
              Configuracao
            </span>
            <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 8 }}>
              Preferencias do sistema e configuracoes
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: '1px solid var(--line)',
              color: 'var(--muted)',
              cursor: 'pointer',
              fontSize: 11,
              padding: '4px 12px',
              borderRadius: 4,
            }}
          >
            Fechar
          </button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex',
          gap: 0,
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-2)',
          padding: '0 12px',
          flexShrink: 0,
          overflowX: 'auto',
        }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '10px 16px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: 'transparent',
                color: activeTab === tab.id ? 'var(--accent)' : 'var(--muted)',
                borderBottom: activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
                fontFamily: 'inherit',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          minHeight: 0,
        }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
