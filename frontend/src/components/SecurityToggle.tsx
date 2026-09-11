import React, { useState } from 'react';
import { API_BASE } from '../lib/constants';

export const SecurityToggle: React.FC = () => {
  const [isSandboxEnabled, setIsSandboxEnabled] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const handleToggle = async () => {
    setLoading(true);
    const newValue = !isSandboxEnabled;
    try {
      const response = await fetch(`${API_BASE}/api/config/sandbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newValue }),
      });
      if (response.ok) {
        setIsSandboxEnabled(newValue);
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(`Erro no servidor: ${errorData.detail || response.statusText}`);
      }
    } catch (error) {
      alert('Não foi possível conectar ao servidor. O backend está rodando?');
      console.error('Erro na requisição:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: 'var(--bg)',
        borderRadius: '6px',
        border: '1px solid var(--line)',
      }}
    >
      <div>
        <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink)', margin: 0 }}>
          Modo de Operacao
        </h3>
        <p style={{ fontSize: '11px', color: 'var(--muted)', margin: '4px 0 0 0' }}>
          {isSandboxEnabled
            ? 'Restrito (pasta do projeto)'
            : 'Desenvolvedor (acesso total)'}
        </p>
      </div>
      <button
        onClick={handleToggle}
        disabled={loading}
        style={{
          width: 36,
          height: 20,
          borderRadius: 10,
          border: `1px solid ${isSandboxEnabled ? 'var(--accent)' : 'var(--line-strong)'}`,
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.6 : 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: isSandboxEnabled ? 'flex-end' : 'flex-start',
          flexShrink: 0,
          background: isSandboxEnabled ? 'var(--accent)' : 'var(--bg-3)',
          padding: '0 2px',
          transition: 'all 0.2s ease',
        }}
        title={isSandboxEnabled ? 'Modo Restrito - clique para mudar' : 'Modo Desenvolvedor - clique para mudar'}
      >
        <div style={{ width: 14, height: 14, borderRadius: '50%', background: isSandboxEnabled ? 'var(--bg-2)' : 'var(--quiet)', boxShadow: '0 1px 2px rgba(0,0,0,0.3)', transition: 'all 0.2s' }} />
      </button>
    </div>
  );
};
