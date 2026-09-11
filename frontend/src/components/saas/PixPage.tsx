import React, { useState, useEffect } from 'react';

interface PixPageProps {
  user?: { id: string; name: string; email: string; plan: string };
}

const PixPage: React.FC<PixPageProps> = ({ user }) => {
  const [pixInfo, setPixInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [myRequests, setMyRequests] = useState<any[]>([]);

  useEffect(() => {
    fetchPixInfo();
    fetchMyRequests();
  }, []);

  const fetchPixInfo = async () => {
    try {
      const res = await fetch('/admin/pix/public');
      if (res.ok) {
        const data = await res.json();
        setPixInfo(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMyRequests = async () => {
    try {
      const token = localStorage.getItem('saas_token');
      const res = await fetch('/plans/public');
      if (res.ok) {
        const data = await res.json();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCopy = () => {
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

  if (loading) {
    return (
      <div style={styles.container} className="pix-page-container">
        <div style={styles.loading}>Carregando informacoes PIX...</div>
      </div>
    );
  }

  if (!pixInfo || !pixInfo.pix_key) {
    return (
      <div style={styles.container} className="pix-page-container">
        <div style={styles.header}>
          <span style={styles.icon}>📱</span>
          <h1 style={styles.title}>Pagamento via PIX</h1>
        </div>
        <div style={styles.emptyCard}>
          <span style={styles.emptyIcon}>⚠️</span>
          <h3 style={styles.emptyTitle}>PIX nao configurado</h3>
          <p style={styles.emptyText}>
            O administrador ainda nao configurou a chave PIX de pagamento.
            Entre em contato com o suporte para mais informacoes.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container} className="pix-page-container">
      <div style={styles.header}>
        <span style={styles.icon}>📱</span>
        <h1 style={styles.title}>Pagamento via PIX</h1>
        <p style={styles.subtitle}>Realize o pagamento utilizing a chave PIX abaixo</p>
      </div>

      <div style={styles.pixCard}>
        <div style={styles.pixTypeBadge}>
          {pixTypeLabel[pixInfo.pix_type] || 'PIX'}
        </div>

        {pixInfo.pix_qr_url && (
          <div style={styles.qrContainer}>
            <img
              src={pixInfo.pix_qr_url}
              alt="QR Code PIX"
              style={styles.qrImage}
            />
          </div>
        )}

        <div style={styles.keySection}>
          <label style={styles.keyLabel}>Chave PIX</label>
          <div style={styles.keyBox}>
            <span style={styles.keyText}>{pixInfo.pix_key}</span>
            <button style={{ ...styles.copyBtn, ...(copied ? styles.copyBtnCopied : {}) }} onClick={handleCopy}>
              {copied ? '✓ Copiado!' : '📋 Copiar'}
            </button>
          </div>
        </div>

        {pixInfo.owner_name && (
          <div style={styles.infoRow}>
            <span style={styles.infoLabel}>Titular:</span>
            <span style={styles.infoValue}>{pixInfo.owner_name}</span>
          </div>
        )}

        {pixInfo.instructions && (
          <div style={styles.instructionsBox}>
            <span style={styles.instructionsLabel}>Instrucoes:</span>
            <p style={styles.instructionsText}>{pixInfo.instructions}</p>
          </div>
        )}

        <div style={styles.stepsBox}>
          <h3 style={styles.stepsTitle}>Como pagar:</h3>
          <div style={styles.step}>
            <span style={styles.stepNum}>1</span>
            <span style={styles.stepText}>Copie a chave PIX acima</span>
          </div>
          <div style={styles.step}>
            <span style={styles.stepNum}>2</span>
            <span style={styles.stepText}>Abra o app do seu banco</span>
          </div>
          <div style={styles.step}>
            <span style={styles.stepNum}>3</span>
            <span style={styles.stepText}>Escolha pagar via PIX e cole a chave</span>
          </div>
          <div style={styles.step}>
            <span style={styles.stepNum}>4</span>
            <span style={styles.stepText}>Confirme o pagamento</span>
          </div>
          <div style={styles.step}>
            <span style={styles.stepNum}>5</span>
            <span style={styles.stepText}>Aguarde a confirmacao do administrador</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '40px',
    minHeight: '100vh',
    maxWidth: '600px',
    margin: '0 auto',
  },
  loading: {
    textAlign: 'center',
    padding: '60px',
    color: '#999',
  },
  header: {
    textAlign: 'center',
    marginBottom: '32px',
  },
  icon: {
    fontSize: '48px',
    display: 'block',
    marginBottom: '16px',
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
  emptyCard: {
    background: 'rgba(245, 158, 11, 0.1)',
    border: '1px solid rgba(245, 158, 11, 0.3)',
    borderRadius: '12px',
    padding: '40px',
    textAlign: 'center',
  },
  emptyIcon: {
    fontSize: '48px',
    display: 'block',
    marginBottom: '16px',
  },
  emptyTitle: {
    fontSize: '18px',
    fontWeight: '600',
    color: '#f59e0b',
    margin: '0 0 8px',
  },
  emptyText: {
    fontSize: '14px',
    color: '#999',
    margin: 0,
    lineHeight: 1.5,
  },
  pixCard: {
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '16px',
    padding: '32px',
  },
  pixTypeBadge: {
    display: 'inline-block',
    background: 'rgba(0, 217, 255, 0.15)',
    color: '#00d9ff',
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: '600',
    marginBottom: '24px',
  },
  qrContainer: {
    textAlign: 'center',
    marginBottom: '24px',
  },
  qrImage: {
    maxWidth: '200px',
    maxHeight: '200px',
    borderRadius: '12px',
    border: '2px solid rgba(255, 255, 255, 0.1)',
  },
  keySection: {
    marginBottom: '20px',
  },
  keyLabel: {
    display: 'block',
    fontSize: '12px',
    color: '#999',
    marginBottom: '8px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  keyBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '8px',
    padding: '12px 16px',
  },
  keyText: {
    flex: 1,
    fontSize: '15px',
    color: '#ffffff',
    fontFamily: 'monospace',
    wordBreak: 'break-all',
  },
  copyBtn: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: 'none',
    background: 'linear-gradient(135deg, #00d9ff 0%, #00ff88 100%)',
    color: '#000',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  copyBtnCopied: {
    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    color: '#fff',
  },
  infoRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '12px 0',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  },
  infoLabel: {
    fontSize: '13px',
    color: '#999',
  },
  infoValue: {
    fontSize: '13px',
    color: '#fff',
    fontWeight: '500',
  },
  instructionsBox: {
    background: 'rgba(255, 255, 255, 0.03)',
    borderRadius: '8px',
    padding: '16px',
    marginTop: '16px',
    marginBottom: '16px',
  },
  instructionsLabel: {
    fontSize: '12px',
    color: '#999',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  instructionsText: {
    fontSize: '14px',
    color: '#ccc',
    margin: '8px 0 0',
    lineHeight: 1.5,
  },
  stepsBox: {
    marginTop: '24px',
    paddingTop: '24px',
    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
  },
  stepsTitle: {
    fontSize: '16px',
    fontWeight: '600',
    color: '#fff',
    margin: '0 0 16px',
  },
  step: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '12px',
  },
  stepNum: {
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    background: 'rgba(0, 217, 255, 0.15)',
    color: '#00d9ff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '13px',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  stepText: {
    fontSize: '14px',
    color: '#ccc',
  },
};

export default PixPage;
