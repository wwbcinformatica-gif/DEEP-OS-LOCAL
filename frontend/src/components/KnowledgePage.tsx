import React, { useState, useEffect, useCallback } from 'react';
import type { Provider, KnowItem } from '../lib/constants';
import { API_BASE } from '../lib/constants';
import GeneratePage from './GeneratePage';
import MemoryPage from './MemoryPage';

const btnStyle = (c = 'var(--muted)', b = 'var(--line-strong)'): React.CSSProperties => ({
  background: 'transparent',
  border: `1px solid ${b || 'var(--line-strong)'}`,
  borderRadius: '4px',
  color: c,
  cursor: 'pointer',
  padding: '4px 10px',
  fontFamily: 'inherit',
  fontSize: '11px',
  fontWeight: 600,
});

const inputStyle = (): React.CSSProperties => ({
  background: 'var(--input-bg)',
  border: '1px solid var(--line-strong)',
  borderRadius: '4px',
  color: 'var(--ink)',
  padding: '6px 10px',
  outline: 'none',
  fontFamily: 'inherit',
  fontSize: 'inherit',
});

interface Props {
  knows: KnowItem[];
  setKnows: React.Dispatch<React.SetStateAction<KnowItem[]>>;
  prov: Provider;
  model: string;
  apiKey: string;
  orApiKey: string;
}

export default function KnowledgePage({ knows, setKnows, prov, model, apiKey, orApiKey }: Props) {
  const [localKnows, setLocalKnows] = useState<KnowItem[]>(knows);
  const [newK, setNewK] = useState('');
  const [feeding, setFeeding] = useState(false);
  const [fedOk, setFedOk] = useState(false);
  const [editK, setEditK] = useState<KnowItem | null>(null);
  const [kSearch, setKSearch] = useState('');

  useEffect(() => {
    if (Array.isArray(knows)) setLocalKnows(knows);
  }, [knows]);

  const fetchKnows = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/knowledge`);
      if (r.ok) {
        const data = await r.json();
        const items = Array.isArray(data) ? data : (data?.items ?? []);
        setKnows(items);
        setLocalKnows(items);
      }
    } catch {}
  }, [setKnows]);

  const addKnow = useCallback(async () => {
    if (!newK.trim() || feeding) return;
    setFeeding(true);
    try {
      const r = await fetch(`${API_BASE}/knowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto: newK.trim() }),
      });
      if (r.ok) {
        setNewK('');
        setFedOk(true);
        setTimeout(() => setFedOk(false), 2000);
        await fetchKnows();
      }
    } catch {}
    setFeeding(false);
  }, [newK, feeding, fetchKnows]);

  const delKnow = useCallback(
    async (id: number) => {
      try {
        await fetch(`${API_BASE}/knowledge/${id}`, { method: 'DELETE' });
        await fetchKnows();
      } catch {}
    },
    [fetchKnows],
  );

  const saveKnow = useCallback(async () => {
    if (!editK) return;
    try {
      await fetch(`${API_BASE}/knowledge/${editK.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto: editK.texto }),
      });
      setEditK(null);
      await fetchKnows();
    } catch {}
  }, [editK, fetchKnows]);

  const filtered = Array.isArray(localKnows)
    ? localKnows.filter((k) => k.texto.toLowerCase().includes(kSearch.toLowerCase()))
    : [];

  const sectionTitle: React.CSSProperties = { fontFamily: 'inherit', fontSize: '13px', fontWeight: 600, color: '#c586c0', margin: '0 0 4px' };
  const sectionSub: React.CSSProperties = { fontFamily: 'inherit', fontSize: '13px', fontWeight: 600, color: '#4ec9b0', margin: '0 0 16px' };
  const divider: React.CSSProperties = { border: 'none', borderTop: '1px solid var(--line)', margin: '24px 0' };

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
      {/* ── CONHECIMENTO ── */}
      <h2 style={sectionTitle}>// conhecimento</h2>
      <p style={sectionSub}>$ base de conhecimento do agente</p>
      <textarea
        value={newK}
        onChange={(e) => setNewK(e.target.value)}
        placeholder="Cole aqui o texto..."
        rows={4}
        style={{ ...inputStyle(), width: '100%', resize: 'vertical', lineHeight: 1.5, marginBottom: '10px' }}
      />
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'center' }}>
        <button onClick={addKnow} disabled={feeding} style={btnStyle('#4ec9b0', '#4ec9b0')}>
          {feeding ? '$ salvando...' : '$ adicionar'}
        </button>
        <button onClick={fetchKnows} style={btnStyle()}>
          $ refresh
        </button>
        {fedOk && (
          <span style={{ fontFamily: 'inherit', fontSize: '13px', fontWeight: 600, color: '#4ec9b0' }}>
            $ salvo!
          </span>
        )}
      </div>
      <input
        value={kSearch}
        onChange={(e) => setKSearch(e.target.value)}
        placeholder="Buscar..."
        style={{ ...inputStyle(), width: '100%', marginBottom: '8px' }}
      />
      {filtered.map((item) => (
        <div key={item.id} style={{ border: '1px solid var(--line)', borderRadius: '4px', padding: '12px', marginBottom: '6px', background: 'var(--bg)' }}>
          {editK?.id === item.id ? (
            <>
              <textarea
                value={editK.texto}
                onChange={(e) => setEditK({ ...editK, texto: e.target.value })}
                rows={3}
                style={{ ...inputStyle(), width: '100%', resize: 'vertical', lineHeight: 1.5, marginBottom: '6px', borderColor: 'var(--accent)' }}
              />
              <div style={{ display: 'flex', gap: '4px' }}>
                <button onClick={saveKnow} style={btnStyle('var(--accent)', 'var(--accent)')}>$ salvar</button>
                <button onClick={() => setEditK(null)} style={btnStyle()}>$ cancelar</button>
              </div>
            </>
          ) : (
            <>
              <p style={{ fontFamily: 'inherit', fontSize: '1em', fontWeight: 600, color: 'var(--ink)', margin: '0 0 8px', lineHeight: 1.5, maxHeight: '56px', overflow: 'hidden' }}>
                {item.texto}
              </p>
              <div style={{ display: 'flex', gap: '4px' }}>
                <button onClick={() => setEditK({ id: item.id, texto: item.texto })} style={btnStyle()}>$ editar</button>
                <button onClick={() => delKnow(item.id)} style={btnStyle('#f44747', '#f44747')}>$ excluir</button>
              </div>
            </>
          )}
        </div>
      ))}

      <hr style={divider} />

      {/* ── GERAR ── */}
      <GeneratePage prov={prov} model={model} apiKey={apiKey} orApiKey={orApiKey} />

      <hr style={divider} />

      {/* ── MEMORIA ── */}
      <MemoryPage />
    </div>
  );
}
