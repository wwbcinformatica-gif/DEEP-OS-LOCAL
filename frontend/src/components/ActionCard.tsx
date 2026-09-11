import React, { useState } from 'react';

interface ActionButton {
  id: string;
  label: string;
  action: string;
}

interface ActionCardData {
  type: 'action_card';
  title: string;
  message: string;
  buttons: ActionButton[];
}

interface ActionCardProps {
  data: ActionCardData;
  onAction: (action: string, label: string) => void;
}

export default function ActionCard({ data, onAction }: ActionCardProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [responded, setResponded] = useState<string | null>(null);

  const handleClick = (action: string, label: string, idx: number) => {
    if (responded !== null) return;
    setResponded(label);
    onAction(action, label);
  };

  return (
    <div style={{
      background: 'var(--bg-2, #1a1a2e)',
      border: '1px solid var(--line, #2a2a3e)',
      borderRadius: '8px',
      overflow: 'hidden',
      maxWidth: '100%',
      width: '100%',
      fontFamily: 'var(--font-ui, "Segoe UI", system-ui, sans-serif)',
      marginTop: '4px',
      marginBottom: '4px',
      opacity: responded !== null ? 0.7 : 1,
      transition: 'opacity 0.2s ease',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '12px 16px',
        borderBottom: '1px solid #2a2a3e',
        background: '#12121f',
      }}>
        <span style={{ fontSize: '16px', lineHeight: 1, filter: 'saturate(1.2)' }}>
          {responded !== null ? '✅' : '⚠️'}
        </span>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#e8a838', letterSpacing: '0.2px' }}>
          {data.title}
        </span>
      </div>

      <div style={{
        padding: '14px 16px',
        borderBottom: data.buttons?.length && responded === null ? '1px solid #2a2a3e' : 'none',
      }}>
        <p style={{ margin: 0, fontSize: '13px', lineHeight: '1.6', color: '#b0b0c0', wordBreak: 'break-word' }}>
          {data.message}
        </p>
      </div>

      {responded !== null ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          background: '#12121f',
          fontSize: '11px',
          color: '#6a6a8a',
          letterSpacing: '0.2px',
        }}>
          <span style={{ color: '#4ecb71' }}>●</span>
          Resposta enviada: <span style={{ color: '#b0b0c0', fontWeight: 500 }}>{responded}</span>
        </div>
      ) : data.buttons && data.buttons.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'row', gap: '0', background: '#12121f' }}>
          {data.buttons.map((btn, idx) => {
            const isHovered = hoveredIdx === idx;
            const isLast = idx === data.buttons.length - 1;

            return (
              <button
                key={btn.id}
                onClick={() => handleClick(btn.action, btn.label, idx)}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  border: 'none',
                  borderRight: !isLast ? '1px solid #2a2a3e' : 'none',
                  borderRadius: 0,
                  background: isHovered
                    ? 'rgba(255,255,255,0.05)'
                    : 'transparent',
                  color: idx === 0
                    ? '#e8a838'
                    : idx === data.buttons.length - 1
                      ? '#ff6b6b'
                      : '#d0d0e0',
                  cursor: 'pointer',
                  fontWeight: 500,
                  fontSize: '12px',
                  fontFamily: 'inherit',
                  transition: 'background 0.12s ease, color 0.12s ease',
                  letterSpacing: '0.1px',
                  whiteSpace: 'nowrap',
                }}
              >
                {btn.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function tryParseJson(raw: string): ActionCardData | null {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.type === 'action_card' && Array.isArray(parsed.buttons)) {
      return parsed as ActionCardData;
    }
  } catch {}
  return null;
}

export function parseActionCard(text: string): ActionCardData | null {
  if (!text || typeof text !== 'string') return null;

  const trimmed = text.trim();
  if (!trimmed) return null;

  const result = tryParseJson(trimmed);
  if (result) return result;

  if (trimmed.startsWith('{')) {
    const lastBrace = trimmed.lastIndexOf('}');
    if (lastBrace > 0) {
      const r2 = tryParseJson(trimmed.slice(0, lastBrace + 1));
      if (r2) return r2;
    }
  }

  const fenceMatch = trimmed.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
  if (fenceMatch) {
    const r3 = tryParseJson(fenceMatch[1].trim());
    if (r3) return r3;
  }

  const firstBrace = trimmed.indexOf('{');
  const lastBrace = trimmed.lastIndexOf('}');
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    const r4 = tryParseJson(trimmed.slice(firstBrace, lastBrace + 1));
    if (r4) return r4;
  }

  return null;
}
