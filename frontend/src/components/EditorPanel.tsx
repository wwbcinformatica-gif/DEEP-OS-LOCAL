import React, { useEffect } from 'react';
import type { FileTab } from '../lib/constants';
import { highlightHtml } from '../lib/syntaxHighlighter';
import MarkdownBlock from './MarkdownBlock';

interface EditorPanelProps {
  tabs: FileTab[];
  curTab: string | null;
  setCurTab: (id: string | null) => void;
  closeTab: (id: string) => void;
  setTabContent: (id: string, content: string) => void;
  saveFile: (id: string) => void;
}

const CLR_TOP = '#0a0a0a';
const CLR_TAB = '#111111';
const CLR_TAB_A = '#000000';

const CLR_LINE = '#333333';

// ─── Common editor styles ─────────────────────────────────────────────────
const editorBase: React.CSSProperties = {
  background: CLR_TAB_A,
  color: 'var(--ink)',
  fontFamily: 'inherit',
  fontSize: 13,
  lineHeight: 1.5,
  whiteSpace: 'pre',
  overflow: 'auto',
  height: '100%',
  outline: 'none',
  padding: '4px 0',
};

const lineNumStyle: React.CSSProperties = {
  display: 'inline-block',
  width: 40,
  textAlign: 'right',
  paddingRight: 12,
  color: 'var(--muted)',
  userSelect: 'none',
  flexShrink: 0,
};

export default function EditorPanel({
  tabs,
  curTab,
  setCurTab,
  closeTab,
  setTabContent,
  saveFile,
}: EditorPanelProps) {
  const tab = tabs.find((t) => t.id === curTab);
  const ext = tab?.ext || '';

  // ─── Ctrl+S ──────────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (curTab) saveFile(curTab);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [curTab, saveFile]);

  // ─── File icons based on extension ──────────────────────────────────
  const fileIcon = (e: string) => {
    if (['ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs'].includes(e)) return '📄';
    if (['py'].includes(e)) return '🐍';
    if (['json'].includes(e)) return '📋';
    if (['md'].includes(e)) return '📝';
    if (['css', 'scss', 'less'].includes(e)) return '🎨';
    if (['html', 'htm'].includes(e)) return '🌐';
    if (['xml', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'env'].includes(e)) return '⚙️';
    if (['sql'].includes(e)) return '🗄️';
    if (['sh', 'bash', 'zsh', 'bat'].includes(e)) return '▶️';
    if (
      [
        'go',
        'rs',
        'java',
        'cpp',
        'c',
        'h',
        'cs',
        'swift',
        'kt',
        'rb',
        'php',
        'pl',
        'lua',
        'dart',
        'r',
      ].includes(e)
    )
      return '📄';
    if (['vue', 'svelte'].includes(e)) return '🧩';
    return '📄';
  };

  const icon = fileIcon(ext);

  // ─── Render code with line numbers ──────────────────────────────────
  const renderCode = (code: string) => {
    // ── Markdown preview for .md files ─────────────────────────────────
    if (ext === 'md') {
      return (
        <div
          style={{
            padding: '20px 32px',
            overflow: 'auto',
            height: '100%',
            background: 'var(--bg)',
          }}
        >
          <MarkdownBlock text={code} />
        </div>
      );
    }

    const lines = code.split('\n');
    // If last line is empty, don't show extra line
    const displayLines = lines;
    const colored = highlightHtml(code, ext);

    return (
      <div
        contentEditable
        suppressContentEditableWarning
        style={{ ...editorBase, width: '100%', minHeight: '100%' }}
        onBlur={(e) => {
          if (tab) {
            let text = e.currentTarget.innerText || '';
            text = text.replace(/\r?\n/g, '\n');
            setTabContent(tab.id, text);
          }
        }}
        dangerouslySetInnerHTML={{ __html: colored }}
      />
    );
  };

  return (
    <div
      style={{ height: '100%', display: 'flex', flexDirection: 'column', background: CLR_TAB_A }}
    >
      {/* ── Tabs bar ─────────────────────────────────────────────────── */}
      {tabs.length > 0 && (
        <div
          style={{
            display: 'flex',
            background: CLR_TOP,
            borderBottom: `1px solid ${CLR_LINE}`,
            minHeight: 34,
            overflowX: 'auto',
            overflowY: 'hidden',
            flexShrink: 0,
          }}
        >
          {tabs.map((t) => {
            const active = t.id === curTab;
            return (
              <div
                key={t.id}
                onClick={() => setCurTab(t.id)}
                className={`editor-tab ${active ? 'active' : 'inactive'}`}
                style={{
                  fontSize: 12,
                  borderRight: `1px solid ${CLR_LINE}`,
                  background: active ? CLR_TAB_A : CLR_TAB,
                }}
              >
                <span style={{ fontSize: 10 }}>{fileIcon(t.ext)}</span>
                <span>{t.name}</span>
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(t.id);
                  }}
                  style={{
                    cursor: 'pointer',
                    opacity: 0.6,
                    fontSize: 14,
                    lineHeight: '14px',
                    marginLeft: 2,
                    borderRadius: 2,
                    padding: '0 3px',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--muted)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  ×
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Editor ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {tabs.length === 0 ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--muted)',
              fontSize: 13,
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <span style={{ fontSize: 32, opacity: 0.3 }}>📂</span>
            <span>Nenhum arquivo aberto</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>
              Clique em um arquivo no explorador para abri-lo
            </span>
          </div>
        ) : tab ? (
          renderCode(tab.content)
        ) : (
          <div style={{ padding: 20, color: 'var(--muted)' }}>Selecione uma aba</div>
        )}
      </div>
    </div>
  );
}
