import React, { useState, useEffect } from 'react';
import { planNames, planFeatures } from './planConfig';

interface User {
  id: string;
  name: string;
  email: string;
  plan: string;
  status: string;
}

interface Payment {
  id: string;
  plan_id: string;
  amount: number;
  method: string;
  source: string;
  status: 'pending' | 'confirmed' | 'rejected';
  created_at: string;
  updated_at: string;
  notes?: string;
}

const MyPlansPage: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const token = localStorage.getItem('saas_token');
    if (!token) return;
    try {
      const [meRes, paymentsRes] = await Promise.all([
        fetch('/auth/me', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/shop/my-payments', { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
      ]);
      if (meRes.ok) {
        const meData = await meRes.json();
        setUser(meData);
      }
      if (paymentsRes && paymentsRes.ok) {
        const paymentsData = await paymentsRes.json();
        setPayments(paymentsData.payments || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loading}>Carregando seus planos...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div style={styles.container}>
        <div style={styles.error}>Usuário não encontrado. Faça login novamente.</div>
      </div>
    );
  }

  const currentPlan = user?.plan || 'free';
  const currentFeatures = planFeatures[currentPlan] || planFeatures.free;

  const statusBadge = (status: string, source?: string) => {
    if (source === 'manual' && status === 'confirmed') {
      return { label: 'Liberado', color: '#8b5cf6' };
    }
    switch (status) {
      case 'confirmed': return { label: 'Confirmado', color: '#10b981' };
      case 'pending': return { label: 'Pendente', color: '#f59e0b' };
      case 'rejected': return { label: 'Rejeitado', color: '#ef4444' };
      default: return { label: status, color: '#999' };
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.icon}>✅</span>
        <h1 style={styles.title}>Meus Planos</h1>
        <p style={styles.subtitle}>Gerencie sua assinatura e acompanhe seus pagamentos</p>
      </div>

      <div style={styles.card}>
        <div style={styles.planHeader}>
          <div>
            <span style={styles.planLabel}>Plano atual</span>
            <h2 style={styles.planName}>{planNames[currentPlan] || 'Gratuito'}</h2>
          </div>
          <span style={{ ...styles.statusBadge, background: currentPlan === 'free' ? '#6b7280' : '#8b5cf6' }}>
            {user.status === 'active' ? 'Ativo' : 'Inativo'}
          </span>
        </div>

        <div style={styles.featuresBox}>
          <h3 style={styles.featuresTitle}>Recursos inclusos:</h3>
          <div style={styles.featuresGrid}>
            {currentFeatures.map((feature, i) => (
              <div key={i} style={styles.featureItem}>
                <span style={styles.checkIcon}>✓</span>
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.historyTitle}>Histórico de pagamentos</h3>
        {payments.length === 0 ? (
          <div style={styles.empty}>
            <p>Nenhum pagamento registrado.</p>
          </div>
        ) : (
          <div style={styles.paymentsList}>
            {payments.map((payment) => {
              const badge = statusBadge(payment.status, payment.source);
              return (
                <div key={payment.id} style={styles.paymentItem}>
                  <div style={styles.paymentInfo}>
                    <span style={styles.paymentPlan}>{planNames[payment.plan_id] || payment.plan_id}</span>
                    <span style={styles.paymentMethod}>{payment.method?.toUpperCase() || 'PIX'}</span>
                    <span style={styles.paymentDate}>Adquirido em: {new Date(payment.created_at).toLocaleDateString('pt-BR')} às {new Date(payment.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                    {payment.updated_at && payment.status !== 'pending' && (
                      <span style={styles.paymentDate}>
                        {payment.status === 'confirmed' ? 'Confirmado' : 'Atualizado'} em: {new Date(payment.updated_at).toLocaleDateString('pt-BR')}
                      </span>
                    )}
                  </div>
                  <div style={styles.paymentRight}>
                    <span style={styles.paymentAmount}>R$ {payment.amount.toFixed(2).replace('.', ',')}</span>
                    <span style={{ ...styles.paymentStatus, color: badge.color, borderColor: badge.color }}>{badge.label}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '32px',
    minHeight: '100vh',
    maxWidth: '800px',
    margin: '0 auto',
  },
  loading: {
    textAlign: 'center',
    padding: '60px',
    color: '#999',
  },
  error: {
    textAlign: 'center',
    padding: '40px',
    color: '#ef4444',
  },
  header: {
    textAlign: 'center',
    marginBottom: '32px',
  },
  icon: {
    fontSize: '48px',
    display: 'block',
    marginBottom: '12px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold',
    color: '#ffffff',
    margin: '0 0 8px',
  },
  subtitle: {
    fontSize: '14px',
    color: '#999',
    margin: 0,
  },
  card: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '20px',
  },
  planHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px',
  },
  planLabel: {
    fontSize: '12px',
    color: '#999',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
  planName: {
    fontSize: '24px',
    fontWeight: 'bold',
    color: '#fff',
    margin: '4px 0 0',
  },
  statusBadge: {
    padding: '4px 12px',
    borderRadius: '12px',
    color: '#fff',
    fontSize: '12px',
    fontWeight: '600',
  },
  featuresBox: {
    borderTop: '1px solid rgba(255,255,255,0.1)',
    paddingTop: '16px',
  },
  featuresTitle: {
    fontSize: '14px',
    color: '#ccc',
    margin: '0 0 12px',
  },
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: '8px',
  },
  featureItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    color: '#ccc',
  },
  checkIcon: {
    color: '#10b981',
    fontWeight: 'bold',
  },
  historyTitle: {
    fontSize: '16px',
    fontWeight: '600',
    color: '#fff',
    margin: '0 0 16px',
  },
  empty: {
    textAlign: 'center',
    color: '#666',
    padding: '20px',
  },
  paymentsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  paymentItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px',
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.05)',
    borderRadius: '8px',
  },
  paymentInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  paymentPlan: {
    fontSize: '15px',
    fontWeight: '600',
    color: '#fff',
  },
  paymentMethod: {
    fontSize: '12px',
    color: '#00d9ff',
    fontWeight: '500',
    textTransform: 'uppercase',
  },
  paymentDate: {
    fontSize: '12px',
    color: '#999',
  },
  paymentRight: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '4px',
  },
  paymentAmount: {
    fontSize: '14px',
    fontWeight: 'bold',
    color: '#00d9ff',
  },
  paymentStatus: {
    fontSize: '11px',
    padding: '2px 8px',
    borderRadius: '10px',
    border: '1px solid',
    fontWeight: '600',
  },
};

export default MyPlansPage;
