/**
 * DEEP-OS - Regenerador/validador das listas de modelos.
 *
 * POR QUE EXISTE
 * As listas de modelos do frontend (frontend/src/lib/constants.ts e o
 * JarvisPage.tsx) foram escritas a mao e envelheceram: varios IDs sairam do ar
 * (`llama-3.3-70b-versatile` na Groq, `anthropic/claude-3.5-sonnet` no
 * OpenRouter...) e havia prefixos inconsistentes (constants.ts usava
 * `nvidia/llama-...` enquanto o JarvisPage ja usava sem o prefixo). Escolher um
 * modelo morto na interface da erro em tempo de execucao, sem pista clara.
 *
 * O QUE FAZ
 *   1. Baixa a lista REAL de modelos de cada provider que tenha endpoint
 *      /models (Groq, OpenRouter, NVIDIA, Gemini, Zhipu).
 *   2. Extrai os IDs declarados no codigo-fonte do frontend.
 *   3. Diz, um por um, quais IDs do codigo NAO existem mais na API.
 *   4. Grava as listas reais em tools/modelos-atuais.json, para montar as
 *      listas curadas sem chutar.
 *
 * COMO RODAR (na raiz C:\DEEP-OS, com o backend/.env preenchido)
 *   node tools/modelos-atuais.cjs
 *
 * NOTA: usa o modulo `https` do Node em vez de curl porque o curl/TLS do
 * Windows desta maquina esta quebrado (SEC_E_NO_CREDENTIALS).
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..');
const ENV = path.join(RAIZ, 'backend', '.env');
const SAIDA = path.join(__dirname, 'modelos-atuais.json');

function get(url, headers) {
  return new Promise((res) => {
    const u = new URL(url);
    https
      .get(
        {
          host: u.hostname,
          path: u.pathname + u.search,
          headers: Object.assign({ 'User-Agent': 'DEEP-OS/1.0' }, headers || {}),
        },
        (r) => {
          let d = '';
          r.on('data', (c) => (d += c));
          r.on('end', () => res({ code: r.statusCode, body: d }));
        }
      )
      .on('error', (e) => res({ err: e.message }));
  });
}

function lerEnv() {
  if (!fs.existsSync(ENV)) return {};
  const chaves = {};
  fs.readFileSync(ENV, 'utf8')
    .split(/\r?\n/)
    .forEach((l) => {
      const m = l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.+)$/);
      if (m) chaves[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
    });
  return chaves;
}

/** Extrai os IDs declarados no codigo: pega `value: 'algum/id'` e `{ id: '...' }`. */
function extrairDoCodigo(arquivo) {
  const p = path.join(RAIZ, arquivo);
  if (!fs.existsSync(p)) return [];
  const texto = fs.readFileSync(p, 'utf8');
  const ids = new Set();
  const re = /(?:value|id)\s*:\s*'([^']+)'/g;
  let m;
  while ((m = re.exec(texto))) ids.add(m[1]);
  return [...ids];
}

(async () => {
  const chaves = lerEnv();
  const real = {};
  const falhas = [];

  async function baixar(nome, url, headers, extrator) {
    const r = await get(url, headers);
    if (r.err) {
      falhas.push(`${nome}: erro de rede (${r.err})`);
      return;
    }
    if (r.code !== 200) {
      falhas.push(`${nome}: HTTP ${r.code}`);
      return;
    }
    try {
      const lista = extrator(JSON.parse(r.body));
      real[nome] = lista;
      console.log(`  ${nome.padEnd(12)} ${String(lista.length).padStart(4)} modelos`);
    } catch (e) {
      falhas.push(`${nome}: resposta ilegivel (${e.message})`);
    }
  }

  console.log('=== 1. Baixando as listas reais ===');
  await baixar('groq', 'https://api.groq.com/openai/v1/models',
    { Authorization: 'Bearer ' + chaves.GROQ_API_KEY },
    (j) => (j.data || []).map((m) => m.id).sort());
  await baixar('openrouter', 'https://openrouter.ai/api/v1/models',
    { Authorization: 'Bearer ' + chaves.OPENROUTER_API_KEY },
    (j) => (j.data || []).map((m) => m.id).sort());
  await baixar('nvidia', 'https://integrate.api.nvidia.com/v1/models',
    { Authorization: 'Bearer ' + chaves.NVIDIA_API_KEY },
    (j) => (j.data || []).map((m) => m.id).sort());
  await baixar('gemini', `https://generativelanguage.googleapis.com/v1beta/models?key=${chaves.GEMINI_API_KEY}&pageSize=200`,
    {}, (j) => (j.models || []).map((m) => String(m.name).replace(/^models\//, ''))
      .filter((n) => n.startsWith('gemini') || n.startsWith('gemma')).sort());
  await baixar('zhipu', 'https://open.bigmodel.cn/api/paas/v4/models',
    { Authorization: 'Bearer ' + chaves.ZHIPU_API_KEY },
    (j) => ((j.data || j.models || []).map((m) => m.id || m.name)).sort());
  await baixar('openai', 'https://api.openai.com/v1/models',
    { Authorization: 'Bearer ' + chaves.OPENAI_API_KEY },
    (j) => (j.data || []).map((m) => m.id).sort());

  if (falhas.length) {
    console.log('\n  Nao foi possivel baixar:');
    falhas.forEach((f) => console.log('    - ' + f));
  }

  fs.writeFileSync(SAIDA, JSON.stringify(real, null, 2), 'utf8');
  console.log(`\n  Listas reais salvas em: ${path.relative(RAIZ, SAIDA)}`);

  // ── Validacao do que esta no codigo ─────────────────────────────────────
  const arquivos = [
    'frontend/src/lib/constants.ts',
    'frontend/src/components/saas/JarvisPage.tsx',
  ];

  console.log('\n=== 2. IDs no codigo que NAO existem mais na API ===');
  let totalRuins = 0;
  for (const arq of arquivos) {
    const ids = extrairDoCodigo(arq);
    console.log(`\n  --- ${arq} (${ids.length} ids declarados) ---`);
    let achou = false;
    for (const id of ids) {
      // Descobre a qual provider o id pertence, pelo prefixo/semelhanca
      let dono = null;
      if (/^(llama|meta\/|mistralai\/|google\/|nvidia\/|qwen\/|deepseek-ai\/)/.test(id) && real.nvidia) {
        if (real.nvidia.includes(id) || real.nvidia.some((x) => x.endsWith('/' + id))) dono = 'nvidia';
      }
      if (!dono && real.groq && (real.groq.includes(id) || /^(openai\/gpt-oss|groq\/|qwen\/qwen3|whisper|llama-3)/.test(id))) dono = 'groq';
      if (!dono && real.gemini && (real.gemini.includes(id) || /^gemini-/.test(id))) dono = 'gemini';
      if (!dono && real.openai && (real.openai.includes(id) || /^(gpt-4|gpt-5|o1|o3)/.test(id))) dono = 'openai';

      if (dono === 'nvidia' && real.nvidia) {
        const existe = real.nvidia.includes(id) || real.nvidia.some((x) => x.endsWith('/' + id));
        const semPrefixo = id.replace(/^nvidia\//, '');
        const existeSemPrefixo = real.nvidia.includes(semPrefixo);
        if (!existe && !existeSemPrefixo) {
          console.log(`    NAO EXISTE  [nvidia]     ${id}`);
          totalRuins++; achou = true;
        } else if (id.startsWith('nvidia/') && existeSemPrefixo) {
          console.log(`    PREFIXO!    [nvidia]     ${id}  -> use "${semPrefixo}"`);
        }
      } else if (dono) {
        if (!real[dono].includes(id)) {
          console.log(`    NAO EXISTE  [${dono.padEnd(10)}] ${id}`);
          totalRuins++; achou = true;
        }
      }
    }
    if (!achou) console.log('    (nenhum problema detectado)');
  }

  console.log('\n=== 3. Modelos ":free" do OpenRouter que ainda existem ===');
  if (real.openrouter) {
    const gratis = real.openrouter.filter((m) => m.endsWith(':free'));
    console.log(`  ${gratis.length} disponiveis:`);
    gratis.forEach((m) => console.log('    ' + m));
  }

  console.log('\n' + '='.repeat(70));
  console.log(totalRuins === 0
    ? 'RESULTADO: todas as listas do codigo batem com as APIs'
    : `RESULTADO: ${totalRuins} ID(s) do codigo nao existem mais — precisam ser trocados`);
})();
