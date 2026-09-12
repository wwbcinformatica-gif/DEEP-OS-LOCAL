import React from 'react';

const LANG_LABELS: Record<string, string> = {
  python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript',
  jsx: 'JSX', tsx: 'TSX', java: 'Java', cpp: 'C++', c: 'C',
  go: 'Go', rust: 'Rust', ruby: 'Ruby', php: 'PHP',
  html: 'HTML', css: 'CSS', sql: 'SQL', bash: 'Bash',
  json: 'JSON', yaml: 'YAML', markdown: 'Markdown', shell: 'Shell',
};

function highlightCode(code: string, lang: string): React.ReactNode {
  const lines = code.split('\n');
  return lines.map((line, i) => {
    let highlighted = line
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/(\/\/.*$|#.*$)/gm, '<span style="color:#6a9955">$1</span>')
      .replace(/(["'`])((?:(?!\1)[^\\]|\\.)*)(\1)/g, '<span style="color:#ce9178">$1$2$3</span>')
      .replace(/\b(import|from|export|default|const|let|var|function|return|if|else|for|while|class|extends|new|this|async|await|try|catch|throw|def|print|self|True|False|None|in|not|and|or|is|with|as|elif|except|lambda|yield|raise|pass|break|continue|switch|case|do|type|interface|enum|struct|pub|fn|mut|use|mod|crate|match|loop|unsafe|impl|trait|where|async|move|ref|dyn|abstract|final|static|synchronized|volatile|transient|native|public|private|protected|internal|override|readonly|optional|nullable)\b/g, '<span style="color:#569cd6">$1</span>')
      .replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#b5cea8">$1</span>');
    return (
      <div key={i} style={{ display: 'flex' }}>
        <span style={{ userSelect: 'none', color: '#555', minWidth: 32, textAlign: 'right', paddingRight: 12, fontSize: 12 }}>{i + 1}</span>
        <span dangerouslySetInnerHTML={{ __html: highlighted }} />
      </div>
    );
  });
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: '#e0e0e0', fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} style={{ background: '#1a1a2e', padding: '1px 5px', borderRadius: 4, fontSize: 12, color: '#e06c75', fontFamily: "'Cascadia Code', 'Fira Code', monospace" }}>{part.slice(1, -1)}</code>;
    }
    return <span key={i}>{part}</span>;
  });
}

export function renderMarkdown(text: string): React.ReactNode {
  let normalized = text
    .replace(/---/g, '\n---\n')
    .replace(/(#{1,6})\s/g, '\n$1 ')
    .replace(/\|([^\n]*\|)/g, (m) => '\n' + m)
    .replace(/(?<!\n)([-*+])\s+(?=[^\s])/g, '\n$1 ')
    .replace(/(?<!\n)(\d+\.)\s+(?=[^\s])/g, '\n$1 ');

  const lines = normalized.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === '') { i++; continue; }

    if (trimmed.startsWith('```')) {
      const lang = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      elements.push(
        <div key={elements.length} style={{ margin: '8px 0', borderRadius: 8, overflow: 'hidden', border: '1px solid #2a2a3e', background: '#0d0d1a' }}>
          {lang && <div style={{ padding: '4px 12px', background: '#16162a', borderBottom: '1px solid #2a2a3e', fontSize: 11, color: '#888', fontWeight: 600 }}>{LANG_LABELS[lang] || lang.toUpperCase()}</div>}
          <pre style={{ margin: 0, padding: '12px 8px', overflowX: 'auto', fontSize: 12.5, lineHeight: 1.65, fontFamily: "'Cascadia Code', 'Fira Code', monospace", color: '#d4d4d4' }}>
            <code>{highlightCode(codeLines.join('\n'), lang)}</code>
          </pre>
        </div>
      );
      continue;
    }

    if (trimmed.includes('|') && !trimmed.startsWith('```')) {
      let j = i + 1;
      while (j < lines.length && lines[j].trim() === '') j++;
      const nextHasPipe = j < lines.length && lines[j].trim().includes('|') && !lines[j].trim().startsWith('```');
      const isSeparator = j < lines.length && /^\s*\|?\s*[-:]+/.test(lines[j].trim()) && lines[j].trim().includes('|');
      if (nextHasPipe || isSeparator) {
        const headerLine = trimmed;
        const headers = headerLine.split('|').map(c => c.trim()).filter(Boolean);
        i++;
        const rows: string[][] = [];
        while (i < lines.length && lines[i].trim().includes('|') && !lines[i].trim().startsWith('```')) {
          const rowContent = lines[i].trim();
          if (/^\s*\|?\s*[-:]+/.test(rowContent) && rowContent.includes('---')) { i++; continue; }
          const cells = rowContent.split('|').map(c => c.trim()).filter(Boolean);
          if (cells.length > 0) rows.push(cells);
          i++;
        }
        if (headers.length > 0 && rows.length > 0) {
          elements.push(
            <div key={elements.length} style={{ margin: '8px 0', overflowX: 'auto', borderRadius: 6, border: '1px solid #2a2a3e' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: "'Cascadia Code', 'Fira Code', monospace" }}>
                <thead><tr>{headers.map((h, hi) => (
                  <th key={hi} style={{ padding: '6px 10px', background: '#16162a', borderBottom: '1px solid #2a2a3e', color: '#00d9ff', fontWeight: 700, textAlign: 'left', fontSize: 11 }}>{renderInline(h)}</th>
                ))}</tr></thead>
                <tbody>{rows.map((row, ri) => (
                  <tr key={ri}>{row.map((cell, ci) => (
                    <td key={ci} style={{ padding: '5px 10px', borderBottom: '1px solid #1a1a2e', color: '#ccc', background: ri % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>{renderInline(cell)}</td>
                  ))}</tr>
                ))}</tbody>
              </table>
            </div>
          );
          continue;
        }
      }
    }

    if (/^\s*[-*_]{3,}\s*$/.test(trimmed)) {
      elements.push(<hr key={elements.length} style={{ border: 'none', borderTop: '1px solid #2a2a3e', margin: '10px 0' }} />);
      i++; continue;
    }

    const hm = trimmed.match(/^(#{1,6})\s+(.+)/);
    if (hm) {
      const lvl = hm[1].length;
      const sz = lvl <= 1 ? 18 : lvl <= 2 ? 15 : 13;
      const clr = lvl <= 2 ? '#00d9ff' : '#b478ff';
      elements.push(<div key={elements.length} style={{ fontSize: sz, fontWeight: 700, color: clr, marginTop: lvl <= 2 ? 12 : 8, marginBottom: 4, fontFamily: "'Inter', sans-serif" }}>{renderInline(hm[2])}</div>);
      i++; continue;
    }

    if (/^\s*[-*+]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\s*[-*+]\s+/, ''));
        i++;
      }
      elements.push(
        <div key={elements.length} style={{ margin: '4px 0' }}>
          {items.map((item, li) => (
            <div key={li} style={{ display: 'flex', gap: 6, padding: '2px 0', paddingLeft: 8 }}>
              <span style={{ color: '#b478ff', flexShrink: 0 }}>{'\u25CF'}</span>
              <span>{renderInline(item)}</span>
            </div>
          ))}
        </div>
      );
      continue;
    }

    if (/^\s*\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\s*\d+\.\s+/, ''));
        i++;
      }
      elements.push(
        <div key={elements.length} style={{ margin: '4px 0' }}>
          {items.map((item, li) => (
            <div key={li} style={{ display: 'flex', gap: 6, padding: '2px 0', paddingLeft: 8 }}>
              <span style={{ color: '#00d9ff', flexShrink: 0, fontWeight: 700, fontSize: 12 }}>{li + 1}.</span>
              <span>{renderInline(item)}</span>
            </div>
          ))}
        </div>
      );
      continue;
    }

    elements.push(
      <div key={elements.length} style={{ margin: '3px 0', lineHeight: 1.75, color: '#ccc' }}>
        {renderInline(trimmed)}
      </div>
    );
    i++;
  }

  return elements;
}

export function renderMessageContent(content: string): React.ReactNode {
  return renderMarkdown(content);
}
