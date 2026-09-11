import React, { useState, useEffect } from 'react';

interface Product {
  id: string;
  name: string;
  description: string;
  icon: string;
  image_url?: string;
  category: string;
  features: string[];
  download_url?: string;
  status: 'available' | 'coming-soon' | 'exclusive';
}

const MyDownloadsPage: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMyProducts();
  }, []);

  const fetchMyProducts = async () => {
    const token = localStorage.getItem('saas_token');
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch('/shop/my-products', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setProducts(data.products || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (product: Product) => {
    if (product.status === 'coming-soon') return;
    if (product.download_url) {
      window.open(product.download_url, '_blank');
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loading}>Carregando seus downloads...</div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.icon}>📥</span>
        <h1 style={styles.title}>Meus Downloads</h1>
        <p style={styles.subtitle}>Produtos e ferramentas liberadas para sua conta</p>
      </div>

      {products.length === 0 ? (
        <div style={styles.emptyCard}>
          <span style={styles.emptyIcon}>📦</span>
          <h3 style={styles.emptyTitle}>Nenhum download liberado</h3>
          <p style={styles.emptyText}>
            Você ainda não possui produtos liberados. Visite a loja para adquirir ferramentas e recursos exclusivos.
          </p>
        </div>
      ) : (
        <div style={styles.productsGrid}>
          {products.map((product) => (
            <div key={product.id} style={styles.productCard}>
              {product.image_url ? (
                <img src={product.image_url} alt={product.name} style={styles.productImage} />
              ) : (
                <div style={styles.productIcon}>{product.icon}</div>
              )}
              <div style={styles.productCategory}>{product.category}</div>
              <h3 style={styles.productName}>{product.name}</h3>
              <p style={styles.productDesc}>{product.description}</p>

              <div style={styles.features}>
                {product.features.map((feat, i) => (
                  <span key={i} style={styles.featureTag}>{feat}</span>
                ))}
              </div>

              <button
                style={{
                  ...styles.downloadBtn,
                  ...(product.status === 'coming-soon' ? styles.downloadBtnDisabled : {}),
                }}
                onClick={() => handleDownload(product)}
                disabled={product.status === 'coming-soon'}
              >
                {product.status === 'coming-soon' ? 'Em Breve' : 'Baixar'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '32px',
    minHeight: '100vh',
    maxWidth: '1200px',
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
  emptyCard: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    padding: '40px',
    textAlign: 'center',
  },
  emptyIcon: {
    fontSize: '48px',
    display: 'block',
    marginBottom: '12px',
  },
  emptyTitle: {
    fontSize: '20px',
    fontWeight: 'bold',
    color: '#fff',
    margin: '0 0 8px',
  },
  emptyText: {
    fontSize: '14px',
    color: '#999',
    lineHeight: 1.5,
  },
  productsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '16px',
  },
  productCard: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
  },
  productImage: {
    width: '100%',
    height: 140,
    objectFit: 'cover',
    borderRadius: 8,
    marginBottom: 12,
  },
  productIcon: {
    fontSize: '40px',
    textAlign: 'center',
    padding: '20px 0',
    marginBottom: 12,
  },
  productCategory: {
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    color: '#00d9ff',
    marginBottom: '4px',
  },
  productName: {
    fontSize: '18px',
    fontWeight: 'bold',
    color: '#fff',
    margin: '0 0 8px',
  },
  productDesc: {
    fontSize: '13px',
    color: '#999',
    margin: '0 0 12px',
    flex: 1,
  },
  features: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
    marginBottom: '16px',
  },
  featureTag: {
    fontSize: '11px',
    padding: '3px 8px',
    background: 'rgba(0, 217, 255, 0.1)',
    color: '#00d9ff',
    borderRadius: '10px',
  },
  downloadBtn: {
    padding: '10px',
    background: 'linear-gradient(135deg, #00d9ff, #00ff88)',
    border: 'none',
    borderRadius: '8px',
    color: '#000',
    fontWeight: '600',
    cursor: 'pointer',
    fontSize: '14px',
  },
  downloadBtnDisabled: {
    background: 'rgba(255,255,255,0.1)',
    color: '#666',
    cursor: 'not-allowed',
  },
};

export default MyDownloadsPage;
