/**
 * DEEP-OS - Checagem final das chaves que faltavam (OpenAI, MiMo, e as que ja
 * sabemos que falham, para deixar o diagnostico completo num lugar so).
 *
 * Uso: node tools/checar-chaves-restantes.cjs
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const ENV = path.resolve(__dirname, '..', 'backend', '.env');

function lerEnv() {
  const k = {};
  for (const l of fs.readFileSync(ENV, 'utf8').split(/\r?\n/)) {
    const m = l.match(/^\s*([A-Z0-9_]+)\s*=\s*([\s\S]+)$/);
    if (m) k[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
  }
  return k;
}

function post(host, caminho, headers, corpo) {
  return new Promise((res) => {
    const d = JSON.stringify(corpo);
    const r = https.request(
      {
        host, path: caminho, method: 'POST', timeout: 40000,
        headers: Object.assign({ 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(d) }, headers),
      },
      (x) => { let s = ''; x.on('data', (c) => (s += c)); x.on('end', () => res({ code: x.statusCode, body: s })); }
    );
    r.on('timeout', () => { r.destroy(); res({ err: 'timeout' }); });
    r.on('error', (e) => res({ err: e.message }));
    r.write(d); r.end();
  });
}

(async () => {
  const k = lerEnv();
  // URLs tiradas do proprio backend (nao chutadas):
  //   core/llm_native.py: mimo -> https://api.xiaomimimo.com/v1
  //                        opencode -> https://opencode.ai/zen/v1
  //                        openclaude -> OPENCLAUDE_BASE_URL (padrao localhost:4000)
  const casos = [
    ['OpenAI', 'api.openai.com', '/v1/chat/completions', k.OPENAI_API_KEY, 'gpt-4o-mini'],
    ['MiMo', 'api.xiaomimimo.com', '/v1/chat/completions', k.MIMO_API_KEY, 'mimo-v2.5'],
    ['OpenCode (zen)', 'opencode.ai', '/zen/v1/chat/completions', k.OPENCODE_API_KEY, 'deepseek-v4-flash-free'],
    ['OpenCode (api)', 'api.opencode.ai', '/v1/chat/completions', k.OPENCODE_API_KEY, 'deepseek-v4-flash-free'],
  ];

  console.log('=== Checagem de chaves restantes ===\n');
  for (const [nome, host, caminho, chave, modelo] of casos) {
    if (!chave) { console.log(`${nome.padEnd(16)} SEM CHAVE no .env`); continue; }
    const r = await post(host, caminho, { Authorization: 'Bearer ' + chave }, {
      model: modelo, messages: [{ role: 'user', content: 'OK' }], max_tokens: 5,
    });
    let msg = '';
    try { msg = JSON.parse(r.body)?.error?.message || ''; } catch { msg = (r.body || '').slice(0, 120); }
    const veredito = r.code === 200 ? 'CHAVE VALIDA'
      : r.code === 401 ? 'CHAVE INVALIDA/REVOGADA'
      : r.code === 429 ? 'SEM SALDO ou limite atingido'
      : r.code === 404 ? 'endpoint ou modelo nao encontrado'
      : r.err ? 'erro de rede: ' + r.err
      : 'HTTP ' + r.code;
    console.log(`${nome.padEnd(16)} ${String(r.code || '-').padEnd(5)} ${veredito}`);
    if (msg && r.code !== 200) console.log(`                 ${String(msg).slice(0, 150)}`);
  }

  console.log('\n--- OpenClaude (servidor local, nao e API na nuvem) ---');
  console.log('  base_url configurada: http://localhost:4000/api/v1');
  console.log('  Se esse servidor local nao estiver rodando, o provider openclaude');
  console.log('  falha por conexao recusada — e isso NAO e problema de chave.');
})();
