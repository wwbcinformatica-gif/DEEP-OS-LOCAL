import { useState } from 'react';

type ToolResponse = {
  status: string;
  stdout?: string;
  stderr?: string;
  returncode?: number;
};

export default function ToolPanel() {
  const [path, setPath] = useState('');
  const [content, setContent] = useState('');
  const [output, setOutput] = useState<ToolResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const callApi = async (endpoint: string, body: object) => {
    setLoading(true);
    try {
      const res = await fetch(`/api${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setOutput(data);
    } catch (e) {
      setOutput({ status: 'error', stderr: `${e}` });
    } finally {
      setLoading(false);
    }
  };

  const handleRead = () => callApi('/tool/read', { path, root: true });
  const handleWrite = () => callApi('/tool/write', { path, content, root: true });
  const handleBash = () => callApi('/tool/bash', { command: content, workdir: '' });

  return (
    <div style={{
      padding: 16,
      background: 'var(--bg-2)',
      color: 'var(--ink)',
      borderRadius: 8,
      boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
    }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Tool Panel</h2>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', marginBottom: 4 }}>Caminho</label>
        <input
          type="text"
          style={{
            width: '100%',
            padding: '4px 8px',
            borderRadius: 4,
            background: 'var(--bg)',
            color: 'var(--ink)',
            border: '1px solid var(--line)',
          }}
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="ex.: data/interactions.db"
        />
      </div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', marginBottom: 4 }}>Conteúdo / Comando</label>
        <textarea
          style={{
            width: '100%',
            height: 96,
            padding: '4px 8px',
            borderRadius: 4,
            background: 'var(--bg)',
            color: 'var(--ink)',
            border: '1px solid var(--line)',
            resize: 'none',
          }}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="texto para gravar ou comando bash"
        />
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          style={{
            flex: 1,
            padding: '4px 12px',
            background: '#2563eb',
            color: 'white',
            borderRadius: 4,
            border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.5 : 1,
          }}
          onClick={handleRead}
          disabled={loading}
        >
          Read
        </button>
        <button
          style={{
            flex: 1,
            padding: '4px 12px',
            background: '#16a34a',
            color: 'white',
            borderRadius: 4,
            border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.5 : 1,
          }}
          onClick={handleWrite}
          disabled={loading}
        >
          Write
        </button>
        <button
          style={{
            flex: 1,
            padding: '4px 12px',
            background: '#9333ea',
            color: 'white',
            borderRadius: 4,
            border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.5 : 1,
          }}
          onClick={handleBash}
          disabled={loading}
        >
          Bash
        </button>
      </div>
      {output && (
        <div style={{
          marginTop: 12,
          padding: 8,
          background: 'var(--bg)',
          borderRadius: 4,
          fontSize: 12,
          overflow: 'auto',
          maxHeight: 192,
        }}>
          <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
            {output.status === 'ok'
              ? `STDOUT:\n${output.stdout}\nSTDERR:\n${output.stderr}`
              : `Erro:\n${output.stderr || 'Desconhecido'}`}
          </pre>
        </div>
      )}
    </div>
  );
}
