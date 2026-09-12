/**
 * Extrai as funcoes de preparacao de voz do JarvisPage.tsx e as executa no Node.
 *
 * POR QUE ASSIM
 * `prepararTextoParaFala` e `dividirEmFrases` vivem dentro de um .tsx e nao tem
 * como serem importadas por um teste. Um teste apenas de TEXTO (procurar strings
 * no arquivo) nao pegaria o bug real: o problema era o EFEITO do regex (apagar a
 * letra "a" com til), nao a presenca de uma linha. Entao extraimos a funcao e
 * rodamos de verdade.
 *
 * As funcoes sao JavaScript puro por dentro (nenhum JSX), entao basta remover as
 * anotacoes de tipo do TypeScript para o Node executar.
 *
 * Uso: node tests-manual/_voz_extrair.cjs <caminho do JarvisPage.tsx>
 * Saida: JSON com o resultado dos casos, no stdout.
 */
const fs = require('fs');

const arquivo = process.argv[2];
if (!arquivo) {
  console.error('uso: node _voz_extrair.cjs <JarvisPage.tsx>');
  process.exit(2);
}
const src = fs.readFileSync(arquivo, 'utf8');

/** Recorta uma funcao pelo nome, equilibrando as chaves. */
function extrair(nome) {
  const i = src.indexOf(`function ${nome}(`);
  if (i < 0) return null;
  const inicioChaves = src.indexOf('{', i);
  let nivel = 0;
  for (let k = inicioChaves; k < src.length; k++) {
    const c = src[k];
    if (c === '{') nivel++;
    else if (c === '}') {
      nivel--;
      if (nivel === 0) return src.slice(i, k + 1);
    }
  }
  return null;
}

/** Remove as anotacoes de tipo do TypeScript (so as que usamos aqui). */
function semTipos(codigo) {
  return codigo
    .replace(/\)\s*:\s*string\[\]\s*\{/, ') {')
    .replace(/\)\s*:\s*string\s*\{/, ') {')
    .replace(/\)\s*:\s*string\[\]\s*$/, ')')
    .replace(/(\w+)\s*:\s*string\[\]/g, '$1')
    .replace(/(\w+)\s*:\s*string/g, '$1');
}

const fontePreparar = extrair('prepararTextoParaFala');
const fonteDividir = extrair('dividirEmFrases');

if (!fontePreparar || !fonteDividir) {
  console.error('nao consegui extrair as funcoes do arquivo');
  process.exit(3);
}

let prepararTextoParaFala, dividirEmFrases;
try {
  // eslint-disable-next-line no-new-func
  const fabrica = new Function(
    `${semTipos(fontePreparar)}\n${semTipos(fonteDividir)}\nreturn { prepararTextoParaFala, dividirEmFrases };`
  );
  ({ prepararTextoParaFala, dividirEmFrases } = fabrica());
} catch (e) {
  console.error('erro ao montar as funcoes: ' + e.message);
  process.exit(4);
}

const resultados = [];
const registrar = (nome, entrada, obtido, esperado) => {
  const ok = typeof esperado === 'function' ? esperado(obtido) : obtido === esperado;
  resultados.push({ nome, entrada, obtido, ok });
};

// ── O BUG: a letra "a" com til era apagada ──────────────────────────────────
const TIL = 'ã';
for (const palavra of ['não', 'então', 'informação', 'manhã', 'irmã', 'coração', 'ação', 'atenção']) {
  const saida = prepararTextoParaFala(palavra);
  registrar(`preserva "${palavra}"`, palavra, saida, palavra);
}
// Frase completa com varios tils
const frase = 'Não é verdade? Então a informação não chegou de manhã.';
registrar('frase com tils sai intacta', frase, prepararTextoParaFala(frase),
  (o) => o.includes(TIL) && o.includes('Não') && o.includes('Então') && o.includes('informação'));

// ── Acentuacao geral precisa sobreviver ────────────────────────────────────
// A frase contem de proposito TODAS as letras exigidas na verificacao
// (ç, é, ê, ú, ô, í). DUAS vezes o teste falhou aqui por exigir uma letra que o
// texto nao tinha ("ú" na 1a versao, "í" na 2a) — o defeito era do teste.
const acentos = 'Ação, coração, você, até, avô, português, último, país, fácil.';
registrar('acentos preservados', acentos, prepararTextoParaFala(acentos),
  (o) => ['ç', 'é', 'ê', 'ú', 'ô', 'í'].every((c) => o.includes(c)));

// ── Markdown vira fala, nao marcador ───────────────────────────────────────
const md = '**Importante:** leia o `config.yaml` e veja [a documentação](https://exemplo.com/doc).';
const saidaMd = prepararTextoParaFala(md);
registrar('negrito nao vira asterisco', md, saidaMd, (o) => !o.includes('*'));
registrar('crase de codigo some', md, saidaMd, (o) => !o.includes('`'));
registrar('URL nao e lida em voz alta', md, saidaMd,
  (o) => !o.includes('http') && !o.includes('exemplo.com'));
registrar('rotulo do link e falado', md, saidaMd, (o) => o.includes('documentação'));
registrar('conteudo do negrito permanece', md, saidaMd, (o) => o.includes('Importante'));

// Bloco de codigo nao deve ser lido
const comCodigo = 'Veja o comando:\n```bash\nrm -rf /tmp/lixo\n```\nPronto.';
const saidaCodigo = prepararTextoParaFala(comCodigo);
registrar('codigo em bloco nao e lido', comCodigo, saidaCodigo,
  (o) => !o.includes('rm -rf') && !o.includes('```'));
registrar('texto em volta do codigo permanece', comCodigo, saidaCodigo,
  (o) => o.includes('Veja o comando') && o.includes('Pronto'));

// Titulos e listas
const lista = '## Resumo\n- Primeiro item\n- Segundo item\n\n1. Um\n2. Dois';
const saidaLista = prepararTextoParaFala(lista);
registrar('titulo sem cerquilha', lista, saidaLista, (o) => !o.includes('#'));
registrar('itens preservados', lista, saidaLista,
  (o) => o.includes('Primeiro item') && o.includes('Segundo item') && o.includes('Um'));

// Tabela: barras nao podem virar leitura
const tabela = '| Nome | Valor |\n|---|---|\n| disco | 48 GB |';
const saidaTabela = prepararTextoParaFala(tabela);
registrar('barra de tabela nao e lida', tabela, saidaTabela, (o) => !o.includes('|'));
registrar('celulas preservadas', tabela, saidaTabela,
  (o) => o.includes('Nome') && o.includes('disco') && o.includes('48'));
registrar('GB vira gigabytes', tabela, saidaTabela, (o) => /gigabytes/i.test(o));

// Simbolos
registrar('R$ vira reais', 'Custa R$ 29,99.', prepararTextoParaFala('Custa R$ 29,99.'),
  (o) => o.includes('reais') && !o.includes('$'));
registrar('% vira por cento', 'Caiu 42%.', prepararTextoParaFala('Caiu 42%.'),
  (o) => o.includes('por cento'));
registrar('seta vira "para"', 'A -> B', prepararTextoParaFala('A -> B'),
  (o) => o.includes(' para ') && !o.includes('->'));
registrar('seta unicode vira "para"', 'A \u2192 B', prepararTextoParaFala('A \u2192 B'),
  (o) => o.includes(' para ') && !o.includes('\u2192'));

// Emojis
registrar('emoji removido', 'Pronto! 🚀🎉', prepararTextoParaFala('Pronto! 🚀🎉'),
  (o) => !/[\u{1F300}-\u{1FAFF}]/u.test(o) && o.includes('Pronto'));

// Texto limpo nao pode ser alterado
const limpo = 'Bom dia, Wilson. Tudo certo por aqui.';
registrar('texto comum nao e alterado', limpo, prepararTextoParaFala(limpo), limpo);

// Vazio
registrar('vazio devolve vazio', '', prepararTextoParaFala(''), '');

// ── Divisao em frases ──────────────────────────────────────────────────────
const longo = 'Primeira frase curta. Segunda frase tambem curta. Terceira frase aqui. Quarta frase final.';
const pedacos = dividirEmFrases(longo, 40);
resultados.push({
  nome: 'divide em varios pedacos',
  entrada: longo,
  obtido: pedacos.length,
  ok: pedacos.length >= 2,
});
resultados.push({
  nome: 'nenhum pedaco perde texto',
  entrada: longo,
  obtido: pedacos.join(' '),
  ok: ['Primeira', 'Segunda', 'Terceira', 'Quarta'].every((p) => pedacos.join(' ').includes(p)),
});
resultados.push({
  nome: 'pedacos respeitam o limite',
  entrada: longo,
  obtido: Math.max(...pedacos.map((p) => p.length)),
  ok: Math.max(...pedacos.map((p) => p.length)) <= 40 + 30,
});
resultados.push({
  nome: 'texto vazio nao gera pedacos',
  entrada: '',
  obtido: dividirEmFrases('').length,
  ok: dividirEmFrases('').length === 0,
});

process.stdout.write(JSON.stringify(resultados, null, 1));
