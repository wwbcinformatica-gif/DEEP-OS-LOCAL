import React, { useRef, useEffect, useState } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { API_BASE } from '../lib/constants';

interface TerminalPanelProps {
  termOpen: boolean;
  setTermOpen: (v: boolean) => void;
  expRoot?: string;
}

export default function TerminalPanel({ termOpen, setTermOpen, expRoot }: TerminalPanelProps) {
  const termRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sessionRef = useRef(localStorage.getItem('wbc-term-session') || '');
  const [connected, setConnected] = useState(false);
  const [reconnectKey, setReconnectKey] = useState(0);
  const [currentDir, setCurrentDir] = useState('');
  const retryRef = useRef(0);
  const maxRetries = 10;

  useEffect(() => {
    if (!termRef.current || !termOpen) return;

    // 1. Cria terminal xterm.js
    const g = getComputedStyle(document.documentElement);
    const accentHex = g.getPropertyValue('--accent').trim() || '#ff7a1a';
    const termBg = g.getPropertyValue('--terminal-bg').trim() || '#080808';
    const term = new Terminal({
      theme: {
        background: termBg,
        foreground: '#e8e8e8',
        cursor: accentHex,
        cursorAccent: '#000000',
        selectionBackground: `rgba(${parseInt(accentHex.slice(1, 3), 16)},${parseInt(accentHex.slice(3, 5), 16)},${parseInt(accentHex.slice(5, 7), 16)},0.3)`,
        black: '#000000',
        red: '#f44747',
        green: '#89d185',
        yellow: '#dcdcaa',
        blue: '#569cd6',
        magenta: '#c586c0',
        cyan: '#4ec9b0',
        white: '#e8e8e8',
        brightBlack: '#666666',
        brightRed: '#f44747',
        brightGreen: '#89d185',
        brightYellow: '#dcdcaa',
        brightBlue: '#569cd6',
        brightMagenta: '#c586c0',
        brightCyan: '#4ec9b0',
        brightWhite: '#ffffff',
      },
      fontFamily: "'SF Mono', 'Fira Code', 'Consolas', 'Courier New', monospace",
      fontSize: 12,
      cursorBlink: true,
      cursorStyle: 'bar',
      allowTransparency: true,
      cols: 80,
      rows: 24,
      convertEol: true,
      disableStdin: false,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termRef.current);
    const fitTimer = setTimeout(() => fitAddon.fit(), 100);

    xtermRef.current = term;
    fitRef.current = fitAddon;

    // 2. Focus ao clicar — garante que xterm recebe foco
    const el = termRef.current;
    const onFocus = () => term.focus();
    if (el) {
      el.addEventListener('click', onFocus);
      el.addEventListener('mousedown', onFocus);
    }
    // Foco imediato após abertura
    setTimeout(() => term.focus(), 50);

    // 3. WebSocket — conecta exclusivamente ao backend principal (powershell)
    let cancelled = false;

    const connectWs = () => {
      // Usa sessionRef.current para manter o session_id entre reconexões
      const currentSid = sessionRef.current || '';
      const wsRoot = expRoot ? `&root=${encodeURIComponent(expRoot)}` : '';
      const ws = new WebSocket(
        `${API_BASE.replace(/^http/, 'ws')}/ws/terminal?session_id=${currentSid}${wsRoot}`,
      );
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setConnected(true);
        term.focus();
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'session') {
            sessionRef.current = msg.session_id;
            localStorage.setItem('wbc-term-session', msg.session_id);
          } else if (msg.type === 'output') {
            term.write(msg.data);
          } else if (msg.type === 'clear') {
            term.clear();
          } else if (msg.type === 'cwd') {
            setCurrentDir(msg.path);
          }
        } catch {
          term.write(ev.data);
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!cancelled) {
          setConnected(false);
          // Reconexão automática com backoff exponencial
          if (retryRef.current < maxRetries) {
            const delay = Math.min(1000 * Math.pow(1.5, retryRef.current), 15000);
            retryRef.current += 1;
            setTimeout(connectWs, delay);
          }
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    // Delay inicial maior na primeira vez para dar tempo ao backend
    const initialDelay = reconnectKey === 0 ? 2000 : 300;
    const connTimer = setTimeout(connectWs, initialDelay);

    // 4. Input: teclado -> WebSocket
    const disposeData = term.onData((data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // 5. Resize
    const ro = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch {}
    });
    if (el) ro.observe(el);

    // 6. Cleanup
    return () => {
      cancelled = true;
      if (fitTimer) clearTimeout(fitTimer);
      clearTimeout(connTimer);
      ro.disconnect();
      if (el) {
        el.removeEventListener('click', onFocus);
        el.removeEventListener('mousedown', onFocus);
      }
      wsRef.current?.close();
      disposeData.dispose();
      term.dispose();
      wsRef.current = null;
    };
  }, [termOpen, reconnectKey]);

  // Auto-fit e foco ao abrir
  useEffect(() => {
    if (termOpen && fitRef.current) {
      const t = setTimeout(() => {
        try {
          fitRef.current?.fit();
          xtermRef.current?.focus();
        } catch {}
      }, 100);
      // Foco adicional após renderização completa
      const t2 = setTimeout(() => {
        try {
          xtermRef.current?.focus();
        } catch {}
      }, 500);
      return () => {
        clearTimeout(t);
        clearTimeout(t2);
      };
    }
  }, [termOpen, reconnectKey]);

  // Reconectar quando expRoot mudar (troca de projeto)
  const prevExpRootRef = useRef(expRoot);
  useEffect(() => {
    if (termOpen && expRoot && expRoot !== prevExpRootRef.current) {
      prevExpRootRef.current = expRoot;
      // Fechar WebSocket e terminal atual
      wsRef.current?.close();
      xtermRef.current?.dispose();
      // Limpar sessao para forcar nova conexao com novo root
      sessionRef.current = '';
      localStorage.removeItem('wbc-term-session');
      setReconnectKey((k) => k + 1);
    }
  }, [expRoot, termOpen]);

  const reconnect = () => {
    wsRef.current?.close();
    xtermRef.current?.dispose();
    sessionRef.current = '';
    localStorage.removeItem('wbc-term-session');
    setReconnectKey((k) => k + 1);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--terminal-bg, #080808)',
        overflow: 'hidden',
        height: '100%',
      }}
      onClick={() => xtermRef.current?.focus()}
    >
      <div
        className="panel-header"
        style={{
          background: 'var(--bg-3, #111)',
          borderBottom: '1px solid var(--line, #222)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.8px',
              textTransform: 'uppercase',
              color: 'var(--accent)',
            }}
          >
            TERMINAL
          </span>
          {currentDir && (
            <span
              style={{
                fontSize: 10,
                color: '#569cd6',
                fontFamily: "'SF Mono', 'Fira Code', monospace",
                maxWidth: 300,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                marginLeft: 4,
              }}
              title={currentDir}
            >
              {currentDir}
            </span>
          )}
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: connected ? '#89d185' : '#f44747',
              transition: 'background 0.3s',
            }}
          />
          <span style={{ fontSize: 9, color: 'var(--muted)' }}>
            {connected ? 'conectado' : 'desconectado'}
          </span>
          {!connected && (
            <button className="btn" onClick={reconnect} style={{ fontSize: 9, padding: '1px 6px' }}>
              reconectar
            </button>
          )}
        </div>
        <button
          className="btn"
          onClick={() => setTermOpen(false)}
          style={{ fontSize: 9, padding: '1px 6px' }}
        >
          ✕
        </button>
      </div>
      <div
        ref={termRef}
        style={{
          flex: 1,
          overflow: 'hidden',
          minHeight: 0,
          padding: '4px',
          cursor: 'text',
          position: 'relative',
          zIndex: 1,
        }}
        onClick={() => xtermRef.current?.focus()}
        onMouseDown={() => xtermRef.current?.focus()}
      />
    </div>
  );
}
