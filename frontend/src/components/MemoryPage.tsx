import React, { useState, useEffect } from 'react';
import { API_BASE } from '../lib/constants';

const btnStyle = (c?: string, b?: string): React.CSSProperties => ({
  background: 'transparent',
  border: `1px solid ${b || 'var(--line-strong)'}`,
  borderRadius: '4px',
  color: c || 'var(--muted)',
  cursor: 'pointer',
  padding: '4px 10px',
  fontFamily: 'inherit',
  fontSize: '11px',
  fontWeight: 600,
});

export default function MemoryPage() {
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchMem = async () => {
    setLoading(true);
    setError('');
    try {
      const r = await fetch(`${API_BASE}/memory/vector/namespaces`);
      if (r.ok) {
        const data = await r.json();
        // API retorna {"namespaces": ["ns1", "ns2", ...]} ou array direto
        const list = Array.isArray(data)
          ? data
          : Array.isArray(data?.namespaces)
            ? data.namespaces
            : [];
        setNamespaces(list);
      } else {
        setError(`Erro HTTP ${r.status}`);
      }
    } catch (e: any) {
      setError(e.message || 'Falha ao carregar memórias');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMem();
  }, []);

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '20px', fontFamily: 'inherit' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
        <h2
          style={{
            fontFamily: 'inherit',
            fontSize: '1em',
            fontWeight: 600,
            color: '#569cd6',
            margin: '0 0 4px',
          }}
        >
          // memoria
        </h2>
        <button onClick={fetchMem} style={btnStyle()}>
          {'\u21BA'}
        </button>
      </div>
      <p
        style={{
          fontFamily: 'inherit',
          fontSize: '1em',
          fontWeight: 600,
          color: '#4ec9b0',
          margin: '0 0 20px',
        }}
      >
        $ namespaces ativos
      </p>
      {loading ? (
        <p
          style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: 'var(--muted)' }}
        >
          $ carregando...
        </p>
      ) : error ? (
        <p style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: '#f44747' }}>
          $ erro: {error}
        </p>
      ) : namespaces.length === 0 ? (
        <p
          style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: 'var(--muted)' }}
        >
          $ nenhum namespace encontrado
        </p>
      ) : (
        namespaces.map((ns) => (
          <div
            key={ns}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              marginBottom: '4px',
              border: '1px solid var(--line)',
              borderRadius: '4px',
              background: 'var(--bg)',
            }}
          >
            <span
              style={{
                fontFamily: 'inherit',
                fontSize: '1em',
                fontWeight: 600,
                color: 'var(--ink)',
              }}
            >
              {ns}
            </span>
            <span
              style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: '#4ec9b0' }}
            >
              {'\u25CF'} ativo
            </span>
          </div>
        ))
      )}
    </div>
  );
}
