/**
 * DEEP-OS - Reteste dos modelos que falharam por erro de REDE (nao por 404).
 *
 * Por que: `read ECONNRESET` e `503 Service temporarily overloaded` NAO dizem
 * que o modelo nao existe — dizem que o servidor da NVIDIA caiu/recusou a
 * conexao naquele instante. Modelos grandes (550B, 253B) derrubam a conexao
 * com facilidade. Sem retestar, eu marcaria como "morto" um modelo bom.
 *
 * Uso: node tools/reteste-rede.cjs
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const ENV = path.resolve(__dirname, '..', 'backend', '.env');
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

function lerEnv() {
  const chaves = {};
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
    const r = https.request(
      {
        host: 'integrate.api.nvidia.com',
        path: '/v1/chat/completions',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(corpo),
          Authorization: 'Bearer ' + apiKey,
        },
        timeout: 90000,
      },
      (x) => {
        let s = '';
        x.on('data', (c) => (s += c));
        x.on('end', () => res({ code: x.statusCode, body: s }));
      }
    );
    r.on('timeout', () => { r.destroy(); res({ err: 'timeout 90s' }); });
    r.on('error', (e) => res({ err: e.message }));
    r.write(corpo);
    r.end();
  });
}

const SUSPEITOS = [
  'nvidia/nemotron-3-ultra-550b-a55b',
  'meta/llama-3.2-90b-vision-instruct',
  'google/gemma-4-31b-it',
  'moonshotai/kimi-k3',
  'nvidia/nemotron-3-super-120b-a12b',
];

(async () => {
  const k = lerEnv();
  console.log('=== Reteste dos que falharam por REDE (2 tentativas, timeout 90s) ===\n');
  const bons = [];

  for (const modelo of SUSPEITOS) {
    let resultado = null;
    for (let tentativa = 1; tentativa <= 2; tentativa++) {
      const r = await chat(k.NVIDIA_API_KEY, modelo);
      if (r.code === 200) {
        resultado = { ok: true, tentativa };
        break;
      }
      resultado = { ok: false, motivo: r.err || 'HTTP ' + r.code + ' ' + (r.body || '').slice(0, 120) };
      if (tentativa === 1) await dormir(4000);
    }
    console.log(`  ${resultado.ok ? 'OK   ' : 'FALHA'}  ${modelo.padEnd(42)} ${resultado.ok ? 'tentativa ' + resultado.tentativa : resultado.motivo}`);
    if (resultado.ok) bons.push(modelo);
    await dormir(800);
  }

  console.log('\n' + '='.repeat(70));
  console.log('Funcionam de verdade: ' + (bons.length ? '\n  ' + bons.join('\n  ') : 'nenhum'));
  console.log('\nConfirmam-se como indisponiveis para esta conta:');
  SUSPEITOS.filter((m) => !bons.includes(m)).forEach((m) => console.log('  - ' + m));
})();
