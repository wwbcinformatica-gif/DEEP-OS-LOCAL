// ─── Types ──────────────────────────────────────────────────────────────
export type Page =
  | 'knowledge'
  | 'memory'
  | 'agents'
  | 'settings'
  | 'generate'
  | 'tasks'
  | 'monitor'
  | 'mcp'
  | 'architecture';
export type Mood = 'descontraido' | 'serio' | 'bravo' | 'jarvis' | 'opencode';
export type Provider =
  | 'groq'
  | 'ollama'
  | 'llamacpp'
  | 'openrouter'
  | 'openai'
  | 'gemini'
  | 'openclaude'
  | 'opencode'
  | 'mimo'
  | 'nvidia';
export type AccentTheme =
  | 'laranja'
  | 'maracuja'
  | 'verde-palha'
  | 'azul-claro'
  | 'dourado-claro'
  | 'grafite'
  | 'dark'
  | 'custom';
export interface Msg {
  from: 'user' | 'bot';
  text: string;
  time: string | number;
  images?: string[];
  thinking?: string;
  planData?: any;
  planTaskId?: string;
  planStatus?: 'pending' | 'approved' | 'rejected' | 'executing' | 'done' | 'error';
  permissionData?: {
    title: string;
    description: string;
    patterns?: string[];
    permissionId: string;
  };
  isLoopError?: boolean;
}
export interface HistItem {
  id: number;
  question: string;
  answer: string;
  created_at: string;
}
export interface KnowItem {
  id: number;
  texto: string;
}
export interface ExpItem {
  name: string;
  type: 'file' | 'directory' | 'background';
  path: string;
  size?: string;
}
export interface TermLine {
  text: string;
  out?: boolean;
  err?: boolean;
}
export interface TLog {
  id?: string;
  tool: string;
  status: 'running' | 'done' | 'error';
  params?: any;
  result?: any;
  startedAt?: number;
  endedAt?: number;
  duration?: number;
}
export interface FileTab {
  id: string;
  name: string;
  path: string;
  content: string;
  ext: string;
  dirty?: boolean;
}
export interface OllamaSt {
  running: boolean;
  models: string[];
}
export type Theme = 'dark' | 'light';

// ─── Accent Themes ─────────────────────────────────────────────────────
export const ACCENT_THEMES: { key: AccentTheme; label: string; color: string; hover: string }[] = [
  { key: 'laranja', label: 'Laranja', color: '#ff7a1a', hover: '#e06a0a' },
  { key: 'maracuja', label: 'Maracujá', color: '#FFB74D', hover: '#e6a43e' },
  { key: 'verde-palha', label: 'Verde Palha', color: '#C8E6C9', hover: '#a5d6a7' },
  { key: 'azul-claro', label: 'Azul Claro (atual)', color: '#D6EAF8', hover: '#aed6f1' },
  { key: 'dourado-claro', label: 'Dourado Claro', color: '#F9E79F', hover: '#f7dc6f' },
  { key: 'grafite', label: 'Grafite', color: '#6b7280', hover: '#52525b' },
  { key: 'dark', label: 'Dark', color: '#3f3f46', hover: '#2a2a2e' },
];

// ─── Constants ─────────────────────────────────────────────────────────
export const now = () =>
  new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

export const MODELS: Record<string, { value: string; label: string }[]> = {
  groq: [
    { value: 'openai/gpt-oss-120b', label: 'GPT OSS 120B' },
    { value: 'openai/gpt-oss-20b', label: 'GPT OSS 20B' },
    { value: 'groq/compound', label: 'Compound (web search + code)' },
    { value: 'groq/compound-mini', label: 'Compound Mini' },
    { value: 'qwen/qwen3.6-27b', label: 'Qwen 3.6 27B (preview)' },
  ],
  ollama: [
    { value: 'qwen3.5:9b', label: 'Qwen 3.5 9B' },
    { value: 'qwen2.5-coder:14b', label: 'Qwen 2.5 Coder 14B' },
    { value: 'qwen2.5-coder:7b', label: 'Qwen 2.5 Coder 7B' },
    { value: 'qwen3:8b', label: 'Qwen 3 8B' },
    { value: 'qwen3:14b', label: 'Qwen 3 14B' },
    { value: 'gemma3:12b', label: 'Gemma 3 12B' },
    { value: 'mistral-nemo:12b', label: 'Mistral Nemo 12B' },
    { value: 'deepseek-coder:latest', label: 'DeepSeek Coder' },
    { value: 'deepseek-r1:latest', label: 'DeepSeek R1' },
  ],
  openrouter: [
    { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
    { value: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
  ],
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  ],
  gemini: [
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  ],
  openclaude: [
    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6 (coworking)' },
    { value: 'claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
    { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  ],
  opencode: [
    { value: 'deepseek-v4-flash-free', label: 'DeepSeek V4 Flash Free' },
    { value: 'nemotron-3-super-free', label: 'Nemotron 3 Super Free' },
    { value: 'gpt-5.1-codex', label: 'GPT 5.1 Codex' },
  ],
  mimo: [
    { value: 'mimo-v2.5', label: 'MiMo V2.5 (gratis)' },
  ],
  nvidia: [
    { value: 'nvidia/llama-3.1-nemotron-70b-instruct', label: 'Nemotron 70B Instruct' },
    { value: 'nvidia/llama-3.3-nemotron-super-49b-v1', label: 'Nemotron Super 49B' },
    { value: 'nvidia/llama-3.1-nemotron-8b-v1', label: 'Nemotron 8B' },
    { value: 'nvidia/llama-3.1-nemotron-mini-4b-instruct', label: 'Nemotron Mini 4B' },
    { value: 'meta/llama-3.1-405b-instruct', label: 'Llama 3.1 405B' },
    { value: 'meta/llama-3.1-70b-instruct', label: 'Llama 3.1 70B' },
    { value: 'meta/llama-3.1-8b-instruct', label: 'Llama 3.1 8B' },
    { value: 'mistralai/mistral-large-2-instruct', label: 'Mistral Large 2' },
    { value: 'google/gemma-2-27b-it', label: 'Gemma 2 27B' },
  ],
  llamacpp: [], // detectado automaticamente via /llamacpp/models
};

export const PROVIDERS = [
  'ollama',
  'llamacpp',
  'openclaude',
  'opencode',
  'groq',
  'openrouter',
  'openai',
  'gemini',
  'mimo',
  'nvidia',
];

export const MOODS = ['descontraido', 'serio', 'bravo', 'jarvis', 'opencode'] as const;

export interface AgentInfo {
  name: string;
  desc: string;
  icon: string;
  color: string;
}

export const AGENTS_LIST: AgentInfo[] = [
  { name: 'Jarvis', desc: 'Assistente geral', icon: '&', color: '#d97706' },
  { name: 'Architect', desc: 'Arquiteto de sistemas', icon: '#', color: '#569cd6' },
  { name: 'Debugger', desc: 'Solucionador de problemas', icon: '@', color: '#f44747' },
  { name: 'Planner', desc: 'Planejador de tarefas', icon: '>', color: '#dcdcaa' },
  { name: 'Coder', desc: 'Programador especialista', icon: '<', color: '#4ec9b0' },
];

// ─── API ───────────────────────────────────────────────────────────────
export const API_BASE = 'http://localhost:8001';

// ─── Defaults ──────────────────────────────────────────────────────────
export const DEFAULT_PROVIDER: Provider = 'openclaude';
export const DEFAULT_MODEL = 'deepseek-v4-flash';
export const DEFAULT_MOOD: Mood = 'opencode';
export const DEFAULT_TEMP = 0.7;
export const DEFAULT_BRIGHT = 100;
export const DEFAULT_FSIZE = 13;
export const DEFAULT_ACCENT_THEME: AccentTheme = 'azul-claro';
export const SETTINGS_KEY = 'wbc2';
