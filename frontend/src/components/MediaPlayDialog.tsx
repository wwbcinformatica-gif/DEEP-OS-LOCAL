import React from 'react';

interface MediaPlayDialogProps {
  fileName: string;
  isVideo: boolean;
  onInternalPlay: () => void;
  onExternalPlay: () => void;
  onCancel: () => void;
}

export default function MediaPlayDialog({
  fileName,
  isVideo,
  onInternalPlay,
  onExternalPlay,
  onCancel,
}: MediaPlayDialogProps) {
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
      }}
    >
      <div
        style={{
          background: 'var(--bg)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: '20px 24px',
          maxWidth: 400,
          width: '90%',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: 20 }}>{isVideo ? '🎬' : '🎵'}</span>
          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--ink)' }}>
            Reproduzir Mídia
          </span>
        </div>

        <div
          style={{
            padding: '10px 12px',
            background: 'var(--bg-2)',
            borderRadius: 4,
            border: '1px solid var(--line)',
            marginBottom: 16,
            fontSize: 12,
            color: 'var(--muted)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {fileName}
        </div>

        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
          Onde deseja reproduzir? <span style={{ color: 'var(--accent)' }}>(ou fale: "media" ou "externo")</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button
            onClick={onInternalPlay}
            style={{
              padding: '10px 16px',
              border: '1px solid var(--accent)',
              borderRadius: 6,
              background: 'var(--accent)',
              color: 'var(--selection-fg)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 12,
              fontFamily: 'inherit',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <rect x="2" y="2" width="12" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
              <path d="M6 4l5 4-5 4z" />
            </svg>
            Player Interno (MEDIA)
          </button>

          <button
            onClick={onExternalPlay}
            style={{
              padding: '10px 16px',
              border: '1px solid var(--line)',
              borderRadius: 6,
              background: 'transparent',
              color: 'var(--ink)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 12,
              fontFamily: 'inherit',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-2)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <rect x="2" y="3" width="12" height="10" rx="1" fill="none" stroke="currentColor" strokeWidth="1.2" />
              <path d="M5 7l6 3-6 3z" />
            </svg>
            Aplicativo Externo (padrão do sistema)
          </button>

          <button
            onClick={onCancel}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: 4,
              background: 'transparent',
              color: 'var(--muted)',
              cursor: 'pointer',
              fontSize: 11,
              fontFamily: 'inherit',
              marginTop: 4,
            }}
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
