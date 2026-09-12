import React, { useState, useRef, useEffect } from 'react';
import {
  Conversation, TranscriptEntry,
  getConversations, createConversation, renameConversation, deleteConversation,
  getTranscripts, saveTranscripts, getActivityLog, saveActivityLog,
  tenantGet, tenantSet,
} from './chatStorage';

/**
 * Marcador visual de "chave ja salva no servidor".
 *
 * A chave real NUNCA e enviada ao navegador (o backend so devolve `has_key`).
 * Este texto ocupa o campo do formulario para o usuario saber que existe algo
 * salvo — mas ele NAO e a chave e NUNCA deve ser enviado de volta.
 *
 * BUG CORRIGIDO: antes o valor literal '***saved***' era gravado no estado E no
 * localStorage, e o botao Salvar montava o payload com TODOS os providers. Ao
 * salvar a chave de um provider, o marcador dos outros ia junto e o backend
 * gravava '***saved***' no `.env`, SOBRESCREVENDO a chave verdadeira.
 */
const SENTINELA_CHAVE_SALVA = '***saved***';

/** True se o valor e o marcador (nao uma chave real do usuario). */
const ehSentinela = (v: string | undefined): boolean => v === SENTINELA_CHAVE_SALVA;

/**
 * Headers de autenticacao para as rotas protegidas de /api/config.
 *
 * SEGUNDO BUG DO MESMO SINTOMA ("troco a chave e o .env nao muda"):
 * o backend protege /api/config* pelo middleware `ProtecaoSensiveis`, que
 * libera apenas quando o header `Host` e local (127.0.0.1/localhost).
 *
 * - Local (start-saas.bat) -> Host local -> liberado, entao a falta do header
 *   nunca aparecia nos testes do usuario.
 * - Producao (deep-os.tech via nginx) -> Host externo -> exige JWT.
 *
 * Como as chamadas nao mandavam `Authorization`, na VPS elas voltavam 401; e
 * como o erro era engolido por `.catch(() => {})`, a tela dizia com tranquilidade
 * "chave salva no servidor" sem ter salvo nada.
 */
const authHeaders = (extra: Record<string, string> = {}): Record<string, string> => {
  const t = tenantGet('saas_token') || localStorage.getItem('saas_token') || '';
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
};

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

/**
 * Listas de modelos por provider.
 *
 * REGRA (aprendida do jeito dificil): so entra aqui modelo que respondeu
 * HTTP 200 numa chamada de chat REAL, testada por `tools/provar-modelos.cjs`.
 *
 * Por que nao basta copiar do endpoint /models de cada provider:
 *   - OpenRouter /api/v1/models e PUBLICO: devolve 445 modelos mesmo com uma
 *     chave FALSA. Nunca prova que a chave funciona.
 *   - NVIDIA /v1/models lista modelos que a conta NAO tem habilitados: eles
 *     aparecem na lista e devolvem 404 "Not found for account" na chamada.
 *   - A lista antiga tinha 9 IDs extintos (llama-3.3-70b-versatile na Groq,
 *     gemini-1.5-*, anthropic/claude-3.5-sonnet...) — escolher um deles dava
 *     404 sem explicacao.
 *
 * Ver `tools/MODELOS-PROVADOS.md` para o resultado da ultima sondagem.
 */
const PROVIDERS = [
  { id: 'ollama', label: 'Ollama (local)', keyField: '', models: [], dynamic: true },
  { id: 'llamacpp', label: 'llama.cpp (GGUF local)', keyField: '', models: [], dynamic: true },
  { id: 'gemini', label: 'Google Gemini', keyField: 'gemini', models: [
    { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash' },
    { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
    { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite (economico)' },
    { id: 'gemini-3-flash-preview', label: 'Gemini 3 Flash (preview)' },
    { id: 'gemini-flash-latest', label: 'Gemini Flash (ultima versao)' },
    { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { id: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
    { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (exige plano pago)' },
  ]},
  { id: 'openrouter', label: 'OpenRouter (gratis/variados)', keyField: 'openrouter', models: [
    // ATENCAO: a chave OpenRouter atual foi recusada com 401 "User not found"
    // (ver tools/diagnostico-chaves.cjs). Estes IDs existem no catalogo, mas
    // so funcionam depois de gerar uma chave nova em openrouter.ai/keys.
    { id: 'openrouter/auto', label: 'Auto (melhor modelo)' },
    { id: 'anthropic/claude-opus-4.6', label: 'Claude Opus 4.6' },
    { id: 'anthropic/claude-sonnet-4.6', label: 'Claude Sonnet 4.6' },
    { id: 'anthropic/claude-haiku-4.5', label: 'Claude Haiku 4.5 (rapido)' },
    { id: 'openai/gpt-4o', label: 'GPT-4o' },
    { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
    { id: 'openai/gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { id: 'google/gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
    { id: 'google/gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
    { id: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { id: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    { id: 'deepseek/deepseek-v3.2', label: 'DeepSeek V3.2' },
    { id: 'qwen/qwen3-235b-a22b', label: 'Qwen3 235B A22B' },
    { id: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B' },
    { id: 'mistralai/mistral-large-2512', label: 'Mistral Large' },
    { id: 'x-ai/grok-4.6', label: 'Grok 4.6' },
    { id: 'google/gemma-4-31b-it:free', label: 'Gemma 4 31B (gratis)' },
    { id: 'nvidia/nemotron-3-super-120b-a12b:free', label: 'Nemotron 3 Super 120B (gratis)' },
  ]},
  { id: 'groq', label: 'Groq (gratis/rapido)', keyField: 'groq', models: [
    // Os 7 abaixo foram TODOS confirmados com chamada de chat real.
    // Saíram: llama-3.3-70b-versatile e llama-3.1-8b-instant (extintos) e
    // minimaxai/minimax-m2.7 (nunca existiu na Groq).
    { id: 'openai/gpt-oss-120b', label: 'GPT-OSS 120B' },
    { id: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B (mais rapido)' },
    { id: 'qwen/qwen3.8-27b', label: 'Qwen 3.8 27B' },
    { id: 'qwen/qwen3.6-27b', label: 'Qwen 3.6 27B' },
    { id: 'groq/compound', label: 'Compound (busca web + codigo)' },
    { id: 'groq/compound-mini', label: 'Compound Mini' },
    { id: 'allam-2-7b', label: 'Allam 2 7B' },
  ]},
  { id: 'mimo', label: 'MiMo', keyField: 'mimo', models: [
    { id: 'mimo-v2.5', label: 'MiMo V2.5' },
  ]},
  { id: 'zhipu', label: 'Zhipu AI (GLM)', keyField: 'zhipu', models: [
    // IDs existem no catalogo, MAS a conta esta sem saldo:
    // HTTP 429 "余额不足或无可用资源包,请充值。" (= saldo insuficiente).
    // Nao ha o que corrigir no codigo; precisa recarregar a conta GLM.
    { id: 'glm-5.3', label: 'GLM-5.3' },
    { id: 'glm-5.3-flash', label: 'GLM-5.3-Flash' },
    { id: 'glm-5.2', label: 'GLM-5.2' },
    { id: 'glm-5.1', label: 'GLM-5.1' },
    { id: 'glm-5', label: 'GLM-5' },
    { id: 'glm-5-turbo', label: 'GLM-5 Turbo' },
    { id: 'glm-4.7', label: 'GLM-4.7' },
    { id: 'glm-4.6', label: 'GLM-4.6' },
  ]},
  { id: 'nvidia', label: 'NVIDIA NIM', keyField: 'nvidia', models: [
    // O prefixo (nvidia/, meta/, deepseek-ai/) e OBRIGATORIO: testado, com
    // prefixo responde 200 e sem prefixo da 404. O commit a8527c4 removeu os
    // prefixos por engano — estes IDs foram revalidados um a um.
    { id: 'nvidia/nemotron-3-super-120b-a12b', label: 'Nemotron 3 Super 120B' },
    { id: 'nvidia/nemotron-3.5-lightning-30b-a3b', label: 'Nemotron 3.5 Lightning 30B' },
    { id: 'deepseek-ai/deepseek-v4-pro-0813', label: 'DeepSeek V4 Pro' },
    { id: 'deepseek-ai/deepseek-v4-flash-0731', label: 'DeepSeek V4 Flash' },
    { id: 'meta/muse-glimmer-30b', label: 'Muse Glimmer 30B' },
    { id: 'meta/llama-3.2-11b-vision-instruct', label: 'Llama 3.2 11B Vision' },
    { id: 'z-ai/glm-5.3-flash', label: 'GLM-5.3-Flash' },
    { id: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B' },
  ]},
  // ─────────────────────────────────────────────────────────────────────────
  // BUG CORRIGIDO: `openai`, `opencode` e `openclaude` FALTAVAM nesta lista.
  //
  // O modal "Chaves de API" monta um campo por item de PROVIDERS
  // (`PROVIDERS.filter(p => !p.dynamic)`). Como estes tres nao estavam aqui,
  // NAO EXISTIA campo para colar a chave deles — o usuario nao tinha onde
  // inserir a chave da OpenAI (relatado por ele). Agravante: as chaves eram
  // carregadas (`apiKeys`), o mapa de envio (`envKeyMap`) e o backend
  // (`llm_native.py`) ja suportavam os tres. Faltava so a interface.
  // ─────────────────────────────────────────────────────────────────────────
  { id: 'openai', label: 'OpenAI', keyField: 'openai', models: [
    { id: 'gpt-4o', label: 'GPT-4o' },
    { id: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { id: 'gpt-4.1', label: 'GPT-4.1' },
    { id: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { id: 'gpt-4.1-nano', label: 'GPT-4.1 Nano (barato)' },
  ]},
  { id: 'openclaude', label: 'OpenClaude (servidor local)', keyField: 'openclaude', models: [
    // Aponta para OPENCLAUDE_BASE_URL (padrao http://localhost:4000/api/v1).
    // Nao e API na nuvem: sem o servidor local rodando, da erro de conexao.
    { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
    { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  ]},
  { id: 'opencode', label: 'OpenCode (zen)', keyField: 'opencode', models: [
    // Catalogo real do endpoint que o backend usa (opencode.ai/zen/v1).
    // ATENCAO: a conta esta sem saldo — todo modelo responde 401
    // "Insufficient balance" ate recarregar em opencode.ai/workspace.
    { id: 'deepseek-v4-flash-free', label: 'DeepSeek V4 Flash (gratis)' },
    { id: 'nemotron-3.5-lightning-free', label: 'Nemotron 3.5 Lightning (gratis)' },
    { id: 'mimo-v2.5-free', label: 'MiMo V2.5 (gratis)' },
    { id: 'gpt-5.1-codex', label: 'GPT 5.1 Codex' },
    { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
    { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    { id: 'glm-5.3', label: 'GLM-5.3' },
    { id: 'kimi-k3', label: 'Kimi K3' },
  ]},
];

import { renderMarkdown, renderMessageContent } from './markdownRenderer';

const LANG_LABELS: Record<string, string> = {
  python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript',
  jsx: 'JSX', tsx: 'TSX', java: 'Java', cpp: 'C++', c: 'C',
  go: 'Go', rust: 'Rust', ruby: 'Ruby', php: 'PHP',
  html: 'HTML', css: 'CSS', sql: 'SQL', bash: 'Bash',
  json: 'JSON', yaml: 'YAML', markdown: 'Markdown', shell: 'Shell',
};


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
  const [autoSpeakEnabled, setAutoSpeakEnabled] = useState(false);
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
  // Provedor cuja chave esta sendo testada agora (mostra "..." no botao).
  const [testando, setTestando] = useState<string | null>(null);

  // ── Provedores: comuns do backend + personalizados do usuario ────────────
  //
  // POR QUE VEM DO BACKEND
  // Antes, os campos de chave eram montados so a partir da lista estatica deste
  // arquivo. Foi assim que `openai`, `opencode` e `openclaude` ficaram SEM campo
  // — o backend aceitava, mas nao havia onde colar a chave. Buscando a lista do
  // backend (`/api/config/provedores`), um provedor novo passa a aparecer
  // sozinho, sem alterar o frontend.
  //
  // A lista estatica continua sendo usada para os MODELOS dos provedores que ja
  // foram verificados por chamada real (ver docs/MODELOS.md).
  const [provedoresRemotos, setProvedoresRemotos] = useState<any[]>([]);
  // Modelos descobertos em runtime pelo botao "Buscar modelos", por provedor.
  const [modelosBuscados, setModelosBuscados] = useState<Record<string, { id: string; label: string }[]>>({});
  const [buscandoModelos, setBuscandoModelos] = useState<string | null>(null);
  // Formulario de provedor novo
  const [formProvedor, setFormProvedor] = useState<{ id: string; label: string; base_url: string; api_key: string } | null>(null);
  const [salvandoProvedor, setSalvandoProvedor] = useState(false);
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
    ['gemini', 'openrouter', 'openai', 'groq', 'nvidia', 'mimo', 'openclaude', 'opencode', 'zhipu'].forEach(p => {
      const k = tenantGet(`${p}_api_key`) || '';
      if (k) keys[p] = k;
    });
    setApiKeys(keys);
    fetch('/api/config/api-keys', { headers: authHeaders() }).then(r => r.ok ? r.json() : null).then(data => {
      if (!data) return;
      // A resposta JA vem indexada pelo NOME do provedor (o backend monta o mapa
      // a partir do registro). Antes havia aqui um mapa fixo (`envToField`) que
      // so conhecia os nove provedores originais — um provedor novo (DeepSeek,
      // xAI, personalizado...) nunca recebia o marcador de "chave salva", e o
      // campo aparecia vazio mesmo com a chave gravada no servidor.
      Object.entries(data).forEach(([field, info]: [string, any]) => {
        if (info?.has_key && !keys[field]) {
          // Marcador visual: a chave EXISTE no servidor mas nao deve ser
          // exibida. NAO e a chave real — nunca enviar isso de volta ao
          // backend (era o bug: o payload mandava o marcador e sobrescrevia
          // a chave verdadeira no .env).
          keys[field] = SENTINELA_CHAVE_SALVA;
          // NAO gravar no localStorage: se gravar, ele volta ao estado no
          // proximo carregamento e e enviado ao servidor (mesmo problema).
        }
      });
      setApiKeys({ ...keys });
    }).catch(() => {});
    const savedInst = tenantGet('jarvis_instance_id') || '';
    fetch('/api/instances', { headers: authHeaders() }).then(r => r.ok ? r.json() : null).then(data => {
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

    // Provedores registrados no backend (comuns + personalizados do usuario).
    // E o que garante que TODO provedor suportado tenha campo de chave: um
    // provedor novo no backend aparece aqui sozinho, sem alterar o frontend.
    fetch('/api/config/provedores', { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        const lista = [
          ...(data.comuns || []),
          ...(data.personalizados || []),
        ];
        setProvedoresRemotos(lista);
        // Chaves guardadas localmente para provedores que nao estao na lista
        // fixa acima (comuns novos e personalizados).
        const locais: Record<string, string> = {};
        lista.forEach((p: any) => {
          if (!p?.id) return;
          const k = tenantGet(`${p.id}_api_key`) || '';
          if (k) locais[p.id] = k;
        });
        if (Object.keys(locais).length) {
          setApiKeys(prev => ({ ...locais, ...prev }));
        }
        // Provedores personalizados com modelos ja conhecidos entram no seletor
        const buscados: Record<string, { id: string; label: string }[]> = {};
        (data.personalizados || []).forEach((p: any) => {
          if (p.models?.length) buscados[p.id] = p.models;
        });
        if (Object.keys(buscados).length) {
          setModelosBuscados(prev => ({ ...prev, ...buscados }));
        }
      })
      .catch(() => {
        // Sem backend acessivel, a lista estatica deste arquivo continua valendo.
      });

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
    // Guarda de cancelamento.
    //
    // BUG CORRIGIDO ("selecionava o provedor e nao carregava os modelos certos"):
    // sem isto, ao trocar de Ollama para Groq a busca dos modelos locais
    // continuava em voo; quando ela respondia (depois), chamava setDynamicModels
    // e a lista do Ollama SOBRESCREVIA a do Groq. Como o <select> abaixo usa
    // `dynamicModels` sempre que ele nao esta vazio, o usuario via os modelos do
    // provedor anterior — e escolher um deles dava 404, porque aquele modelo nao
    // existe no provedor selecionado.
    let ativo = true;

    if (selectedProvider === 'ollama') {
      setLoadingModels(true);
      fetch('/ollama/models', { headers: authHeaders() }).then(r => r.ok ? r.json() : { models: [] }).then(data => {
        if (!ativo) return;
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
      }).catch(() => { if (!ativo) return; setDynamicModels([]); setLoadingModels(false); });
    } else if (selectedProvider === 'llamacpp') {
      setLoadingModels(true);
      fetch('/llamacpp/models', { headers: authHeaders() }).then(r => r.ok ? r.json() : { models: [] }).then(data => {
        if (!ativo) return;
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
      }).catch(() => { if (!ativo) return; setDynamicModels([]); setLoadingModels(false); });
    } else {
      // Provider estatico: limpa a lista dinamica para o <select> cair na
      // lista fixa do PROVIDERS correspondente.
      setDynamicModels([]);
      setLoadingModels(false);
    }

    return () => { ativo = false; };
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

      if (fullAnswer && autoSpeakEnabled) speak(fullAnswer);

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

  // ── Lista unificada de provedores ────────────────────────────────────────
  //
  // Junta tres origens, sem duplicar:
  //   1. PROVIDERS (estatico) — tem os modelos JA VERIFICADOS por chamada real;
  //   2. comuns do backend que nao estao no estatico (DeepSeek, xAI, Mistral,
  //      Anthropic, Together, Fireworks, Cerebras, Perplexity, DeepInfra, e os
  //      servidores locais LM Studio / vLLM / text-gen-webui / Jan);
  //   3. personalizados criados pelo usuario.
  //
  // Isto resolve a causa raiz do "nao tenho onde colar a chave da OpenAI": a
  // secao de chaves e montada a partir DESTA lista, entao todo provedor que o
  // backend aceita tem campo.
  const provedoresUnificados = [
    ...PROVIDERS.map(p => ({
      id: p.id,
      label: p.label,
      keyField: p.keyField,
      dynamic: !!p.dynamic,
      models: (p.models || []) as { id: string; label: string }[],
      precisaChave: !!p.keyField,
      local: false,
      aviso: '',
      personalizado: false,
    })),
    ...provedoresRemotos
      .filter(r => r && r.id && !PROVIDERS.some(p => p.id === r.id))
      .map(r => {
        const conhecidos = modelosBuscados[r.id] || r.models || [];
        return {
          id: r.id as string,
          label: (r.label || r.id) as string,
          keyField: (r.precisa_chave ? r.id : '') as string,
          dynamic: false,
          models: conhecidos as { id: string; label: string }[],
          precisaChave: !!r.precisa_chave,
          local: !!r.local,
          aviso: (r.aviso || '') as string,
          personalizado: r.tipo === 'personalizado',
        };
      }),
  ];

  // Somente os que precisam de chave aparecem na secao "Chaves de API"
  const provedoresComChave = provedoresUnificados.filter(p => p.precisaChave);

  // Modelos do provedor ATIVO.
  //
  // A lista dinamica (Ollama/llama.cpp, detectada em runtime) so vale para os
  // provedores marcados `dynamic: true`. Antes o seletor usava `dynamicModels`
  // sempre que ele nao estivesse vazio, entao um resto de lista do Ollama
  // aparecia sob outro provedor e o modelo escolhido dava 404.
  const providerAtual = provedoresUnificados.find(p => p.id === selectedProvider);
  const modelosDisponiveis = providerAtual?.dynamic
    ? dynamicModels
    : (providerAtual?.models?.length
        ? providerAtual.models
        : (modelosBuscados[selectedProvider] || []));

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
              <select value={selectedProvider} onChange={(e) => {
                const novo = e.target.value;
                setSelectedProvider(novo);
                // Ao trocar de provedor o modelo anterior quase sempre nao existe
                // no novo. Sem isto o <select> de modelo ficava sem valor valido
                // (aparecia em branco) porque `value` nao casava com nenhuma
                // <option> — o que parecia "nao carregou os modelos".
                const prov = provedoresUnificados.find(p => p.id === novo);
                const lista = prov?.models?.length ? prov.models : (modelosBuscados[novo] || []);
                setSelectedModel(lista.length ? lista[0].id : '');
              }} style={s.modelSelect}>
                {provedoresUnificados.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
              <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} style={s.modelSelectWide}>
                {modelosDisponiveis.map(m => (
                  <option key={m.id} value={m.id}>{(m as any).hasVision ? '\uD83D\uDC41 ' : ''}{m.label}</option>
                ))}
                {modelosDisponiveis.length === 0 && (
                  <option value="">(use "Buscar modelos" nas Configuracoes)</option>
                )}
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
                  <button onClick={() => { if (isSpeaking) stopSpeaking(); setAutoSpeakEnabled(!autoSpeakEnabled); }} style={{ ...s.iconBtn, background: autoSpeakEnabled ? '#0c0' : '#1a1a2e', color: autoSpeakEnabled ? '#fff' : '#666' }} title={autoSpeakEnabled ? 'Falante ON (clique para desativar)' : 'Falante OFF (clique para ativar)'}>
                    {autoSpeakEnabled ? '\uD83D\uDD0A' : '\uD83D\uDD07'}
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
                {/* Texto de ajuda: o usuario nao encontrou onde colar a chave da
                    OpenAI (o campo nao existia) e tambem nao tinha como saber se
                    uma chave salva estava funcionando. As duas coisas foram
                    corrigidas; esta linha explica o fluxo. */}
                <div style={{ fontSize: 11, color: '#888', marginBottom: 8, lineHeight: 1.5 }}>
                  Ha um campo por provedor. Cole a chave e clique em <b style={{ color: '#9ecbff' }}>Salvar</b>; depois
                  clique em <b style={{ color: '#9ecbff' }}>Testar</b> — o teste faz uma chamada de verdade ao provedor e
                  diz se a chave funciona, se esta sem saldo ou se o modelo nao existe mais.
                  <br />
                  Uma chave salva <b>nao</b> significa chave funcionando: pode estar revogada ou com a conta sem credito.
                  <br />
                  Falta um provedor? Use <b style={{ color: '#9ecbff' }}>+ Adicionar provedor</b> no fim da lista.
                </div>
                {provedoresComChave.map(prov => (
                  <div key={prov.id} style={s.settingsRow}>
                    <label style={s.settingsLabel} title={prov.aviso || prov.label}>
                      {prov.label}
                      {prov.personalizado && <span style={{ color: '#7c9', fontSize: 9 }}> (seu)</span>}
                    </label>
                    <div style={{ display: 'flex', gap: 6, flex: 1 }}>
                      <input type="password" value={prov.keyField === 'gemini' ? apiKey : (apiKeys[prov.keyField] || '')}
                        onChange={(e) => { if (prov.keyField === 'gemini') setApiKey(e.target.value); else setApiKeys({ ...apiKeys, [prov.keyField]: e.target.value }); }}
                        style={s.configInput} placeholder="sk-..." />

                      {/* Buscar modelos: pergunta ao provedor quais modelos ele tem.
                          Serve para nao digitar um por um — e o unico jeito de
                          usar um provedor novo sem adivinhar os nomes. */}
                      <button onClick={async () => {
                        setBuscandoModelos(prov.id);
                        try {
                          const r = await fetch('/api/config/provedores/modelos', {
                            method: 'POST',
                            headers: authHeaders({ 'Content-Type': 'application/json' }),
                            body: JSON.stringify({ provider: prov.id }),
                          });
                          const j = await r.json().catch(() => null);
                          if (!j) { alert(`${prov.label}: resposta inesperada.`); return; }
                          if (!j.ok) { alert(`${prov.label}: ${j.mensagem}`); return; }
                          setModelosBuscados(prev => ({ ...prev, [prov.id]: j.modelos || [] }));
                          alert(`${prov.label}: ${j.mensagem}`);
                        } catch (e: any) {
                          alert(`${prov.label}: falha ao buscar modelos (${e?.message || 'rede'}).`);
                        } finally {
                          setBuscandoModelos(null);
                        }
                      }} disabled={buscandoModelos === prov.id}
                        style={{ ...s.saveBtn, background: '#333', color: '#bbb', fontSize: 10 }}>
                        {buscandoModelos === prov.id ? '...' : 'Modelos'}
                      </button>
                      <button onClick={async () => {
                        const key = prov.keyField === 'gemini' ? apiKey : (apiKeys[prov.keyField] || '');

                        // Guarda: o marcador de "ja salva" nao e uma chave.
                        // Enviar isso ao servidor SOBRESCREVERIA a chave real.
                        if (ehSentinela(key) || ehSentinela(apiKey)) {
                          alert('A chave ja esta salva no servidor.\n\nPara troca-la, digite a nova chave no campo e clique em Salvar.');
                          return;
                        }

                        if (!key.trim()) {
                          alert(`Digite a chave de ${prov.label} antes de salvar.`);
                          return;
                        }

                        // Salva SO ESTE provider.
                        //
                        // Antes montava um payload com TODOS os providers, e os
                        // que estavam com o marcador iam junto — o backend gravava
                        // o marcador por cima da chave verdadeira no .env.
                        const envKeyMap: Record<string, string> = { gemini: 'GEMINI_API_KEY', openrouter: 'OPENROUTER_API_KEY', openai: 'OPENAI_API_KEY', groq: 'GROQ_API_KEY', nvidia: 'NVIDIA_API_KEY', mimo: 'MIMO_API_KEY', openclaude: 'OPENCLAUDE_API_KEY', opencode: 'OPENCODE_API_KEY', zhipu: 'ZHIPU_API_KEY' };

                        // FALLBACK para os provedores que NAO estao no mapa fixo:
                        // os comuns novos (DeepSeek, xAI, Mistral...) e os criados
                        // pelo usuario. O padrao e <ID>_API_KEY, o MESMO que o
                        // backend monta em `provedores.env_key_do_id()`.
                        //
                        // Sem isto, clicar Salvar num provedor novo nao enviava
                        // nada (envKeyMap[id] era undefined) e a chave era
                        // silenciosamente descartada — a mesma classe de bug que
                        // estamos consertando.
                        const envKey = envKeyMap[prov.keyField]
                          || (prov.keyField ? `${prov.keyField.toUpperCase()}_API_KEY` : '');
                        const envPayload: Record<string, string> = {};
                        if (envKey && key.trim()) envPayload[envKey] = key.trim();

                        // IMPORTANTE: NAO usar `.catch(() => {})`.
                        //
                        // Antes o erro era engolido e o alerta dizia "salva" mesmo
                        // quando o servidor recusava — foi assim que o usuario viu
                        // "troco a chave e o .env nao muda" sem nenhuma pista.
                        const falhas: string[] = [];
                        try {
                          // --- Gemini: endpoint dedicado (grava .env + api_keys.json) ---
                          if (prov.keyField === 'gemini') {
                            const r = await fetch('/api/config/api-key', {
                              method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }),
                              body: JSON.stringify({ gemini_api_key: key.trim() }),
                            });
                            if (!r.ok) {
                              const detalhe = r.status === 401
                                ? 'sessao expirada — faca login novamente'
                                : await r.text().catch(() => '');
                              falhas.push(`Gemini: HTTP ${r.status} ${detalhe}`.trim());
                            }
                          }

                          // --- Os demais: endpoint multi-chave, so o provider salvo ---
                          if (Object.keys(envPayload).length) {
                            const r = await fetch('/api/config/api-keys', {
                              method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }),
                              body: JSON.stringify(envPayload),
                            });
                            if (!r.ok) {
                              const detalhe = r.status === 401
                                ? 'sessao expirada — faca login novamente'
                                : await r.text().catch(() => '');
                              falhas.push(`${prov.label}: HTTP ${r.status} ${detalhe}`.trim());
                            } else {
                              const j = await r.json().catch(() => null);
                              if (j && Array.isArray(j.recusados) && j.recusados.length) {
                                falhas.push(`${prov.label}: o servidor recusou o valor (parece mascarado/placeholder).`);
                              }
                            }
                          }
                        } catch (e: any) {
                          falhas.push(`${prov.label}: ${e?.message || 'falha de rede'}`);
                        }

                        if (falhas.length) {
                          alert('A chave NAO foi salva.\n\n' + falhas.join('\n') +
                            '\n\nVerifique se a sessao ainda esta valida (faca login de novo) e tente outra vez.');
                          return;
                        }

                        tenantSet(`${prov.keyField}_api_key`, key.trim());
                        if (prov.keyField === 'gemini') { tenantSet('saas_api_key', key.trim()); setApiKey(key.trim()); }
                        else setApiKeys({ ...apiKeys, [prov.keyField]: key.trim() });

                        alert(`Chave de ${prov.label} salva no servidor.`);
                      }} style={s.saveBtn}>Salvar</button>

                      {/* Testar: faz uma chamada de chat REAL com a chave salva.
                          Existe porque "salvo" nao significa "funcionando" — a
                          chave pode estar revogada (401), a conta sem saldo
                          (402/429) ou o modelo extinto (404). Antes o usuario so
                          descobria isso ao tentar conversar. */}
                      <button onClick={async () => {
                        const modelo = prov.keyField === 'gemini'
                          ? selectedModel
                          : (prov.models[0]?.id || '');
                        setTestando(prov.keyField);
                        try {
                          const r = await fetch('/api/config/testar-chave', {
                            method: 'POST',
                            headers: authHeaders({ 'Content-Type': 'application/json' }),
                            body: JSON.stringify({ provider: prov.keyField, model: modelo }),
                          });
                          if (r.status === 401) {
                            alert('Sessao expirada — faca login novamente.');
                            return;
                          }
                          const j = await r.json().catch(() => null);
                          if (!j) { alert(`${prov.label}: resposta inesperada do servidor.`); return; }
                          if (j.ok) {
                            alert(`${prov.label}: OK\n\n${j.mensagem}\n\nResposta do modelo: ${j.resposta || '(vazia)'}`);
                          } else {
                            alert(`${prov.label}: NAO FUNCIONA\n\n${j.mensagem}` +
                              (j.erro ? `\n\nDetalhe tecnico:\n${j.erro}` : ''));
                          }
                        } catch (e: any) {
                          alert(`${prov.label}: falha ao testar (${e?.message || 'erro de rede'}).`);
                        } finally {
                          setTestando(null);
                        }
                      }} disabled={testando === prov.keyField}
                        style={{ ...s.saveBtn, background: '#2a3f5f', color: '#9ecbff' }}>
                        {testando === prov.keyField ? '...' : 'Testar'}
                      </button>

                      {/* Remover so para provedores CRIADOS pelo usuario. Os
                          comuns vem do codigo e nao podem ser apagados. */}
                      {prov.personalizado && (
                        <button onClick={async () => {
                          if (!confirm(`Remover o provedor "${prov.label}"?\n\nA chave salva permanece no servidor.`)) return;
                          try {
                            const r = await fetch(`/api/config/provedores/${encodeURIComponent(prov.id)}`, {
                              method: 'DELETE', headers: authHeaders(),
                            });
                            if (!r.ok) { alert(`Nao consegui remover (HTTP ${r.status}).`); return; }
                            setProvedoresRemotos(prev => prev.filter(p => p.id !== prov.id));
                            alert(`Provedor "${prov.label}" removido.`);
                          } catch (e: any) {
                            alert(`Falha ao remover: ${e?.message || 'rede'}`);
                          }
                        }} style={{ ...s.saveBtn, background: '#3a2222', color: '#f88', fontSize: 10 }}>X</button>
                      )}
                    </div>
                  </div>
                ))}

                {/* ── Criar provedor novo ────────────────────────────────────
                    Qualquer servico que fale a API do OpenAI (a maioria, e
                    tambem servidores locais como LM Studio / vLLM) funciona
                    aqui: basta a URL base, a chave e os modelos. Sem deploy. */}
                {formProvedor === null ? (
                  <button onClick={() => setFormProvedor({ id: '', label: '', base_url: '', api_key: '' })}
                    style={{ ...s.saveBtn, marginTop: 8, background: '#1e3a2e', color: '#7c9' }}>
                    + Adicionar provedor
                  </button>
                ) : (
                  <div style={{ marginTop: 10, padding: 10, background: '#141414', border: '1px solid #2a2a2a', borderRadius: 6 }}>
                    <div style={{ fontSize: 11, color: '#9ecbff', marginBottom: 8, fontWeight: 600 }}>
                      Novo provedor
                    </div>
                    <div style={{ fontSize: 10, color: '#888', marginBottom: 8, lineHeight: 1.5 }}>
                      Funciona com qualquer servico que use a API do OpenAI. A URL base costuma terminar em
                      <b> /v1</b> (ex: <code style={{ color: '#bbb' }}>https://api.exemplo.com/v1</code>).
                      Servidores locais tambem entram (ex: <code style={{ color: '#bbb' }}>http://localhost:1234/v1</code>
                      para o LM Studio).
                    </div>

                    {[
                      { campo: 'label' as const, rotulo: 'Nome', exemplo: 'Meu Provedor' },
                      { campo: 'base_url' as const, rotulo: 'URL base', exemplo: 'https://api.exemplo.com/v1' },
                      { campo: 'api_key' as const, rotulo: 'Chave da API', exemplo: 'sk-...' },
                    ].map(({ campo, rotulo, exemplo }) => (
                      <div key={campo} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <label style={{ ...s.settingsLabel, minWidth: 90 }}>{rotulo}</label>
                        <input
                          type={campo === 'api_key' ? 'password' : 'text'}
                          value={formProvedor[campo]}
                          onChange={e => setFormProvedor({ ...formProvedor, [campo]: e.target.value })}
                          placeholder={exemplo}
                          style={{ ...s.configInput, flex: 1 }}
                        />
                      </div>
                    ))}

                    <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                      <button disabled={salvandoProvedor} onClick={async () => {
                        const f = formProvedor;
                        if (!f.label.trim() || !f.base_url.trim()) {
                          alert('Preencha pelo menos o Nome e a URL base.');
                          return;
                        }
                        setSalvandoProvedor(true);
                        try {
                          // 1. Cria o provedor no registro do backend
                          const r = await fetch('/api/config/provedores', {
                            method: 'POST',
                            headers: authHeaders({ 'Content-Type': 'application/json' }),
                            body: JSON.stringify({ label: f.label, base_url: f.base_url }),
                          });
                          const j = await r.json().catch(() => null);
                          if (!r.ok) {
                            alert(`Nao consegui criar: ${j?.detail || `HTTP ${r.status}`}`);
                            return;
                          }
                          const criado = j.provedor;

                          // 2. Se veio chave, salva junto (mesmo fluxo das outras)
                          if (f.api_key.trim()) {
                            await fetch('/api/config/api-keys', {
                              method: 'PUT',
                              headers: authHeaders({ 'Content-Type': 'application/json' }),
                              body: JSON.stringify({ [criado.key_env]: f.api_key.trim() }),
                            });
                          }

                          // 3. Descobre os modelos automaticamente
                          let msgExtra = '\n\nAgora use o botao "Modelos" na linha dele para carregar a lista.';
                          try {
                            const rm = await fetch('/api/config/provedores/modelos', {
                              method: 'POST',
                              headers: authHeaders({ 'Content-Type': 'application/json' }),
                              body: JSON.stringify({ provider: criado.id }),
                            });
                            const jm = await rm.json().catch(() => null);
                            if (jm?.ok && jm.modelos?.length) {
                              setModelosBuscados(prev => ({ ...prev, [criado.id]: jm.modelos }));
                              // Persiste os modelos no registro
                              await fetch('/api/config/provedores', {
                                method: 'POST',
                                headers: authHeaders({ 'Content-Type': 'application/json' }),
                                body: JSON.stringify({ label: criado.label, base_url: criado.base_url, models: jm.modelos }),
                              });
                              msgExtra = `\n\n${jm.total} modelos carregados automaticamente.`;
                            } else if (jm && !jm.ok) {
                              msgExtra = `\n\nNao consegui listar os modelos: ${jm.mensagem}`;
                            }
                          } catch { /* segue sem modelos */ }

                          // Recarrega a lista de provedores
                          const rl = await fetch('/api/config/provedores', { headers: authHeaders() });
                          const jl = await rl.json().catch(() => null);
                          if (jl) setProvedoresRemotos([...(jl.comuns || []), ...(jl.personalizados || [])]);

                          setFormProvedor(null);
                          alert(`Provedor "${criado.label}" criado.${msgExtra}\n\nClique em Testar para confirmar que funciona.`);
                        } catch (e: any) {
                          alert(`Falha ao criar: ${e?.message || 'rede'}`);
                        } finally {
                          setSalvandoProvedor(false);
                        }
                      }} style={{ ...s.saveBtn, background: '#1e3a2e', color: '#7c9' }}>
                        {salvandoProvedor ? '...' : 'Criar'}
                      </button>
                      <button onClick={() => setFormProvedor(null)}
                        style={{ ...s.saveBtn, background: '#333', color: '#999' }}>
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}
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
