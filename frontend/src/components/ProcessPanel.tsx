import React, { useRef, useEffect, useState } from 'react';
import type { TLog } from '../lib/constants';

interface ProcessPanelProps {
  loading: boolean;
  stream: string;
  thinking: string;
  thinkingLog: string[];
  thinkOn: boolean;
  showThoughts: boolean;
  toolLogs: TLog[];
  model?: string;
  prov?: string;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function ProcessPanel({
  loading,
  stream,
  thinking,
  thinkingLog,
  thinkOn,
  showThoughts,
  toolLogs,
  model,
  prov,
}: ProcessPanelProps) {
  const logEndRef = useRef<HTMLDivElement>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    context: true,
    lsp: true,
    todo: true,
  });
  const [expandedLogs, setExpandedLogs] = useState<Record<number, boolean>>({});
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef<number>(0);
  const lastThinkingRef = useRef('');

  // Timer real enquanto está processando
  useEffect(() => {
    if (loading) {
      if (!startTimeRef.current) startTimeRef.current = Date.now();
      const interval = setInterval(() => {
        setElapsed(Date.now() - startTimeRef.current);
      }, 100);
      return () => clearInterval(interval);
    } else {
      startTimeRef.current = 0;
      setElapsed(0);
    }
  }, [loading]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [toolLogs, stream, thinking]);

  useEffect(() => {
    if (thinking) lastThinkingRef.current = thinking;
  }, [thinking]);

  const toggle = (key: string) =>
    setOpenSections((p) => ({ ...p, [key]: !p[key] }));

  const toggleLog = (idx: number) =>
    setExpandedLogs((p) => ({ ...p, [idx]: !p[idx] }));

  const runningTools = toolLogs.filter((l) => l.status === 'running');
  const totalTokens = stream.length;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#000000',
        fontFamily: 'var(--font-mono), "Cascadia Code", "Fira Code", Consolas, monospace',
        fontSize: 13,
        overflowX: 'auto',
        overflowY: 'auto',
        resize: 'horizontal',
        cursor: 'ew-resize',
        minWidth: 200,
        maxWidth: '80vw',
        width: 'auto',
        flexGrow: 0,
        flexShrink: 1,
        flexBasis: 'auto',
        color: '#cccccc',
        lineHeight: 1.5,
        userSelect: 'text',
        wordBreak: 'break-word',
      }}
    >
      {/* Header com tempo real */}
      <div style={{
        padding: '8px 14px',
        borderBottom: '1px solid #333333',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, color: '#808080' }}>projeto</span>
        <span style={{ fontSize: 11, color: '#cccccc' }}>{window.location.origin}</span>
      </div>

      {/* Context */}
      <Section title="Context" open={openSections.context} onToggle={() => toggle('context')}>
        <div style={{ padding: '2px 0', fontSize: 12, color: '#808080' }}>
          <div>{totalTokens.toLocaleString()} tokens</div>
          <div>{stream ? '~' : '0'}% used</div>
          <div>$0.00 spent</div>
        </div>
        {/* Thinking do modelo */}
        {thinking && (
          <div style={{
            marginTop: 8,
            padding: '8px 10px',
            background: '#0a0f1a',
            borderRadius: 6,
            border: '1px solid #1a2a4a',
            fontSize: 11,
            lineHeight: 1.5,
          }}>
            <div style={{ fontSize: 10, color: '#569cd6', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Thinking
            </div>
            <div style={{ color: '#808080', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflow: 'auto' }}>
              {thinking}
            </div>
          </div>
        )}
      </Section>

      {/* LSP */}
      <Section title="LSP" open={openSections.lsp} onToggle={() => toggle('lsp')}>
        <div style={{ padding: '2px 0', fontSize: 12, color: '#808080' }}>
          LSPs are disabled
        </div>
      </Section>

      {/* Todo — processo real */}
      <Section title="Todo" open={openSections.todo} onToggle={() => toggle('todo')} count={toolLogs.length}>
        <div style={{ padding: '2px 0' }}>
          {toolLogs.map((log, i) => {
            const isRunning = log.status === 'running';
            const isDone = log.status === 'done';
            const isError = log.status === 'error';
            const isExpanded = expandedLogs[i] || false;

            const params = log.params || {};
            const command = params.command || params.cmd || '';
            const filePath = params.path || params.file || '';
            const displayCmd = command || filePath || '';

            // Resultado
            let resultStr = '';
            if (log.result) {
              if (typeof log.result === 'object') {
                resultStr = log.result.stdout || log.result.error || JSON.stringify(log.result, null, 2);
              } else {
                resultStr = String(log.result);
              }
            }

            return (
              <div key={log.id || i} style={{ marginBottom: 6 }}>
                {/* Timing/Thought (Acima do check) */}
                {log.duration !== undefined ? (
                  <div style={{ fontSize: 10, color: '#e8a644', marginBottom: 2, paddingLeft: 2 }}>
                    + Thought: {formatDuration(log.duration)}
                  </div>
                ) : isRunning ? (
                  <div style={{ fontSize: 10, color: '#e8a644', marginBottom: 2, paddingLeft: 2, animation: 'blink 1s infinite' }}>
                    + Thought: {formatDuration(elapsed)}
                  </div>
                ) : null}

                {/* Linha principal — clicável para expandir */}
                <div
                  onClick={() => !isRunning && toggleLog(i)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 6,
                    cursor: isRunning ? 'default' : 'pointer',
                    padding: '3px 0',
                    borderRadius: 3,
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => !isRunning && (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  {/* Status */}
                  <span style={{
                    color: isRunning ? '#e8a644' : isDone ? '#4ec9b0' : '#f44747',
                    fontWeight: 700,
                    fontSize: 12,
                    lineHeight: '18px',
                    flexShrink: 0,
                    width: 16,
                    textAlign: 'center',
                  }}>
                    {isDone ? '\u2713' : isError ? '\u2717' : '\u25CB'}
                  </span>

                  {/* Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{
                        color: isRunning ? '#e8a644' : '#cccccc',
                        fontSize: 12,
                        fontWeight: 600,
                      }}>
                        {log.tool}
                      </span>
                    </div>

                    {/* Comando */}
                    {displayCmd && (
                      <div style={{
                        fontSize: 11,
                        color: '#808080',
                        marginTop: 2,
                        wordBreak: 'break-word',
                        whiteSpace: 'normal',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {displayCmd}
                      </div>
                    )}
                  </div>

                  {/* Seta de expand */}
                  {!isRunning && resultStr && (
                    <span style={{ color: '#606060', fontSize: 10, flexShrink: 0, marginTop: 2 }}>
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </span>
                  )}
                </div>

                {/* Output expandível */}
                {!isRunning && isExpanded && resultStr && (
                  <div style={{
                    marginLeft: 22,
                    marginTop: 4,
                    padding: '6px 8px',
                    background: '#0a0a0a',
                    borderRadius: 4,
                    border: '1px solid #2a2a2a',
                    fontSize: 11,
                    color: '#808080',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    maxHeight: 200,
                    overflow: 'auto',
                    lineHeight: 1.4,
                  }}>
                    {resultStr}
                  </div>
                )}

                {/* Resultado inline quando colapsado */}
                {!isRunning && !isExpanded && resultStr && (
                  <div style={{
                    marginLeft: 22,
                    fontSize: 10,
                    color: isError ? '#f44747' : '#606060',
                    maxHeight: 16,
                    overflow: 'hidden',
                    whiteSpace: 'nowrap',
                    textOverflow: 'ellipsis',
                  }}>
                    {resultStr.split('\n')[0].slice(0, 60)}
                  </div>
                )}
              </div>
            );
          })}

          {/* Thinking em tempo real — log acumulado */}
          {showThoughts && thinkingLog.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {thinkingLog.map((entry, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 6,
                  padding: '2px 0',
                  opacity: i < thinkingLog.length - 1 ? 0.5 : 1,
                }}>
                  <span style={{ color: '#569cd6', fontSize: 11, flexShrink: 0, width: 16, textAlign: 'center' }}>
                    {"\u25B6"}
                  </span>
                  <span style={{ color: '#569cd6', fontSize: 11, fontStyle: 'italic' }}>
                    {entry}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Streaming em tempo real */}
          {loading && stream && (
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 6,
              padding: '3px 0',
              marginTop: 4,
            }}>
              <span style={{ color: '#e8a644', fontSize: 12, flexShrink: 0, width: 16, textAlign: 'center', animation: 'blink 1s infinite' }}>
                {"\u25CF"}
              </span>
              <span style={{ color: '#808080', fontSize: 11 }}>
                Gerando... ({stream.length} chars)
              </span>
            </div>
          )}

          {/* Loading sem nada */}
          {loading && !stream && !thinkOn && runningTools.length === 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
              <span style={{ color: '#e8a644', fontSize: 12, animation: 'blink 1s infinite' }}>{"\u25CF"}</span>
              <span style={{ color: '#808080', fontSize: 12 }}>Processando...</span>
            </div>
          )}

          {/* Aguardando */}
          {!loading && toolLogs.length === 0 && (
            <div style={{ fontSize: 12, color: '#606060', fontStyle: 'italic', padding: '2px 0' }}>
              Aguardando...
            </div>
          )}
        </div>
      </Section>

      <div ref={logEndRef} />
    </div>
  );
}

function Section({
  title,
  open,
  onToggle,
  count,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '6px 14px',
          cursor: 'pointer',
          userSelect: 'none',
          borderBottom: '1px solid #333333',
        }}
      >
        <span
          style={{
            fontSize: 10,
            color: '#808080',
            transition: 'transform 0.15s',
            transform: open ? 'rotate(0deg)' : 'rotate(-90deg)',
            display: 'inline-block',
            width: 10,
          }}
        >
          {"\u25BC"}
        </span>
        <span style={{ fontWeight: 600, fontSize: 12, color: '#cccccc' }}>{title}</span>
        {count !== undefined && count > 0 && (
          <span style={{ fontSize: 10, color: '#606060', marginLeft: 4 }}>({count})</span>
        )}
      </div>
      {open && (
        <div style={{ padding: '4px 14px 8px 24px' }}>{children}</div>
      )}
    </div>
  );
}
