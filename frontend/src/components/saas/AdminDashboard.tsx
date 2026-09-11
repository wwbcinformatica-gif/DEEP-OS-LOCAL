import React, { useEffect, useState } from 'react';
import AdminLogin from './AdminLogin';

interface AdminDashboardProps {
  onLogout: () => void;
}

const AdminDashboard: React.FC<AdminDashboardProps> = ({ onLogout }) => {
  const [isAdminAuth, setIsAdminAuth] = useState(() => !!localStorage.getItem('admin_token'));
  const [stats, setStats] = useState<any>(null);
  const [tenants, setTenants] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'tenants' | 'plans' | 'products' | 'payments'>('overview');
  const [editingTenant, setEditingTenant] = useState<any>(null);
  const [editingPlan, setEditingPlan] = useState<any>(null);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [newPlan, setNewPlan] = useState({ id: '', name: '', price: 0, interval: 'month', description: '', discount_percent: 0, is_active: true });
  const [editingProduct, setEditingProduct] = useState<any>(null);
  const [creatingTenant, setCreatingTenant] = useState(false);
  const [creatingProduct, setCreatingProduct] = useState(false);
  const [newTenant, setNewTenant] = useState({ name: '', email: '', password: '', plan: 'free', company: '', phone: '' });
  const [newProduct, setNewProduct] = useState({ name: '', description: '', icon: '📦', image_url: '', category: 'Geral', price: 0, original_price: 0, badge: '', badge_color: '', features: '', download_url: '', status: 'available', sort_order: 0 });
  const [uploading, setUploading] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<any>(null);
  const [tenantProducts, setTenantProducts] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [pendingPayments, setPendingPayments] = useState<any[]>([]);
  const [paymentHistory, setPaymentHistory] = useState<any[]>([]);
  const [pixConfig, setPixConfig] = useState({ pix_key: '', pix_type: 'random', owner_name: '', instructions: '', pix_qr: '' });
  const token = localStorage.getItem('admin_token');

  useEffect(() => {
    if (isAdminAuth && token) fetchData();
  }, [isAdminAuth]);

  const fetchData = async () => {
    setError('');
    try {
      const [statsRes, tenantsRes, plansRes, productsRes, paymentsRes, historyRes, pixRes] = await Promise.all([
        fetch('/admin/dashboard/stats', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/admin/tenants?limit=50', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/admin/plans', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/admin/products', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/admin/payments/pending', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/admin/payments/all', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/admin/pix', { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      else setError('Stats: ' + statsRes.status);
      if (tenantsRes.ok) { const d = await tenantsRes.json(); setTenants(d.tenants || []); }
      if (plansRes.ok) { const d = await plansRes.json(); setPlans(d.plans || []); }
      if (productsRes.ok) { const d = await productsRes.json(); setProducts(d.products || []); }
      if (paymentsRes.ok) { const d = await paymentsRes.json(); setPendingPayments(d.payments || []); }
      if (historyRes.ok) { const d = await historyRes.json(); setPaymentHistory(d.payments || []); }
      if (pixRes.ok) { const d = await pixRes.json(); setPixConfig(d); }
    } catch (e: any) { setError(e.message); }
  };

  const handleSuspend = async (id: string) => {
    if (!confirm('Suspender este usuario?')) return;
    await fetch(`/admin/tenants/${id}/suspend`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    fetchData();
  };

  const handleReactivate = async (id: string) => {
    await fetch(`/admin/tenants/${id}/reactivate`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    fetchData();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Excluir este usuario?')) return;
    await fetch(`/admin/tenants/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
    fetchData();
  };

  const handleSaveTenant = async () => {
    if (!editingTenant) return;
    try {
      const res = await fetch(`/admin/tenants/${editingTenant.id}/edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: editingTenant.name, email: editingTenant.email, plan: editingTenant.plan, status: editingTenant.status }),
      });
      if (res.ok) {
        alert('Usuario atualizado com sucesso!');
      }
    } catch (e) {
      alert('Erro ao salvar');
    }
    setEditingTenant(null);
    fetchData();
  };

  const handleCreateTenant = async () => {
    if (!newTenant.name || !newTenant.email || !newTenant.password) {
      alert('Preencha nome, email e senha!');
      return;
    }
    try {
      const res = await fetch('/admin/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(newTenant),
      });
      if (res.ok) {
        alert('Usuario criado com sucesso!');
        setCreatingTenant(false);
        setNewTenant({ name: '', email: '', password: '', plan: 'free', company: '', phone: '' });
        fetchData();
      } else {
        const d = await res.json();
        alert('Erro: ' + (d.detail || 'desconhecido'));
      }
    } catch (e: any) {
      alert('Erro ao criar: ' + e.message);
    }
  };

  const handleCreateProduct = async () => {
    if (!newProduct.name) { alert('Nome obrigatorio!'); return; }
    const body = { ...newProduct, features: newProduct.features.split(',').map(f => f.trim()).filter(Boolean) };
    try {
      const res = await fetch('/admin/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        alert('Produto criado!');
        setCreatingProduct(false);
        setNewProduct({ name: '', description: '', icon: '📦', image_url: '', category: 'Geral', price: 0, original_price: 0, badge: '', badge_color: '', features: '', download_url: '', status: 'available', sort_order: 0 });
        fetchData();
      } else {
        const d = await res.json();
        alert('Erro: ' + (d.detail || 'desconhecido'));
      }
    } catch (e: any) { alert('Erro: ' + e.message); }
  };

  const handleSaveProduct = async () => {
    if (!editingProduct) return;
    const body = { ...editingProduct, features: Array.isArray(editingProduct.features) ? editingProduct.features : editingProduct.features.split(',').map((f: string) => f.trim()).filter(Boolean) };
    await fetch(`/admin/products/${editingProduct.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    });
    setEditingProduct(null);
    fetchData();
  };

  const handleDeleteProduct = async (id: string) => {
    if (!confirm('Excluir este produto?')) return;
    await fetch(`/admin/products/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
    fetchData();
  };

  const handleUploadFile = async (e: React.ChangeEvent<HTMLInputElement>, target: 'new' | 'edit') => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const reader = new FileReader();
      reader.onload = async () => {
        const base64 = (reader.result as string).split(',')[1];
        const res = await fetch('/admin/upload-file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ filename: file.name, content_base64: base64, content_type: file.type }),
        });
        if (res.ok) {
          const data = await res.json();
          if (target === 'new') {
            setNewProduct({ ...newProduct, download_url: data.download_url });
          } else {
            setEditingProduct({ ...editingProduct, download_url: data.download_url });
          }
          alert(`Arquivo uploadado! URL: ${data.download_url}`);
        } else {
          const err = await res.json();
          alert('Erro: ' + (err.detail || 'falha no upload'));
        }
        setUploading(false);
      };
      reader.readAsDataURL(file);
    } catch (err: any) {
      alert('Erro: ' + err.message);
      setUploading(false);
    }
  };

  const handleOpenTenantProducts = async (tenant: any) => {
    setSelectedTenant(tenant);
    const res = await fetch(`/admin/tenants/${tenant.id}/all-products`, { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) { const d = await res.json(); setTenantProducts(d.products || []); }
  };

  const handleConfirmPayment = async (tenantId: string, planId: string, amount: number) => {
    if (!confirm('Confirmar pagamento e ativar plano?')) return;
    try {
      const res = await fetch('/admin/payments/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ tenant_id: tenantId, plan_id: planId, amount }),
      });
      if (res.ok) {
        alert('Pagamento confirmado e plano ativado!');
        fetchData();
      }
    } catch (e) {
      alert('Erro ao confirmar pagamento');
    }
  };

  const handleRejectPayment = async (tenantId: string) => {
    if (!confirm('Rejeitar pagamento?')) return;
    try {
      const res = await fetch(`/admin/payments/reject?tenant_id=${tenantId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        alert('Pagamento rejeitado');
        fetchData();
      }
    } catch (e) {
      alert('Erro ao rejeitar pagamento');
    }
  };

  const handleSavePixConfig = async () => {
    try {
      const res = await fetch('/admin/pix', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(pixConfig),
      });
      if (res.ok) {
        alert('PIX configurado com sucesso!');
        const pixRes = await fetch('/admin/pix', { headers: { Authorization: `Bearer ${token}` } });
        if (pixRes.ok) { const d = await pixRes.json(); setPixConfig(d); }
      }
    } catch (e) {
      alert('Erro ao salvar PIX');
    }
  };


  const handleSavePlan = async () => {
    if (!editingPlan) return;
    try {
      const res = await fetch(`/admin/plans/${editingPlan.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(editingPlan),
      });
      if (res.ok) {
        alert('Plano atualizado!');
        setEditingPlan(null);
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || 'Erro ao atualizar plano');
      }
    } catch (e) {
      alert('Erro ao salvar plano');
    }
  };

  const handleDeletePlan = async (planId: string) => {
    if (!confirm('Remover este plano?')) return;
    try {
      const res = await fetch(`/admin/plans/${planId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        alert('Plano removido!');
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || 'Erro ao remover plano');
      }
    } catch (e) {
      alert('Erro ao remover plano');
    }
  };

  const handleCreatePlan = async () => {
    try {
      const res = await fetch('/admin/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(newPlan),
      });
      if (res.ok) {
        alert('Plano criado!');
        setCreatingPlan(false);
        setNewPlan({ id: '', name: '', price: 0, interval: 'month', description: '', discount_percent: 0, is_active: true });
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || 'Erro ao criar plano');
      }
    } catch (e) {
      alert('Erro ao criar plano');
    }
  };

  const handleUploadPixQR = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = (reader.result as string).split(',')[1];
      setPixConfig({ ...pixConfig, pix_qr: base64 });
    };
    reader.readAsDataURL(file);
  };

  const handleToggleProductAccess = async (productId: string, granted: boolean) => {
    if (!selectedTenant) return;
    const endpoint = granted ? '/admin/revoke-product' : '/admin/grant-product';
    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ tenant_id: selectedTenant.id, product_id: productId }),
    });
    handleOpenTenantProducts(selectedTenant);
  };

  const planColor = (p: string) => p === 'free' ? '#10b981' : p === 'monthly' ? '#3b82f6' : p === 'quarterly' ? '#8b5cf6' : '#f59e0b';
  const planName = (p: string) => p === 'free' ? 'Colaborador' : p === 'monthly' ? 'Mensal' : p === 'quarterly' ? 'Trimestral' : 'Anual';
  const statusBadge = (st: string) => {
    if (st === 'available') return { bg: '#10b98120', color: '#10b981', label: 'Disponivel' };
    if (st === 'coming-soon') return { bg: '#f59e0b20', color: '#f59e0b', label: 'Em Breve' };
    return { bg: '#8b5cf620', color: '#8b5cf6', label: 'Exclusivo' };
  };

  const s: Record<string, React.CSSProperties> = {
    container: { minHeight: '100vh', background: '#0a0a1a', color: '#fff', padding: 20 },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
    title: { fontSize: 22, fontWeight: 'bold', margin: 0 },
    tabs: { display: 'flex', gap: 0, marginBottom: 20, borderBottom: '1px solid #333' },
    tab: { padding: '10px 20px', border: 'none', background: 'transparent', color: '#999', fontSize: 14, cursor: 'pointer', borderBottom: '2px solid transparent' },
    tabActive: { color: '#fff', borderBottom: '2px solid #8b5cf6' },
    card: { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, padding: 20, marginBottom: 16 },
    statGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 16 },
    statCard: { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: 16, display: 'flex', alignItems: 'center', gap: 12 },
    statValue: { fontSize: 24, fontWeight: 'bold', color: '#00d9ff' },
    statLabel: { fontSize: 12, color: '#999' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { padding: '8px 12px', textAlign: 'left', fontSize: 12, color: '#999', borderBottom: '1px solid #333' },
    td: { padding: '8px 12px', fontSize: 13, borderBottom: '1px solid #222' },
    btn: { padding: '4px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#ccc', marginRight: 4 },
    badge: { padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 500 },
    plansGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 16 },
    planCard: { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, padding: 20 },
    planPrice: { fontSize: 28, fontWeight: 'bold', margin: '8px 0' },
    modalOverlay: { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
    modal: { background: '#1a1a2e', borderRadius: 12, padding: 24, width: '100%', maxWidth: 400, border: '1px solid rgba(255,255,255,0.1)' },
    input: { width: '100%', padding: '8px 12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, color: '#fff', fontSize: 13, boxSizing: 'border-box', marginBottom: 12 },
    saveBtn: { padding: '8px 16px', background: 'linear-gradient(135deg, #00d9ff, #00ff88)', border: 'none', borderRadius: 6, color: '#000', fontWeight: 600, cursor: 'pointer' },
    cancelBtn: { padding: '8px 16px', background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, color: '#999', cursor: 'pointer', marginRight: 8 },
    empty: { textAlign: 'center', padding: 40, color: '#666' },
  };

  const handleAdminLogin = (adminToken: string, adminEmail: string) => {
    setIsAdminAuth(true);
  };

  const handleAdminLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_email');
    setIsAdminAuth(false);
    onLogout();
  };

  if (!isAdminAuth) {
    return <AdminLogin onLogin={handleAdminLogin} />;
  }

  return (
    <div style={s.container}>
      <div style={s.header}>
        <div>
          <h1 style={s.title}>Painel Mestre</h1>
          <p style={{ color: '#999', margin: 0 }}>DEEP-OS Admin</p>
        </div>
        <button onClick={handleAdminLogout} style={{ ...s.btn, padding: '8px 16px' }}>Sair</button>
      </div>

      {error && <div style={{ color: '#f44', marginBottom: 12, fontSize: 12 }}>Erro: {error}</div>}

      <div style={s.tabs}>
        <button style={{ ...s.tab, ...(activeTab === 'overview' ? s.tabActive : {}) }} onClick={() => setActiveTab('overview')}>Visao Geral</button>
        <button style={{ ...s.tab, ...(activeTab === 'tenants' ? s.tabActive : {}) }} onClick={() => setActiveTab('tenants')}>Usuarios</button>
        <button style={{ ...s.tab, ...(activeTab === 'plans' ? s.tabActive : {}) }} onClick={() => setActiveTab('plans')}>Planos</button>
        <button style={{ ...s.tab, ...(activeTab === 'products' ? s.tabActive : {}) }} onClick={() => setActiveTab('products')}>Produtos</button>
        <button style={{ ...s.tab, ...(activeTab === 'payments' ? s.tabActive : {}) }} onClick={() => setActiveTab('payments')}>Pagamentos {pendingPayments.length > 0 && <span style={{ background: '#ef4444', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 10, marginLeft: 4 }}>{pendingPayments.length}</span>}</button>
      </div>

      {activeTab === 'overview' && (
        <div>
          <div style={s.statGrid}>
            <div style={s.statCard}><span style={{ fontSize: 24 }}>👥</span><div><div style={s.statValue}>{stats?.total_tenants || 0}</div><div style={s.statLabel}>Total</div></div></div>
            <div style={s.statCard}><span style={{ fontSize: 24 }}>✅</span><div><div style={{ ...s.statValue, color: '#10b981' }}>{stats?.active_tenants || 0}</div><div style={s.statLabel}>Ativos</div></div></div>
            <div style={s.statCard}><span style={{ fontSize: 24 }}>💰</span><div><div style={{ ...s.statValue, color: '#8b5cf6' }}>R$ {stats?.mrr?.toFixed(2) || '0.00'}</div><div style={s.statLabel}>Receita/mês</div></div></div>
            <div style={s.statCard}><span style={{ fontSize: 24 }}>📈</span><div><div style={{ ...s.statValue, color: '#f59e0b' }}>{stats?.new_this_month || 0}</div><div style={s.statLabel}>Novos/mês</div></div></div>
          </div>
          <div style={s.card}>
            <h3 style={{ margin: '0 0 12px 0' }}>Distribuição por Plano</h3>
            {stats?.tenants_by_plan && Object.entries(stats.tenants_by_plan).map(([plan, count]: any) => (
              <div key={plan} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 13 }}>{planName(plan)}</span>
                  <span style={{ fontSize: 13, color: '#999' }}>{count}</span>
                </div>
                <div style={{ height: 6, background: '#222', borderRadius: 3 }}>
                  <div style={{ height: '100%', width: `${stats.total_tenants > 0 ? (count / stats.total_tenants) * 100 : 0}%`, background: planColor(plan), borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'tenants' && (
        <div style={s.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Usuarios ({tenants.length})</h3>
            <button onClick={() => setCreatingTenant(true)} style={{ ...s.saveBtn, padding: '8px 16px' }}>+ Criar Usuario</button>
          </div>
          {tenants.length === 0 ? (
            <div style={s.empty}>
              <p>Nenhum assinante ainda</p>
              <p style={{ fontSize: 12, color: '#666' }}>Novos usuarios aparecem aqui apos se cadastrarem</p>
            </div>
          ) : (
            <table style={s.table}>
              <thead><tr><th style={s.th}>Nome</th><th style={s.th}>Email</th><th style={s.th}>Plano</th><th style={s.th}>Status</th><th style={s.th}>Ações</th></tr></thead>
              <tbody>
                {tenants.map((t) => (
                  <tr key={t.id}>
                    <td style={s.td}>{t.name}</td>
                    <td style={s.td}>{t.email}</td>
                    <td style={s.td}><span style={{ ...s.badge, background: planColor(t.plan) + '20', color: planColor(t.plan) }}>{planName(t.plan)}</span></td>
                    <td style={s.td}><span style={{ ...s.badge, background: t.status === 'active' ? '#10b98120' : '#ef444420', color: t.status === 'active' ? '#10b981' : '#ef4444' }}>{t.status === 'active' ? 'Ativo' : 'Suspenso'}</span></td>
                    <td style={s.td}>
                      <button style={s.btn} onClick={() => setEditingTenant({ ...t })}>Editar</button>
                      <button style={{ ...s.btn, color: '#8b5cf6' }} onClick={() => handleOpenTenantProducts(t)}>Downloads</button>
                      {t.status === 'active' ? <button style={s.btn} onClick={() => handleSuspend(t.id)}>Suspender</button> : <button style={s.btn} onClick={() => handleReactivate(t.id)}>Reativar</button>}
                      <button style={{ ...s.btn, color: '#f44' }} onClick={() => handleDelete(t.id)}>Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'plans' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <button style={s.saveBtn} onClick={() => setCreatingPlan(true)}>+ Novo Plano</button>
          </div>
          <div style={s.plansGrid}>
            {plans.map((plan) => (
              <div key={plan.id} style={{ ...s.planCard, borderColor: plan.is_active === false ? '#ef444440' : planColor(plan.id) + '40', opacity: plan.is_active === false ? 0.6 : 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                  <div>
                    <h4 style={{ margin: '0 0 4px 0', fontSize: 16 }}>{plan.name}</h4>
                    {plan.is_active === false && <span style={{ ...s.badge, background: '#ef444420', color: '#ef4444', fontSize: 10 }}>INATIVO</span>}
                  </div>
                  <span style={{ fontSize: 11, color: '#999', textTransform: 'uppercase' }}>{plan.id}</span>
                </div>
                <div style={s.planPrice}>R$ {plan.price?.toFixed(2)}</div>
                <p style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>{plan.description}</p>
                <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 12px 0', fontSize: 12, color: '#ccc' }}>
                  <li>Intervalo: {plan.interval || 'month'}</li>
                  {plan.discount_percent && <li>Desconto: {plan.discount_percent}%</li>}
                  <li>Instancias: {plan.features?.max_instances || 1}</li>
                  <li>Mensagens/dia: {plan.features?.max_messages_per_day || 20}</li>
                  {plan.features?.has_chatbot && <li>ChatBot</li>}
                  {plan.features?.has_radar_leads && <li>Radar de Leads</li>}
                  {plan.features?.has_pix && <li>PIX</li>}
                </ul>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button style={{ ...s.btn, flex: 1, textAlign: 'center' }} onClick={() => setEditingPlan({ ...plan })}>Editar</button>
                  {!['free', 'monthly', 'quarterly', 'annual'].includes(plan.id) && (
                    <button style={{ ...s.btn, color: '#ef4444', borderColor: '#ef4444' }} onClick={() => handleDeletePlan(plan.id)}>Excluir</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'products' && (
        <div style={s.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Produtos Digitais ({products.length})</h3>
            <button onClick={() => setCreatingProduct(true)} style={{ ...s.saveBtn, padding: '8px 16px' }}>+ Criar Produto</button>
          </div>
          {products.length === 0 ? (
            <div style={s.empty}><p>Nenhum produto criado</p></div>
          ) : (
            <table style={s.table}>
              <thead><tr>
                <th style={s.th}>Icone</th><th style={s.th}>Nome</th><th style={s.th}>Categoria</th>
                <th style={s.th}>Preco</th><th style={s.th}>Status</th><th style={s.th}>Acoes</th>
              </tr></thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id}>
                    <td style={s.td}>{p.icon}</td>
                    <td style={s.td}>{p.name}</td>
                    <td style={s.td}>{p.category}</td>
                    <td style={s.td}>{p.price === 0 ? 'Gratis' : 'R$ ' + p.price}</td>
                    <td style={s.td}><span style={{ ...s.badge, background: statusBadge(p.status).bg, color: statusBadge(p.status).color }}>{statusBadge(p.status).label}</span></td>
                    <td style={s.td}>
                      <button style={s.btn} onClick={() => setEditingProduct({ ...p, features: Array.isArray(p.features) ? p.features.join(', ') : p.features })}>Editar</button>
                      <button style={{ ...s.btn, color: '#f44' }} onClick={() => handleDeleteProduct(p.id)}>Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'payments' && (
        <div>
          {/* PIX Settings Card */}
          <div style={s.card}>
            <h3 style={{ margin: '0 0 12px 0' }}>Configuracao PIX</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 2 }}>
                <label style={{ fontSize: 11, color: '#999' }}>Chave PIX</label>
                <input style={s.input} value={pixConfig.pix_key} onChange={(e) => setPixConfig({ ...pixConfig, pix_key: e.target.value })} placeholder="Chave PIX" />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 11, color: '#999' }}>Tipo</label>
                <select style={s.input} value={pixConfig.pix_type} onChange={(e) => setPixConfig({ ...pixConfig, pix_type: e.target.value })}>
                  <option value="random">Aleatoria</option>
                  <option value="cpf">CPF</option>
                  <option value="cnpj">CNPJ</option>
                  <option value="email">Email</option>
                  <option value="phone">Telefone</option>
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 11, color: '#999' }}>Titular</label>
                <input style={s.input} value={pixConfig.owner_name} onChange={(e) => setPixConfig({ ...pixConfig, owner_name: e.target.value })} placeholder="Nome" />
              </div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 11, color: '#999' }}>Instrucoes (opcional)</label>
              <textarea style={{ ...s.input, minHeight: 50 }} value={pixConfig.instructions} onChange={(e) => setPixConfig({ ...pixConfig, instructions: e.target.value })} placeholder="Instrucoes de pagamento..." />
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <label style={{ ...s.saveBtn, cursor: 'pointer' }}>
                📷 QR Code
                <input type="file" accept="image/*" style={{ display: 'none' }} onChange={handleUploadPixQR} />
              </label>
              {pixConfig.pix_qr && <span style={{ fontSize: 11, color: '#10b981' }}>✓ QR Code carregado</span>}
              <div style={{ flex: 1 }} />
              <button style={s.saveBtn} onClick={handleSavePixConfig}>Salvar PIX</button>
            </div>
            {(pixConfig.pix_qr || pixConfig.pix_qr_url) && (
              <div style={{ marginTop: 12, textAlign: 'center' }}>
                <img
                  src={pixConfig.pix_qr ? `data:image/png;base64,${pixConfig.pix_qr}` : pixConfig.pix_qr_url}
                  alt="Preview QR Code"
                  style={{ maxWidth: 150, maxHeight: 150, borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)' }}
                />
              </div>
            )}
          </div>

          {/* Payment History */}
          <div style={s.card}>
            <h3 style={{ margin: '0 0 12px 0' }}>Historico de Pagamentos</h3>
            {paymentHistory.length === 0 ? (
              <div style={s.empty}>
                <p>Nenhum pagamento no historico</p>
              </div>
            ) : (
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Usuario</th>
                    <th style={s.th}>Email</th>
                    <th style={s.th}>Plano</th>
                    <th style={s.th}>Valor</th>
                    <th style={s.th}>Metodo</th>
                    <th style={s.th}>Status</th>
                    <th style={s.th}>Data</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentHistory.map((p: any, i: number) => (
                    <tr key={i}>
                      <td style={s.td}>{p.tenant_name || 'N/A'}</td>
                      <td style={s.td}>{p.tenant_email || 'N/A'}</td>
                      <td style={s.td}>{p.plan_id}</td>
                      <td style={s.td}>R$ {p.amount?.toFixed(2).replace('.', ',')}</td>
                      <td style={s.td}>{p.method?.toUpperCase()}</td>
                      <td style={s.td}>
                        <span style={{ 
                          ...s.badge, 
                          background: p.source === 'manual' ? '#8b5cf620' : p.status === 'confirmed' ? '#10b98120' : p.status === 'rejected' ? '#ef444420' : '#f59e0b20',
                          color: p.source === 'manual' ? '#8b5cf6' : p.status === 'confirmed' ? '#10b981' : p.status === 'rejected' ? '#ef4444' : '#f59e0b'
                        }}>
                          {p.source === 'manual' ? 'Liberado' : p.status === 'confirmed' ? 'Confirmado' : p.status === 'rejected' ? 'Rejeitado' : 'Pendente'}
                        </span>
                      </td>
                      <td style={s.td}>{new Date(p.created_at).toLocaleDateString('pt-BR')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pending Payments */}
          <div style={s.card}>
            <h3 style={{ margin: '0 0 12px 0' }}>Pagamentos Pendentes</h3>
            {pendingPayments.length === 0 ? (
              <div style={s.empty}>
                <p>Nenhum pagamento pendente</p>
              </div>
            ) : (
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Usuario</th>
                    <th style={s.th}>Email</th>
                    <th style={s.th}>Plano</th>
                    <th style={s.th}>Valor</th>
                    <th style={s.th}>Data</th>
                    <th style={s.th}>Acoes</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingPayments.map((p: any, i: number) => (
                    <tr key={i}>
                      <td style={s.td}>{p.tenant_name}</td>
                      <td style={s.td}>{p.tenant_email}</td>
                      <td style={s.td}><span style={{ ...s.badge, background: planColor(p.plan_id) + '20', color: planColor(p.plan_id) }}>{planName(p.plan_id)}</span></td>
                      <td style={s.td}>R$ {p.amount?.toFixed(2)}</td>
                      <td style={s.td}>{p.requested_at ? new Date(p.requested_at).toLocaleDateString('pt-BR') : '-'}</td>
                      <td style={s.td}>
                        <button style={{ ...s.btn, background: '#10b98120', color: '#10b981', borderColor: '#10b981' }} onClick={() => handleConfirmPayment(p.tenant_id, p.plan_id, p.amount)}>
                          Confirmar
                        </button>
                        <button style={{ ...s.btn, color: '#ef4444', borderColor: '#ef4444' }} onClick={() => handleRejectPayment(p.tenant_id)}>
                          Rejeitar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {editingTenant && (
        <div style={s.modalOverlay} onClick={() => setEditingTenant(null)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Editar Usuario</h2>
            <input style={s.input} value={editingTenant.name} onChange={(e) => setEditingTenant({ ...editingTenant, name: e.target.value })} placeholder="Nome" />
            <input style={s.input} value={editingTenant.email} onChange={(e) => setEditingTenant({ ...editingTenant, email: e.target.value })} placeholder="Email" />
            <select style={s.input} value={editingTenant.plan} onChange={(e) => setEditingTenant({ ...editingTenant, plan: e.target.value })}>
              <option value="free">Colaborador (Gratis)</option>
              <option value="monthly">Mensal</option>
              <option value="quarterly">Trimestral</option>
              <option value="annual">Anual</option>
            </select>
            <select style={s.input} value={editingTenant.status} onChange={(e) => setEditingTenant({ ...editingTenant, status: e.target.value })}>
              <option value="active">Ativo</option>
              <option value="suspended">Suspenso</option>
              <option value="deleted">Excluido</option>
            </select>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setEditingTenant(null)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleSaveTenant}>Salvar</button>
            </div>
          </div>
        </div>
      )}

      {editingPlan && (
        <div style={s.modalOverlay} onClick={() => setEditingPlan(null)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Editar: {editingPlan.id}</h2>
            <input style={s.input} value={editingPlan.name} onChange={(e) => setEditingPlan({ ...editingPlan, name: e.target.value })} placeholder="Nome" />
            <input style={s.input} type="number" step="0.01" value={editingPlan.price} onChange={(e) => setEditingPlan({ ...editingPlan, price: parseFloat(e.target.value) || 0 })} placeholder="Preço R$" />
            <textarea style={{ ...s.input, minHeight: 60 }} value={editingPlan.description || ''} onChange={(e) => setEditingPlan({ ...editingPlan, description: e.target.value })} placeholder="Descrição" />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setEditingPlan(null)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleSavePlan}>Salvar</button>
            </div>
          </div>
        </div>
      )}

      {creatingTenant && (
        <div style={s.modalOverlay} onClick={() => setCreatingTenant(false)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Criar Usuario</h2>
            <input style={s.input} value={newTenant.name} onChange={(e) => setNewTenant({ ...newTenant, name: e.target.value })} placeholder="Nome *" />
            <input style={s.input} value={newTenant.email} onChange={(e) => setNewTenant({ ...newTenant, email: e.target.value })} placeholder="Email *" type="email" />
            <input style={s.input} value={newTenant.password} onChange={(e) => setNewTenant({ ...newTenant, password: e.target.value })} placeholder="Senha *" type="password" />
            <select style={s.input} value={newTenant.plan} onChange={(e) => setNewTenant({ ...newTenant, plan: e.target.value })}>
              <option value="free">Colaborador (Gratis)</option>
              <option value="monthly">Mensal</option>
              <option value="quarterly">Trimestral</option>
              <option value="annual">Anual</option>
            </select>
            <input style={s.input} value={newTenant.company} onChange={(e) => setNewTenant({ ...newTenant, company: e.target.value })} placeholder="Empresa (opcional)" />
            <input style={s.input} value={newTenant.phone} onChange={(e) => setNewTenant({ ...newTenant, phone: e.target.value })} placeholder="Telefone (opcional)" />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setCreatingTenant(false)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleCreateTenant}>Criar</button>
            </div>
          </div>
        </div>
      )}

      {creatingProduct && (
        <div style={s.modalOverlay} onClick={() => setCreatingProduct(false)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Criar Produto</h2>
            <input style={s.input} value={newProduct.name} onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })} placeholder="Nome *" />
            <input style={s.input} value={newProduct.description} onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })} placeholder="Descricao" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} value={newProduct.icon} onChange={(e) => setNewProduct({ ...newProduct, icon: e.target.value })} placeholder="Icone (emoji)" />
              <input style={{ ...s.input, flex: 1 }} value={newProduct.category} onChange={(e) => setNewProduct({ ...newProduct, category: e.target.value })} placeholder="Categoria" />
            </div>
            <input style={s.input} value={newProduct.image_url} onChange={(e) => setNewProduct({ ...newProduct, image_url: e.target.value })} placeholder="URL da imagem (opcional)" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} type="number" value={newProduct.price || ''} onChange={(e) => setNewProduct({ ...newProduct, price: parseFloat(e.target.value) || 0 })} placeholder="Preco R$" />
              <input style={{ ...s.input, flex: 1 }} type="number" value={newProduct.original_price || ''} onChange={(e) => setNewProduct({ ...newProduct, original_price: parseFloat(e.target.value) || 0 })} placeholder="Preco original R$" />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} value={newProduct.badge} onChange={(e) => setNewProduct({ ...newProduct, badge: e.target.value })} placeholder="Badge (ex: MAIS VENDIDO)" />
              <input style={{ ...s.input, flex: 1 }} value={newProduct.badge_color} onChange={(e) => setNewProduct({ ...newProduct, badge_color: e.target.value })} placeholder="Cor badge (hex)" />
            </div>
            <input style={s.input} value={newProduct.features} onChange={(e) => setNewProduct({ ...newProduct, features: e.target.value })} placeholder="Features (separar por virgula)" />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input style={{ ...s.input, flex: 1, marginBottom: 0 }} value={newProduct.download_url} onChange={(e) => setNewProduct({ ...newProduct, download_url: e.target.value })} placeholder="URL de download" />
              <label style={{ ...s.saveBtn, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                📁 Upload
                <input type="file" style={{ display: 'none' }} onChange={(e) => handleUploadFile(e, 'new')} />
              </label>
            </div>
            {uploading && <p style={{ fontSize: 11, color: '#8b5cf6', margin: '4px 0 0' }}>Enviando arquivo...</p>}
            <select style={s.input} value={newProduct.status} onChange={(e) => setNewProduct({ ...newProduct, status: e.target.value })}>
              <option value="available">Disponivel</option>
              <option value="coming-soon">Em Breve</option>
              <option value="exclusive">Exclusivo</option>
            </select>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setCreatingProduct(false)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleCreateProduct}>Criar</button>
            </div>
          </div>
        </div>
      )}

      
      {editingPlan && (
        <div style={s.modalOverlay} onClick={() => setEditingPlan(null)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Editar Plano</h2>
            <input style={s.input} value={editingPlan.name} onChange={(e) => setEditingPlan({ ...editingPlan, name: e.target.value })} placeholder="Nome" />
            <input style={s.input} value={editingPlan.description || ''} onChange={(e) => setEditingPlan({ ...editingPlan, description: e.target.value })} placeholder="Descricao" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} type="number" value={editingPlan.price || 0} onChange={(e) => setEditingPlan({ ...editingPlan, price: parseFloat(e.target.value) || 0 })} placeholder="Preco R$" />
              <input style={{ ...s.input, flex: 1 }} type="number" value={editingPlan.discount_percent || 0} onChange={(e) => setEditingPlan({ ...editingPlan, discount_percent: parseInt(e.target.value) || 0 })} placeholder="Desconto %" />
            </div>
            <select style={s.input} value={editingPlan.interval || 'month'} onChange={(e) => setEditingPlan({ ...editingPlan, interval: e.target.value })}>
              <option value="month">Mensal</option>
              <option value="quarter">Trimestral</option>
              <option value="year">Anual</option>
            </select>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <input type="checkbox" id="plan-active" checked={editingPlan.is_active !== false} onChange={(e) => setEditingPlan({ ...editingPlan, is_active: e.target.checked })} />
              <label htmlFor="plan-active" style={{ fontSize: 13, color: '#ccc' }}>Plano ativo (disponivel para compra)</label>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setEditingPlan(null)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleSavePlan}>Salvar</button>
            </div>
          </div>
        </div>
      )}

      {creatingPlan && (
        <div style={s.modalOverlay} onClick={() => setCreatingPlan(false)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Novo Plano</h2>
            <input style={s.input} value={newPlan.id} onChange={(e) => setNewPlan({ ...newPlan, id: e.target.value.toLowerCase().replace(/s+/g, '-') })} placeholder="ID (ex: mensal-pro)" />
            <input style={s.input} value={newPlan.name} onChange={(e) => setNewPlan({ ...newPlan, name: e.target.value })} placeholder="Nome" />
            <input style={s.input} value={newPlan.description} onChange={(e) => setNewPlan({ ...newPlan, description: e.target.value })} placeholder="Descricao" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} type="number" value={newPlan.price} onChange={(e) => setNewPlan({ ...newPlan, price: parseFloat(e.target.value) || 0 })} placeholder="Preco R$" />
              <input style={{ ...s.input, flex: 1 }} type="number" value={newPlan.discount_percent} onChange={(e) => setNewPlan({ ...newPlan, discount_percent: parseInt(e.target.value) || 0 })} placeholder="Desconto %" />
            </div>
            <select style={s.input} value={newPlan.interval} onChange={(e) => setNewPlan({ ...newPlan, interval: e.target.value })}>
              <option value="month">Mensal</option>
              <option value="quarter">Trimestral</option>
              <option value="year">Anual</option>
            </select>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <input type="checkbox" id="new-plan-active" checked={newPlan.is_active} onChange={(e) => setNewPlan({ ...newPlan, is_active: e.target.checked })} />
              <label htmlFor="new-plan-active" style={{ fontSize: 13, color: '#ccc' }}>Plano ativo (disponivel para compra)</label>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setCreatingPlan(false)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleCreatePlan}>Criar</button>
            </div>
          </div>
        </div>
      )}

      {editingProduct && (
        <div style={s.modalOverlay} onClick={() => setEditingProduct(null)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 16px 0' }}>Editar Produto</h2>
            <input style={s.input} value={editingProduct.name} onChange={(e) => setEditingProduct({ ...editingProduct, name: e.target.value })} placeholder="Nome" />
            <input style={s.input} value={editingProduct.description} onChange={(e) => setEditingProduct({ ...editingProduct, description: e.target.value })} placeholder="Descricao" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} value={editingProduct.icon} onChange={(e) => setEditingProduct({ ...editingProduct, icon: e.target.value })} placeholder="Icone" />
              <input style={{ ...s.input, flex: 1 }} value={editingProduct.category} onChange={(e) => setEditingProduct({ ...editingProduct, category: e.target.value })} placeholder="Categoria" />
            </div>
            <input style={s.input} value={editingProduct.image_url || ''} onChange={(e) => setEditingProduct({ ...editingProduct, image_url: e.target.value })} placeholder="URL da imagem" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} type="number" value={editingProduct.price || 0} onChange={(e) => setEditingProduct({ ...editingProduct, price: parseFloat(e.target.value) || 0 })} placeholder="Preco R$" />
              <input style={{ ...s.input, flex: 1 }} type="number" value={editingProduct.original_price || ''} onChange={(e) => setEditingProduct({ ...editingProduct, original_price: parseFloat(e.target.value) || 0 })} placeholder="Preco original" />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} value={editingProduct.badge || ''} onChange={(e) => setEditingProduct({ ...editingProduct, badge: e.target.value })} placeholder="Badge" />
              <input style={{ ...s.input, flex: 1 }} value={editingProduct.badge_color || ''} onChange={(e) => setEditingProduct({ ...editingProduct, badge_color: e.target.value })} placeholder="Cor badge" />
            </div>
            <input style={s.input} value={Array.isArray(editingProduct.features) ? editingProduct.features.join(', ') : editingProduct.features || ''} onChange={(e) => setEditingProduct({ ...editingProduct, features: e.target.value })} placeholder="Features (virgula)" />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input style={{ ...s.input, flex: 1, marginBottom: 0 }} value={editingProduct.download_url || ''} onChange={(e) => setEditingProduct({ ...editingProduct, download_url: e.target.value })} placeholder="URL download" />
              <label style={{ ...s.saveBtn, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                📁 Upload
                <input type="file" style={{ display: 'none' }} onChange={(e) => handleUploadFile(e, 'edit')} />
              </label>
            </div>
            {uploading && <p style={{ fontSize: 11, color: '#8b5cf6', margin: '4px 0 0' }}>Enviando arquivo...</p>}
            <select style={s.input} value={editingProduct.status} onChange={(e) => setEditingProduct({ ...editingProduct, status: e.target.value })}>
              <option value="available">Disponivel</option>
              <option value="coming-soon">Em Breve</option>
              <option value="exclusive">Exclusivo</option>
            </select>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={s.cancelBtn} onClick={() => setEditingProduct(null)}>Cancelar</button>
              <button style={s.saveBtn} onClick={handleSaveProduct}>Salvar</button>
            </div>
          </div>
        </div>
      )}

      {selectedTenant && (
        <div style={s.modalOverlay} onClick={() => setSelectedTenant(null)}>
          <div style={{ ...s.modal, maxWidth: 500 }} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: '0 0 8px 0' }}>Downloads: {selectedTenant.name}</h2>
            <p style={{ margin: '0 0 16px', fontSize: 12, color: '#999' }}>Marque os produtos que este usuario pode baixar</p>
            {tenantProducts.length === 0 ? (
              <p style={{ color: '#666', fontSize: 13 }}>Nenhum produto criado ainda</p>
            ) : (
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                {tenantProducts.map((p: any) => (
                  <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #222' }}>
                    <div>
                      <span style={{ fontSize: 16, marginRight: 8 }}>{p.icon}</span>
                      <span style={{ fontSize: 13 }}>{p.name}</span>
                      <span style={{ fontSize: 11, color: '#999', marginLeft: 8 }}>{p.price === 0 ? 'Gratis' : 'R$ ' + p.price}</span>
                    </div>
                    <button
                      style={{ ...s.btn, background: p.granted ? '#10b98120' : 'transparent', color: p.granted ? '#10b981' : '#ccc', borderColor: p.granted ? '#10b981' : undefined }}
                      onClick={() => handleToggleProductAccess(p.id, p.granted)}
                    >
                      {p.granted ? 'Liberado' : 'Liberar'}
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
              <button style={s.cancelBtn} onClick={() => setSelectedTenant(null)}>Fechar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;