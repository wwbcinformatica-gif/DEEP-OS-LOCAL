import React, { useState } from 'react';
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

interface GenResult {
  project_name?: string;
  project_dir?: string;
  total_files?: number;
  run_command?: string;
  test_command?: string;
  files?: { path: string; size: number }[];
}

interface Props {
  prov: string;
  model: string;
  apiKey: string;
  orApiKey: string;
}

export default function GeneratePage({ prov, model, apiKey, orApiKey }: Props) {
  const [genPrompt, setGenPrompt] = useState('');
  const [genLoading, setGenLoading] = useState(false);
  const [genLog, setGenLog] = useState<string[]>([]);
  const [genResult, setGenResult] = useState<GenResult | null>(null);

  const logColor = (l: string) => {
    if (l.startsWith('!')) return 'var(--red)';
    if (l.startsWith('$')) return 'var(--accent)';
    if (l.startsWith('  +')) return 'var(--teal)';
    if (l.startsWith('  #')) return 'var(--blue)';
    if (l.startsWith('  *')) return 'var(--yellow)';
    return 'var(--muted)';
  };

  return (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'inherit',
      }}
    >
      <h2
        style={{
          fontFamily: 'inherit',
          fontSize: '1em',
          fontWeight: 600,
          color: 'var(--teal)',
          margin: '0 0 4px',
        }}
      >
        // gerar projeto
      </h2>
      <p
        style={{
          fontFamily: 'inherit',
          fontSize: '1em',
          fontWeight: 600,
          color: 'var(--muted)',
          margin: '0 0 16px',
        }}
      >
        $ descreva o projeto que deseja criar
      </p>

      <textarea
        value={genPrompt}
        onChange={(e) => setGenPrompt(e.target.value)}
        placeholder="Ex: Crie um site de portfólio pessoal com HTML, CSS e JavaScript..."
        rows={5}
        style={{
          ...inputStyle(),
          width: '100%',
          resize: 'vertical',
          lineHeight: 1.5,
          marginBottom: '10px',
          fontFamily: 'inherit',
        }}
      />

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
        <button
          onClick={async () => {
            if (!genPrompt.trim() || genLoading) return;
            setGenLoading(true);
            setGenLog([]);
            setGenResult(null);
            const log = (msg: string) => setGenLog((p) => [...p, msg]);
            try {
              const r = await fetch(`${API_BASE}/generate/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  prompt: genPrompt,
                  provider: prov,
                  model,
                  api_key:
                    prov === 'opencode'
                      ? apiKey
                      : prov === 'openclaude'
                        ? apiKey || orApiKey
                        : prov === 'openrouter'
                          ? orApiKey
                          : '',
                }),
              });
              if (!r.ok || !r.body) {
                log('! Erro de conexao');
                setGenLoading(false);
                return;
              }
              const reader = r.body.getReader();
              const dec = new TextDecoder();
              let buf = '';
              while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buf += dec.decode(value, { stream: true });
                const lines = buf.split('\n');
                buf = lines.pop() || '';
                for (const line of lines) {
                  if (!line.trim()) continue;
                  try {
                    const ev = JSON.parse(line);
                    if (ev.type === 'status') log(`$ ${ev.message}`);
                    else if (ev.type === 'plan')
                      log(`$ plano: ${ev.data.project_name} — ${ev.data.description}`);
                    else if (ev.type === 'file')
                      log(
                        `  ${ev.data.status === 'created' ? '+' : '\u223C'} ${ev.data.path}${ev.data.size ? ` (${ev.data.size}b)` : ''}`,
                      );
                    else if (ev.type === 'fix') log(`  * fixed: ${ev.data.path}`);
                    else if (ev.type === 'test_file') log(`  # test: ${ev.data.path}`);
                    else if (ev.type === 'test_result')
                      log(
                        `$ test: ${ev.data.passed ? 'passed' : 'failed'} (exit ${ev.data.returncode})`,
                      );
                    else if (ev.type === 'dependencies')
                      log(`$ deps: ${ev.data.returncode === 0 ? 'installed' : 'error'}`);
                    else if (ev.type === 'complete') {
                      log(`$ pronto! ${ev.data.total_files} arquivos em ${ev.data.project_dir}`);
                      setGenResult(ev.data);
                    } else if (ev.type === 'error') log(`! ${ev.message}`);
                  } catch {}
                }
              }
            } catch (e: any) {
              log(`! ${e.message}`);
            }
            setGenLoading(false);
          }}
          disabled={genLoading}
          style={btnStyle('var(--teal)', 'var(--teal)')}
        >
          {genLoading ? '$ gerando...' : '$ gerar projeto'}
        </button>
        <button
          onClick={() => {
            setGenLog([]);
            setGenResult(null);
          }}
          style={btnStyle()}
        >
          $ limpar
        </button>
      </div>

      <div
        style={{
          flex: 1,
          overflow: 'auto',
          border: '1px solid var(--line)',
          borderRadius: '4px',
          padding: '12px',
          background: 'var(--bg)',
          fontFamily: 'inherit',
          fontSize: '12px',
          lineHeight: '1.6',
        }}
      >
        {genLog.length === 0 && (
          <div style={{ color: 'var(--quiet)', fontFamily: 'inherit' }}>
            // aguardando geracao...
          </div>
        )}
        {genLog.map((l, i) => (
          <div
            key={i}
            style={{ color: logColor(l), whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}
          >
            {l}
          </div>
        ))}
        {genLoading && (
          <div style={{ color: 'var(--accent)', fontFamily: 'inherit', marginTop: '4px' }}>
            processando<span style={{ animation: 'blink 1s step-end infinite' }}>_</span>
          </div>
        )}
      </div>

      {genResult && (
        <div
          style={{
            marginTop: '12px',
            padding: '12px',
            border: '1px solid var(--accent)',
            borderRadius: '4px',
            background: 'var(--bg)',
          }}
        >
          <div
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--teal)',
              marginBottom: '6px',
              fontFamily: 'inherit',
            }}
          >
            $ projeto: {genResult.project_name}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: 'inherit' }}>
            {genResult.total_files} arquivos • {genResult.project_dir}
          </div>
        </div>
      )}
    </div>
  );
}
