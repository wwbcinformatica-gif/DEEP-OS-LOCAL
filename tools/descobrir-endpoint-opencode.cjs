/**
 * DEEP-OS - Descobrir o endpoint CORRETO do provider OpenCode.
 *
 * ACHADO: o backend (core/llm_native.py linha ~152) aponta para
 *     https://opencode.ai/zen/v1
 * e essa URL devolve HTTP 400 "Model is unavailable" para o modelo que o
 * proprio frontend oferece. Ja
 *     https://api.opencode.ai/v1
 * responde 200 com o mesmo modelo e a mesma chave.
 *
 * Se isso se confirmar, o provider "opencode" esta quebrado no DEEP-OS e a
 * correcao e trocar a base_url.
 *
 * Uso: node tools/descobrir-endpoint-opencode.cjs
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

function pedir(metodo, host, caminho, chave, corpo) {
  return new Promise((res) => {
    const headers = { Authorization: 'Bearer ' + chave, Accept: 'application/json' };
    let d = null;
    if (corpo) {
      d = JSON.stringify(corpo);
      headers['Content-Type'] = 'application/json';
      headers['Content-Length'] = Buffer.byteLength(d);
    }
    const r = https.request({ host, path: caminho, method: metodo, headers, timeout: 40000 }, (x) => {
      let s = '';
      x.on('data', (c) => (s += c));
      x.on('end', () => res({ code: x.statusCode, body: s }));
    });
    r.on('timeout', () => { r.destroy(); res({ err: 'timeout' }); });
    r.on('error', (e) => res({ err: e.message }));
    if (d) r.write(d);
    r.end();
  });
}

const ENDPOINTS = [
  { nome: 'opencode.ai/zen/v1 (o que o BACKEND usa hoje)', host: 'opencode.ai', base: '/zen/v1' },
  { nome: 'api.opencode.ai/v1 (candidato que funcionou)', host: 'api.opencode.ai', base: '/v1' },
];

(async () => {
  const k = lerEnv();
  const chave = k.OPENCODE_API_KEY;
  if (!chave) { console.log('Sem OPENCODE_API_KEY no .env'); return; }

  for (const ep of ENDPOINTS) {
    console.log('\n' + '='.repeat(72));
    console.log('=== ' + ep.nome);
    console.log('='.repeat(72));

    const m = await pedir('GET', ep.host, ep.base + '/models', chave);
    console.log('  GET ' + ep.base + '/models -> HTTP ' + (m.code || m.err));
    let modelos = [];
    if (m.code === 200) {
      try {
        const j = JSON.parse(m.body);
        modelos = (j.data || j.models || []).map((x) => x.id || x.name).filter(Boolean);
        console.log('  ' + modelos.length + ' modelos disponiveis:');
        modelos.slice(0, 25).forEach((x) => console.log('     ' + x));
        if (modelos.length > 25) console.log('     ... +' + (modelos.length - 25) + ' mais');
      } catch { console.log('  resposta ilegivel: ' + m.body.slice(0, 200)); }
    } else {
      console.log('  ' + (m.body || '').slice(0, 200));
    }

    // Testa exatamente os modelos que o frontend oferece para opencode
    const doFrontend = ['deepseek-v4-flash-free', 'nemotron-3-super-free', 'gpt-5.1-codex'];
    console.log('\n  Chamada de chat com os modelos que o FRONTEND oferece:');
    for (const modelo of doFrontend) {
      const r = await pedir('POST', ep.host, ep.base + '/chat/completions', chave,
        { model: modelo, messages: [{ role: 'user', content: 'OK' }], max_tokens: 5 });
      let msg = '';
      try { msg = JSON.parse(r.body)?.error?.message || ''; } catch { msg = ''; }
      console.log('    ' + (r.code === 200 ? 'OK   ' : 'FALHA') + '  ' + modelo.padEnd(26) +
        (r.code === 200 ? '' : (r.err || 'HTTP ' + r.code + (msg ? ' — ' + msg.slice(0, 80) : ''))));
    }
  }
})();
