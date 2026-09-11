import React from 'react';

interface Step {
  label: string;
  status: string;
  error?: string;
}

interface Props {
  steps: Step[];
}

const STATUS_ICONS: Record<string, { icon: string; color: string; strike: boolean }> = {
  done: { icon: '✓', color: '#ff9800', strike: true },
  running: { icon: '+', color: '#ff9800', strike: false },
  error: { icon: '✗', color: '#f44747', strike: false },
  pending: { icon: ' ', color: '#ff9800', strike: false },
};

export default function TaskChecklist({ steps }: Props) {
  if (!steps || steps.length === 0) return null;

  const completed = steps.filter((s) => s.status === 'done').length;
  const total = steps.length;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div
      style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--line)',
        borderRadius: 6,
        overflow: 'hidden',
        marginTop: 8,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          borderBottom: '1px solid var(--line)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.5px',
        }}
      >
        <span style={{ color: '#ff9800' }}># Todos</span>
        <span style={{ color: 'var(--muted)' }}>
          {completed}/{total} ({progress}%)
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 2, background: 'var(--line)' }}>
        <div
          style={{
            height: '100%',
            width: `${progress}%`,
            background: '#ff9800',
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      {/* Steps */}
      <div style={{ padding: '4px 0' }}>
        {steps.map((step, idx) => {
          const cfg = STATUS_ICONS[step.status] || STATUS_ICONS.pending;
          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 6,
                padding: '3px 10px',
                fontSize: 11,
                fontFamily: 'var(--font-mono), monospace',
                color: step.status === 'done' ? 'var(--muted)' : 'var(--ink)',
                textDecoration: cfg.strike ? 'line-through' : 'none',
                opacity: step.status === 'done' ? 0.6 : 1,
                background: step.status === 'running' ? 'var(--accent-soft)' : 'transparent',
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  color: cfg.color,
                  minWidth: 20,
                  textAlign: 'center',
                  fontSize: 10,
                }}
              >
                [<span style={{ color: cfg.color }}>{cfg.icon}</span>]
              </span>
              <span style={{ flex: 1 }}>{step.label}</span>
              {step.error && (
                <span style={{ fontSize: 9, color: '#f44747' }}>
                  {step.error.slice(0, 40)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Current task indicator */}
      {steps.some((s) => s.status === 'running') && (
        <div
          style={{
            padding: '4px 10px',
            borderTop: '1px solid var(--line)',
            fontSize: 9,
            color: '#ff9800',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <span style={{ animation: 'blink 1s step-end infinite' }}>●</span>
          Executando...
        </div>
      )}
    </div>
  );
}
