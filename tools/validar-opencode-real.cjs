/**
 * DEEP-OS - O endpoint api.opencode.ai devolve resposta REAL ou e um proxy que
 * responde 200 para qualquer coisa?
 *
 * POR QUE ISSO E OBRIGATORIO
 * No teste anterior, api.opencode.ai respondeu 200 para TODOS os 3 modelos do
 * frontend — inclusive 'gpt-5.1-codex' — e o /models dele devolveu 404. Um
 * servico que aprova tudo nao prova nada. Se eu trocar a base_url do backend
 * com base nisso e o servico for falso, eu quebro o provider de vez.
 *
 * Este script mostra o CORPO da resposta e exige uma pergunta cuja resposta
 * seja verificavel (um numero exato), alem de testar um modelo inexistente:
 * se ele tambem responder 200, o endpoint e falso.
 *
 * Uso: node tools/validar-opencode-real.cjs
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

function chat(host, base, chave, modelo, pergunta, maxTokens) {
  return new Promise((res) => {
    const corpo = JSON.stringify({
      model: modelo,
      messages: [{ role: 'user', content: pergunta }],
      max_tokens: maxTokens || 60,
    });
    const r = https.request(
      {
        host,
        path: base + '/chat/completions',
        method: 'POST',
        timeout: 60000,
        headers: {
          Authorization: 'Bearer ' + chave,
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(corpo),
        },
      },
      (x) => {
        let s = '';
        x.on('data', (c) => (s += c));
        x.on('end', () => res({ code: x.statusCode, body: s }));
      }
    );
    r.on('timeout', () => { r.destroy(); res({ err: 'timeout' }); });
    r.on('error', (e) => res({ err: e.message }));
    r.write(corpo);
    r.end();
  });
}

function extrair(body) {
  try {
    const j = JSON.parse(body);
    const c = j?.choices?.[0];
    return {
      texto: c?.message?.content ?? c?.text ?? null,
      modeloDeVolta: j?.model ?? null,
      temUso: !!j?.usage,
      bruto: null,
    };
  } catch {
    return { texto: null, modeloDeVolta: null, temUso: false, bruto: (body || '').slice(0, 300) };
  }
}

(async () => {
  const k = lerEnv();
  const chave = k.OPENCODE_API_KEY;

  console.log('=== Teste 1: api.opencode.ai devolve resposta REAL? ===');
  console.log('Pergunta verificavel: "Quanto e 17 * 23? Responda so o numero."');
  console.log('Esperado: 391\n');

  const a = await chat('api.opencode.ai', '/v1', chave, 'deepseek-v4-flash-free',
    'Quanto e 17 * 23? Responda apenas o numero, sem explicacao.', 60);
  console.log('  HTTP ' + (a.code || a.err));
  const ea = extrair(a.body || '');
  if (ea.bruto) console.log('  corpo nao-JSON: ' + ea.bruto);
  else {
    console.log('  modelo devolvido: ' + ea.modeloDeVolta);
    console.log('  tem bloco usage:  ' + ea.temUso);
    console.log('  TEXTO: ' + JSON.stringify(ea.texto));
  }
  const acertou = typeof ea.texto === 'string' && ea.texto.includes('391');
  console.log('  -> ' + (acertou ? 'RESPOSTA REAL (calculou 391)' : 'NAO respondeu 391 — suspeito'));

  console.log('\n=== Teste 2: modelo que NAO existe (controle negativo) ===');
  console.log('Um endpoint honesto deve RECUSAR. Se aprovar, aprova qualquer coisa.\n');
  const b = await chat('api.opencode.ai', '/v1', chave,
    'modelo-que-nao-existe-xyz-123', 'diga OK', 20);
  console.log('  HTTP ' + (b.code || b.err));
  console.log('  corpo: ' + (b.body || '').slice(0, 220));
  const aprovaTudo = b.code === 200;
  console.log('  -> ' + (aprovaTudo
    ? 'APROVOU MODELO INEXISTENTE => endpoint NAO e confiavel'
    : 'recusou corretamente => endpoint parece honesto'));

  console.log('\n=== Teste 3: o mesmo modelo no endpoint que o backend usa ===');
  const c = await chat('opencode.ai', '/zen/v1', chave, 'deepseek-v4-flash-free', 'diga OK', 20);
  console.log('  opencode.ai/zen/v1 + deepseek-v4-flash-free -> HTTP ' + (c.code || c.err));
  console.log('  corpo: ' + (c.body || '').slice(0, 220));

  console.log('\n=== Teste 4: modelo do catalogo zen que o backend poderia usar ===');
  for (const m of ['gemini-3.6-flash', 'claude-sonnet-4-6', 'gpt-5.5']) {
    const r = await chat('opencode.ai', '/zen/v1', chave, m, 'diga apenas: OK', 20);
    let det = '';
    try { det = JSON.parse(r.body)?.error?.message || ''; } catch {}
    console.log('  ' + (r.code === 200 ? 'OK   ' : 'FALHA') + '  ' + m.padEnd(22) +
      (r.code === 200 ? '' : (r.err || 'HTTP ' + r.code + (det ? ' — ' + det.slice(0, 90) : ''))));
  }

  console.log('\n' + '='.repeat(72));
  console.log('CONCLUSAO');
  console.log('='.repeat(72));
  if (aprovaTudo) {
    console.log(' api.opencode.ai aprova ate modelo inexistente -> NAO trocar a base_url');
    console.log(' do backend para ele. O endpoint correto e o que o backend ja usa');
    console.log(' (opencode.ai/zen/v1); o que esta errado sao os IDs de modelo do');
    console.log(' frontend, que nao existem no catalogo zen.');
  } else if (acertou) {
    console.log(' api.opencode.ai responde de verdade e recusa modelo invalido.');
    console.log(' Nesse caso vale trocar a base_url do backend.');
  } else {
    console.log(' Inconclusivo — nao trocar nada sem mais evidencia.');
  }
})();
