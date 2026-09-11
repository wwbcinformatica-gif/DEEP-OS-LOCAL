import React, { useEffect, useState } from 'react';
import { API_BASE } from '../lib/constants';

interface DashData {
  cpu: number;
  ram: { total_gb: number; used_gb: number; percent: number };
  vram: { total_gb: number; used_gb: number; percent: number };
  logs: string[];
  timestamp: number;
}

function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', marginTop: 3 }}>
      <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 2, transition: 'width 0.6s' }} />
    </div>
  );
}

function Card({ label, value, sub, pct, color }: { label: string; value: string; sub?: string; pct: number; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-2)',
      border: '1px solid var(--thinking-border, var(--line))',
      borderRadius: 4,
      padding: '6px 8px',
    }}>
      <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' as const, letterSpacing: '0.4px', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 1 }}>
          {sub}
        </div>
      )}
      <MiniBar pct={pct} color={color} />
    </div>
  );
}

export default function MonitorPanel() {
  const [data, setData] = useState<DashData | null>(null);
  const mountedRef = React.useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    const fetch_ = () => {
      if (!mountedRef.current) return;
      fetch(`${API_BASE}/monitor`)
        .then(r => r.json())
        .then(d => { if (mountedRef.current) setData(d); })
        .catch(() => {});
    };
    // Busca imediata
    fetch_();
    const iv = setInterval(fetch_, 3000);
    return () => { mountedRef.current = false; clearInterval(iv); };
  }, []);

  const d = data;
  const cpuPct = d?.cpu ?? 0;
  const ramPct = d?.ram?.percent ?? 0;
  const vramPct = d?.vram?.percent ?? 0;

  return (
    <div style={{
      background: 'var(--bg)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      height: '100%',
      padding: '4px 4px',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 4px',
        marginBottom: 4,
        borderBottom: '1px solid var(--thinking-border, var(--line))',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.8px', textTransform: 'uppercase' as const, color: '#4ec9b0' }}>
          MONITOR
        </span>
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: d ? '#89d185' : '#f44747', transition: 'background 0.3s' }} />
        <span style={{ fontSize: 8, color: 'var(--muted)' }}>{d ? 'atualizando...' : 'offline'}</span>
      </div>

      {/* Cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4, marginBottom: 6 }}>
        <Card
          label="CPU"
          value={cpuPct > 0 ? `${cpuPct.toFixed(0)}%` : '---'}
          pct={cpuPct}
          color={cpuPct > 80 ? '#f44747' : '#4ec9b0'}
        />
        <Card
          label="RAM"
          value={d?.ram?.used_gb != null ? `${d.ram.used_gb.toFixed(1)}GB` : '---'}
          sub={d?.ram?.percent != null ? `${d.ram.percent.toFixed(0)}% de ${(d.ram.total_gb ?? 0).toFixed(1)}GB` : ''}
          pct={ramPct}
          color={ramPct > 85 ? '#f44747' : '#89d185'}
        />
        <Card
          label="VRAM (GPU)"
          value={d?.vram?.used_gb != null && (d.vram.total_gb ?? 0) > 0 ? `${d.vram.used_gb.toFixed(1)}GB` : '---'}
          sub={d?.vram?.percent != null && (d.vram.total_gb ?? 0) > 0 ? `${d.vram.percent.toFixed(0)}% de ${(d.vram.total_gb ?? 0).toFixed(1)}GB` : d?.vram ? 'GPU não detectada' : ''}
          pct={vramPct}
          color={vramPct > 85 ? '#f44747' : '#b388ff'}
        />
      </div>

      {/* Logs */}
      {d?.logs && d.logs.length > 0 && (
        <div style={{
          flex: 1,
          overflowY: 'auto',
          background: 'var(--bg-2)',
          border: '1px solid var(--thinking-border, var(--line))',
          borderRadius: 3,
          padding: 4,
          fontFamily: "'Consolas','Courier New',monospace",
          fontSize: 10,
          lineHeight: 1.4,
        }}>
          <div style={{ fontSize: 8, color: 'var(--muted)', marginBottom: 3, textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>Logs</div>
          {d.logs.slice(-15).map((line, i) => (
            <div key={i} style={{ color: i === 0 ? '#89d185' : 'var(--muted)', whiteSpace: 'pre-wrap' as const, wordBreak: 'break-all' as const }}>
              {line}
            </div>
          ))}
        </div>
      )}
      {(!d?.logs || d.logs.length === 0) && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>(sem logs)</span>
        </div>
      )}
    </div>
  );
}
