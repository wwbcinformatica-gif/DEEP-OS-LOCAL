import React from 'react';
import DiffViewer from './DiffViewer';

interface ChangeInfo {
  file: string;
  change_type: string;
  lines_added: number;
  lines_removed: number;
  summary: string;
  is_config: boolean;
  is_auth: boolean;
  is_database: boolean;
}

interface PlanStep {
  order: number;
  tool: string;
  description: string;
  status: string;
  files_affected: string[];
  diff?: string;
  change_info?: ChangeInfo;
}

interface PlanData {
  steps: PlanStep[];
  risk: string;
  files: string[];
  backup_needed: boolean;
  summary: string;
  total_additions: number;
  total_deletions: number;
  risk_reason: string;
  level?: string;
}

interface PlanPanelProps {
  plan: PlanData | null;
  mode: 'auto' | 'plan' | 'safe';
  isPending: boolean;
  onApprove: () => void;
  onReject: () => void;
  onCancel: () => void;
}

const CHANGE_LABELS: Record<string, { label: string; color: string }> = {
  CREATE: { label: 'CREATE', color: '#4ec9b0' },
  MODIFY: { label: 'MODIFY', color: '#dcdcaa' },
  DELETE: { label: 'DELETE', color: '#f44747' },
  RENAME: { label: 'RENAME', color: '#569cd6' },
  READ: { label: 'READ', color: '#6a9955' },
  EXECUTE: { label: 'EXECUTE', color: '#ce9178' },
  OTHER: { label: 'OTHER', color: '#808080' },
};

const RISK_CONFIG: Record<string, { emoji: string; color: string; label: string }> = {
  alto: { emoji: '🔴', color: '#f44747', label: 'Alto' },
  medio: { emoji: '🟡', color: '#dcdcaa', label: 'Médio' },
  baixo: { emoji: '🟢', color: '#4ec9b0', label: 'Baixo' },
};

const cardStyle: React.CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: '4px',
  padding: '16px',
  background: 'var(--bg)',
  fontFamily: 'var(--font-ui)',
};

export default function PlanPanel({
  plan,
  mode,
  isPending,
  onApprove,
  onReject,
  onCancel,
}: PlanPanelProps) {
  if (!plan) return null;

  const riskCfg = RISK_CONFIG[plan.risk] || RISK_CONFIG.baixo;
  const numFiles = plan.files.length;
  const numCreates = plan.steps.filter((s) => s.change_info?.change_type === 'CREATE').length;
  const numModifies = plan.steps.filter((s) => s.change_info?.change_type === 'MODIFY').length;
  const numDeletes = plan.steps.filter((s) => s.change_info?.change_type === 'DELETE').length;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: '#000',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--font-ui)',
      }}
    >
      <div
        style={{
          ...cardStyle,
          width: '700px',
          maxHeight: '90vh',
          overflow: 'auto',
          maxWidth: '95vw',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {/* ── Header ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            borderBottom: '1px solid var(--line)',
            paddingBottom: '10px',
          }}
        >
          <span style={{ fontSize: '16px' }}>📋</span>
          <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--ink)' }}>
            Plano de Execução
          </span>
          {plan.level && <LevelBadge level={plan.level} />}
          <span
            style={{
              marginLeft: 'auto',
              fontSize: '10px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              padding: '2px 8px',
              borderRadius: '3px',
              border: '1px solid var(--accent)',
              color: 'var(--accent)',
            }}
          >
            {mode.toUpperCase()}
          </span>
        </div>

        {/* ── Summary ── */}
        {plan.summary && (
          <div
            style={{
              padding: '8px 10px',
              background: 'var(--bg-2)',
              borderRadius: '4px',
              fontSize: '11px',
              color: 'var(--muted)',
              lineHeight: 1.5,
              border: '1px solid var(--line)',
            }}
          >
            {plan.summary.slice(0, 400)}
          </div>
        )}

        {/* ── Stats Bar ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
          <StatBox label="Arquivos" value={`${numFiles}`} />
          <StatBox label="Adições" value={`+${plan.total_additions || 0}`} color="#4ec9b0" />
          <StatBox label="Remoções" value={`-${plan.total_deletions || 0}`} color="#f44747" />
          <StatBox label="Risco" value={`${riskCfg.emoji} ${riskCfg.label}`} />
        </div>

        {/* ── Change type summary ── */}
        {(numCreates > 0 || numModifies > 0 || numDeletes > 0) && (
          <div style={{ display: 'flex', gap: '12px', fontSize: '10px', color: 'var(--muted)' }}>
            {numCreates > 0 && (
              <span style={{ color: '#4ec9b0' }}>▸ {numCreates} criação(ões)</span>
            )}
            {numModifies > 0 && (
              <span style={{ color: '#dcdcaa' }}>▸ {numModifies} modificação(ões)</span>
            )}
            {numDeletes > 0 && (
              <span style={{ color: '#f44747' }}>▸ {numDeletes} exclusão(ões)</span>
            )}
          </div>
        )}

        {/* ── Risk reason ── */}
        {plan.risk_reason && (
          <div
            style={{
              padding: '6px 10px',
              borderRadius: '4px',
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              fontSize: '10px',
              color: riskCfg.color,
            }}
          >
            {riskCfg.emoji} {riskCfg.label}: {plan.risk_reason}
          </div>
        )}

        {/* ── Steps ── */}
        <div>
          <div
            style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink)', marginBottom: '8px' }}
          >
            Etapas ({plan.steps.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {plan.steps.map((s) => {
              const ci = s.change_info;
              const ch = ci
                ? CHANGE_LABELS[ci.change_type] || CHANGE_LABELS.OTHER
                : CHANGE_LABELS.OTHER;
              return (
                <div key={s.order}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 10px',
                      borderRadius: '4px',
                      background: s.status === 'running' ? 'var(--accent-soft)' : 'var(--bg-2)',
                      border: '1px solid var(--line)',
                      fontSize: '11px',
                      flexWrap: 'wrap',
                    }}
                  >
                    {/* Step number */}
                    <span style={{ color: 'var(--quiet)', fontWeight: 600, minWidth: '24px' }}>
                      #{s.order}
                    </span>

                    {/* Change type badge */}
                    {ci && (
                      <span
                        style={{
                          padding: '1px 5px',
                          borderRadius: '2px',
                          background: `${ch.color}22`,
                          color: ch.color,
                          fontSize: '9px',
                          fontWeight: 700,
                          letterSpacing: '0.5px',
                        }}
                      >
                        {ch.label}
                      </span>
                    )}

                    {/* File name */}
                    <span
                      style={{
                        color: 'var(--ink)',
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {ci?.file || s.description}
                    </span>

                    {/* Lines */}
                    {ci && ci.lines_added > 0 && (
                      <span style={{ color: '#4ec9b0', fontSize: '10px', fontWeight: 600 }}>
                        +{ci.lines_added}
                      </span>
                    )}
                    {ci && ci.lines_removed > 0 && (
                      <span style={{ color: '#f44747', fontSize: '10px', fontWeight: 600 }}>
                        -{ci.lines_removed}
                      </span>
                    )}

                    {/* Tool badge */}
                    <span
                      style={{
                        padding: '1px 6px',
                        borderRadius: '2px',
                        background: 'var(--bg-3)',
                        color: 'var(--muted)',
                        fontSize: '9px',
                        fontWeight: 600,
                      }}
                    >
                      {s.tool}
                    </span>
                  </div>

                  {/* Step summary */}
                  {ci?.summary && ci.summary !== s.description && (
                    <div
                      style={{
                        marginLeft: '30px',
                        marginTop: '2px',
                        fontSize: '10px',
                        color: 'var(--quiet)',
                      }}
                    >
                      {ci.summary}
                    </div>
                  )}

                  {/* Diff preview */}
                  {s.diff && (
                    <div style={{ marginLeft: '24px', marginTop: '2px', marginBottom: '2px' }}>
                      <DiffViewer diff={s.diff} filename={s.files_affected[0] || ci?.file || ''} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Summary footer ── */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 10px',
            borderRadius: '4px',
            background: 'var(--bg-2)',
            border: '1px solid var(--line)',
            fontSize: '10px',
            fontWeight: 600,
            color: 'var(--muted)',
          }}
        >
          <span>Arquivos: {numFiles}</span>
          <span style={{ color: '#4ec9b0' }}>Adições: +{plan.total_additions || 0}</span>
          <span style={{ color: '#f44747' }}>Remoções: -{plan.total_deletions || 0}</span>
          <span style={{ color: riskCfg.color }}>
            Risco: {riskCfg.emoji} {riskCfg.label}
          </span>
          <span style={{ color: plan.backup_needed ? '#dcdcaa' : '#4ec9b0' }}>
            Backup: {plan.backup_needed ? 'Sim' : 'Não necessário'}
          </span>
        </div>

        {/* ── Buttons ── */}
        {!isPending && (
          <div
            style={{
              display: 'flex',
              gap: '8px',
              borderTop: '1px solid var(--line)',
              paddingTop: '12px',
              marginTop: '4px',
            }}
          >
            <button
              onClick={onApprove}
              style={{
                flex: 1,
                padding: '8px 16px',
                border: '1px solid var(--accent)',
                borderRadius: '4px',
                background: 'var(--accent)',
                color: 'var(--selection-fg)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
                fontFamily: 'inherit',
              }}
            >
              ✅ Aprovar e Executar
            </button>
            <button
              onClick={onReject}
              style={{
                padding: '8px 16px',
                border: '1px solid var(--line-strong)',
                borderRadius: '4px',
                background: 'transparent',
                color: 'var(--muted)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
                fontFamily: 'inherit',
              }}
            >
              Rejeitar
            </button>
            <button
              onClick={onCancel}
              style={{
                padding: '8px 16px',
                border: '1px solid transparent',
                borderRadius: '4px',
                background: 'transparent',
                color: '#f44747',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
                fontFamily: 'inherit',
              }}
            >
              Cancelar
            </button>
          </div>
        )}

        {isPending && (
          <div
            style={{
              textAlign: 'center',
              padding: '8px',
              color: 'var(--muted)',
              fontSize: '11px',
              borderTop: '1px solid var(--line)',
              paddingTop: '12px',
            }}
          >
            Executando plano...
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div
      style={{
        padding: '8px 10px',
        borderRadius: '4px',
        background: 'var(--bg-2)',
        border: '1px solid var(--line)',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontSize: '9px',
          color: 'var(--quiet)',
          marginBottom: '2px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: '14px', fontWeight: 700, color: color || 'var(--ink)' }}>{value}</div>
    </div>
  );
}

function LevelBadge({ level }: { level: string }) {
  const cfg: Record<string, { color: string; bg: string }> = {
    LOW: { color: '#4ec9b0', bg: 'rgba(78,201,176,0.15)' },
    MEDIUM: { color: '#dcdcaa', bg: 'rgba(220,220,170,0.15)' },
    HIGH: { color: '#f44747', bg: 'rgba(244,71,71,0.15)' },
  };
  const c = cfg[level] || cfg.LOW;
  return (
    <span
      style={{
        padding: '1px 6px',
        borderRadius: '3px',
        background: c.bg,
        color: c.color,
        fontSize: '10px',
        fontWeight: 700,
        letterSpacing: '0.5px',
      }}
    >
      {level}
    </span>
  );
}
