import React from 'react';

interface CharonToolMessageProps {
  icon: string;
  label: string;
  color: string;
  content: string;
}

const CharonToolMessage: React.FC<CharonToolMessageProps> = ({ icon, label, color, content }) => {
  // Detecta se o conteúdo é uma lista
  const isList = content.includes('\n') && (content.includes('**Pastas:**') || content.includes('**Arquivos:**'));
  
  // Formata o conteúdo
  const formatContent = (text: string) => {
    // Processa negrito markdown
    let formatted = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Se for lista, formata comindentação
    if (isList) {
      formatted = formatted
        .split('\n')
        .map(line => {
          if (line.startsWith('**Pastas:**') || line.startsWith('**Arquivos:**')) {
            return `<div style="margin-top: 8px; margin-bottom: 4px; font-weight: 600; color: ${color}">${line}</div>`;
          }
          if (line.trim()) {
            return `<div style="padding-left: 12px; color: var(--ink-2)">• ${line}</div>`;
          }
          return '';
        })
        .join('');
    }
    
    return formatted;
  };

  return (
    <div style={{
      background: `linear-gradient(135deg, ${color}08 0%, ${color}15 100%)`,
      border: `1px solid ${color}30`,
      borderRadius: 8,
      overflow: 'hidden',
      margin: '4px 0',
    }}>
      {/* Header */}
      <div style={{
        background: `${color}20`,
        padding: '8px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        borderBottom: `1px solid ${color}25`,
      }}>
        <span style={{ fontSize: 14 }}>{icon}</span>
        <span style={{
          fontSize: 11,
          fontWeight: 700,
          color: color,
          letterSpacing: '0.3px',
        }}>
          Charon · {label.toUpperCase()}
        </span>
        <div style={{
          marginLeft: 'auto',
          fontSize: 9,
          color: 'var(--muted)',
          background: 'rgba(0,0,0,0.2)',
          padding: '2px 6px',
          borderRadius: 3,
        }}>
          {new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      
      {/* Content */}
      <div style={{
        padding: '10px 12px',
        fontSize: 12,
        lineHeight: 1.6,
        color: 'var(--ink)',
        fontFamily: 'var(--font-mono), "Cascadia Code", monospace',
      }}>
        {isList ? (
          <div dangerouslySetInnerHTML={{ __html: formatContent(content) }} />
        ) : (
          <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>
        )}
      </div>
      
      {/* Footer sutil */}
      <div style={{
        padding: '4px 12px',
        background: 'rgba(0,0,0,0.1)',
        fontSize: 9,
        color: 'var(--muted)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}>
        executado via Charon
      </div>
    </div>
  );
};

export default CharonToolMessage;
