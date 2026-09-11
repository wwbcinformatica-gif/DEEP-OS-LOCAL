import React, { useState, useEffect, Fragment } from 'react';

interface PlanFeature {
  label: string;
  included: boolean;
  highlight?: boolean;
}

interface Plan {
  id: string;
  name: string;
  price: number;
  interval: string;
  period: string;
  description: string;
  features: PlanFeature[];
  popular?: boolean;
  discount?: string;
  cta: string;
  ctaStyle: 'primary' | 'secondary' | 'dark';
}

const defaultPlans: Plan[] = [
  {
    id: 'monthly',
    name: 'Mensal',
    price: 14.99,
    interval: 'mês',
    period: '/mês',
    description: 'ChatBot + Commands + Gatilhos + Relatorios',
    features: [
      { label: 'ChatBot', included: true, highlight: true },
      { label: 'Commands', included: true },
      { label: 'Gatilhos', included: true },
      { label: 'Relatorios', included: true },
      { label: 'Comunicados', included: true },
    ],
    cta: 'Assinar Agora',
    ctaStyle: 'secondary',
  },
  {
    id: 'quarterly',
    name: 'Trimestral',
    price: 29.99,
    interval: 'trimestre',
    period: '/trimestre',
    description: 'Jarvis + Charon + 33% de desconto',
    features: [
      { label: 'Tudo do Mensal', included: true, highlight: true },
      { label: 'Jarvis (Chat IA)', included: true, highlight: true },
      { label: 'Charon (Voz IA)', included: true, highlight: true },
      { label: '33% de desconto', included: true },
      { label: 'PIX', included: true },
    ],
    popular: true,
    discount: '33% OFF',
    cta: 'ASSINAR AGORA',
    ctaStyle: 'primary',
  },
  {
    id: 'annual',
    name: 'Anual',
    price: 79.99,
    interval: 'ano',
    period: '/ano',
    description: 'Acesso completo - Tudo liberado',
    features: [
      { label: 'Tudo do Trimestral', included: true, highlight: true },
      { label: 'Instancias', included: true, highlight: true },
      { label: 'ChatBot', included: true, highlight: true },
      { label: 'Radar de Leads', included: true, highlight: true },
      { label: '71% de desconto', included: true },
      { label: 'Jarvis Vitalicio', included: true },
    ],
    cta: 'Assinar Agora',
    ctaStyle: 'dark',
  },
];

const PricingPage: React.FC = () => {
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [plans, setPlans] = useState<Plan[]>(defaultPlans);
  const [loading, setLoading] = useState(true);
  const [showPixModal, setShowPixModal] = useState(false);
  const [pixInfo, setPixInfo] = useState<any>(null);
  const [pixLoading, setPixLoading] = useState(false);
  const [paymentSent, setPaymentSent] = useState(false);
  const [selectedPlanData, setSelectedPlanData] = useState<Plan | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchPlans();
    const handleFocus = () => fetchPlans();
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  const fetchPlans = async () => {
    try {
      const res = await fetch('/plans/public');
      if (res.ok) {
        const data = await res.json();
        if (data.plans && data.plans.length > 0) {
          const periodMap: Record<string, string> = { month: '/mês', quarter: '/trimestre', year: '/ano' };
          const intervalMap: Record<string, string> = { month: 'mês', quarter: 'trimestre', year: 'ano' };
          const discountMap: Record<string, string> = { quarterly: '33% OFF', annual: '71% OFF' };
          const popularMap: Record<string, boolean> = { quarterly: true };
          
          const mapped: Plan[] = data.plans
            .filter((p: any) => p.id !== 'free')
            .map((p: any) => ({
              id: p.id,
              name: p.name,
              price: p.price,
              interval: intervalMap[p.interval] || p.interval,
              period: periodMap[p.period || p.interval] || `/${p.interval}`,
              description: p.description,
              features: p.features ? [
                { label: 'Instâncias', included: true },
                { label: 'Suporte', included: true },
                { label: 'Acesso ao Painel', included: true },
                ...(p.features.has_radar_leads ? [{ label: 'Radar de Leads', included: true, highlight: true }] : []),
                ...(p.includes_jarvis_lifetime ? [{ label: 'Jarvis Vitalício', included: true, highlight: true }] : []),
              ] : defaultPlans.find(dp => dp.id === p.id)?.features || [],
              popular: popularMap[p.id],
              discount: discountMap[p.id] || (p.discount_percent ? `${p.discount_percent}% OFF` : undefined),
              cta: p.id === 'quarterly' ? 'ASSINAR AGORA' : 'Assinar Agora',
              ctaStyle: (p.id === 'quarterly' ? 'primary' : p.id === 'annual' ? 'dark' : 'secondary') as 'primary' | 'secondary' | 'dark',
            }));
          
          if (mapped.length > 0) {
            setPlans(mapped);
          }
        }
      }
    } catch (e) {
      // Usa planos padrao em caso de erro
    } finally {
      setLoading(false);
    }
  };

  const fetchPixInfo = async () => {
    setPixLoading(true);
    try {
      const res = await fetch('/admin/pix/public');
      if (res.ok) {
        const data = await res.json();
        setPixInfo(data);
      } else {
        setPixInfo(null);
      }
    } catch (e) {
      setPixInfo(null);
    } finally {
      setPixLoading(false);
    }
  };

  const handleSubscribe = async (planId: string) => {
    const plan = plans.find(p => p.id === planId);
    if (!plan) return;

    if (plan.price > 0) {
      setSelectedPlanData(plan);
      setSelectedPlan(planId);
      setPaymentSent(false);
      fetchPixInfo();
      setShowPixModal(true);
      return;
    }

    try {
      const token = localStorage.getItem('saas_token');
      const res = await fetch('/plans/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan_id: planId }),
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || `Plano ${plan.name} ativado com sucesso!`);
        const savedUser = JSON.parse(localStorage.getItem('saas_user') || '{}');
        savedUser.plan = planId;
        localStorage.setItem('saas_user', JSON.stringify(savedUser));
        window.location.reload();
      } else {
        alert(data.detail || 'Erro ao ativar plano');
      }
    } catch {
      alert('Erro de conexao ao ativar plano');
    }
  };

  const handleRequestPayment = async () => {
    if (!selectedPlanData) return;
    try {
      const token = localStorage.getItem('saas_token');
      const res = await fetch('/plans/request-payment', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          plan_id: selectedPlanData.id,
          amount: selectedPlanData.price,
          notes: `Assinatura ${selectedPlanData.name}`,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setPaymentSent(true);
      } else {
        alert(data.detail || 'Erro ao enviar solicitacao');
      }
    } catch {
      alert('Erro de conexao');
    }
  };

  const handleCopyPix = () => {
    if (pixInfo?.pix_key) {
      navigator.clipboard.writeText(pixInfo.pix_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const pixTypeLabel: Record<string, string> = {
    random: 'Chave Aleatoria',
    cpf: 'CPF',
    cnpj: 'CNPJ',
    email: 'E-mail',
    phone: 'Telefone',
  };

  return (
    <div style={styles.container} className="pricing-container">
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title} className="pricing-title">Planos</h1>
        <p style={styles.subtitle} className="pricing-subtitle">Planos flexíveis para qualquer tamanho de operação.</p>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          <p>Carregando planos...</p>
        </div>
      ) : (
      <Fragment>
      <div style={styles.plansGrid}>
        {plans.map((plan) => (
          <div
            key={plan.id}
            style={{
              ...styles.planCard,
              ...(plan.popular ? styles.planCardPopular : {}),
            }}
            className="pricing-plan-card"
          >
            {plan.popular && (
              <div style={styles.popularBadge}>MAIS POPULAR</div>
            )}
            {plan.discount && (
              <div style={styles.discountBadge}>{plan.discount}</div>
            )}
            <h2 style={styles.planName}>{plan.name}</h2>
            <div style={styles.priceContainer}>
              <span style={styles.currency}>R$</span>
              <span style={styles.price} className="pricing-price">{plan.price.toFixed(2).replace('.', ',')}</span>
              <span style={styles.period}>{plan.period}</span>
            </div>
            <ul style={styles.featureList}>
              {plan.features.map((feature, index) => (
                <li
                  key={index}
                  style={{
                    ...styles.featureItem,
                    ...(feature.highlight ? styles.featureItemHighlight : {}),
                  }}
                  className="pricing-feature"
                >
                  <span style={styles.checkmark}>✓</span>
                  {feature.label}
                </li>
              ))}
            </ul>
            <button
              style={{
                ...styles.ctaButton,
                ...(plan.ctaStyle === 'primary' ? styles.ctaPrimary : {}),
                ...(plan.ctaStyle === 'dark' ? styles.ctaDark : {}),
              }}
              className="pricing-cta"
              onClick={() => handleSubscribe(plan.id)}
            >
              {plan.cta}
            </button>
          </div>
        ))}
      </div>

      {/* Jarvis Lifetime Banner */}
      <div style={styles.jarvisBanner} className="pricing-jarvis-banner">
        <div style={styles.jarvisContent}>
          <div style={styles.jarvisInfo}>
            <span style={styles.jarvisIcon}>🤖</span>
            <span style={styles.jarvisLabel}>JARVIS</span>
            <span style={styles.jarvisBadge}>VITALICIO</span>
          </div>
          <p style={styles.jarvisDescription}>
            Seu proprio Jarvis, personalizavel e com acesso vitalicio. Clientes do plano anual recebem
            este item como brinde.
          </p>
        </div>
        <button style={styles.downloadButton} className="pricing-download-btn">
          <span style={styles.downloadIcon}>⬇</span>
          Baixar Jarvis
        </button>
      </div>
      </Fragment>
      )}

      {/* PIX Payment Modal */}
      {showPixModal && (
        <div style={styles.modalOverlay} onClick={() => setShowPixModal(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h2 style={styles.modalTitle}>
                Pagamento via PIX - {selectedPlanData?.name}
              </h2>
              <button style={styles.modalClose} onClick={() => setShowPixModal(false)}>✕</button>
            </div>

            {pixLoading ? (
              <div style={styles.modalLoading}>Carregando informacoes PIX...</div>
            ) : !pixInfo || !pixInfo.pix_key ? (
              <div style={styles.modalEmpty}>
                <span style={{ fontSize: 32 }}>⚠️</span>
                <p>Chave PIX nao configurada pelo administrador.</p>
                <p style={{ fontSize: 12, color: '#999' }}>Entre em contato com o suporte.</p>
              </div>
            ) : paymentSent ? (
              <div style={styles.modalSuccess}>
                <span style={{ fontSize: 48 }}>✅</span>
                <h3 style={{ color: '#10b981', margin: '12px 0 8px' }}>Solicitacao Enviada!</h3>
                <p style={{ color: '#ccc', fontSize: 14, margin: 0, lineHeight: 1.5, textAlign: 'center' }}>
                  Sua solicitacao de pagamento foi enviada ao administrador.<br />
                  Apos a confirmacao, seu plano sera ativado automaticamente.
                </p>
                <button
                  style={{ ...styles.pixCopyBtn, marginTop: 16 }}
                  onClick={() => setShowPixModal(false)}
                >
                  Fechar
                </button>
              </div>
            ) : (
              <div>
                <div style={styles.pixAmountBox}>
                  <span style={styles.pixAmountLabel}>Valor</span>
                  <span style={styles.pixAmountValue}>
                    R$ {selectedPlanData?.price.toFixed(2).replace('.', ',')}
                  </span>
                </div>

                {pixInfo.pix_qr_url && (
                  <div style={styles.pixQrBox}>
                    <img
                      src={pixInfo.pix_qr_url}
                      alt="QR Code PIX"
                      style={styles.pixQrImage}
                    />
                  </div>
                )}

                <div style={styles.pixKeyBox}>
                  <span style={styles.pixKeyType}>{pixTypeLabel[pixInfo.pix_type] || 'PIX'}</span>
                  <span style={styles.pixKeyValue}>{pixInfo.pix_key}</span>
                  <button
                    style={{ ...styles.pixCopyBtn, ...(copied ? styles.pixCopyBtnCopied : {}) }}
                    onClick={handleCopyPix}
                  >
                    {copied ? '✓ Copiado!' : '📋 Copiar'}
                  </button>
                </div>

                {pixInfo.instructions && (
                  <div style={styles.pixInstructions}>
                    <strong>Instrucoes:</strong> {pixInfo.instructions}
                  </div>
                )}

                <button style={styles.pixConfirmBtn} onClick={handleRequestPayment}>
                  ✅ Ja paguei - Enviar para confirmacao
                </button>

                <p style={styles.pixNote}>
                  Apos o pagamento, envie a solicitacao acima. O admin ira confirmar e ativar seu plano.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '40px',
    minHeight: '100vh',
    position: 'relative',
    zIndex: 1,
    background: 'transparent',
  },
  header: {
    textAlign: 'center',
    marginBottom: '32px',
  },
  title: {
    fontSize: '48px',
    fontWeight: 'bold',
    marginBottom: '16px',
    background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  subtitle: {
    fontSize: '18px',
    color: '#a0a0a0',
    maxWidth: '500px',
    margin: '0 auto',
  },
  plansGrid: {
    display: 'flex',
    justifyContent: 'center',
    gap: '24px',
    flexWrap: 'wrap',
    maxWidth: '1200px',
    margin: '0 auto 32px',
    padding: '0 16px',
  },
  planCard: {
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '16px',
    padding: '32px',
    width: '100%',
    maxWidth: '320px',
    position: 'relative',
    transition: 'transform 0.3s ease, box-shadow 0.3s ease',
    display: 'flex',
    flexDirection: 'column',
  },
  planCardPopular: {
    background: 'rgba(139, 92, 246, 0.1)',
    border: '2px solid #8b5cf6',
    transform: 'scale(1.05)',
    boxShadow: '0 0 40px rgba(139, 92, 246, 0.3)',
  },
  popularBadge: {
    position: 'absolute',
    top: '-12px',
    left: '50%',
    transform: 'translateX(-50%)',
    background: 'linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)',
    color: '#ffffff',
    padding: '6px 16px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: 'bold',
    letterSpacing: '0.5px',
  },
  discountBadge: {
    position: 'absolute',
    top: '16px',
    right: '16px',
    background: 'rgba(0, 217, 255, 0.2)',
    color: '#00d9ff',
    padding: '4px 8px',
    borderRadius: '8px',
    fontSize: '11px',
    fontWeight: 'bold',
  },
  planName: {
    fontSize: '24px',
    fontWeight: '600',
    marginBottom: '16px',
    color: '#ffffff',
  },
  priceContainer: {
    display: 'flex',
    alignItems: 'baseline',
    marginBottom: '24px',
  },
  currency: {
    fontSize: '24px',
    fontWeight: '600',
    color: '#00d9ff',
    marginRight: '4px',
  },
  price: {
    fontSize: '48px',
    fontWeight: 'bold',
    color: '#ffffff',
    lineHeight: 1,
  },
  period: {
    fontSize: '16px',
    color: '#a0a0a0',
    marginLeft: '4px',
  },
  featureList: {
    listStyle: 'none',
    padding: 0,
    margin: '0 0 32px 0',
    flex: 1,
  },
  featureItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 0',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
    color: '#d0d0d0',
    fontSize: '15px',
  },
  featureItemHighlight: {
    color: '#00ff88',
    fontWeight: '500',
  },
  checkmark: {
    color: '#00d9ff',
    fontWeight: 'bold',
    fontSize: '16px',
  },
  ctaButton: {
    width: '100%',
    padding: '16px 24px',
    borderRadius: '12px',
    border: 'none',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    background: 'rgba(255, 255, 255, 0.1)',
    color: '#ffffff',
  },
  ctaPrimary: {
    background: 'linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)',
    color: '#ffffff',
    boxShadow: '0 4px 20px rgba(139, 92, 246, 0.4)',
  },
  ctaDark: {
    background: 'linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%)',
    color: '#ffffff',
    border: '1px solid rgba(255, 255, 255, 0.2)',
  },
  jarvisBanner: {
    maxWidth: '800px',
    margin: '0 auto',
    background: 'rgba(0, 217, 255, 0.05)',
    border: '1px solid rgba(0, 217, 255, 0.2)',
    borderRadius: '16px',
    padding: '24px 32px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '24px',
    flexWrap: 'wrap' as const,
  },
  jarvisContent: {
    flex: 1,
    minWidth: '300px',
  },
  jarvisInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '8px',
  },
  jarvisIcon: {
    fontSize: '24px',
  },
  jarvisLabel: {
    fontSize: '18px',
    fontWeight: 'bold',
    color: '#ffffff',
  },
  jarvisBadge: {
    background: '#00d9ff',
    color: '#000000',
    padding: '4px 8px',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 'bold',
  },
  jarvisDescription: {
    color: '#a0a0a0',
    fontSize: '14px',
    margin: 0,
    lineHeight: 1.5,
  },
  downloadButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)',
    color: '#000000',
    padding: '12px 24px',
    borderRadius: '12px',
    border: 'none',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'transform 0.2s ease',
    whiteSpace: 'nowrap' as const,
  },
  downloadIcon: {
    fontSize: '16px',
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0,0,0,0.8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: 16,
  },
  modal: {
    background: '#1a1a2e',
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 440,
    border: '1px solid rgba(255,255,255,0.1)',
    maxHeight: '90vh',
    overflow: 'auto',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    margin: 0,
  },
  modalClose: {
    background: 'transparent',
    border: 'none',
    color: '#999',
    fontSize: 20,
    cursor: 'pointer',
    padding: 4,
  },
  modalLoading: {
    textAlign: 'center',
    padding: 32,
    color: '#999',
  },
  modalEmpty: {
    textAlign: 'center',
    padding: 24,
  },
  modalSuccess: {
    textAlign: 'center',
    padding: 24,
  },
  pixAmountBox: {
    background: 'rgba(139, 92, 246, 0.1)',
    border: '1px solid rgba(139, 92, 246, 0.3)',
    borderRadius: 12,
    padding: 16,
    textAlign: 'center',
    marginBottom: 16,
  },
  pixAmountLabel: {
    display: 'block',
    fontSize: 12,
    color: '#999',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  pixAmountValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  pixQrBox: {
    textAlign: 'center',
    marginBottom: 16,
  },
  pixQrImage: {
    maxWidth: 180,
    maxHeight: 180,
    borderRadius: 12,
    border: '2px solid rgba(255,255,255,0.1)',
  },
  pixKeyBox: {
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  pixKeyType: {
    display: 'block',
    fontSize: 11,
    color: '#999',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  pixKeyValue: {
    display: 'block',
    fontSize: 14,
    color: '#fff',
    fontFamily: 'monospace',
    wordBreak: 'break-all',
    marginBottom: 8,
  },
  pixCopyBtn: {
    width: '100%',
    padding: '10px 16px',
    borderRadius: 8,
    border: 'none',
    background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)',
    color: '#000',
    fontSize: 13,
    fontWeight: '600',
    cursor: 'pointer',
  },
  pixCopyBtnCopied: {
    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    color: '#fff',
  },
  pixInstructions: {
    background: 'rgba(255,255,255,0.03)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 13,
    color: '#ccc',
    lineHeight: 1.5,
  },
  pixConfirmBtn: {
    width: '100%',
    padding: '14px 16px',
    borderRadius: 8,
    border: 'none',
    background: 'linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)',
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
    cursor: 'pointer',
    marginBottom: 8,
  },
  pixNote: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
    margin: 0,
    lineHeight: 1.5,
  },
};

export default PricingPage;
