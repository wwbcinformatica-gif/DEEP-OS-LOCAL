import React from 'react';

interface PermissionDialogProps {
  title: string;
  description: string;
  patterns?: string[];
  onAllowOnce: () => void;
  onAllowAlways: () => void;
  onReject: () => void;
}

export default function PermissionDialog({
  title,
  description,
  patterns,
  onAllowOnce,
  onAllowAlways,
  onReject,
}: PermissionDialogProps) {
  return (
    <div
      style={{
        border: '1px solid var(--accent)',
        borderRadius: '6px',
        padding: '12px 16px',
        background: 'var(--bg-2)',
        fontFamily: 'var(--font-ui)',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '8px',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 18,
            height: 18,
            borderRadius: '3px',
            background: '#dcdcaa22',
            color: '#dcdcaa',
            fontSize: '10px',
            fontWeight: 700,
          }}
        >
          !
        </span>
        <span style={{ fontWeight: 700, fontSize: '11px', color: '#dcdcaa' }}>
          {title || 'Permissão necessária'}
        </span>
      </div>

      {/* Description */}
      <div
        style={{
          fontSize: '10px',
          color: 'var(--muted)',
          marginBottom: patterns?.length ? '6px' : '10px',
          lineHeight: 1.4,
        }}
      >
        {description}
      </div>

      {/* Patterns */}
      {patterns && patterns.length > 0 && (
        <div
          style={{
            fontSize: '10px',
            color: 'var(--muted)',
            marginBottom: '10px',
          }}
        >
          <span style={{ fontWeight: 600 }}>Padrões:</span>
          {patterns.map((p, i) => (
            <div
              key={i}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '9px',
                color: 'var(--accent)',
                padding: '2px 0',
              }}
            >
              - {p}
            </div>
          ))}
        </div>
      )}

      {/* Buttons */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
        <button
          onClick={onAllowOnce}
          style={{
            padding: '6px 12px',
            border: '1px solid var(--accent)',
            borderRadius: '4px',
            background: 'var(--accent)',
            color: '#fff',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '10px',
            fontFamily: 'var(--font-ui)',
          }}
        >
          Allow once
        </button>
        <button
          onClick={onAllowAlways}
          style={{
            padding: '6px 12px',
            border: '1px solid var(--line)',
            borderRadius: '4px',
            background: 'transparent',
            color: 'var(--muted)',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '10px',
            fontFamily: 'var(--font-ui)',
          }}
        >
          Allow always
        </button>
        <button
          onClick={onReject}
          style={{
            padding: '6px 12px',
            border: '1px solid transparent',
            borderRadius: '4px',
            background: 'transparent',
            color: '#f44747',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '10px',
            fontFamily: 'var(--font-ui)',
          }}
        >
          Reject
        </button>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: '8px',
            color: 'var(--muted)',
            opacity: 0.6,
          }}
        >
          ctrl+f fullscreen &middot; enter confirm
        </span>
      </div>
    </div>
  );
}
