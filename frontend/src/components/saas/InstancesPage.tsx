import React, { useState, useEffect } from 'react';

interface Instance {
  id: string;
  name: string;
  status: string;
  model: string;
  provider: string;
  messages_used: number;
  message_limit: number;
  system_prompt: string;
  temperature: number;
  created_at: string;
}

const MODELS = [
  { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', provider: 'gemini' },
  { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash', provider: 'gemini' },
  { id: 'openrouter/auto', label: 'OpenRouter Auto', provider: 'openrouter' },
  { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini', provider: 'openrouter' },
  { id: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B', provider: 'openrouter' },
];

const InstancesPage: React.FC = () => {
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewModal, setShowNewModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState<string | null>(null);
  const [newInstanceName, setNewInstanceName] = useState('');
  const [newInstanceModel, setNewInstanceModel] = useState('gemini-2.5-flash');
  const [configData, setConfigData] = useState<Instance | null>(null);

  const fetchInstances = async () => {
    try {
      const res = await fetch('/api/instances');
      if (res.ok) {
        const data = await res.json();
        setInstances(data.instances || []);
      }
    } catch (e) {
      console.error('Erro ao buscar instancias:', e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchInstances(); }, []);

  const handleCreate = async () => {
    if (!newInstanceName.trim()) return;
    const model = MODELS.find(m => m.id === newInstanceModel);
    try {
      const res = await fetch('/api/instances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newInstanceName, model: newInstanceModel, provider: model?.provider || 'gemini' }),
      });
      if (res.ok) {
        setNewInstanceName('');
        setNewInstanceModel('gemini-2.5-flash');
        setShowNewModal(false);
        fetchInstances();
      }
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Excluir esta instancia?')) return;
    try {
      await fetch(`/api/instances/${id}`, { method: 'DELETE' });
      fetchInstances();
    } catch (e) { console.error(e); }
  };

  const handleConfig = (inst: Instance) => {
    setConfigData({ ...inst });
    setShowConfigModal(inst.id);
  };

  const handleSaveConfig = async () => {
    if (!configData) return;
    try {
      await fetch(`/api/instances/${configData.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: configData.name,
          model: configData.model,
          provider: configData.provider,
          system_prompt: configData.system_prompt,
          temperature: configData.temperature,
        }),
      });
      setShowConfigModal(null);
      setConfigData(null);
      fetchInstances();
    } catch (e) { console.error(e); }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#10b981';
      case 'inactive': return '#6b7280';
      case 'error': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const [showHelp, setShowHelp] = useState(false);

  if (loading) return <div style={{ padding: 40, color: '#999' }}>Carregando...</div>;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div>
            <h1 style={styles.title}>Instâncias</h1>
            <p style={styles.subtitle}>Gerencie seus agentes de IA</p>
          </div>
          <button onClick={() => setShowHelp(!showHelp)} title="Ajuda" style={styles.helpBtn}>?</button>
        </div>
        <button style={styles.newButton} onClick={() => setShowNewModal(true)}>+ Nova Instância</button>
      </div>

      {showHelp && (
        <div style={styles.helpBox}>
          <h3 style={styles.helpTitle}>📖 Como funcionam as Instâncias</h3>
          <p style={styles.helpText}>
            <strong>O que é uma Instância?</strong><br/>
            Uma instância é um agente de IA personalizado. Cada instância tem seu próprio modelo, configurações e limite de mensagens.
          </p>
          <p style={styles.helpText}>
            <strong>Como criar:</strong><br/>
            1. Clique em "+ Nova Instância"<br/>
            2. Dê um nome (ex: "Atendimento", "Pesquisador")<br/>
            3. Escolha o modelo de IA<br/>
            4. Clique em "Criar"
          </p>
          <p style={styles.helpText}>
            <strong>Configurar:</strong><br/>
            Clique em "⚙️ Configurar" para ajustar:<br/>
            • <strong>Nome:</strong> renomeie a instância<br/>
            • <strong>Modelo:</strong> troque entre Gemini, OpenRouter, etc<br/>
            • <strong>Temperatura:</strong> 0 = preciso, 1 = criativo<br/>
            • <strong>Prompt do Sistema:</strong> instruções personalizadas (ex: "Responda como advogado")
          </p>
          <p style={styles.helpText}>
            <strong>Modelos disponíveis:</strong><br/>
            • <strong>Gemini 2.5 Flash:</strong> rápido e gratuito (Google)<br/>
            • <strong>GPT-4o Mini:</strong> OpenAI via OpenRouter<br/>
            • <strong>Llama 3.3 70B:</strong> Meta via OpenRouter
          </p>
          <p style={styles.helpText}>
            <strong>Limite de mensagens:</strong><br/>
            Cada instância tem um limite de 20 mensagens (plano free). Faça upgrade para aumentar.
          </p>
          <p style={styles.helpText}>
            <strong>Excluir:</strong><br/>
            Clique em "Excluir" para remover permanentemente a instância e seus dados.
          </p>
        </div>
      )}

      <div style={styles.stats}>
        <div style={styles.statCard}>
          <span style={styles.statValue}>{instances.length}</span>
          <span style={styles.statLabel}>Total</span>
        </div>
        <div style={styles.statCard}>
          <span style={{...styles.statValue, color: '#10b981'}}>{instances.filter(i => i.status === 'active').length}</span>
          <span style={styles.statLabel}>Ativas</span>
        </div>
      </div>

      <div style={styles.instancesList}>
        {instances.map((inst) => (
          <div key={inst.id} style={styles.instanceCard}>
            <div style={styles.instanceHeader}>
              <div style={styles.instanceInfo}>
                <h3 style={styles.instanceName}>{inst.name}</h3>
                <span style={{...styles.statusBadge, backgroundColor: getStatusColor(inst.status) + '20', color: getStatusColor(inst.status)}}>
                  {inst.status === 'active' ? 'Ativa' : inst.status === 'inactive' ? 'Inativa' : 'Erro'}
                </span>
              </div>
              <div style={styles.instanceActions}>
                <button style={styles.actionButton} onClick={() => handleConfig(inst)}>⚙️ Configurar</button>
                <button style={{...styles.actionButton, ...styles.deleteButton}} onClick={() => handleDelete(inst.id)}>Excluir</button>
              </div>
            </div>
            <div style={styles.instanceDetails}>
              <div style={styles.detailItem}>
                <span style={styles.detailLabel}>Modelo:</span>
                <span style={styles.detailValue}>{inst.model}</span>
              </div>
              <div style={styles.detailItem}>
                <span style={styles.detailLabel}>Mensagens:</span>
                <span style={styles.detailValue}>{inst.messages_used}/{inst.message_limit}</span>
              </div>
              <div style={styles.detailItem}>
                <span style={styles.detailLabel}>Criada em:</span>
                <span style={styles.detailValue}>{inst.created_at?.substring(0, 10) || '-'}</span>
              </div>
            </div>
            <div style={styles.usageBar}>
              <div style={{...styles.usageProgress, width: `${Math.min(100, (inst.messages_used / inst.message_limit) * 100)}%`}} />
            </div>
          </div>
        ))}

        {instances.length === 0 && (
          <div style={styles.emptyState}>
            <span style={styles.emptyIcon}>⚡</span>
            <h3>Nenhuma instancia criada</h3>
            <p>Crie sua primeira instancia para comecar a usar os agentes de IA.</p>
            <button style={styles.newButton} onClick={() => setShowNewModal(true)}>+ Criar Primeira Instancia</button>
          </div>
        )}
      </div>

      {showNewModal && (
        <div style={styles.modalOverlay} onClick={() => setShowNewModal(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Nova Instancia</h2>
            <div style={styles.formGroup}>
              <label style={styles.label}>Nome</label>
              <input type="text" value={newInstanceName} onChange={(e) => setNewInstanceName(e.target.value)} placeholder="Ex: Meu Agente" style={styles.input} />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Modelo de IA</label>
              <select value={newInstanceModel} onChange={(e) => setNewInstanceModel(e.target.value)} style={styles.select}>
                {MODELS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </div>
            <div style={styles.modalActions}>
              <button style={styles.cancelButton} onClick={() => setShowNewModal(false)}>Cancelar</button>
              <button style={styles.createButton} onClick={handleCreate}>Criar</button>
            </div>
          </div>
        </div>
      )}

      {showConfigModal && configData && (
        <div style={styles.modalOverlay} onClick={() => setShowConfigModal(null)}>
          <div style={{...styles.modal, maxWidth: 500}} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Configurar: {configData.name}</h2>
            <div style={styles.formGroup}>
              <label style={styles.label}>Nome</label>
              <input type="text" value={configData.name} onChange={(e) => setConfigData({...configData, name: e.target.value})} style={styles.input} />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Modelo</label>
              <select value={configData.model} onChange={(e) => {
                const m = MODELS.find(m => m.id === e.target.value);
                setConfigData({...configData, model: e.target.value, provider: m?.provider || 'gemini'});
              }} style={styles.select}>
                {MODELS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Temperatura: {configData.temperature?.toFixed(1)}</label>
              <input type="range" min="0" max="1" step="0.1" value={configData.temperature || 0.7} onChange={(e) => setConfigData({...configData, temperature: parseFloat(e.target.value)})} style={{ width: '100%' }} />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Prompt do Sistema (opcional)</label>
              <textarea value={configData.system_prompt || ''} onChange={(e) => setConfigData({...configData, system_prompt: e.target.value})} placeholder="Instrucoes personalizadas para este agente..." style={{...styles.input, minHeight: 80, resize: 'vertical'}} />
            </div>
            <div style={styles.modalActions}>
              <button style={styles.cancelButton} onClick={() => setShowConfigModal(null)}>Cancelar</button>
              <button style={styles.createButton} onClick={handleSaveConfig}>Salvar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '40px', color: '#ffffff' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' },
  title: { fontSize: '28px', fontWeight: 'bold', margin: '0 0 8px 0' },
  subtitle: { color: '#a0a0a0', margin: 0 },
  newButton: { background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)', color: '#000', border: 'none', borderRadius: '8px', padding: '12px 24px', fontSize: '14px', fontWeight: '600', cursor: 'pointer' },
  stats: { display: 'flex', gap: '16px', marginBottom: '32px' },
  statCard: { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '120px' },
  statValue: { fontSize: '28px', fontWeight: 'bold', color: '#00d9ff' },
  statLabel: { fontSize: '12px', color: '#a0a0a0', marginTop: '4px' },
  instancesList: { display: 'flex', flexDirection: 'column', gap: '16px' },
  instanceCard: { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', padding: '20px' },
  instanceHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' },
  instanceInfo: { display: 'flex', alignItems: 'center', gap: '12px' },
  instanceName: { margin: 0, fontSize: '18px', fontWeight: '600' },
  statusBadge: { padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: '500' },
  instanceActions: { display: 'flex', gap: '8px' },
  actionButton: { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '8px 12px', color: '#a0a0a0', fontSize: '12px', cursor: 'pointer' },
  deleteButton: { color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)' },
  instanceDetails: { display: 'flex', gap: '24px', marginBottom: '16px' },
  detailLabel: { fontSize: '12px', color: '#a0a0a0', display: 'block' },
  detailValue: { fontSize: '14px', color: '#ffffff' },
  usageBar: { height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' },
  usageProgress: { height: '100%', background: 'linear-gradient(90deg, #00d9ff 0%, #00ff88 100%)', borderRadius: '2px', transition: 'width 0.3s' },
  emptyState: { textAlign: 'center', padding: '60px 40px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.1)' },
  emptyIcon: { fontSize: '48px', display: 'block', marginBottom: '16px' },
  modalOverlay: { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
  modal: { background: '#1a1a2e', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '400px', border: '1px solid rgba(255,255,255,0.1)' },
  modalTitle: { margin: '0 0 24px 0', fontSize: '20px', fontWeight: 'bold' },
  formGroup: { marginBottom: '20px' },
  label: { display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' },
  input: { width: '100%', padding: '12px 16px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff', fontSize: '14px', boxSizing: 'border-box' },
  select: { width: '100%', padding: '12px 16px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff', fontSize: '14px', boxSizing: 'border-box' },
  modalActions: { display: 'flex', gap: '12px', justifyContent: 'flex-end' },
  cancelButton: { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '10px 20px', color: '#a0a0a0', cursor: 'pointer' },
  createButton: { background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)', border: 'none', borderRadius: '8px', padding: '10px 20px', color: '#000', fontWeight: '600', cursor: 'pointer' },
  helpBtn: { width: 28, height: 28, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(255,255,255,0.05)', color: '#00d9ff', fontSize: 14, fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  helpBox: { background: 'rgba(0,217,255,0.05)', border: '1px solid rgba(0,217,255,0.2)', borderRadius: 12, padding: 20, marginBottom: 24 },
  helpTitle: { margin: '0 0 12px 0', fontSize: 16, color: '#00d9ff' },
  helpText: { fontSize: 13, color: '#ccc', lineHeight: 1.6, margin: '0 0 12px 0' },
};

export default InstancesPage;