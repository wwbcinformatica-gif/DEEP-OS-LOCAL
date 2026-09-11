import React, { useEffect, useState } from 'react';
import { API_BASE } from '../lib/constants';

interface McpServerEntry {
  type: 'local' | 'remote';
  command?: string[];
  url?: string;
  enabled: boolean;
  environment?: Record<string, string>;
  headers?: Record<string, string>;
  timeout?: number;
}

interface RunningServer {
  [serverKey: string]: {
    type: string;
    config: any;
    tools?: { name: string; description?: string; inputSchema?: any }[];
  };
}

const base: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--font-size-base)',
  fontWeight: 600,
  color: 'var(--ink)',
};

function s(extra: React.CSSProperties = {}): React.CSSProperties {
  return { ...base, ...extra };
}

function inputStyle(): React.CSSProperties {
  return {
    background: 'transparent',
    border: '1px solid var(--line-strong)',
    borderRadius: '4px',
    color: 'var(--ink)',
    padding: '6px 10px',
    outline: 'none',
    ...base,
    width: '100%',
  };
}

function btnStyle(c: string, b?: string): React.CSSProperties {
  return {
    background: 'transparent',
    border: `1px solid ${b || 'var(--line-strong)'}`,
    borderRadius: '4px',
    color: c,
    cursor: 'pointer',
    padding: '4px 10px',
    ...base,
    fontSize: '11px',
  };
}

export default function MCPPage() {
  const [servers, setServers] = useState<Record<string, McpServerEntry>>({});
  const [running, setRunning] = useState<RunningServer>({});
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');

  // New server form
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState<'local' | 'remote'>('local');
  const [newCommand, setNewCommand] = useState('');
  const [newUrl, setNewUrl] = useState('');
  const [newEnabled, setNewEnabled] = useState(true);
  const [newEnv, setNewEnv] = useState('');
  const [newHeaders, setNewHeaders] = useState('');
  const [editing, setEditing] = useState<string | null>(null);

  const toastMsg = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2500);
  };

  const fetchConfig = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/config/mcp-servers`);
      if (r.ok) {
        const data = await r.json();
        setServers(data.servers || {});
      }
    } catch {}
  };

  const fetchRunning = async () => {
    try {
      const r = await fetch(`${API_BASE}/plugins/servers`);
      if (r.ok) {
        const data = await r.json();
        setRunning(data.servers || {});
      }
    } catch {}
  };

  const refresh = async () => {
    setLoading(true);
    await Promise.all([fetchConfig(), fetchRunning()]);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  const saveServer = async () => {
    const name = editing || newName;
    if (!name.trim()) {
      toastMsg('$ nome obrigatorio');
      return;
    }
    const entry: McpServerEntry = { type: newType, enabled: newEnabled };
    if (newType === 'local' && newCommand.trim()) {
      entry.command = newCommand.split(/\s+/).filter(Boolean);
    }
    if (newType === 'remote' && newUrl.trim()) {
      entry.url = newUrl.trim();
    }
    if (newEnv.trim()) {
      try {
        entry.environment = JSON.parse(newEnv);
      } catch {
        toastMsg('$ env JSON invalido');
        return;
      }
    }
    if (newHeaders.trim()) {
      try {
        entry.headers = JSON.parse(newHeaders);
      } catch {
        toastMsg('$ headers JSON invalido');
        return;
      }
    }
    try {
      const r = await fetch(`${API_BASE}/api/config/mcp-servers/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      });
      if (r.ok) {
        toastMsg(`$ servidor '${name}' salvo`);
        resetForm();
        await fetchConfig();
      } else {
        const err = await r.json();
        toastMsg(`$ erro: ${err.detail}`);
      }
    } catch (e) {
      toastMsg('$ erro ao salvar servidor');
    }
  };

  const deleteServer = async (name: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/config/mcp-servers/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      });
      if (r.ok) {
        toastMsg(`$ servidor '${name}' removido`);
        await fetchConfig();
      }
    } catch {}
  };

  const initServer = async (name: string) => {
    try {
      const r = await fetch(`${API_BASE}/plugins/${encodeURIComponent(name)}/init`, {
        method: 'POST',
      });
      if (r.ok) {
        toastMsg(`$ plugin '${name}' inicializado`);
        await fetchRunning();
      } else {
        const err = await r.json();
        toastMsg(`$ erro: ${err.detail}`);
      }
    } catch {}
  };

  const shutdownAll = async () => {
    try {
      await fetch(`${API_BASE}/plugins/shutdown`, { method: 'POST' });
      toastMsg('$ servores MCP desligados');
      await fetchRunning();
    } catch {}
  };

  const editServer = (name: string) => {
    const srv = servers[name];
    if (!srv) return;
    setEditing(name);
    setNewName(name);
    setNewType(srv.type);
    setNewCommand(srv.command?.join(' ') || '');
    setNewUrl(srv.url || '');
    setNewEnabled(srv.enabled);
    setNewEnv(srv.environment ? JSON.stringify(srv.environment, null, 2) : '');
    setNewHeaders(srv.headers ? JSON.stringify(srv.headers, null, 2) : '');
  };

  const resetForm = () => {
    setEditing(null);
    setNewName('');
    setNewType('local');
    setNewCommand('');
    setNewUrl('');
    setNewEnabled(true);
    setNewEnv('');
    setNewHeaders('');
  };

  const card: React.CSSProperties = {
    border: '1px solid var(--line)',
    borderRadius: '4px',
    padding: '16px',
    background: 'var(--bg)',
  };

  const h3: React.CSSProperties = {
    ...base,
    fontSize: '1em',
    fontWeight: 600,
    color: 'var(--ink)',
    marginBottom: '10px',
  };

  const labelStyle: React.CSSProperties = {
    ...base,
    fontSize: '11px',
    color: 'var(--muted)',
    marginBottom: '6px',
    marginTop: '10px',
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle(),
    cursor: 'pointer',
  };

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
      <h2 style={s({ color: 'var(--accent)', marginBottom: '4px' })}>// servidores MCP</h2>
      <p style={s({ color: 'var(--accent-2)', marginBottom: '20px' })}>$ model context protocol</p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '14px',
          maxWidth: '1000px',
        }}
      >
        {/* New / Edit server form */}
        <div style={card}>
          <h3 style={h3}>{editing ? '~ editar servidor' : '> novo servidor'}</h3>

          <div style={labelStyle}>Nome</div>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="ex: meu-servidor-mcp"
            style={inputStyle()}
            disabled={!!editing}
          />

          <div style={labelStyle}>Tipo</div>
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as any)}
            style={selectStyle}
          >
            <option value="local">Local (stdio)</option>
            <option value="remote">Remoto (HTTP)</option>
          </select>

          {newType === 'local' ? (
            <>
              <div style={labelStyle}>Comando</div>
              <input
                value={newCommand}
                onChange={(e) => setNewCommand(e.target.value)}
                placeholder="ex: npx -y @modelcontextprotocol/server-everything"
                style={inputStyle()}
              />
            </>
          ) : (
            <>
              <div style={labelStyle}>URL</div>
              <input
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="ex: https://mcp.meuservidor.com"
                style={inputStyle()}
              />
            </>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '12px' }}>
            <span style={s({ fontSize: '11px', color: 'var(--muted)' })}>Ativo</span>
            <div
              onClick={() => setNewEnabled(!newEnabled)}
              style={{
                width: 34,
                height: 18,
                borderRadius: 3,
                cursor: 'pointer',
                position: 'relative',
                background: newEnabled ? 'var(--accent)' : 'var(--line-strong)',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: 2,
                  background: 'var(--muted)',
                  position: 'absolute',
                  top: 2,
                  left: newEnabled ? 18 : 2,
                  transition: 'left 0.2s',
                }}
              />
            </div>
          </div>

          <div style={labelStyle}>Environment (JSON opcional)</div>
          <textarea
            value={newEnv}
            onChange={(e) => setNewEnv(e.target.value)}
            placeholder='{"API_KEY": "..."}'
            rows={2}
            style={{
              ...inputStyle(),
              resize: 'vertical',
              lineHeight: 1.4,
              fontFamily: 'inherit',
              fontSize: '11px',
            }}
          />

          <div style={labelStyle}>Headers (JSON opcional, remoto)</div>
          <textarea
            value={newHeaders}
            onChange={(e) => setNewHeaders(e.target.value)}
            placeholder='{"Authorization": "Bearer ..."}'
            rows={2}
            style={{
              ...inputStyle(),
              resize: 'vertical',
              lineHeight: 1.4,
              fontFamily: 'inherit',
              fontSize: '11px',
            }}
          />

          <div style={{ display: 'flex', gap: '8px', marginTop: '14px' }}>
            <button onClick={saveServer} style={btnStyle('var(--accent)', 'var(--accent)')}>
              {editing ? '$ salvar alteracoes' : '$ adicionar servidor'}
            </button>
            {editing && (
              <button onClick={resetForm} style={btnStyle('var(--muted)')}>
                $ cancelar
              </button>
            )}
          </div>
        </div>

        {/* Server list */}
        <div style={card}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '10px',
            }}
          >
            <h3 style={{ ...h3, marginBottom: 0 }}>{'>'} servidores configurados</h3>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button onClick={shutdownAll} style={btnStyle('var(--red)')}>
                $ desligar todos
              </button>
              <button onClick={() => refresh()} style={btnStyle('var(--accent-2)')}>
                $ atualizar
              </button>
            </div>
          </div>
          {loading ? (
            <p style={s({ color: 'var(--muted)' })}>carregando...</p>
          ) : Object.keys(servers).length === 0 ? (
            <p style={s({ color: 'var(--muted)' })}>nenhum servidor MCP configurado</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(servers).map(([name, srv]) => {
                const isRunning = Object.keys(running).some((k) => k.includes(name));
                return (
                  <div
                    key={name}
                    style={{
                      border: '1px solid var(--line)',
                      borderRadius: '4px',
                      padding: '10px 12px',
                      background: 'var(--bg-2)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            background: isRunning
                              ? 'var(--teal)'
                              : srv.enabled
                                ? 'var(--accent-2)'
                                : 'var(--red)',
                            flexShrink: 0,
                          }}
                        />
                        <span style={s({ fontSize: '12px' })}>{name}</span>
                        <span style={s({ fontSize: '10px', color: 'var(--muted)' })}>
                          {srv.type === 'local' ? 'stdio' : 'http'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          onClick={() => editServer(name)}
                          style={btnStyle('var(--accent-2)')}
                        >
                          editar
                        </button>
                        <button
                          onClick={() => initServer(name)}
                          style={btnStyle('var(--teal)')}
                          title="Inicializar plugin"
                        >
                          init
                        </button>
                        <button onClick={() => deleteServer(name)} style={btnStyle('var(--red)')}>
                          remover
                        </button>
                      </div>
                    </div>
                    {srv.type === 'local' && srv.command && (
                      <div style={s({ fontSize: '10px', color: 'var(--muted)', marginTop: '4px' })}>
                        $ {srv.command.join(' ')}
                      </div>
                    )}
                    {srv.type === 'remote' && srv.url && (
                      <div style={s({ fontSize: '10px', color: 'var(--muted)', marginTop: '4px' })}>
                        {srv.url}
                      </div>
                    )}
                    {srv.environment && Object.keys(srv.environment).length > 0 && (
                      <div style={s({ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' })}>
                        env: {Object.keys(srv.environment).join(', ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Running servers status */}
        <div style={card}>
          <h3 style={h3}>{'>'} servidores ativos</h3>
          {Object.keys(running).length === 0 ? (
            <p style={s({ color: 'var(--muted)' })}>nenhum servidor ativo no momento</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(running).map(([key, srv]) => (
                <div
                  key={key}
                  style={{
                    border: '1px solid var(--line)',
                    borderRadius: '4px',
                    padding: '10px 12px',
                    background: 'var(--bg-2)',
                  }}
                >
                  <div style={s({ fontSize: '11px', color: 'var(--teal)', marginBottom: '4px' })}>
                    {'>'} {key}
                  </div>
                  {srv.tools && srv.tools.length > 0 && (
                    <div
                      style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}
                    >
                      {srv.tools.map((t: any) => (
                        <span
                          key={t.name}
                          style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: 'var(--accent)',
                            color: 'var(--selection-fg)',
                          }}
                        >
                          {t.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 36,
            right: 16,
            background: 'var(--bg)',
            border: '1px solid var(--teal)',
            borderRadius: '4px',
            padding: '6px 14px',
            color: 'var(--teal)',
            fontSize: '11px',
            zIndex: 9999,
            fontWeight: 600,
            fontFamily: 'inherit',
            boxShadow: '0 4px 12px var(--line)',
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}
