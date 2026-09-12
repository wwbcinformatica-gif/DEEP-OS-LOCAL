/**
 * DEEP-OS - Prova cada modelo com uma chamada de chat REAL.
 *
 * POR QUE ISSO E NECESSARIO (e por que nao basta ler /v1/models)
 * Descobrimos que a lista de /v1/models MENTE em dois sentidos:
 *
 *   1. FALSO POSITIVO: `nvidia/llama-3.1-nemotron-70b-instruct` aparece na
 *      lista de /v1/models da NVIDIA, mas a chamada de chat devolve 404. Se
 *      listarmos so o que /models diz, o usuario escolhe e da erro.
 *   2. FORMATO DE ID: `nvidia/nemotron-3-super-120b-a12b` funciona COM o
 *      prefixo e da 404 SEM ele. O commit a8527c4 removeu o prefixo dos IDs
 *      da NVIDIA por engano — este script prova isso com chamada real.
 *
 * Entao a unica fonte confiavel e a propria inferencia: manda "responda OK" e
 * ve o que volta 200.
 *
 * Uso: node tools/provar-modelos.cjs
 * Saida: tools/modelos-provados.json  (somente o que funcionou de verdade)
 *        tools/MODELOS-PROVADOS.md    (relatorio legivel)
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..');
const ENV = path.join(RAIZ, 'backend', '.env');

function lerEnv() {
  const chaves = {};
  if (!fs.existsSync(ENV)) return chaves;
  for (const linha of fs.readFileSync(ENV, 'utf8').split(/\r?\n/)) {
    const m = linha.match(/^\s*([A-Z0-9_]+)\s*=\s*([\s\S]+)$/);
    if (m) chaves[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
  }
  return chaves;
}

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Chamada de chat minima. `estilo` decide o formato do corpo/URL.
 *
 * ATENCAO ao caminho: cada provider tem o SEU prefixo, e errar isso faz TODOS
 * os modelos falharem com 404 enganoso (foi o que aconteceu na 1a versao deste
 * script, que concatenava "/v1/chat/completions" na base crua):
 *     Groq        https://api.groq.com/openai/v1/chat/completions
 *     OpenRouter  https://openrouter.ai/api/v1/chat/completions
 *     Zhipu       https://open.bigmodel.cn/api/paas/v4/chat/completions
 *     NVIDIA      https://integrate.api.nvidia.com/v1/chat/completions
 */
function chat(estilo, urlBase, apiKey, model) {
  return new Promise((res) => {
    let caminho;
    let corpo;

    if (estilo === 'gemini') {
      // Gemini: /v1beta/models/{model}:generateContent?key=...
      caminho = `/v1beta/models/${model}:generateContent?key=${apiKey}`;
      corpo = JSON.stringify({ contents: [{ parts: [{ text: 'responda apenas: OK' }] }] });
    } else if (estilo === 'groq') {
      caminho = '/openai/v1/chat/completions';
      corpo = JSON.stringify({ model, messages: [{ role: 'user', content: 'responda apenas: OK' }], max_tokens: 8 });
    } else if (estilo === 'openrouter') {
      caminho = '/api/v1/chat/completions';
      corpo = JSON.stringify({ model, messages: [{ role: 'user', content: 'responda apenas: OK' }], max_tokens: 8 });
    } else if (estilo === 'zhipu') {
      caminho = '/api/paas/v4/chat/completions';
      corpo = JSON.stringify({ model, messages: [{ role: 'user', content: 'responda apenas: OK' }], max_tokens: 8 });
    } else {
      caminho = '/v1/chat/completions';
      corpo = JSON.stringify({ model, messages: [{ role: 'user', content: 'responda apenas: OK' }], max_tokens: 8 });
    }

    const u = new URL(urlBase);
    const headers = {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(corpo),
      Accept: 'application/json',
    };
    if (estilo !== 'gemini') headers.Authorization = 'Bearer ' + apiKey;
    if (estilo === 'openrouter') {
      headers['HTTP-Referer'] = 'https://deep-os.tech';
      headers['X-Title'] = 'DEEP-OS';
    }

    const req = https.request(
      { host: u.hostname, path: caminho, method: 'POST', headers, timeout: 45000 },
      (r) => {
        let s = '';
        r.on('data', (c) => (s += c));
        r.on('end', () => res({ code: r.statusCode, body: s }));
      }
    );
    req.on('timeout', () => { req.destroy(); res({ err: 'timeout (45s)' }); });
    req.on('error', (e) => res({ err: e.message }));
    req.write(corpo);
    req.end();
  });
}

function classificar(r) {
  if (r.err) return { ok: false, motivo: r.err };
  if (r.code === 200) {
    try {
      const j = JSON.parse(r.body);
      const temTexto =
        j?.choices?.[0]?.message !== undefined ||
        j?.candidates?.[0]?.content !== undefined;
      return temTexto ? { ok: true, motivo: 'respondeu' } : { ok: false, motivo: '200 sem texto' };
    } catch {
      return { ok: false, motivo: '200 ilegivel' };
    }
  }
  let detalhe = '';
  try {
    const j = JSON.parse(r.body);
    detalhe = j?.error?.message || j?.detail || j?.message || '';
  } catch {
    detalhe = (r.body || '').slice(0, 90);
  }
  return { ok: false, motivo: `HTTP ${r.code}${detalhe ? ' — ' + String(detalhe).slice(0, 110) : ''}` };
}

// ── Candidatos: o que pretendemos colocar nas listas do frontend ──────────
const CANDIDATOS = {
  groq: {
    estilo: 'groq', url: 'https://api.groq.com',
    chave: 'GROQ_API_KEY',
    modelos: [
      'openai/gpt-oss-120b',
      'openai/gpt-oss-20b',
      'qwen/qwen3.6-27b',
      'qwen/qwen3.8-27b',
      'groq/compound',
      'groq/compound-mini',
      'allam-2-7b',
    ],
  },
  gemini: {
    estilo: 'gemini', url: 'https://generativelanguage.googleapis.com',
    chave: 'GEMINI_API_KEY',
    modelos: [
      'gemini-3.6-flash',
      'gemini-3.5-flash',
      'gemini-3.5-flash-lite',
      'gemini-3.1-pro-preview',
      'gemini-3-flash-preview',
      'gemini-2.5-pro',
      'gemini-2.5-flash',
      'gemini-2.5-flash-lite',
      'gemini-flash-latest',
      'gemini-pro-latest',
    ],
  },
  openrouter: {
    estilo: 'openrouter', url: 'https://openrouter.ai',
    chave: 'OPENROUTER_API_KEY',
    modelos: [
      'openrouter/auto',
      'anthropic/claude-opus-4.6',
      'anthropic/claude-sonnet-4.6',
      'anthropic/claude-haiku-4.5',
      'openai/gpt-4o',
      'openai/gpt-4o-mini',
      'openai/gpt-4.1',
      'openai/gpt-4.1-mini',
      'google/gemini-2.5-pro',
      'google/gemini-2.5-flash',
      'google/gemini-3.5-flash',
      'deepseek/deepseek-v3.2',
      'deepseek/deepseek-v4-flash',
      'qwen/qwen3-235b-a22b',
      'meta-llama/llama-3.3-70b-instruct',
      'mistralai/mistral-large-2512',
      'x-ai/grok-4.6',
    ],
  },
  nvidia: {
    estilo: 'nvidia', url: 'https://integrate.api.nvidia.com',
    chave: 'NVIDIA_API_KEY',
    modelos: [
      // COM prefixo (a forma que descobrimos funcionar) e SEM, para provar
      'nvidia/nemotron-3-super-120b-a12b',
      'nvidia/nemotron-3-ultra-550b-a55b',
      'nvidia/llama-3.1-nemotron-ultra-253b-v1',
      'nvidia/llama-3.1-nemotron-70b-instruct',
      'nvidia/llama-3.1-nemotron-51b-instruct',
      'nvidia/nemotron-3.5-lightning-30b-a3b',
      'meta/llama-3.2-90b-vision-instruct',
      'meta/llama-3.2-11b-vision-instruct',
      'meta/muse-glimmer-30b',
      'mistralai/mistral-large-2-instruct',
      'google/gemma-4-31b-it',
      'google/gemma-3-12b-it',
      'moonshotai/kimi-k3',
      'moonshotai/kimi-k2.6',
      'z-ai/glm-5.3-flash',
      'deepseek-ai/deepseek-v4-pro-0813',
      'deepseek-ai/deepseek-v4-flash-0731',
      'openai/gpt-oss-20b',
      'nemotron-3-super-120b-a12b', // sem prefixo: deve dar 404
    ],
  },
  zhipu: {
    estilo: 'zhipu', url: 'https://open.bigmodel.cn',
    chave: 'ZHIPU_API_KEY',
    modelos: ['glm-5.3', 'glm-5.3-flash', 'glm-5.2', 'glm-5', 'glm-4.7', 'glm-4.6'],
  },
};

(async () => {
  const k = lerEnv();
  const provados = {};
  const relatorio = [];

  for (const [prov, cfg] of Object.entries(CANDIDATOS)) {
    const chave = k[cfg.chave];
    console.log('\n' + '='.repeat(74));
    console.log(`=== ${prov.toUpperCase()}  (${cfg.modelos.length} candidatos)`);
    console.log('='.repeat(74));
    if (!chave) {
      console.log('  SEM CHAVE (' + cfg.chave + ') — pulando');
      relatorio.push({ prov, semChave: true });
      continue;
    }

    const bons = [];
    for (const modelo of cfg.modelos) {
      const r = await chat(cfg.estilo, cfg.url, chave, modelo);
      const c = classificar(r);
      console.log(`  ${c.ok ? 'OK   ' : 'FALHA'}  ${modelo.padEnd(44)} ${c.ok ? '' : c.motivo}`);
      if (c.ok) bons.push(modelo);
      else relatorio.push({ prov, modelo, motivo: c.motivo });
      await dormir(350); // gentileza com rate limit
    }
    provados[prov] = bons;
    console.log(`\n  -> ${bons.length}/${cfg.modelos.length} funcionam`);
  }

  fs.writeFileSync(path.join(__dirname, 'modelos-provados.json'), JSON.stringify(provados, null, 2), 'utf8');

  const linhas = [
    '# Modelos PROVADOS por chamada real',
    '',
    'Gerado por `node tools/provar-modelos.cjs`.',
    'So entra nesta lista o modelo que respondeu HTTP 200 com texto de verdade.',
    '',
  ];
  for (const [prov, modelos] of Object.entries(provados)) {
    linhas.push(`## ${prov} (${modelos.length})`, '');
    modelos.forEach((m) => linhas.push(`- \`${m}\``));
    linhas.push('');
  }
  linhas.push('## Falharam (NAO usar)', '');
  relatorio
    .filter((r) => !r.semChave)
    .forEach((r) => linhas.push(`- \`${r.modelo}\` (${r.prov}) — ${r.motivo}`));
  fs.writeFileSync(path.join(__dirname, 'MODELOS-PROVADOS.md'), linhas.join('\n'), 'utf8');

  console.log('\n' + '='.repeat(74));
  console.log('RESUMO');
  console.log('='.repeat(74));
  for (const [prov, modelos] of Object.entries(provados)) {
    console.log(`  ${prov.padEnd(12)} ${modelos.length} funcionando`);
  }
  console.log('\n  tools/modelos-provados.json  e  tools/MODELOS-PROVADOS.md gravados');
})();
