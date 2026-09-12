/**
 * DEEP-OS - Diagnostico das chaves de API (valida de verdade, nao so o formato).
 *
 * POR QUE EXISTE
 * A sondagem de modelos (`tools/provar-modelos.cjs`) revelou duas falhas que NAO
 * sao culpa do codigo do DEEP-OS, mas do estado das contas:
 *
 *   - OpenRouter: HTTP 401 "User not found." em TODOS os modelos.
 *     Suspeita: a chave e invalida/revogada. O endpoint /api/v1/models e
 *     PUBLICO no OpenRouter, entao ele devolver 445 modelos NAO prova que a
 *     chave funciona — foi por isso que isso passou despercebido.
 *
 *   - Zhipu: HTTP 429 "余额不足或无可用资源包,请充值。"
 *     Traducao: "Saldo insuficiente ou nenhum pacote de recursos disponivel,
 *     por favor recarregue." Ou seja: a conta GLM esta sem credito.
 *
 * Este script usa os endpoints que existem SO para validar credencial, em vez
 * de inferir pelo /models.
 *
 * Uso: node tools/diagnostico-chaves.cjs
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const ENV = path.resolve(__dirname, '..', 'backend', '.env');

function lerEnv() {
  const chaves = {};
  if (!fs.existsSync(ENV)) return chaves;
  for (const linha of fs.readFileSync(ENV, 'utf8').split(/\r?\n/)) {
    const m = linha.match(/^\s*([A-Z0-9_]+)\s*=\s*([\s\S]+)$/);
    if (m) chaves[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
  }
  return chaves;
}

function req(metodo, host, caminho, headers, corpo) {
  return new Promise((res) => {
    const h = Object.assign({ Accept: 'application/json', 'User-Agent': 'DEEP-OS/1.0' }, headers || {});
    let d = null;
    if (corpo) {
      d = JSON.stringify(corpo);
      h['Content-Type'] = 'application/json';
      h['Content-Length'] = Buffer.byteLength(d);
    }
    const r = https.request({ host, path: caminho, method: metodo, headers: h, timeout: 30000 }, (x) => {
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

const TRAVESSOES = {};
function traduzir(msg) {
  if (!msg) return '';
  if (msg.includes('余额不足') || msg.includes('请充值')) {
    return '  >>> SALDO INSUFICIENTE na conta Zhipu/GLM (precisa recarregar)';
  }
  if (msg.includes('User not found')) {
    return '  >>> CHAVE INVALIDA ou REVOGADA (o OpenRouter nao reconhece este usuario)';
  }
  return '';
}

(async () => {
  const k = lerEnv();
  console.log('=== DIAGNOSTICO DAS CHAVES DE API ===');
  console.log('Fonte: ' + ENV + '\n');

  // --- OpenRouter: /api/v1/key existe so para validar credencial ---
  console.log('--- OpenRouter ---');
  const chaveOR = k.OPENROUTER_API_KEY || '';
  console.log('  chave: ' + (chaveOR ? chaveOR.slice(0, 14) + '... (' + chaveOR.length + ' chars)' : 'AUSENTE'));
  if (chaveOR) {
    const a = await req('GET', 'openrouter.ai', '/api/v1/key', { Authorization: 'Bearer ' + chaveOR });
    console.log('  GET /api/v1/key (valida a credencial) -> HTTP ' + a.code);
    if (a.code === 200) {
      console.log('    OK: chave VALIDA');
      try {
        const j = JSON.parse(a.body).data;
        console.log('    limite: ' + (j?.limit ?? 'sem limite') + ' | usado: ' + (j?.usage ?? '?') + ' | gratis: ' + (j?.is_free_tier ?? '?'));
      } catch {}
    } else {
      console.log('    ' + (a.body || a.err || '').slice(0, 200) + traduzir(a.body));
    }

    // Prova de que /models e publico: manda uma chave falsa e ve se ainda responde 200
    const falso = await req('GET', 'openrouter.ai', '/api/v1/models', { Authorization: 'Bearer sk-or-v1-CHAVE-FALSA-000' });
    console.log('  GET /api/v1/models com chave FALSA -> HTTP ' + falso.code +
      (falso.code === 200 ? '  (confirma: /models e PUBLICO, nao serve para validar chave)' : ''));
  }
  console.log();

  // --- Zhipu: /api/paas/v4/models com a chave ---
  console.log('--- Zhipu (GLM) ---');
  const chaveZ = k.ZHIPU_API_KEY || '';
  console.log('  chave: ' + (chaveZ ? chaveZ.slice(0, 12) + '... (' + chaveZ.length + ' chars)' : 'AUSENTE'));
  if (chaveZ) {
    const z = await req('POST', 'open.bigmodel.cn', '/api/paas/v4/chat/completions',
      { Authorization: 'Bearer ' + chaveZ },
      { model: 'glm-4.6', messages: [{ role: 'user', content: 'OK' }], max_tokens: 5 });
    console.log('  POST chat/completions (glm-4.6) -> HTTP ' + z.code);
    console.log('    ' + (z.body || z.err || '').slice(0, 220) + traduzir(z.body));
  }
  console.log();

  // --- Groq / Gemini / NVIDIA: confirmacao rapida ---
  console.log('--- Groq ---');
  const g = await req('POST', 'api.groq.com', '/openai/v1/chat/completions',
    { Authorization: 'Bearer ' + (k.GROQ_API_KEY || '') },
    { model: 'openai/gpt-oss-20b', messages: [{ role: 'user', content: 'OK' }], max_tokens: 5 });
  console.log('  POST chat/completions -> HTTP ' + g.code + (g.code === 200 ? '  OK: chave valida' : '  ' + (g.body || '').slice(0, 160)));

  console.log('--- Gemini ---');
  const gm = await req('POST', 'generativelanguage.googleapis.com',
    '/v1beta/models/gemini-3.6-flash:generateContent?key=' + (k.GEMINI_API_KEY || ''),
    {}, { contents: [{ parts: [{ text: 'OK' }] }] });
  console.log('  POST generateContent -> HTTP ' + gm.code + (gm.code === 200 ? '  OK: chave valida' : '  ' + (gm.body || '').slice(0, 160)));

  console.log('--- NVIDIA ---');
  const nv = await req('POST', 'integrate.api.nvidia.com', '/v1/chat/completions',
    { Authorization: 'Bearer ' + (k.NVIDIA_API_KEY || '') },
    { model: 'nvidia/nemotron-3-super-120b-a12b', messages: [{ role: 'user', content: 'OK' }], max_tokens: 5 });
  console.log('  POST chat/completions -> HTTP ' + nv.code + (nv.code === 200 ? '  OK: chave valida' : '  ' + (nv.body || '').slice(0, 160)));

  console.log('\n' + '='.repeat(72));
  console.log('LEMBRETE: /models responder 200 NAO significa chave valida');
  console.log('(OpenRouter /models e publico; NVIDIA /models lista modelos que a');
  console.log(' sua conta NAO tem habilitados). So a chamada de chat prova.');
})();
