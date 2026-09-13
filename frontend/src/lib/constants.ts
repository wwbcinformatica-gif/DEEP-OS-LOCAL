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

/**
 * Listas de modelos por provider (usadas pelo seletor do chat classico).
 *
 * MANTENHA SINCRONIZADO com `PROVIDERS` em components/saas/JarvisPage.tsx.
 * Estavam divergentes: aqui os IDs da NVIDIA tinham prefixo `nvidia/` e la nao
 * (e o prefixo E obrigatorio — sem ele a API devolve 404). Tambem havia IDs
 * extintos nos dois lugares.
 *
 * So entra modelo confirmado por chamada real — ver tools/provar-modelos.cjs e
 * tools/MODELOS-PROVADOS.md.
 */
export const MODELS: Record<string, { value: string; label: string }[]> = {
  groq: [
    { value: 'openai/gpt-oss-120b', label: 'GPT-OSS 120B' },
    { value: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B' },
    { value: 'qwen/qwen3.8-27b', label: 'Qwen 3.8 27B' },
    { value: 'qwen/qwen3.6-27b', label: 'Qwen 3.6 27B' },
    { value: 'groq/compound', label: 'Compound (busca web + codigo)' },
    { value: 'groq/compound-mini', label: 'Compound Mini' },
    { value: 'allam-2-7b', label: 'Allam 2 7B' },
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
  // ATENCAO: a chave OpenRouter atual foi recusada com 401 "User not found"
  // (ver tools/diagnostico-chaves.cjs). Estes IDs existem no catalogo, mas so
  // funcionam depois de gerar uma chave nova em openrouter.ai/keys.
  openrouter: [
    { value: 'openrouter/auto', label: 'Auto (melhor modelo)' },
    { value: 'anthropic/claude-opus-4.6', label: 'Claude Opus 4.6' },
    { value: 'anthropic/claude-sonnet-4.6', label: 'Claude Sonnet 4.6' },
    { value: 'anthropic/claude-haiku-4.5', label: 'Claude Haiku 4.5 (rapido)' },
    { value: 'openai/gpt-4o', label: 'GPT-4o' },
    { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'openai/gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'google/gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
    { value: 'google/gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
    { value: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { value: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    { value: 'deepseek/deepseek-v3.2', label: 'DeepSeek V3.2' },
    { value: 'qwen/qwen3-235b-a22b', label: 'Qwen3 235B A22B' },
    { value: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B' },
    { value: 'mistralai/mistral-large-2512', label: 'Mistral Large' },
    { value: 'x-ai/grok-4.6', label: 'Grok 4.6' },
    { value: 'google/gemma-4-31b-it:free', label: 'Gemma 4 31B (gratis)' },
    { value: 'nvidia/nemotron-3-super-120b-a12b:free', label: 'Nemotron 3 Super 120B (gratis)' },
  ],
  // Mantenha identico a PROVIDERS.openai em JarvisPage.tsx (o teste
  // tests-manual/test_model_lists.py reprova se divergirem).
  // ATENCAO: a chave OpenAI do .env estava invalida (401 "Incorrect API key").
  // Use o botao "Testar" no Jarvis depois de salvar a chave nova.
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4.1', label: 'GPT-4.1' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'gpt-4.1-nano', label: 'GPT-4.1 Nano (barato)' },
  ],
  gemini: [
    { value: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash' },
    { value: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
    { value: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite' },
    { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash (preview)' },
    { value: 'gemini-flash-latest', label: 'Gemini Flash (ultima versao)' },
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
    { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (exige plano pago)' },
  ],
  openclaude: [
    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6 (coworking)' },
    { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  ],
  // Endpoint: https://opencode.ai/zen/v1 (e o que o backend ja usa — conferido).
  // Os IDs abaixo sao do catalogo real do zen (70 modelos).
  //
  // BUG CORRIGIDO: aqui estava 'nemotron-3-super-free', que NAO existe no
  // catalogo (o certo e nemotron-3.5-lightning-free / nemotron-3-ultra-free).
  // ATENCAO: a conta OpenCode esta com saldo zerado — todo modelo responde
  // HTTP 401 "Insufficient balance" ate recarregar em opencode.ai/workspace.
  opencode: [
    { value: 'deepseek-v4-flash-free', label: 'DeepSeek V4 Flash (gratis)' },
    { value: 'nemotron-3.5-lightning-free', label: 'Nemotron 3.5 Lightning (gratis)' },
    { value: 'mimo-v2.5-free', label: 'MiMo V2.5 (gratis)' },
    { value: 'gpt-5.1-codex', label: 'GPT 5.1 Codex' },
    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
    { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    { value: 'glm-5.3', label: 'GLM-5.3' },
    { value: 'kimi-k3', label: 'Kimi K3' },
  ],
  mimo: [
    { value: 'mimo-v2.5', label: 'MiMo V2.5 (gratis)' },
  ],
  // IDs existem no catalogo, MAS a conta esta sem saldo:
  // HTTP 429 "余额不足或无可用资源包,请充值。" (= saldo insuficiente).
  // Nao ha o que corrigir no codigo; precisa recarregar a conta GLM.
  zhipu: [
    { value: 'glm-5.3', label: 'GLM-5.3' },
    { value: 'glm-5.3-flash', label: 'GLM-5.3-Flash' },
    { value: 'glm-5.2', label: 'GLM-5.2' },
    { value: 'glm-5.1', label: 'GLM-5.1' },
    { value: 'glm-5', label: 'GLM-5' },
    { value: 'glm-5-turbo', label: 'GLM-5 Turbo' },
    { value: 'glm-4.7', label: 'GLM-4.7' },
    { value: 'glm-4.6', label: 'GLM-4.6' },
  ],
  // O prefixo (nvidia/, meta/, deepseek-ai/) e OBRIGATORIO — testado com
  // chamada real: com prefixo 200, sem prefixo 404.
  nvidia: [
    { value: 'nvidia/nemotron-3-super-120b-a12b', label: 'Nemotron 3 Super 120B' },
    { value: 'nvidia/nemotron-3.5-lightning-30b-a3b', label: 'Nemotron 3.5 Lightning 30B' },
    { value: 'deepseek-ai/deepseek-v4-pro-0813', label: 'DeepSeek V4 Pro' },
    { value: 'deepseek-ai/deepseek-v4-flash-0731', label: 'DeepSeek V4 Flash' },
    { value: 'meta/muse-glimmer-30b', label: 'Muse Glimmer 30B' },
    { value: 'meta/llama-3.2-11b-vision-instruct', label: 'Llama 3.2 11B Vision' },
    { value: 'z-ai/glm-5.3-flash', label: 'GLM-5.3-Flash' },
    { value: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B' },
  ],
  llamacpp: [], // detectado automaticamente via /llamacpp/models
};

/**
 * Provedores do seletor do chat classico.
 *
 * BUG CORRIGIDO: `zhipu` estava faltando aqui, embora MODELS.zhipu existisse —
 * ou seja, o provedor tinha modelos cadastrados mas NUNCA aparecia no seletor.
 * Era uma das causas de "nao carregava todos de cada provedor".
 *
 * Mantenha em sincronia com PROVIDERS em components/saas/JarvisPage.tsx.
 */
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
  'zhipu',
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
/**
 * Base das chamadas de API.
 *
 * POR QUE NAO E MAIS `'http://localhost:8001'` FIXO
 *
 * Com o endereco fixo, o `MiniMonitors` (que lia `${API_BASE}/monitor`) nao
 * funcionava no modo SaaS:
 *
 *   1. aberto por `http://localhost:5176`, o navegador ia direto na 8001 e
 *      escapava do proxy do Vite (funcionava por sorte, sem passar pelo
 *      middleware de seguranca);
 *   2. aberto no site publicado (HTTPS), `http://localhost:8001` aponta para a
 *      MAQUINA DO USUARIO — e o navegador ainda bloqueia `http://` dentro de
 *      pagina `https://` (conteudo misto). Resultado: barra nenhuma.
 *
 * Regra agora:
 *   - servido por um servidor web (http/https) -> caminho RELATIVO, que passa
 *     pelo proxy do Vite (dev) ou pelo nginx (producao). E o que todos os
 *     componentes do SaaS ja fazem (`fetch('/api/...')`);
 *   - rodando de outra forma (ex.: arquivo local, Electron) -> mantem
 *     `http://localhost:8001`, que era o comportamento antigo.
 */
export const API_BASE =
  typeof window !== 'undefined' && /^https?:$/.test(window.location.protocol)
    ? ''
    : 'http://localhost:8001';

// ─── Defaults ──────────────────────────────────────────────────────────
export const DEFAULT_PROVIDER: Provider = 'openclaude';
export const DEFAULT_MODEL = 'deepseek-v4-flash';
export const DEFAULT_MOOD: Mood = 'opencode';
export const DEFAULT_TEMP = 0.7;
export const DEFAULT_BRIGHT = 100;
export const DEFAULT_FSIZE = 13;
export const DEFAULT_ACCENT_THEME: AccentTheme = 'azul-claro';
export const SETTINGS_KEY = 'wbc2';
