import React, { useState } from 'react';
import type { Msg } from '../lib/constants';

interface Props {
  msg: Msg;
  onConfirm?: (taskId: string) => void;
  onReject?: (taskId: string) => void;
}

const RISK: Record<string, { emoji: string; color: string; label: string }> = {
  alto: { emoji: '🔴', color: '#f44747', label: 'Alto' },
  medio: { emoji: '🟡', color: '#dcdcaa', label: 'Médio' },
  baixo: { emoji: '🟢', color: '#4ec9b0', label: 'Baixo' },
};

export default function PlanMessage({ msg, onConfirm, onReject }: Props) {
  const [showAll, setShowAll] = useState(false);
  const plan = msg.planData;
  if (!plan) return null;

  const riskCfg = RISK[plan.risk] || RISK.baixo;
  const totalSteps = plan.steps?.length || 0;
  const isPending = msg.planStatus === 'pending';
  const isExecuting = msg.planStatus === 'executing';
  const isDone = msg.planStatus === 'done' || msg.planStatus === 'approved';

  // Calc progress
  const completedSteps = isDone ? totalSteps : isExecuting ? Math.floor(totalSteps * 0.3) : 0;
  const progressPct = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  // Build problem table data from steps
  const problemRows = (plan.steps || []).map((s: any, idx: number) => ({
    num: idx + 1,
    file: s.change_info?.file || s.files_affected?.[0] || '-',
    line: s.change_info?.line || s.description?.match(/linha\s*(\d+)/i)?.[1] || '~',
    problem: s.description || s.change_info?.summary || '-',
    type: s.change_info?.change_type || 'OTHER',
    status: s.status || 'pending',
  }));

  const displayedRows = showAll ? problemRows : problemRows.slice(0, 5);

  // Status labels
  const statusLabel = isPending
    ? 'AGUARDANDO'
    : isExecuting
      ? 'EM ANDAMENTO'
      : isDone
        ? 'CONCLUIDO'
        : msg.planStatus === 'error'
          ? 'ERRO'
          : 'REJEITADO';

  const statusColor = isPending
    ? '#dcdcaa'
    : isExecuting
      ? 'var(--accent)'
      : isDone
        ? '#4ec9b0'
        : msg.planStatus === 'error'
          ? '#f44747'
          : '#808080';

  return (
    <div style={{ width: '100%' }}>
      {/* ── Header bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          background: 'var(--bg-3, #1a1a1a)',
          border: '1px solid var(--line)',
          borderRadius: '6px 6px 0 0',
          borderBottom: 'none',
        }}
      >
        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '1px',
            textTransform: 'uppercase',
            color: 'var(--accent)',
          }}
        >
          PLANO DE EXECUCAO
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '9px',
              fontWeight: 700,
              letterSpacing: '0.5px',
              padding: '2px 8px',
              borderRadius: '3px',
              background: `${statusColor}22`,
              color: statusColor,
              border: `1px solid ${statusColor}44`,
            }}
          >
            {statusLabel}
          </span>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ink)' }}>
            {completedSteps}/{totalSteps} ({progressPct}%)
          </span>
        </div>
      </div>

      {/* ── Progress bar ── */}
      <div
        style={{
          height: '3px',
          background: 'var(--bg-3, #1a1a1a)',
          borderLeft: '1px solid var(--line)',
          borderRight: '1px solid var(--line)',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progressPct}%`,
            background: 'var(--accent)',
            transition: 'width 0.5s ease',
            borderRadius: '0 2px 2px 0',
          }}
        />
      </div>

      {/* ── Problem table ── */}
      <div
        style={{
          border: '1px solid var(--line)',
          borderTop: 'none',
          borderRadius: '0 0 6px 6px',
          overflow: 'hidden',
        }}
      >
        {/* Table header */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '32px 1fr 60px 2fr',
            padding: '6px 12px',
            background: 'var(--bg-3, #1a1a1a)',
            borderBottom: '1px solid var(--line)',
            fontSize: '10px',
            fontWeight: 700,
            color: 'var(--muted)',
            letterSpacing: '0.5px',
          }}
        >
          <span>#</span>
          <span>Arquivo</span>
          <span style={{ textAlign: 'center' }}>Linha</span>
          <span>Problema</span>
        </div>

        {/* Table rows */}
        {displayedRows.map((row: typeof problemRows[0]) => (
          <div
            key={row.num}
            style={{
              display: 'grid',
              gridTemplateColumns: '32px 1fr 60px 2fr',
              padding: '6px 12px',
              borderBottom: '1px solid var(--line)',
              fontSize: '10px',
              background: row.status === 'running' ? 'var(--accent-soft)' : 'transparent',
            }}
          >
            <span style={{ color: 'var(--muted)', fontWeight: 600 }}>{row.num}</span>
            <span
              style={{
                color: 'var(--accent)',
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {row.file}
            </span>
            <span style={{ color: 'var(--muted)', textAlign: 'center' }}>{row.line}</span>
            <span
              style={{
                color: 'var(--ink)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {row.problem}
            </span>
          </div>
        ))}

        {/* Show more */}
        {problemRows.length > 5 && (
          <div
            onClick={() => setShowAll(!showAll)}
            style={{
              padding: '6px 12px',
              fontSize: '9px',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontWeight: 600,
              textAlign: 'center',
              background: 'var(--bg-2)',
            }}
          >
            {showAll
              ? '▲ Mostrar menos'
              : `▼ Mostrar todos (${problemRows.length} problemas)`}
          </div>
        )}
      </div>

      {/* ── Steps checklist ── */}
      <div style={{ marginTop: '8px' }}>
        {(plan.steps || []).map((s: any, idx: number) => {
          const isComplete = isDone || (isExecuting && idx < completedSteps);
          const isCurrent = isExecuting && idx === completedSteps;
          return (
            <div
              key={s.order || idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 8px',
                fontSize: '11px',
                color: isComplete
                  ? 'var(--muted)'
                  : isCurrent
                    ? 'var(--accent)'
                    : 'var(--ink)',
                textDecoration: isComplete ? 'line-through' : 'none',
                opacity: isComplete ? 0.6 : 1,
              }}
            >
              <span style={{ fontWeight: 700, minWidth: 14 }}>
                {isComplete ? '✓' : isCurrent ? '●' : '○'}
              </span>
              <span style={{ flex: 1 }}>{s.description}</span>
              {s.change_info && (
                <span
                  style={{
                    fontSize: '9px',
                    padding: '1px 5px',
                    borderRadius: '2px',
                    background: 'var(--bg-3)',
                    color: 'var(--muted)',
                  }}
                >
                  {s.change_info.change_type}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Risk info ── */}
      {plan.risk_reason && (
        <div
          style={{
            marginTop: '6px',
            padding: '6px 10px',
            borderRadius: '4px',
            background: `${riskCfg.color}11`,
            border: `1px solid ${riskCfg.color}33`,
            fontSize: '10px',
            color: riskCfg.color,
          }}
        >
          {riskCfg.emoji} Risco {riskCfg.label}: {plan.risk_reason}
        </div>
      )}

      {/* ── Action buttons ── */}
      {isPending && (
        <div
          style={{
            display: 'flex',
            gap: '8px',
            marginTop: '10px',
          }}
        >
          <button
            onClick={() => onConfirm?.(msg.planTaskId || '')}
            style={{
              flex: 1,
              padding: '8px 16px',
              border: '1px solid var(--accent)',
              borderRadius: '4px',
              background: 'var(--accent)',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '11px',
              fontFamily: 'inherit',
              letterSpacing: '0.3px',
            }}
          >
            Aprovar e Executar
          </button>
          <button
            onClick={() => onReject?.(msg.planTaskId || '')}
            style={{
              padding: '8px 16px',
              border: '1px solid var(--line)',
              borderRadius: '4px',
              background: 'transparent',
              color: 'var(--muted)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '11px',
              fontFamily: 'inherit',
            }}
          >
            Rejeitar
          </button>
        </div>
      )}

      {/* ── Executing indicator ── */}
      {isExecuting && (
        <div
          style={{
            marginTop: '8px',
            padding: '6px 12px',
            borderRadius: '4px',
            background: 'var(--accent-soft)',
            border: '1px solid var(--accent)',
            fontSize: '10px',
            color: 'var(--accent)',
            textAlign: 'center',
            fontWeight: 600,
          }}
        >
          Executando plano...
        </div>
      )}
    </div>
  );
}
