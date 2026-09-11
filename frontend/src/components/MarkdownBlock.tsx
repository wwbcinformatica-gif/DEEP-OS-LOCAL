import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import vscDarkPlus from 'react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus';

/* ─── Markdown Parser ─────────────────────────────────────────────── */

interface MarkdownNode {
  type: 'code' | 'heading' | 'list' | 'table' | 'paragraph' | 'hr';
  level?: number;
  lang?: string;
  content: string;
  items?: string[];
  rows?: string[][];
  headers?: string[];
  [key: string]: unknown;
}

function parseMarkdown(text: string): MarkdownNode[] {
  const lines = text.split('\n');
  const nodes: MarkdownNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Horizontal rule
    if (/^[-*_]{3,}\s*$/.test(line.trim())) {
      nodes.push({ type: 'hr', content: '' });
      i++;
      continue;
    }

    // Code block
    const codeMatch = line.match(/^```(\w*)/);
    if (codeMatch) {
      const lang = codeMatch[1] || '';
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      nodes.push({ type: 'code', lang, content: codeLines.join('\n') });
      continue;
    }

    // Heading
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      nodes.push({
        type: 'heading',
        level: headingMatch[1].length,
        content: headingMatch[2].trim(),
      });
      i++;
      continue;
    }

    // Table
    if (
      line.includes('|') &&
      i + 1 < lines.length &&
      /^\|?[-:| ]+\|?[-:| ]+\|?[-:| ]*$/.test(lines[i + 1]?.trim())
    ) {
      const headers = parseTableRow(line);
      i += 2; // skip header and separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes('|')) {
        const row = parseTableRow(lines[i]);
        if (row.length > 0) rows.push(row);
        i++;
      }
      nodes.push({ type: 'table', headers, rows, content: '' });
      continue;
    }

    // List (unordered)
    if (/^[\s]*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[\s]*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[\s]*[-*+]\s+/, ''));
        i++;
      }
      nodes.push({ type: 'list', items, content: '' });
      continue;
    }

    // List (ordered)
    if (/^[\s]*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[\s]*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[\s]*\d+\.\s+/, ''));
        i++;
      }
      nodes.push({ type: 'list', items, content: '' });
      continue;
    }

    // Paragraph (collect consecutive lines)
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^(#{1,6}\s|```|-{3,}|[*_]{3,})/.test(lines[i]) &&
      !lines[i].includes('|')
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      nodes.push({ type: 'paragraph', content: paraLines.join('\n') });
      continue;
    }

    i++;
  }

  return nodes;
}

function parseTableRow(line: string): string[] {
  return line
    .split('|')
    .map((c) => c.trim())
    .filter((c) => c !== '');
}

/* ─── Inline Markdown Parser ──────────────────────────────────────── */

interface InlineSpan {
  text: string;
  bold?: boolean;
  italic?: boolean;
  code?: boolean;
  link?: { href: string; text: string };
  image?: { src: string; alt: string };
}

function parseInline(text: string): InlineSpan[] {
  const spans: InlineSpan[] = [];

  // Processa imagens primeiro: ![alt](url)
  let remaining = text;
  const imgRegex = /!\[([^\]]*)\]\(([^)]*)\)/;
  let imgMatch: RegExpExecArray | null;
  while ((imgMatch = imgRegex.exec(remaining)) !== null) {
    if (imgMatch.index > 0) {
      spans.push({ text: remaining.slice(0, imgMatch.index) });
    }
    spans.push({ text: imgMatch[1], image: { src: imgMatch[2], alt: imgMatch[1] || 'image' } });
    remaining = remaining.slice(imgMatch.index + imgMatch[0].length);
  }

  // Processa links: [text](url)
  const linkRegex = /\[([^\]]*)\]\(([^)]*)\)/;
  let m: RegExpExecArray | null;
  while ((m = linkRegex.exec(remaining)) !== null) {
    if (m.index > 0) {
      spans.push({ text: remaining.slice(0, m.index) });
    }
    spans.push({ text: m[1], link: { href: m[2], text: m[1] } });
    remaining = remaining.slice(m.index + m[0].length);
  }
  if (remaining) spans.push({ text: remaining });

  // Agora processa bold, italic, code inline em cada span não-link
  const result: InlineSpan[] = [];
  const inlineRegex =
    /(~~~[\s\S]*?~~~|`[^`]+`|\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|_(.+?)_|__(.+?)__)/;
  for (const span of spans) {
    if (span.link || span.image) {
      result.push(span);
      continue;
    }
    let txt = span.text;
    let m2: RegExpExecArray | null;
    while ((m2 = inlineRegex.exec(txt)) !== null) {
      if (m2.index > 0) result.push({ text: txt.slice(0, m2.index) });
      if (m2[1]?.startsWith('~~~') || m2[1]?.startsWith('`')) {
        result.push({ text: m2[1].replace(/~~~|`/g, ''), code: true });
      } else if (m2[2]) {
        result.push({ text: m2[2], bold: true, italic: true });
      } else if (m2[3]) {
        result.push({ text: m2[3], bold: true });
      } else if (m2[4]) {
        result.push({ text: m2[4], italic: true });
      } else if (m2[5]) {
        result.push({ text: m2[5], italic: true });
      } else if (m2[6]) {
        result.push({ text: m2[6], bold: true });
      }
      txt = txt.slice(m2.index + m2[0].length);
    }
    if (txt) result.push({ text: txt });
  }
  return result;
}

/* ─── React Component ─────────────────────────────────────────────── */

interface MarkdownBlockProps {
  text: string;
}

function safeText(value: unknown) {
  return typeof value === 'string' ? value : String(value ?? '');
}

export default function MarkdownBlock({ text }: MarkdownBlockProps) {
  const normalizedText = safeText(text);
  const nodes: MarkdownNode[] = React.useMemo(() => {
    try {
      return parseMarkdown(normalizedText);
    } catch (e) {
      return [{ type: 'paragraph', content: normalizedText }];
    }
  }, [normalizedText]);

  const renderNodes = () => {
    const fallback = <p className="markdown-paragraph">{normalizedText}</p>;
    try {
      return nodes.map((node, idx) => {
        switch (node.type) {
          case 'code':
            return <CodeBlock key={idx} lang={node.lang || ''} code={node.content} />;

          case 'heading':
            return <HeadingBlock key={idx} level={node.level!} text={node.content} />;

          case 'list':
            return <ListBlock key={idx} items={node.items!} />;

          case 'table':
            return <TableBlock key={idx} headers={node.headers} rows={node.rows!} />;

          case 'hr':
            return <hr key={idx} className="markdown-hr" />;

          case 'paragraph':
          default:
            return <ParagraphBlock key={idx} text={node.content} />;
        }
      });
    } catch (e) {
      return fallback;
    }
  };

  return <div className="markdown-body">{renderNodes()}</div>;
}

/* ─── Sub-components ───────────────────────────────────────────────── */

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = React.useState(false);

  return (
    <div
      style={{
        margin: '12px 0',
        borderRadius: '6px',
        overflow: 'hidden',
        border: '1px solid var(--line)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          background: 'var(--bg)',
          borderBottom: '1px solid var(--line)',
          fontFamily: "'Segoe UI', sans-serif",
          fontSize: '12px',
          color: 'var(--muted)',
        }}
      >
        <span>{lang || 'text'}</span>
        <button
          onClick={() => {
            navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
          style={{
            background: 'none',
            border: '1px solid var(--line)',
            borderRadius: '3px',
            color: copied ? 'var(--teal)' : 'var(--muted)',
            cursor: 'pointer',
            fontSize: '11px',
            padding: '2px 8px',
            fontFamily: 'inherit',
          }}
        >
          {copied ? 'Copiado ✓' : 'Copiar'}
        </button>
      </div>
      <SyntaxHighlighter
        language={lang || 'text'}
        style={vscDarkPlus}
        showLineNumbers={true}
        customStyle={{
          margin: 0,
          padding: '14px 16px',
          fontSize: 'var(--base-font-size, 13px)',
          lineHeight: '1.55',
          background: 'var(--bg)',
          fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', Consolas, monospace",
        }}
        codeTagProps={{ style: { background: 'none' } }}
        lineNumberStyle={{ minWidth: '3.2em', paddingRight: '1em', color: '#858585', textAlign: 'right' }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

function HeadingBlock({ level, text }: { level: number; text: string }) {
  const Tag = `h${Math.min(level, 6)}` as keyof React.JSX.IntrinsicElements;
  const spans = parseInline(text);
  return <Tag className={`markdown-heading markdown-h${level}`}>{renderSpans(spans)}</Tag>;
}

function ParagraphBlock({ text }: { text: string }) {
  const spans = parseInline(text);
  return <p className="markdown-paragraph">{renderSpans(spans)}</p>;
}

function ListBlock({ items }: { items: string[] }) {
  return (
    <ul className="markdown-list">
      {items.map((item, i) => (
        <li key={i} className="markdown-list-item">
          <InlineRenderer text={item} />
        </li>
      ))}
    </ul>
  );
}

function TableBlock({ headers, rows }: { headers?: string[]; rows: string[][] }) {
  return (
    <div className="markdown-table-wrapper">
      <table className="markdown-table">
        {headers && headers.length > 0 && (
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i} className="markdown-th">
                  <InlineRenderer text={h} />
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="markdown-td">
                  <InlineRenderer text={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InlineRenderer({ text }: { text: string }) {
  const spans = parseInline(text);
  return <>{renderSpans(spans)}</>;
}

function renderSpans(spans: InlineSpan[]) {
  return spans.map((s, i) => {
    if (s.image) {
      return (
        <img
          key={i}
          src={s.image.src}
          alt={s.image.alt}
          style={{ maxWidth: '100%', borderRadius: 4 }}
          loading="lazy"
        />
      );
    }
    if (s.link) {
      return (
        <a
          key={i}
          href={s.link.href}
          target="_blank"
          rel="noopener noreferrer"
          className="markdown-link"
        >
          {s.link.text}
        </a>
      );
    }
    let el: React.ReactNode = s.text;
    if (s.code)
      el = (
        <code key={i} className="markdown-inline-code">
          {s.text}
        </code>
      );
    else if (s.bold && s.italic)
      el = (
        <strong key={i}>
          <em>{s.text}</em>
        </strong>
      );
    else if (s.bold) el = <strong key={i}>{s.text}</strong>;
    else if (s.italic) el = <em key={i}>{s.text}</em>;
    return <React.Fragment key={i}>{el}</React.Fragment>;
  });
}
