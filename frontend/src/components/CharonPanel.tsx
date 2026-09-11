import React, { useEffect, useRef, useState, useCallback } from 'react';

interface TranscriptEntry {
  speaker: string;
  text: string;
  time: string;
}

interface CharonPanelProps {
  visible: boolean;
  onClose: () => void;
  transcripts: TranscriptEntry[];
  voiceName?: string;
  voiceStatus?: string;
  onSendText?: (text: string) => void;
}

const CharonPanel: React.FC<CharonPanelProps> = ({ visible, onClose, transcripts, voiceName = 'Charon', voiceStatus = 'idle', onSendText }) => {
  const listRef = useRef<HTMLDivElement>(null);
  const [inputText, setInputText] = useState('');
  const [textareaH, setTextareaH] = useState(120);
  const dragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartH = useRef(0);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [transcripts]);

  const handleSend = () => {
    const text = inputText.trim();
    if (!text || voiceStatus === 'idle' || voiceStatus === 'processing' || !onSendText) return;
    onSendText(text);
    setInputText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    dragStartY.current = e.clientY;
    dragStartH.current = textareaH;
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const delta = dragStartY.current - ev.clientY;
      setTextareaH(Math.max(36, Math.min(300, dragStartH.current + delta)));
    };
    const onUp = () => {
      dragging.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [textareaH]);

  const isActive = voiceStatus !== 'idle' && voiceStatus !== 'error' && voiceStatus !== 'processing';

  if (!visible) return null;

  return (
    <div style={{
      flex: 1,
      background: 'var(--bg-2)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      minHeight: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--line)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: '#b478ff', fontWeight: 600 }}>⚡ Charon</span>
          <span style={{
            fontSize: 9,
            padding: '1px 6px',
            borderRadius: 3,
            background: voiceStatus === 'speaking' ? 'rgba(255,200,0,0.15)' :
                        voiceStatus === 'listening' ? 'rgba(0,200,0,0.15)' :
                        voiceStatus === 'processing' ? 'rgba(255,128,0,0.15)' :
                        voiceStatus === 'error' ? 'rgba(255,0,0,0.15)' :
                        'rgba(255,255,255,0.05)',
            color: voiceStatus === 'speaking' ? '#ffc800' :
                   voiceStatus === 'listening' ? '#0c0' :
                   voiceStatus === 'processing' ? '#f80' :
                   voiceStatus === 'error' ? '#f44' :
                   'var(--muted)',
          }}>
            {voiceStatus === 'speaking' ? ' falando' :
             voiceStatus === 'listening' ? ' ouvindo' :
             voiceStatus === 'processing' ? ' processando...' :
             voiceStatus === 'connecting' ? ' conectando...' :
             voiceStatus === 'error' ? ' erro' :
             ' inativo'}
          </span>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: 'var(--muted)',
          cursor: 'pointer', fontSize: 14, padding: 0,
        }}>×</button>
      </div>

      {/* Transcript list */}
      <div ref={listRef} style={{
        flex: 1,
        overflowY: 'auto',
        padding: '8px 12px',
        fontSize: 11,
        lineHeight: 1.5,
      }}>
        {transcripts.length === 0 ? (
          <div style={{ color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>
            {voiceStatus === 'idle' ? (
              <>
                Charon desligado.<br />
                Clique em <span style={{ color: '#b478ff', fontWeight: 600 }}>⚡ Charon</span> na barra de status para ativar.<br />
                <span style={{ fontSize: 10, opacity: 0.7 }}>Uma vez ativado, ficara sempre ouvindo.</span>
              </>
            ) : (
              <>
                Aguardando sua voz...<br />
                <span style={{ fontSize: 10, opacity: 0.7 }}>Fale diretamente com o Charon</span>
              </>
            )}
          </div>
        ) : (
          transcripts.map((t, i) => (
            <div key={i} style={{ marginBottom: 8 }}>
              <div style={{
                fontSize: 9,
                color: t.speaker === 'user' ? '#569cd6' : '#b478ff',
                fontWeight: 600,
                marginBottom: 2,
              }}>
                {t.speaker === 'user' ? '👤 Você' : '⚡ Charon'} · {t.time}
              </div>
              <div style={{
                color: 'var(--ink-2)',
                whiteSpace: 'pre-wrap',
              }}>
                {t.text}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Input area - igual ao ChatPanel */}
      <div style={{
        padding: '10px 12px',
        borderTop: '1px solid var(--line)',
        flexShrink: 0,
      }}>
        {/* Textarea container com drag handle */}
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <div
            onMouseDown={onDragStart}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: 6,
              cursor: 'ns-resize',
              zIndex: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title="Arraste para redimensionar"
          >
            <div style={{ width: 32, height: 2, borderRadius: 1, background: 'var(--line)' }} />
          </div>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isActive ? 'Digite sua mensagem...' : 'Ative o microfone para enviar'}
            disabled={!isActive}
            style={{
              width: '100%',
              height: textareaH,
              resize: 'none',
              padding: '10px',
              paddingTop: 12,
              borderRadius: 6,
              border: '1px solid var(--line)',
              background: isActive ? 'var(--bg)' : 'rgba(255,255,255,0.03)',
              color: isActive ? 'var(--ink)' : 'var(--muted)',
              fontFamily: 'inherit',
              fontSize: '12px',
              lineHeight: 1.4,
              opacity: isActive ? 1 : 0.5,
            }}
          />
        </div>

        {/* Botões embaixo */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Esquerda: info */}
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <span style={{
              fontSize: 9,
              color: isActive ? '#0c0' : 'var(--muted)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}>
              <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: isActive ? '#0c0' : 'var(--muted)',
              }} />
              {isActive ? 'Charon ativo' : 'Charon inativo'}
            </span>
            <span style={{ fontSize: 9, color: 'var(--muted)' }}>·</span>
            <span style={{ fontSize: 9, color: 'var(--muted)' }}>Voz: {voiceName}</span>
          </div>

          {/* Direita: botão enviar */}
          <button
            onClick={handleSend}
            disabled={!isActive || !inputText.trim()}
            style={{
              width: 36,
              height: 36,
              borderRadius: 6,
              border: `1px solid ${isActive && inputText.trim() ? '#b478ff' : 'var(--line)'}`,
              color: isActive && inputText.trim() ? '#b478ff' : 'var(--muted)',
              cursor: isActive && inputText.trim() ? 'pointer' : 'default',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              background: isActive && inputText.trim() ? 'rgba(180,120,255,0.15)' : 'transparent',
              opacity: isActive && inputText.trim() ? 1 : 0.4,
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default CharonPanel;
