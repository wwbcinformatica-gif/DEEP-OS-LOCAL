/**
 * DEEP-OS - Teste real de qual forma do ID da NVIDIA a API aceita.
 *
 * CONTEXTO / CONTRADICAO A RESOLVER
 * O commit a8527c4 "remove nvidia/ prefix from NVIDIA model IDs" tirou o prefixo
 * dos IDs da NVIDIA no frontend. Mas o endpoint /v1/models da propria NVIDIA
 * devolve os IDs COM prefixo (ex: "nvidia/llama-3.1-nemotron-70b-instruct").
 * Se o prefixo for obrigatorio, aquele commit quebrou todos os modelos NVIDIA.
 *
 * Este script faz uma chamada de chat REAL com e sem prefixo e compara.
 *
 * Uso: node tools/teste-nvidia-id.cjs
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

function chat(apiKey, model) {
  return new Promise((res) => {
    const corpo = JSON.stringify({
      model,
      messages: [{ role: 'user', content: 'responda apenas: OK' }],
      max_tokens: 8,
    });
    const req = https.request(
      {
        host: 'integrate.api.nvidia.com',
        path: '/v1/chat/completions',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(corpo),
          Authorization: 'Bearer ' + apiKey,
          Accept: 'application/json',
        },
      },
      (r) => {
        let s = '';
        r.on('data', (c) => (s += c));
        r.on('end', () => res({ code: r.statusCode, body: s }));
      }
    );
    req.on('error', (e) => res({ err: e.message }));
    req.write(corpo);
    req.end();
  });
}

(async () => {
  const k = lerEnv();
  const chave = k.NVIDIA_API_KEY || '';
  console.log('chave NVIDIA lida: ' + (chave ? chave.slice(0, 12) + '... (' + chave.length + ' chars)' : 'AUSENTE'));
  if (!chave) {
    console.log('Nada a testar: sem NVIDIA_API_KEY no backend/.env');
    return;
  }

  // Pares (com prefixo, sem prefixo) para os modelos que o frontend lista
  const pares = [
    ['nvidia/llama-3.1-nemotron-70b-instruct', 'llama-3.1-nemotron-70b-instruct'],
    ['nvidia/nemotron-3-super-120b-a12b', 'nemotron-3-super-120b-a12b'],
    ['meta/llama-3.2-90b-vision-instruct', 'llama-3.2-90b-vision-instruct'],
  ];

  console.log('\n=== Chamada de chat real: qual forma o ID precisa ter? ===');
  for (const [comPrefixo, semPrefixo] of pares) {
    const a = await chat(chave, comPrefixo);
    const b = await chat(chave, semPrefixo);
    const ok = (r) =>
      r.code === 200 ? 'FUNCIONA' : r.code === 404 ? 'nao encontrado (404)' : r.code === 401 ? 'sem autorizacao (401)' : 'HTTP ' + r.code;
    console.log('\n  ' + comPrefixo);
    console.log('    COM prefixo : ' + ok(a));
    console.log('    SEM prefixo : ' + ok(b));
  }

  console.log('\n' + '='.repeat(70));
  console.log('Leitura: se "COM prefixo" funciona e "SEM prefixo" da 404, entao o');
  console.log('prefixo e OBRIGATORIO e o commit a8527c4 quebrou a NVIDIA.');
})();
