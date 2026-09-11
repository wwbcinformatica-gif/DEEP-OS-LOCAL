import React, { useState } from 'react';

interface DiffViewerProps {
  diff: string;
  filename: string;
  defaultOpen?: boolean;
}

const diffLineStyle = (line: string): React.CSSProperties => {
  if (line.startsWith('+') && !line.startsWith('+++'))
    return { background: 'rgba(78,201,176,0.12)', color: '#4ec9b0' };
  if (line.startsWith('-') && !line.startsWith('---'))
    return { background: 'rgba(244,71,71,0.12)', color: '#f44747' };
  if (line.startsWith('@@')) return { background: 'var(--accent-soft)', color: 'var(--accent)' };
  return {};
};

const btn: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--accent)',
  cursor: 'pointer',
  fontSize: '10px',
  fontWeight: 600,
  fontFamily: 'inherit',
  padding: '2px 4px',
  borderRadius: '2px',
};

const codeStyle: React.CSSProperties = {
  fontSize: '10px',
  lineHeight: 1.4,
  fontFamily: "'SF Mono','Fira Code','Consolas','Courier New',monospace",
  whiteSpace: 'pre',
  overflowX: 'auto',
  margin: 0,
};

const extensions: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  py: 'python',
  rs: 'rust',
  go: 'go',
  java: 'java',
  rb: 'ruby',
  php: 'php',
  c: 'c',
  cpp: 'cpp',
  h: 'c',
  hpp: 'cpp',
  css: 'css',
  scss: 'scss',
  less: 'less',
  html: 'html',
  htm: 'html',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  md: 'markdown',
  xml: 'xml',
  sql: 'sql',
  sh: 'bash',
  bash: 'bash',
  zsh: 'bash',
  ps1: 'powershell',
  toml: 'toml',
  ini: 'ini',
  cfg: 'ini',
  conf: 'ini',
};

const KEYWORD_SETS: Record<string, string[]> = {
  typescript: [
    'import',
    'export',
    'from',
    'const',
    'let',
    'var',
    'function',
    'return',
    'if',
    'else',
    'for',
    'while',
    'do',
    'switch',
    'case',
    'break',
    'continue',
    'new',
    'this',
    'async',
    'await',
    'class',
    'interface',
    'type',
    'extends',
    'implements',
    'typeof',
    'instanceof',
    'keyof',
    'in',
    'of',
    'true',
    'false',
    'null',
    'undefined',
    'void',
    'never',
    'any',
    'unknown',
    'readonly',
    'static',
    'private',
    'public',
    'protected',
    'abstract',
    'declare',
    'enum',
    'throw',
    'try',
    'catch',
    'finally',
    'yield',
    'generator',
    'as',
    'is',
    'satisfies',
  ],
  javascript: [
    'import',
    'export',
    'from',
    'const',
    'let',
    'var',
    'function',
    'return',
    'if',
    'else',
    'for',
    'while',
    'do',
    'switch',
    'case',
    'break',
    'continue',
    'new',
    'this',
    'async',
    'await',
    'class',
    'extends',
    'typeof',
    'instanceof',
    'of',
    'in',
    'true',
    'false',
    'null',
    'undefined',
    'throw',
    'try',
    'catch',
    'finally',
    'yield',
  ],
  python: [
    'import',
    'from',
    'as',
    'def',
    'return',
    'if',
    'elif',
    'else',
    'for',
    'while',
    'class',
    'async',
    'await',
    'with',
    'as',
    'try',
    'except',
    'finally',
    'raise',
    'yield',
    'lambda',
    'pass',
    'break',
    'continue',
    'and',
    'or',
    'not',
    'in',
    'is',
    'None',
    'True',
    'False',
    'self',
    'super',
  ],
  rust: [
    'fn',
    'let',
    'mut',
    'const',
    'if',
    'else',
    'for',
    'while',
    'loop',
    'match',
    'return',
    'struct',
    'enum',
    'impl',
    'trait',
    'pub',
    'use',
    'mod',
    'crate',
    'self',
    'super',
    'where',
    'as',
    'in',
    'ref',
    'move',
    'async',
    'await',
    'unsafe',
    'dyn',
    'true',
    'false',
  ],
  go: [
    'func',
    'return',
    'if',
    'else',
    'for',
    'range',
    'switch',
    'case',
    'default',
    'break',
    'continue',
    'go',
    'defer',
    'select',
    'chan',
    'map',
    'struct',
    'interface',
    'type',
    'package',
    'import',
    'var',
    'const',
    'nil',
    'true',
    'false',
    'make',
    'new',
    'append',
    'len',
    'cap',
  ],
  bash: [
    'if',
    'then',
    'else',
    'elif',
    'fi',
    'for',
    'while',
    'do',
    'done',
    'case',
    'esac',
    'function',
    'return',
    'exit',
    'export',
    'local',
    'source',
    'echo',
    'read',
    'set',
    'unset',
    'trap',
  ],
};

function detectLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return extensions[ext] || '';
}

function highlightLine(line: string, lang: string): React.ReactNode {
  if (!lang || lang === 'diff') return line;
  const keywords = KEYWORD_SETS[lang];
  if (!keywords) return line;

  const parts: React.ReactNode[] = [];
  const regex = /\b([a-zA-Z_$][\w$]*)\b/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(line)) !== null) {
    const word = match[1];
    if (keywords.includes(word)) {
      if (match.index > lastIdx) {
        parts.push(line.slice(lastIdx, match.index));
      }
      parts.push(
        <span key={match.index} style={{ color: '#569cd6' }}>
          {word}
        </span>,
      );
      lastIdx = match.index + word.length;
    }
  }
  if (lastIdx < line.length) {
    parts.push(line.slice(lastIdx));
  }
  return parts.length > 0 ? parts : line;
}

function renderDiffLine(line: string, lang: string, lineIdx: number): React.ReactNode {
  const baseStyle = diffLineStyle(line);
  if (line.startsWith('+') || line.startsWith('-')) {
    const content = line[0] + (line.length > 1 ? line.slice(1) : '');
    const highlighted = highlightLine(content, lang);
    return (
      <div key={lineIdx} style={{ padding: '0 12px', ...baseStyle }}>
        {highlighted}
      </div>
    );
  }
  return (
    <div key={lineIdx} style={{ padding: '0 12px', ...baseStyle }}>
      {line || ' '}
    </div>
  );
}

export default function DiffViewer({ diff, filename, defaultOpen = false }: DiffViewerProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (!diff || !diff.trim()) return null;

  const lines = diff.split('\n');
  const addCount = lines.filter((l) => l.startsWith('+') && !l.startsWith('+++')).length;
  const delCount = lines.filter((l) => l.startsWith('-') && !l.startsWith('---')).length;
  const lang = detectLanguage(filename);

  return (
    <div
      style={{
        marginTop: '6px',
        border: '1px solid var(--line)',
        borderRadius: '4px',
        overflow: 'hidden',
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '4px 8px',
          background: 'var(--bg-2)',
          borderBottom: open ? '1px solid var(--line)' : 'none',
          cursor: 'pointer',
          userSelect: 'none',
          fontSize: '10px',
          fontFamily: "'SF Mono','Fira Code','Consolas','Courier New',monospace",
        }}
      >
        <span
          style={{
            color: 'var(--muted)',
            transition: 'transform 0.15s',
            display: 'inline-block',
            transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
        >
          ▶
        </span>
        <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{filename}</span>
        <span style={{ color: '#4ec9b0', fontSize: '9px' }}>+{addCount}</span>
        <span style={{ color: '#f44747', fontSize: '9px' }}>-{delCount}</span>
        {lang && (
          <span style={{ color: 'var(--quiet)', fontSize: '8px', textTransform: 'uppercase' }}>
            {lang}
          </span>
        )}
        {!open && (
          <span style={{ marginLeft: 'auto', color: 'var(--quiet)', fontSize: '9px' }}>
            clique para expandir
          </span>
        )}
      </div>
      {open && (
        <div
          style={{
            padding: '4px 0',
            maxHeight: '360px',
            overflow: 'auto',
            background: 'var(--bg)',
          }}
        >
          <code style={codeStyle}>{lines.map((line, i) => renderDiffLine(line, lang, i))}</code>
        </div>
      )}
    </div>
  );
}
