import React from 'react';

// ─── Syntax colors ────────────────────────────────────────────────────────────
const GRN = '#6a9955';
const BLU = '#569cd6';
const TEA = '#4ec9b0';
const YLW = '#dcdcaa';
const DIM = '#9d9d9d';

// ─── Keywords ─────────────────────────────────────────────────────────────────
const KEYWORDS_JS = new Set([
  'break',
  'case',
  'catch',
  'class',
  'const',
  'continue',
  'debugger',
  'default',
  'delete',
  'do',
  'else',
  'export',
  'extends',
  'finally',
  'for',
  'function',
  'if',
  'import',
  'in',
  'instanceof',
  'let',
  'new',
  'of',
  'return',
  'static',
  'super',
  'switch',
  'this',
  'throw',
  'try',
  'typeof',
  'var',
  'void',
  'while',
  'with',
  'yield',
  'async',
  'await',
  'from',
  'as',
  'interface',
  'type',
  'enum',
  'implements',
  'abstract',
  'readonly',
  'private',
  'protected',
  'public',
  'declare',
  'namespace',
  'module',
  'require',
  'true',
  'false',
  'null',
  'undefined',
  'NaN',
  'Infinity',
]);
const KEYWORDS_HTML = new Set([
  'html',
  'head',
  'body',
  'div',
  'span',
  'p',
  'a',
  'img',
  'ul',
  'ol',
  'li',
  'table',
  'tr',
  'td',
  'th',
  'form',
  'input',
  'button',
  'select',
  'option',
  'textarea',
  'label',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'header',
  'footer',
  'nav',
  'section',
  'article',
  'aside',
  'main',
  'figure',
  'figcaption',
  'script',
  'style',
  'link',
  'meta',
  'title',
  'br',
  'hr',
  'em',
  'strong',
  'i',
  'b',
  'u',
  's',
  'code',
  'pre',
  'blockquote',
  'iframe',
  'video',
  'canvas',
  'svg',
  'path',
  'circle',
  'rect',
  'line',
  'g',
  'defs',
  'use',
  'stop',
  'linearGradient',
]);

const LANG_EXT: Record<string, string> = {
  ts: 'tsx',
  tsx: 'tsx',
  js: 'tsx',
  jsx: 'tsx',
  mjs: 'tsx',
  cjs: 'tsx',
  json: 'json',
  md: 'md',
  css: 'css',
  scss: 'css',
  less: 'css',
  html: 'html',
  htm: 'html',
  xml: 'xml',
  py: 'py',
  php: 'php',
  rb: 'rb',
  go: 'go',
  rs: 'rs',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  h: 'c',
  hpp: 'cpp',
  cs: 'cs',
  swift: 'swift',
  kt: 'kt',
  sh: 'sh',
  bash: 'sh',
  zsh: 'sh',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'toml',
  cfg: 'ini',
  ini: 'ini',
  env: 'ini',
  sql: 'sql',
  graphql: 'graphql',
  gql: 'graphql',
  dart: 'dart',
  lua: 'lua',
  r: 'r',
  pl: 'pl',
  pas: 'pas',
  vue: 'tsx',
  svelte: 'tsx',
};

function esc(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── React nodes syntax highlighting ──────────────────────────────────────────
export function highlightCode(code: string, ext: string): React.ReactNode[] {
  const lang = LANG_EXT[ext] || ext;
  const lines = code.split('\n');
  const result: React.ReactNode[] = [];

  for (let li = 0; li < lines.length; li++) {
    if (li > 0) result.push('\n');
    let line = lines[li];
    const tokens: React.ReactNode[] = [];
    let i = 0;

    while (i < line.length) {
      if (/^\s/.test(line[i])) {
        let ws = '';
        while (i < line.length && /\s/.test(line[i])) {
          ws += line[i];
          i++;
        }
        tokens.push(ws);
        continue;
      }
      if (line[i] === '/' && line[i + 1] === '/') {
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: GRN }}>
            {line.slice(i)}
          </span>,
        );
        i = line.length;
        continue;
      }
      if (line[i] === '/' && line[i + 1] === '*') {
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: GRN }}>
            {line.slice(i)}
          </span>,
        );
        i = line.length;
        continue;
      }
      if (
        (lang === 'tsx' || lang === 'html') &&
        line[i] === '<' &&
        /[a-zA-Z/]/.test(line[i + 1] || '')
      ) {
        let tag = '<';
        i++;
        let isClosing = false;
        if (line[i] === '/') {
          tag += '/';
          i++;
          isClosing = true;
        }
        let tagName = '';
        while (i < line.length && /[a-zA-Z0-9_:.-]/.test(line[i])) {
          tagName += line[i];
          i++;
        }
        tag += tagName;
        let attrs = '';
        while (i < line.length && line[i] !== '>' && line[i] !== '/') {
          if (line[i] === "'" || line[i] === '"') {
            const q = line[i];
            attrs += q;
            i++;
            while (i < line.length && line[i] !== q) {
              attrs += line[i];
              i++;
            }
            if (i < line.length) {
              attrs += q;
              i++;
            }
          } else {
            if (line[i] === '{') {
              let depth = 1;
              attrs += '{';
              i++;
              while (i < line.length && depth > 0) {
                if (line[i] === '{') depth++;
                if (line[i] === '}') depth--;
                if (depth > 0) {
                  attrs += line[i];
                  i++;
                }
              }
              if (i < line.length) {
                attrs += '}';
                i++;
              }
            } else {
              attrs += line[i];
              i++;
            }
          }
        }
        if (i < line.length && line[i] === '/') {
          tag += '/';
          i++;
        }
        if (i < line.length) {
          tag += '>';
          i++;
        }
        const tagColor = isClosing ? BLU : KEYWORDS_HTML.has(tagName.toLowerCase()) ? BLU : TEA;
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: tagColor }}>
            {tag}
          </span>,
        );
        if (attrs)
          tokens.push(
            <span key={`${li}-${i}-attrs`} style={{ color: YLW }}>
              {attrs}
            </span>,
          );
        continue;
      }
      if (line[i] === '`') {
        let s = '`';
        i++;
        while (i < line.length && line[i] !== '`') {
          if (line[i] === '$' && line[i + 1] === '{') {
            s += '${';
            i += 2;
            let depth = 1;
            while (i < line.length && depth > 0) {
              if (line[i] === '{') depth++;
              if (line[i] === '}') depth--;
              if (depth > 0) {
                s += line[i];
                i++;
              }
            }
            if (i < line.length) {
              s += '}';
              i++;
            }
          } else {
            if (line[i] === '\\' && i + 1 < line.length) {
              s += line[i] + line[i + 1];
              i += 2;
            } else {
              s += line[i];
              i++;
            }
          }
        }
        if (i < line.length) {
          s += '`';
          i++;
        }
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: '#ce9178' }}>
            {s}
          </span>,
        );
        continue;
      }
      if (line[i] === "'" || line[i] === '"') {
        const q = line[i];
        let s = q;
        i++;
        while (i < line.length && line[i] !== q) {
          if (line[i] === '\\' && i + 1 < line.length) {
            s += line[i] + line[i + 1];
            i += 2;
          } else {
            s += line[i];
            i++;
          }
        }
        if (i < line.length) {
          s += q;
          i++;
        }
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: '#ce9178' }}>
            {s}
          </span>,
        );
        continue;
      }
      if (/[0-9]/.test(line[i]) && (i === 0 || !/[a-zA-Z_]/.test(line[i - 1]))) {
        let n = '';
        if (line[i] === '0' && (line[i + 1] === 'x' || line[i + 1] === 'X')) {
          n = '0x';
          i += 2;
          while (i < line.length && /[0-9a-fA-F]/.test(line[i])) {
            n += line[i];
            i++;
          }
        } else if (line[i] === '0' && (line[i + 1] === 'b' || line[i + 1] === 'B')) {
          n = '0b';
          i += 2;
          while (i < line.length && /[01]/.test(line[i])) {
            n += line[i];
            i++;
          }
        } else {
          while (i < line.length && /[0-9.]/.test(line[i])) {
            n += line[i];
            i++;
          }
        }
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: '#b5cea8' }}>
            {n}
          </span>,
        );
        continue;
      }
      if (/[a-zA-Z_$]/.test(line[i])) {
        let w = '';
        while (i < line.length && /[a-zA-Z0-9_$\-]/.test(line[i])) {
          w += line[i];
          i++;
        }
        if (KEYWORDS_JS.has(w))
          tokens.push(
            <span key={`${li}-${i}`} style={{ color: BLU }}>
              {w}
            </span>,
          );
        else if (w.length >= 2 && w[0] === w[0].toUpperCase() && w[0] !== w[0].toLowerCase())
          tokens.push(
            <span key={`${li}-${i}`} style={{ color: TEA }}>
              {w}
            </span>,
          );
        else if (i < line.length && line[i] === '(')
          tokens.push(
            <span key={`${li}-${i}`} style={{ color: YLW }}>
              {w}
            </span>,
          );
        else if (w === 'true' || w === 'false')
          tokens.push(
            <span key={`${li}-${i}`} style={{ color: BLU }}>
              {w}
            </span>,
          );
        else tokens.push(w);
        continue;
      }
      if (/[{}()\[\];:.,<>=+\-*/%!&|^~?@]/.test(line[i])) {
        tokens.push(
          <span key={`${li}-${i}`} style={{ color: DIM }}>
            {line[i]}
          </span>,
        );
        i++;
        continue;
      }
      tokens.push(line[i]);
      i++;
    }
    if (tokens.length > 0) result.push(<span key={`l${li}`}>{tokens}</span>);
    else if (line === '') result.push('');
    else result.push(line);
  }
  return result;
}

// ─── HTML string syntax highlighting (for contentEditable) ────────────────────
export function highlightHtml(code: string, ext: string): string {
  const lang = LANG_EXT[ext] || ext;
  const lines = code.split('\n');
  const out: string[] = [];

  if (lang === 'md') {
    let html = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // 1. Títulos H1, H2, H3 (Cores vibrantes do Dracula)
    html = html.replace(/^(# .+)$/gm, '<span style="color: #ff79c6; font-weight: bold;">$1</span>');
    html = html.replace(
      /^(## .+)$/gm,
      '<span style="color: #8be9fd; font-weight: bold;">$1</span>',
    );
    html = html.replace(
      /^(### .+)$/gm,
      '<span style="color: #50fa7b; font-weight: bold;">$1</span>',
    );

    // 2. Listas e Marcadores (Laranja)
    html = html.replace(/^(\s*[-*+]\s)/gm, '<span style="color: #ffb86c;">$1</span>');
    html = html.replace(/^(\s*\d+\.\s)/gm, '<span style="color: #ffb86c;">$1</span>');

    // 3. Links e URLs (Ciano/Amarelo)
    html = html.replace(/(\[[^\]]+\]\([^)]+\))/g, '<span style="color: #f1fa8c;">$1</span>');

    // 4. Negrito e Itálico
    html = html.replace(
      /(\*\*[^*]+\*\*)/g,
      '<span style="color: #ff79c6; font-weight: bold;">$1</span>',
    );
    html = html.replace(
      /(\*[^*]+\*)/g,
      '<span style="color: #f1fa8c; font-style: italic;">$1</span>',
    );

    // 5. Blocos de Código ``` (Cinza de Fundo / Roxo)
    html = html.replace(
      /(```[\s\S]*?```)/g,
      '<span style="color: #bd93f9; background: #282a36; padding: 2px 4px; border-radius: 4px;">$1</span>',
    );

    // 6. Código inline `code` (Rosa claro)
    html = html.replace(
      /(`[^`]+`)/g,
      '<span style="color: #f1fa8c; background: #282a36; padding: 1px 4px; border-radius: 3px;">$1</span>',
    );

    return html.replace(/\n/g, '<br>');
  }

  for (let li = 0; li < lines.length; li++) {
    let line = lines[li];
    const tokens: string[] = [];
    let i = 0;
    while (i < line.length) {
      if (/^\s/.test(line[i])) {
        let ws = '';
        while (i < line.length && /\s/.test(line[i])) {
          ws += line[i];
          i++;
        }
        tokens.push(esc(ws));
        continue;
      }
      if (line[i] === '/' && line[i + 1] === '/') {
        tokens.push(`<span style="color:${GRN}">${esc(line.slice(i))}</span>`);
        i = line.length;
        continue;
      }
      if (line[i] === '/' && line[i + 1] === '*') {
        tokens.push(`<span style="color:${GRN}">${esc(line.slice(i))}</span>`);
        i = line.length;
        continue;
      }
      if (
        (lang === 'tsx' || lang === 'html') &&
        line[i] === '<' &&
        /[a-zA-Z/]/.test(line[i + 1] || '')
      ) {
        let tag = '<';
        i++;
        if (line[i] === '/') {
          tag += '/';
          i++;
        }
        let tn = '';
        while (i < line.length && /[a-zA-Z0-9_:.-]/.test(line[i])) {
          tn += line[i];
          i++;
        }
        tag += tn;
        while (i < line.length && line[i] !== '>' && line[i] !== '/') {
          if (line[i] === "'" || line[i] === '"') {
            const q = line[i];
            tag += q;
            i++;
            while (i < line.length && line[i] !== q) {
              tag += line[i];
              i++;
            }
            if (i < line.length) {
              tag += q;
              i++;
            }
          } else if (line[i] === '{') {
            let d = 1;
            tag += '{';
            i++;
            while (i < line.length && d > 0) {
              if (line[i] === '{') d++;
              if (line[i] === '}') d--;
              if (d > 0) {
                tag += line[i];
                i++;
              }
            }
            if (i < line.length) {
              tag += '}';
              i++;
            }
          } else {
            tag += line[i];
            i++;
          }
        }
        if (i < line.length && line[i] === '/') {
          tag += '/';
          i++;
        }
        if (i < line.length) {
          tag += '>';
          i++;
        }
        const tc = KEYWORDS_HTML.has(tn.toLowerCase()) ? BLU : TEA;
        tokens.push(`<span style="color:${tc}">${esc(tag)}</span>`);
        continue;
      }
      if (line[i] === '`') {
        let s = '`';
        i++;
        while (i < line.length && line[i] !== '`') {
          if (line[i] === '$' && line[i + 1] === '{') {
            s += '${';
            i += 2;
            let d = 1;
            while (i < line.length && d > 0) {
              if (line[i] === '{') d++;
              if (line[i] === '}') d--;
              if (d > 0) {
                s += line[i];
                i++;
              }
            }
            if (i < line.length) {
              s += '}';
              i++;
            }
          } else {
            if (line[i] === '\\' && i + 1 < line.length) {
              s += line[i] + line[i + 1];
              i += 2;
            } else {
              s += line[i];
              i++;
            }
          }
        }
        if (i < line.length) {
          s += '`';
          i++;
        }
        tokens.push(`<span style="color:#ce9178">${esc(s)}</span>`);
        continue;
      }
      if (line[i] === "'" || line[i] === '"') {
        const q = line[i];
        let s = q;
        i++;
        while (i < line.length && line[i] !== q) {
          if (line[i] === '\\' && i + 1 < line.length) {
            s += line[i] + line[i + 1];
            i += 2;
          } else {
            s += line[i];
            i++;
          }
        }
        if (i < line.length) {
          s += q;
          i++;
        }
        tokens.push(`<span style="color:#ce9178">${esc(s)}</span>`);
        continue;
      }
      if (/[0-9]/.test(line[i]) && (i === 0 || !/[a-zA-Z_]/.test(line[i - 1]))) {
        let n = '';
        if (line[i] === '0' && (line[i + 1] === 'x' || line[i + 1] === 'X')) {
          n = '0x';
          i += 2;
          while (i < line.length && /[0-9a-fA-F]/.test(line[i])) {
            n += line[i];
            i++;
          }
        } else if (line[i] === '0' && (line[i + 1] === 'b' || line[i + 1] === 'B')) {
          n = '0b';
          i += 2;
          while (i < line.length && /[01]/.test(line[i])) {
            n += line[i];
            i++;
          }
        } else {
          while (i < line.length && /[0-9.]/.test(line[i])) {
            n += line[i];
            i++;
          }
        }
        tokens.push(`<span style="color:#b5cea8">${esc(n)}</span>`);
        continue;
      }
      if (/[a-zA-Z_$]/.test(line[i])) {
        let w = '';
        while (i < line.length && /[a-zA-Z0-9_$\-]/.test(line[i])) {
          w += line[i];
          i++;
        }
        if (KEYWORDS_JS.has(w)) {
          tokens.push(`<span style="color:${BLU}">${esc(w)}</span>`);
        } else if (w.length >= 2 && w[0] === w[0].toUpperCase() && w[0] !== w[0].toLowerCase()) {
          tokens.push(`<span style="color:${TEA}">${esc(w)}</span>`);
        } else if (i < line.length && line[i] === '(') {
          tokens.push(`<span style="color:${YLW}">${esc(w)}</span>`);
        } else if (w === 'true' || w === 'false') {
          tokens.push(`<span style="color:${BLU}">${esc(w)}</span>`);
        } else {
          tokens.push(esc(w));
        }
        continue;
      }
      if (/[{}()\[\];:.,<>=+\-*/%!&|^~?@]/.test(line[i])) {
        tokens.push(`<span style="color:${DIM}">${esc(line[i])}</span>`);
        i++;
        continue;
      }
      tokens.push(esc(line[i]));
      i++;
    }
    out.push(`<div style="min-height:1.6em">${tokens.join('') || '\u00a0'}</div>`);
  }
  return out.join('');
}

// ─── Inline markdown ──────────────────────────────────────────────────────────
function inlineMd(text: string): string {
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    if (text[i] === '*' && text[i + 1] === '*') {
      let content = '';
      i += 2;
      while (i < text.length && !(text[i] === '*' && text[i + 1] === '*')) {
        content += text[i];
        i++;
      }
      if (i < text.length) i += 2;
      out.push(`<strong style="color:#dcdcaa">${esc(content)}</strong>`);
      continue;
    }
    if (text[i] === '`') {
      let content = '';
      i++;
      while (i < text.length && text[i] !== '`') {
        content += text[i];
        i++;
      }
      if (i < text.length) i++;
      out.push(
        `<code style="background:var(--bg-3);color:#ce9178;padding:1px 5px;border-radius:3px;font-family:inherit;font-size:0.92em">${esc(content)}</code>`,
      );
      continue;
    }
    if (text[i] === '|') {
      out.push(
        `<span style="color:var(--muted);border-right:1px solid var(--line);padding:0 6px">${esc(text[i])}</span>`,
      );
      i++;
      continue;
    }
    out.push(esc(text[i]));
    i++;
  }
  return out.join('');
}
