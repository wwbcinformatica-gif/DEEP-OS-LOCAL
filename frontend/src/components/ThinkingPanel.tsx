import React, { useState, useEffect, useRef } from 'react';
import type { TLog } from '../lib/constants';

interface ThinkingPanelProps {
  loading: boolean;
  thinkOn: boolean;
  thinking: string;
  thinkOpen: boolean;
  setThinkOpen: (v: boolean) => void;
  toolLogs: TLog[];
  onStop?: () => void;
}

const TIMEOUT_MS = 20_000;
const CHECK_INTERVAL_MS = 1_000;

const TOOL_STATUS: Record<string, { icon: string; label: string }> = {
  bash: { icon: '\u2699\uFE0F', label: 'Executando comando...' },
  write: { icon: '\u270D\uFE0F', label: 'Escrevendo arquivo...' },
  read: { icon: '\uD83D\uDCD6', label: 'Lendo arquivo...' },
  web_search: { icon: '\uD83C\uDF10', label: 'Buscando na web...' },
  web_fetch: { icon: '\uD83D\uDCE1', label: 'Baixando pagina...' },
  execute_python: { icon: '\uD83D\uDC0D', label: 'Executando Python...' },
  file_edit: { icon: '\u270F\uFE0F', label: 'Editando arquivo...' },
  search: { icon: '\uD83D\uDD0D', label: 'Buscando no codigo...' },
  grep: { icon: '\uD83D\uDD0D', label: 'Buscando no codigo...' },
  delete: { icon: '\uD83D\uDDD1\uFE0F', label: 'Removendo arquivo...' },
  create_directory: { icon: '\uD83D\uDCC1', label: 'Criando pasta...' },
  rename: { icon: '\uD83D\uDD04', label: 'Renomeando...' },
  monitor_dashboard: { icon: '\uD83D\uDCCA', label: 'Coletando metricas...' },
  tool_search: { icon: '\uD83D\uDD0E', label: 'Buscando ferramenta...' },
  fork_subagent: { icon: '\uD83E\uDDE0', label: 'Delegando subagente...' },
  cron_create: { icon: '\u23F0', label: 'Agendando tarefa...' },
  install_package: { icon: '\uD83D\uDCE6', label: 'Instalando pacote...' },
  glob: { icon: '\uD83D\uDCC1', label: 'Localizando arquivos...' },
  explorer: { icon: '\uD83D\uDCC2', label: 'Navegando diretorios...' },
  explorer_read: { icon: '\uD83D\uDCDD', label: 'Lendo arquivo...' },
  memory_write: { icon: '\uD83D\uDCDD', label: 'Salvando na memoria...' },
  memory_read: { icon: '\uD83D\uDCDA', label: 'Consultando memoria...' },
  memory_list: { icon: '\uD83D\uDCCA', label: 'Listando memorias...' },
  memory_delete: { icon: '\uD83D\uDDD1\uFE0F', label: 'Limpando memoria...' },
  task_create: { icon: '\uD83D\uDCCB', label: 'Criando tarefa...' },
  task_get: { icon: '\uD83D\uDCC4', label: 'Consultando tarefa...' },
  task_update: { icon: '\u270F\uFE0F', label: 'Atualizando tarefa...' },
  task_list: { icon: '\uD83D\uDCCA', label: 'Listando tarefas...' },
  task_stop: { icon: '\u23F9\uFE0F', label: 'Parando tarefa...' },
};

function getStatus(running: TLog | undefined, thinking: boolean) {
  if (thinking) return { icon: 'thinking_dots', label: 'Pensando...' };
  if (running) {
    const s = TOOL_STATUS[running.tool];
    if (s) return s;
    return { icon: '\u2699\uFE0F', label: `Executando ${running.tool}...` };
  }
  return { icon: '\u23F3', label: 'Processando...' };
}

function ThinkingDots() {
  return (
    <div style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
      {[0, 1, 2].map((i) => (
        <div
          key={`orange-${i}`}
          style={{
            width: '4px',
            height: '4px',
            borderRadius: '50%',
            background: '#60a5fa',
            animation: 'dotPulse 1.4s ease-in-out infinite',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </div>
  );
}

export default function ThinkingPanel({
  loading,
  thinkOn,
  thinking,
  thinkOpen,
  setThinkOpen,
  toolLogs,
  onStop,
}: ThinkingPanelProps) {
  const [stuck, setStuck] = useState(false);
  const lastActivityRef = useRef(Date.now());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Atualiza o timestamp sempre que houver atividade nos logs ou thinking
  useEffect(() => {
    if (loading) {
      lastActivityRef.current = Date.now();
      setStuck(false);
    }
  }, [toolLogs, thinking, loading]);

  // Watchdog: verifica a cada 1s se passou 20s sem atividade
  useEffect(() => {
    if (!loading) {
      setStuck(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - lastActivityRef.current;
      if (elapsed >= TIMEOUT_MS) {
        setStuck(true);
      }
    }, CHECK_INTERVAL_MS);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [loading]);

  if (!loading) return null;

  const safeToolLogs = toolLogs ?? [];
  const safeThinking = thinking ?? '';
  const running = safeToolLogs.find((l) => l.status === 'running');
  const doneCount = safeToolLogs.filter((l) => l.status === 'done').length;
  const status = getStatus(running, thinkOn && !!safeThinking.trim());

  const thinkingLines = safeThinking.split('\n').filter(Boolean);

  // Cores do topo: normal vs travado
  const headerBg = stuck
    ? 'rgba(244, 71, 71, 0.15)'
    : thinkOpen
      ? 'var(--bg-2, #111)'
      : 'transparent';
  const headerBorder = stuck
    ? '1px solid #f44747'
    : thinkOpen
      ? '1px solid var(--thinking-border, #2a2a2a)'
      : 'none';
  const labelColor = stuck ? '#f44747' : 'var(--accent)';
  const pulseAnimation = stuck ? 'stuckPulse 1s ease-in-out infinite' : 'none';

  return (
    <div
      style={{
        border: stuck ? '1px solid #f44747' : '1px solid var(--thinking-border, #2a2a2a)',
        borderRadius: '6px',
        overflow: 'hidden',
        background: stuck ? 'rgba(244, 71, 71, 0.05)' : 'var(--thinking-bg, #0a0a0a)',
        margin: '8px 0',
        animation: pulseAnimation,
      }}
    >
      {/* Header */}
      <div
        onClick={() => setThinkOpen(!thinkOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 12px',
          cursor: 'pointer',
          userSelect: 'none',
          background: headerBg,
          borderBottom: headerBorder,
          fontSize: '11px',
          color: labelColor,
          fontFamily: 'inherit',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            width: 16,
            height: 16,
            transform: thinkOpen ? 'rotate(90deg)' : 'none',
            transition: 'transform 0.15s',
            fontSize: '10px',
            color: stuck ? '#f44747' : 'var(--muted)',
          }}
        >
          ▶
        </span>
        <span style={{ fontSize: '12px' }}>
          {stuck ? '\u26A0\uFE0F' : status.icon === 'thinking_dots' ? <ThinkingDots /> : status.icon}
        </span>
        <span style={{ flex: 1, color: labelColor }}>
          {stuck ? '\u26A0\uFE0F IA Ociosa (Poss\u00EDvel Travamento)' : status.label}
        </span>
        {!stuck && safeToolLogs.length > 0 && (
          <span
            style={{
              fontSize: '9px',
              color: 'var(--muted)',
              background: 'var(--bg-3, #1a1a1a)',
              padding: '1px 6px',
              borderRadius: '8px',
            }}
          >
            {doneCount}/{safeToolLogs.length}
          </span>
        )}
      </div>

      {/* Progress bar — pulsing normal / stopped when stuck */}
      <div
        style={{
          height: 2,
          background: stuck ? '#f44747' : 'var(--thinking-border, #2a2a2a)',
          overflow: 'hidden',
        }}
      >
        {!stuck && (
          <div
            style={{
              height: '100%',
              width: '30%',
              background: 'var(--accent)',
              borderRadius: 1,
              animation: 'thinkingProgress 1.5s ease-in-out infinite',
            }}
          />
        )}
      </div>

      {/* Botao de Forçar Parada quando travado */}
      {stuck && (
        <div style={{ padding: '8px 12px', borderBottom: '1px solid rgba(244,71,71,0.3)' }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onStop?.();
            }}
            style={{
              width: '100%',
              padding: '8px 12px',
              background: '#f44747',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: '0 0 12px rgba(244,71,71,0.5)',
              animation: 'stuckPulse 1s ease-in-out infinite',
              fontFamily: 'inherit',
            }}
          >
            \u26A0\uFE0F For\u00E7ar Parada
          </button>
        </div>
      )}

      {/* Content */}
      {thinkOpen && (
        <div
          style={{
            maxHeight: 500,
            overflow: 'auto',
            padding: '4px 0',
            fontSize: '11px',
            lineHeight: '1.6',
            fontFamily: 'inherit',
          }}
        >
          {/* Thinking text */}
          {thinkingLines.length > 0 && (
            <div
              style={{
                padding: '4px 16px 8px',
                borderBottom:
                  safeToolLogs.length > 0 ? '1px solid var(--thinking-border, #2a2a2a)' : 'none',
              }}
            >
              {thinkingLines.map((line, i) => {
                const isStep = line.startsWith('[') && line.includes('/');
                const isToolCall = line.includes('Executando:') || line.includes('concluido');
                const isError = line.includes('Erro em') || line.includes('erro:');
                let color = 'var(--ink-2, #ccc)';
                let leftPad = 0;
                let prefix = '';
                if (isStep) {
                  color = '#60a5fa';
                  leftPad = 0;
                  prefix = '\u25B6 ';
                } else if (isToolCall) {
                  color = 'var(--blue, #569cd6)';
                  leftPad = 12;
                } else if (isError) {
                  color = '#f44747';
                  leftPad = 12;
                  prefix = '\u2716 ';
                }
                return (
                  <div
                    key={i}
                    style={{
                      paddingLeft: leftPad,
                      color,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {prefix}
                    {line}
                  </div>
                );
              })}
            </div>
          )}

          {/* Tool Logs */}
          {safeToolLogs.length > 0 && (
            <div style={{ padding: '4px 12px', background: 'rgba(59, 130, 246, 0.04)', borderRadius: '4px', margin: '0 4px' }}>
              <div
                style={{
                  fontSize: '9px',
                  color: '#60a5fa',
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  marginBottom: '4px',
                  paddingLeft: '4px',
                }}
              >
                ferramentas
              </div>
              {safeToolLogs.map((log, i) => (
                <ToolLogItem key={i} log={log} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolLogItem({ log }: { log: TLog }) {
  const [open, setOpen] = useState(false);

  const statusColor =
    log.status === 'done' ? '#4ec9b0' : log.status === 'error' ? '#f44747' : '#60a5fa';
  const statusIcon =
    log.status === 'done' ? '\u2713' : log.status === 'error' ? '\u2717' : '\u21BB';

  return (
    <div
      style={{
        borderLeft: `2px solid ${statusColor}`,
        borderRadius: '2px',
        marginBottom: '2px',
        background: log.status === 'running' ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 8px',
          cursor: 'pointer',
        }}
      >
        <span style={{ color: statusColor, fontSize: '10px' }}>{statusIcon}</span>
        <span
          style={{
            color: statusColor,
            fontWeight: 600,
            fontSize: '11px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {log.tool}
        </span>
        <span
          style={{
            fontSize: '9px',
            color: statusColor,
            fontWeight: 600,
            marginLeft: 'auto',
          }}
        >
          {log.status === 'done' ? 'ok' : log.status === 'error' ? 'erro' : '...'}
        </span>
      </div>
      {open && (
        <div
          style={{
            padding: '4px 10px 8px 24px',
            fontSize: '10px',
            lineHeight: '1.5',
            color: 'var(--muted)',
            whiteSpace: 'pre-wrap',
            borderTop: '1px solid var(--thinking-border, #2a2a2a)',
            background: 'var(--bg-4, rgba(0,0,0,0.15))',
            maxHeight: 200,
            overflow: 'auto',
          }}
        >
          {log.params && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: 'var(--blue)' }}>params:</span>
              <span style={{ marginLeft: 4 }}>{JSON.stringify(log.params, null, 1)}</span>
            </div>
          )}
          {log.result && log.status === 'done' && (
            <div>
              <span style={{ color: 'var(--teal)' }}>result:</span>
              <span style={{ marginLeft: 4 }}>{String(log.result).slice(0, 300)}</span>
            </div>
          )}
          {log.status === 'error' && (
            <div style={{ marginTop: 4 }}>
              <span style={{ color: '#f44747' }}>error:</span>
              <span style={{ marginLeft: 4 }}>
                {String(log.result || log.params || 'Erro').slice(0, 200)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
