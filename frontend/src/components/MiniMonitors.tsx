import React, { useEffect, useState } from 'react';
import { API_BASE } from '../lib/constants';

interface DashData {
  cpu: number;
  ram: { total_gb: number; used_gb: number; percent: number };
  vram: { total_gb: number; used_gb: number; percent: number };
}

export default function MiniMonitors() {
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
    fetch_();
    const iv = setInterval(fetch_, 5000);
    return () => { mountedRef.current = false; clearInterval(iv); };
  }, []);

  const d = data;
  const cpuPct = d?.cpu ?? 0;
  const ramPct = d?.ram?.percent ?? 0;
  const vramPct = d?.vram?.percent ?? 0;

  const barStyle = (pct: number, color: string): React.CSSProperties => ({
    width: 60,
    height: 4,
    borderRadius: 2,
    background: 'var(--bg-4)',
    overflow: 'hidden',
    position: 'relative' as const,
  });

  const fillStyle = (pct: number, color: string): React.CSSProperties => ({
    width: `${Math.min(pct, 100)}%`,
    height: '100%',
    borderRadius: 2,
    background: color,
    transition: 'width 0.5s ease',
  });

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '0 4px' }}>
      {/* CPU */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ fontSize: 9, color: 'var(--muted)', fontWeight: 600 }}>CPU</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: cpuPct > 80 ? '#f44747' : '#4ec9b0' }}>
          {cpuPct > 0 ? `${cpuPct.toFixed(0)}%` : '---'}
        </span>
        <div style={barStyle(cpuPct, '#4ec9b0')}>
          <div style={fillStyle(cpuPct, cpuPct > 80 ? '#f44747' : '#4ec9b0')} />
        </div>
      </div>
      {/* RAM */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ fontSize: 9, color: 'var(--muted)', fontWeight: 600 }}>RAM</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: ramPct > 85 ? '#f44747' : '#89d185' }}>
          {d?.ram?.used_gb != null ? `${d.ram.used_gb.toFixed(1)}G` : '---'}
        </span>
        <span style={{ fontSize: 8, color: 'var(--muted)' }}>
          {d?.ram?.percent != null ? `${d.ram.percent.toFixed(0)}%` : ''}
        </span>
        <div style={barStyle(ramPct, '#89d185')}>
          <div style={fillStyle(ramPct, ramPct > 85 ? '#f44747' : '#89d185')} />
        </div>
      </div>
      {/* GPU */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ fontSize: 9, color: 'var(--muted)', fontWeight: 600 }}>GPU</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: vramPct > 85 ? '#f44747' : '#b388ff' }}>
          {d?.vram?.used_gb != null && (d.vram.total_gb ?? 0) > 0 ? `${d.vram.used_gb.toFixed(1)}G` : '---'}
        </span>
        <span style={{ fontSize: 8, color: 'var(--muted)' }}>
          {d?.vram?.percent != null && (d.vram.total_gb ?? 0) > 0 ? `${d.vram.percent.toFixed(0)}%` : ''}
        </span>
        <div style={barStyle(vramPct, '#b388ff')}>
          <div style={fillStyle(vramPct, vramPct > 85 ? '#f44747' : '#b388ff')} />
        </div>
      </div>
    </div>
  );
}
