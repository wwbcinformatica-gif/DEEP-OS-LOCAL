import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import type { ExpItem, HistItem } from '../lib/constants';
import { playSound } from '../lib/soundFx';

interface ExplorerPanelProps {
  expRoot: string;
  setExpRoot: (v: string) => void;
  expTree: ExpItem[];
  setExpTree: (v: ExpItem[]) => void;
  expPath: string[];
  toggleDir: (path: string) => void;
  openFile: (item: ExpItem) => void;
  histItens: HistItem[];
  loadHist: (id: number) => void;
  delHist: (id: number) => void;
  histSearch: string;
  setHistSearch: (v: string) => void;
  apiBase: string;
  currentDir: string;
  goUpDir: () => void;
  loadDir: (path: string, rootOverride?: string) => void;
  onInjectChat?: (text: string) => void;
  onWorkspaceChange?: (path: string) => Promise<boolean>;
}

interface CtxMenu {
  x: number;
  y: number;
  item: ExpItem;
}

interface CtxOpt {
  key: string;
  label?: string;
  sep?: boolean;
  danger?: boolean;
}

const indentLevel = (path: string, currentDir: string): number => {
  const p = path.split('/').filter(Boolean).length;
  const c = currentDir ? currentDir.split('/').filter(Boolean).length : 0;
  return Math.max(0, p - c - 1);
};

const FolderClosed = () => (
  <svg viewBox="0 0 18 18" fill="none" width="14" height="14" style={{ display: 'block' }}>
    <line x1="4" y1="2.5" x2="13" y2="2.5" stroke="#52525b" strokeWidth="2" strokeLinecap="round" />
    <line x1="4" y1="5" x2="11" y2="5" stroke="#52525b" strokeWidth="2" strokeLinecap="round" />
    <path
      d="M2 8v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"
      stroke="var(--accent)"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <path d="M2 8h14" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
    <path
      d="M11 7V5.5a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1V7"
      stroke="var(--accent)"
      strokeWidth="2"
      strokeLinejoin="round"
    />
  </svg>
);

const FolderOpen = () => (
  <svg viewBox="0 0 18 18" fill="none" width="14" height="14" style={{ display: 'block' }}>
    <line x1="3" y1="1.5" x2="14" y2="1.5" stroke="#52525b" strokeWidth="2" strokeLinecap="round" />
    <line x1="3" y1="4" x2="12" y2="4" stroke="#52525b" strokeWidth="2" strokeLinecap="round" />
    <line x1="3" y1="6.5" x2="10" y2="6.5" stroke="#52525b" strokeWidth="2" strokeLinecap="round" />
    <path
      d="M2.5 8.5L4 14h10l1.5-5.5"
      stroke="var(--accent)"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <path d="M4 14V8.5h10V8.5" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
    <path
      d="M11 7.5V6a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1v1.5"
      stroke="var(--accent)"
      strokeWidth="2"
      strokeLinejoin="round"
    />
  </svg>
);

const FileIcon = () => (
  <svg viewBox="0 0 18 18" fill="none" width="14" height="14" style={{ display: 'block' }}>
    <path
      d="M4 2h6l4 4v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"
      stroke="#a1a1aa"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <path d="M10 2v3a1 1 0 0 0 1 1h3" stroke="#a1a1aa" strokeWidth="2" strokeLinejoin="round" />
    <line
      x1="5.5"
      y1="8.5"
      x2="11.5"
      y2="8.5"
      stroke="#52525b"
      strokeWidth="2"
      strokeLinecap="round"
    />
    <line x1="5.5" y1="11" x2="10" y2="11" stroke="#52525b" strokeWidth="2" strokeLinecap="round" />
    <line
      x1="5.5"
      y1="13.5"
      x2="8"
      y2="13.5"
      stroke="#52525b"
      strokeWidth="2"
      strokeLinecap="round"
    />
  </svg>
);

const ctxOpts = (item: ExpItem): CtxOpt[] => {
  if (item.type === 'background')
    return [
      { key: 'newfile', label: 'Novo Arquivo' },
      { key: 'newfolder', label: 'Nova Pasta' },
    ];
  const base: CtxOpt[] = [
    { key: 'reveal', label: 'Revelar no Explorador de Arquivos' },
    { key: 'sep1', sep: true },
    { key: 'copy', label: 'Copiar Caminho' },
    { key: 'copyrel', label: 'Copiar Caminho Relativo' },
    { key: 'sep2', sep: true },
  ];
  if (item.type === 'directory') {
    base.push({ key: 'newfile', label: 'Novo Arquivo' });
    base.push({ key: 'newfolder', label: 'Nova Pasta' });
    base.push({ key: 'sep3', sep: true });
  }
  base.push({ key: 'rename', label: 'Renomear (F2)' });
  base.push({ key: 'delete', label: 'Excluir (Del)', danger: true });
  return base;
};

const s: Record<string, React.CSSProperties> = {
  ctxOverlay: { position: 'fixed', inset: 0, zIndex: 9998 },
  ctxMenu: {
    position: 'fixed',
    zIndex: 9999,
    background: 'var(--bg)',
    backdropFilter: 'blur(12px)',
    border: '1px solid var(--line-strong)',
    borderRadius: 8,
    padding: '4px 0',
    minWidth: 190,
    boxShadow: '0 12px 32px var(--line)',
    fontSize: 12,
    fontFamily: 'inherit',
    overflow: 'hidden',
  },
  ctxItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '7px 14px',
    cursor: 'pointer',
    color: 'var(--ink)',
    fontFamily: 'var(--font-ui)',
    fontSize: 14,
    borderRadius: 4,
    lineHeight: 1.5,
    letterSpacing: '0.02em',
    transition: 'all 0.15s ease',
  },
  ctxSep: { height: 1, background: 'var(--bg-2)', margin: '3px 8px' },
  toast: {
    position: 'fixed',
    top: 20,
    right: 20,
    zIndex: 10000,
    background: 'var(--bg)',
    border: '1px solid var(--accent)',
    borderRadius: 8,
    padding: '10px 18px',
    fontSize: 12,
    color: 'var(--ink)',
    boxShadow: '0 8px 24px var(--line)',
    fontFamily: 'inherit',
    animation: 'toastIn 0.3s ease',
  },
  inlineInput: {
    flex: 1,
    background: 'var(--bg)',
    border: '1px solid var(--accent)',
    color: 'var(--ink)',
    padding: '1px 6px',
    fontSize: 12,
    outline: 'none',
    borderRadius: 3,
    fontFamily: 'inherit',
    height: 20,
  },
};

const ExplorerPanel: React.FC<ExplorerPanelProps> = ({
  expRoot,
  setExpRoot,
  expTree,
  setExpTree,
  expPath,
  toggleDir,
  openFile,
  histItens,
  loadHist,
  delHist,
  histSearch,
  setHistSearch,
  apiBase,
  currentDir,
  goUpDir,
  loadDir,
  onInjectChat,
  onWorkspaceChange,
}) => {
  const [rootInput, setRootInput] = useState('');
  const [showHist, setShowHist] = useState(false);
  const [ctx, setCtx] = useState<CtxMenu | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState('');
  const [creating, setCreating] = useState<{
    type: 'file' | 'directory';
    parentPath?: string;
  } | null>(null);
  const [creatingVal, setCreatingVal] = useState('');
  const [toast, setToast] = useState('');
  const [focusedPath, setFocusedPath] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const renameRef = useRef<HTMLInputElement>(null);
  const creatingRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renaming && renameRef.current) renameRef.current.focus();
  }, [renaming]);
  useEffect(() => {
    if (creating && creatingRef.current) creatingRef.current.focus();
  }, [creating]);

  useEffect(() => {
    const close = () => setCtx(null);
    window.addEventListener('scroll', close, true);
    return () => window.removeEventListener('scroll', close, true);
  }, []);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2500);
  }, []);

  const filtered = useMemo(
    () => histItens.filter((h) => h.question.toLowerCase().includes(histSearch.toLowerCase())),
    [histItens, histSearch],
  );

  const handleRoot = async () => {
    const path = rootInput.trim();
    if (!path) return;
    setExpRoot(path);
    loadDir('', path);
    if (onWorkspaceChange) {
      onWorkspaceChange(path)
        .then((ok) => {
          if (!ok) showToast('Workspace não atualizado, mas diretório carregado.');
        })
        .catch(() => {});
    }
  };

  const fetchDir = async (root: string) => {
    try {
      const p = new URLSearchParams();
      p.set('path', '');
      p.set('root', root);
      const r = await fetch(`${apiBase}/explorer?${p}`);
      if (r.ok) {
        const d = await r.json();
        if (d.type === 'directory') setExpTree(d.items || []);
      }
    } catch {}
  };

  const execDelete = (path: string) => {
    fetch(`${apiBase}/api/files/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, root: expRoot }),
    })
      .then((r) => {
        if (r.ok) {
          loadDir(currentDir);
          showToast('\uD83D\uDDD1\uFE0F Exclu\u00EDdo');
        }
      })
      .catch(() => {});
  };

  const handleCtxAction = (key: string) => {
    if (!ctx) return;
    const { item } = ctx;
    // Normaliza para barras front (forward slash) — compativel com terminal, URLs e imports
    const rootClean = expRoot.replace(/\\/g, '/').replace(/\/+$/, '');
    const itemPath = item.path.replace(/\\/g, '/');
    const fullPath = `${rootClean}/${itemPath}`;
    const relPath = itemPath;
    setCtx(null);

    if (key === 'newfile' || key === 'newfolder') {
      const parentPath = item.type === 'directory' ? item.path : undefined;
      setCreating({ type: key === 'newfolder' ? 'directory' : 'file', parentPath });
      setCreatingVal('');
      return;
    }
    if (key === 'copy') {
      navigator.clipboard
        .writeText(fullPath)
        .then(() => showToast('\uD83D\uDCCB Caminho copiado com sucesso!'))
        .catch(() => {});
      return;
    }
    if (key === 'copyrel') {
      navigator.clipboard
        .writeText(relPath)
        .then(() => showToast('\uD83D\uDCCB Caminho relativo copiado!'))
        .catch(() => {});
      return;
    }
    if (key === 'reveal') {
      fetch(`${apiBase}/api/files/reveal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path, root: expRoot }),
      }).catch(() => {});
      return;
    }
    if (key === 'rename') {
      setRenaming(item.path);
      setRenameVal(item.name);
      return;
    }
    if (key === 'delete') {
      execDelete(item.path);
    }
  };

  const submitCreate = async () => {
    if (!creating || !creatingVal.trim()) return;
    const parent = creating.parentPath ? creating.parentPath : currentDir || '';
    const full = parent ? `${parent}/${creatingVal.trim()}` : creatingVal.trim();
    const t = creating.type;
    const anchorPath = creating.parentPath;
    setCreating(null);
    setCreatingVal('');
    try {
      const r = await fetch(`${apiBase}/api/files/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: full, root: expRoot, type: t }),
      });
      if (r.ok) loadDir(currentDir);
    } catch {}
  };

  const cancelCreate = () => {
    setCreating(null);
    setCreatingVal('');
  };

  const submitRename = async (oldPath: string) => {
    setRenaming(null);
    if (!renameVal.trim()) return;
    try {
      const r = await fetch(`${apiBase}/api/files/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: oldPath, new_name: renameVal.trim(), root: expRoot }),
      });
      if (r.ok) loadDir(currentDir);
    } catch {}
  };

  const cancelRename = () => setRenaming(null);

  const startCreate = (type: 'file' | 'directory') => {
    setCreating({ type });
    setCreatingVal('');
  };

  const creatingRow =
    creating &&
    (() => {
      const depth = creating.parentPath ? indentLevel(creating.parentPath, currentDir) + 1 : 0;
      return (
        <div
          key="__creating__"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '2px',
            padding: '5px 8px',
            paddingLeft: `${12 + depth * 16}px`,
            fontSize: '14px',
            fontWeight: 500,
            fontFamily: 'inherit',
            borderRadius: '3px',
            background: 'rgba(255,122,26,0.05)',
          }}
        >
          <span
            style={{
              flexShrink: 0,
              width: 14,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg
              viewBox="0 0 10 10"
              fill="none"
              width="10"
              height="10"
              style={{ display: 'block' }}
            >
              <path
                d="M3 1.5L7 5L3 8.5"
                stroke="var(--accent)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span
            style={{
              flexShrink: 0,
              width: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {creating.type === 'directory' ? <FolderClosed /> : <FileIcon />}
          </span>
          <input
            ref={creatingRef}
            value={creatingVal}
            onChange={(e) => setCreatingVal(e.target.value)}
            placeholder={creating.type === 'directory' ? 'nome-da-pasta' : 'nome.ext'}
            onBlur={cancelCreate}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitCreate();
              if (e.key === 'Escape') cancelCreate();
            }}
            onClick={(e) => e.stopPropagation()}
            style={s.inlineInput}
            autoComplete="chrome-off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
          />
        </div>
      );
    })();

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 0,
        fontFamily: 'inherit',
        position: 'relative',
      }}
    >
      <div className="panel-header">
        <span className="panel-title" style={{ color: 'var(--accent)' }}>
          EXPLORER
        </span>
        <div style={{ display: 'flex', gap: '4px' }}>
          <button className="btn" onClick={() => startCreate('file')} title="novo arquivo">
            +
          </button>
          <button className="btn" onClick={() => startCreate('directory')} title="nova pasta">
            {'\u25B6'}
          </button>
          <button
            className="btn"
            onClick={goUpDir}
            title="subir"
            style={currentDir ? {} : { opacity: 0.3, cursor: 'default' }}
            disabled={!currentDir}
          >
            {'\u21A9'}
          </button>
          <button className="btn" onClick={() => fetchDir(expRoot)} title="refresh">
            {'\u21BA'}
          </button>
        </div>
      </div>
      {currentDir && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            padding: '3px 8px',
            borderBottom: '1px solid var(--line)',
            fontSize: '10px',
            color: 'var(--muted)',
            fontFamily: 'inherit',
            gap: '1px',
            cursor: 'default',
            overflow: 'hidden',
            maxHeight: 28,
          }}
        >
          {(() => {
            const parts = currentDir.replace(/\\/g, '/').split('/').filter(Boolean);
            return [
              <span
                key="root"
                onClick={() => {
                  setRootInput('');
                  loadDir('', expRoot);
                }}
                style={{
                  cursor: 'pointer',
                  color: 'var(--accent)',
                  fontWeight: 600,
                  padding: '0 2px',
                  flexShrink: 0,
                }}
                title="raiz"
              >
                ~
              </span>,
              ...parts.map((p, i) => {
                if (i === parts.length - 1)
                  return (
                    <span
                      key={i}
                      style={{
                        color: 'var(--ink)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: 120,
                      }}
                    >
                      {p}
                    </span>
                  );
                const pathSoFar = parts.slice(0, i + 1).join('/');
                return (
                  <span
                    key={i}
                    style={{ display: 'flex', alignItems: 'center', gap: '1px', minWidth: 0 }}
                  >
                    <span style={{ color: 'var(--quiet)' }}>/</span>
                    <span
                      onClick={() => {
                        setRootInput('');
                        loadDir(pathSoFar);
                      }}
                      style={{
                        cursor: 'pointer',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: 80,
                        padding: '0 2px',
                      }}
                      title={pathSoFar}
                    >
                      {p}
                    </span>
                  </span>
                );
              }),
              <span key="end" style={{ color: 'var(--quiet)' }}>
                /
              </span>,
            ];
          })()}
        </div>
      )}
      <div
        style={{
          display: 'flex',
          gap: '4px',
          padding: '6px 8px',
          borderBottom: '1px solid var(--line)',
        }}
      >
        <input
          className="input"
          value={rootInput}
          onChange={(e) => setRootInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRoot()}
          placeholder="caminho..."
          style={{ flex: 1, fontSize: '11px' }}
        />
        <button className="btn btn-accent" onClick={handleRoot}>
          ir
        </button>
        <button
          className="btn"
          onClick={async () => {
            try {
              const r = await fetch(`${apiBase}/api/explorer/pick-folder`);
              if (r.ok) {
                const data = await r.json();
                if (data.status === 'ok' && data.path) {
                  const normalizedPath = data.path.replace(/\//g, '\\');
                  setRootInput(normalizedPath);
                  setExpRoot(normalizedPath);
                  loadDir('', normalizedPath);
                  if (onWorkspaceChange) {
                    onWorkspaceChange(normalizedPath).catch(() => {});
                  }
                }
              } else {
                showToast('Não foi possível abrir o seletor nativo de pastas.');
              }
            } catch (e) {
              showToast('Erro ao comunicar com o backend para selecionar pasta.');
            }
          }}
          title="Abrir Pasta"
        >
          📂
        </button>
      </div>
      <div
        tabIndex={0}
        style={{ flex: 1, overflow: 'auto', padding: '2px 0', minHeight: 0, outline: 'none' }}
        onContextMenu={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!ctx && expRoot) {
            setCtx({
              x: e.clientX,
              y: e.clientY,
              item: { name: '', path: currentDir || '', type: 'background' } as any,
            });
          }
        }}
        onKeyDown={(e) => {
          if (!focusedPath) return;
          const item = expTree.find((it) => it.path === focusedPath);
          if (!item) return;
          if (e.key === 'F2') {
            e.preventDefault();
            setRenaming(item.path);
            setRenameVal(item.name);
          } else if (e.key === 'Delete') {
            e.preventDefault();
            if (confirmDelete === item.path) {
              setConfirmDelete(null);
              execDelete(item.path);
            } else {
              setConfirmDelete(item.path);
              showToast('Pressione Delete novamente para confirmar a exclus\u00E3o');
              setTimeout(() => setConfirmDelete((c) => (c === item.path ? null : c)), 3000);
            }
          }
        }}
      >
        {expTree.length === 0 && !creating && (
          <div
            style={{
              padding: '12px',
              textAlign: 'center',
              fontSize: '11px',
              color: 'var(--quiet)',
              fontFamily: 'inherit',
            }}
          >
            abra uma pasta
          </div>
        )}
        {currentDir && expTree.length > 0 && (
          <div
            onClick={goUpDir}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '5px 8px',
              paddingLeft: '12px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
              color: 'var(--muted)',
              borderRadius: '3px',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-2)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <span
              style={{ fontSize: '14px', flexShrink: 0, color: 'var(--accent)', fontWeight: 500 }}
            >
              {'\u21A9'}
            </span>
            <span style={{ fontStyle: 'italic' }}>.. (voltar)</span>
          </div>
        )}
        {expTree.flatMap((item) => {
          const isDir = item.type === 'directory';
          const isRenaming = renaming === item.path;
          const insertCreating = creating && creating.parentPath === item.path;
          const depth = indentLevel(item.path, currentDir);
          const row = (
            <div
              key={item.path}
              onClick={() => {
                setFocusedPath(item.path);
                if (!isRenaming) {
                  if (isDir) {
                    playSound('click_folder_open');
                    toggleDir(item.path);
                  } else {
                    playSound('click_file');
                    openFile(item);
                  }
                }
              }}
              onDoubleClick={() => {
                if (!isRenaming && !isDir && onInjectChat) {
                  const rootClean = expRoot.replace(/\\/g, '/').replace(/\/+$/, '');
                  const itemPath = item.path.replace(/\\/g, '/');
                  onInjectChat(`An\u00E1lise do arquivo: ${rootClean}/${itemPath}`);
                }
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setCtx({ x: e.clientX, y: e.clientY, item });
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 8px',
                paddingLeft: `${12 + depth * 16}px`,
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 500,
                fontFamily: 'var(--font-ui)',
                color: 'var(--ink-2)',
                borderRadius: '4px',
                lineHeight: 1.5,
                letterSpacing: '0.01em',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-2)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              title={item.path}
            >
              {isDir ? (
                <span
                  style={{
                    flexShrink: 0,
                    width: 14,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <svg
                    viewBox="0 0 10 10"
                    fill="none"
                    width="10"
                    height="10"
                    style={{ display: 'block' }}
                  >
                    <path
                      d="M3 1.5L7 5L3 8.5"
                      stroke="var(--accent)"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              ) : (
                <span style={{ flexShrink: 0, width: 14 }} />
              )}
              <span
                style={{
                  flexShrink: 0,
                  width: 16,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {isDir ? <FolderClosed /> : <FileIcon />}
              </span>
              {isRenaming ? (
                <input
                  ref={renameRef}
                  value={renameVal}
                  onChange={(e) => setRenameVal(e.target.value)}
                  onBlur={cancelRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') submitRename(item.path);
                    if (e.key === 'Escape') cancelRename();
                  }}
                  onClick={(e) => e.stopPropagation()}
                  style={s.inlineInput}
                  autoComplete="chrome-off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                />
              ) : (
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontFamily: 'inherit',
                  }}
                >
                  {item.name}
                </span>
              )}
            </div>
          );
          return insertCreating ? [row, creatingRow!] : [row];
        })}

        {/* Creating at root/currentDir level (no parentPath) */}
        {creating && !creating.parentPath && creatingRow}
      </div>

      {/* Context Menu */}
      {ctx && (
        <>
          <div
            style={s.ctxOverlay}
            onClick={() => setCtx(null)}
            onContextMenu={(e) => e.preventDefault()}
          />
          <div
            style={{
              ...s.ctxMenu,
              left: Math.min(ctx.x, window.innerWidth - 200),
              top: Math.min(ctx.y, window.innerHeight - 160),
            }}
          >
            {ctxOpts(ctx.item).map((opt) => {
              if (opt.sep) return <div key={opt.key} style={s.ctxSep} />;
              return (
                <div
                  key={opt.key}
                  onClick={() => handleCtxAction(opt.key)}
                  style={{ ...s.ctxItem, color: opt.danger ? 'var(--red)' : 'var(--ink)' }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = 'var(--accent-soft)')
                  }
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  {opt.label}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Toast */}
      {toast && <div style={s.toast}>{toast}</div>}

      <div style={{ borderTop: '1px solid var(--line)', flexShrink: 0 }}>
        <div
          className="panel-header"
          onClick={() => setShowHist(!showHist)}
          style={{ cursor: 'pointer' }}
        >
          <span className="panel-title" style={{ color: 'var(--accent)' }}>
            {showHist ? '\u25BE' : '\u25B8'} HIST\u00D3RICO
          </span>
        </div>
        {showHist && (
          <>
            <div style={{ padding: '4px 8px' }}>
              <input
                className="input"
                value={histSearch}
                onChange={(e) => setHistSearch(e.target.value)}
                placeholder="buscar..."
                style={{ width: '100%', fontSize: '11px' }}
                autoComplete="chrome-off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
              />
            </div>
            <div style={{ maxHeight: 150, overflow: 'auto' }}>
              {filtered.slice(0, 30).map((h) => (
                <div
                  key={h.id}
                  onClick={() => loadHist(h.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 8px',
                    cursor: 'pointer',
                    fontSize: '13px',
                    fontFamily: 'var(--font-ui)',
                    color: 'var(--ink-2)',
                    borderRadius: '4px',
                    lineHeight: 1.5,
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-2)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <span
                    style={{
                      flex: 1,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      fontFamily: 'inherit',
                    }}
                  >
                    {h.question}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      delHist(h.id);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--muted)',
                      cursor: 'pointer',
                      fontSize: '10px',
                      padding: '1px',
                      flexShrink: 0,
                      fontFamily: 'inherit',
                    }}
                  >
                    x
                  </button>
                </div>
              ))}
              {filtered.length === 0 && (
                <div
                  style={{
                    padding: '8px',
                    fontSize: '11px',
                    color: 'var(--quiet)',
                    textAlign: 'center',
                    fontFamily: 'inherit',
                  }}
                >
                  vazio
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ExplorerPanel;
