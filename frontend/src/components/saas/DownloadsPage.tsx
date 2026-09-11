import React, { useState, useEffect } from 'react';

interface Product {
  id: string;
  name: string;
  description: string;
  icon: string;
  image_url?: string;
  category: string;
  price: number;
  original_price?: number;
  badge?: string;
  badge_color?: string;
  features: string[];
  download_url?: string;
  status: 'available' | 'coming-soon' | 'exclusive';
}

const DownloadsPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    fetch('/shop/products')
      .then(r => r.json())
      .then(d => setProducts(d.products || []))
      .catch(() => {});
  }, []);

  const categories = ['all', ...new Set(products.map(p => p.category))];

  const filteredProducts = products.filter(p => {
    const matchesCategory = selectedCategory === 'all' || p.category === selectedCategory;
    const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         p.description.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleDownload = (product: Product) => {
    if (product.status === 'coming-soon') {
      alert('Este produto estara disponivel em breve!');
      return;
    }
    if (product.download_url) {
      window.open(product.download_url, '_blank');
    } else if (product.price > 0) {
      alert(`Para adquirir ${product.name}, acesse a pagina de Planos ou entre em contato.`);
    } else {
      alert(`Download de ${product.name} iniciado!`);
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Downloads</h1>
          <p style={styles.subtitle}>Loja digital - Baixe suas ferramentas</p>
        </div>
      </div>

      {/* Search and Filters */}
      <div style={styles.filters}>
        <input
          type="text"
          placeholder="Buscar produtos..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={styles.searchInput}
        />
        <div style={styles.categoryTabs}>
          {categories.map(cat => (
            <button
              key={cat}
              style={{
                ...styles.categoryTab,
                ...(selectedCategory === cat ? styles.categoryTabActive : {}),
              }}
              onClick={() => setSelectedCategory(cat)}
            >
              {cat === 'all' ? 'Todos' : cat}
            </button>
          ))}
        </div>
      </div>

      {/* Products Grid */}
      <div style={styles.productsGrid}>
        {filteredProducts.map(product => (
          <div key={product.id} style={styles.productCard}>
            {product.badge && (
              <span style={{...styles.badge, background: product.badge_color}}>
                {product.badge}
              </span>
            )}
            
            {product.image_url ? (
              <img src={product.image_url} alt={product.name} style={{ width: '100%', height: 140, objectFit: 'cover', borderRadius: 8, marginBottom: 12 }} />
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

            <div style={styles.productFooter}>
              <div style={styles.priceContainer}>
                {product.original_price && (
                  <span style={styles.originalPrice}>R$ {product.original_price}</span>
                )}
                <span style={styles.price}>
                  {product.price === 0 ? 'Gratis' : 'R$ ' + product.price}
                </span>
              </div>
              
              <button
                style={{
                  ...styles.downloadBtn,
                  ...(product.status === 'coming-soon' ? styles.downloadBtnDisabled : {}),
                }}
                onClick={() => handleDownload(product)}
              >
                {product.status === 'coming-soon' ? 'Em Breve' : 
                 product.price === 0 ? 'Baixar' : 'Comprar'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div style={styles.statsBar}>
        <div style={styles.statItem}>
          <span style={styles.statValue}>{products.filter(p => p.status === 'available').length}</span>
          <span style={styles.statLabel}>Produtos Disponíveis</span>
        </div>
        <div style={styles.statItem}>
          <span style={styles.statValue}>{products.filter(p => p.status === 'coming-soon').length}</span>
          <span style={styles.statLabel}>Em Breve</span>
        </div>
        <div style={styles.statItem}>
          <span style={styles.statValue}>{products.filter(p => p.price === 0).length}</span>
          <span style={styles.statLabel}>Gratuitos</span>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '40px',
    color: 'var(--saas-text)',
    height: 'calc(100vh - 80px)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    marginBottom: '24px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold',
    margin: '0 0 8px 0',
  },
  subtitle: {
    color: 'var(--saas-text-muted)',
    margin: 0,
  },
  filters: {
    marginBottom: '24px',
    flexShrink: 0,
  },
  searchInput: {
    width: '100%',
    maxWidth: '400px',
    padding: '12px 16px',
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: '8px',
    color: 'var(--saas-text)',
    fontSize: '14px',
    marginBottom: '16px',
    boxSizing: 'border-box',
  },
  categoryTabs: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  },
  categoryTab: {
    padding: '8px 16px',
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '20px',
    color: 'var(--saas-text-muted)',
    fontSize: '13px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  categoryTabActive: {
    background: 'var(--saas-accent)',
    color: '#ffffff',
    borderColor: 'var(--saas-accent)',
  },
  productsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '20px',
    marginBottom: '24px',
    flex: 1,
    overflow: 'auto',
    paddingRight: '8px',
  },
  productCard: {
    position: 'relative',
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '16px',
    padding: '24px',
    transition: 'all 0.3s',
  },
  badge: {
    position: 'absolute',
    top: '16px',
    right: '16px',
    padding: '4px 10px',
    borderRadius: '6px',
    fontSize: '10px',
    fontWeight: 'bold',
    color: '#ffffff',
    letterSpacing: '0.5px',
  },
  productIcon: {
    fontSize: '40px',
    marginBottom: '16px',
  },
  productCategory: {
    fontSize: '11px',
    color: 'var(--saas-accent)',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    marginBottom: '8px',
  },
  productName: {
    fontSize: '20px',
    fontWeight: '600',
    margin: '0 0 8px 0',
    color: 'var(--saas-text)',
  },
  productDesc: {
    fontSize: '14px',
    color: 'var(--saas-text-muted)',
    margin: '0 0 16px 0',
    lineHeight: 1.5,
  },
  features: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    marginBottom: '20px',
  },
  featureTag: {
    padding: '4px 10px',
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: '6px',
    fontSize: '11px',
    color: 'var(--saas-text-muted)',
  },
  productFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: '16px',
    borderTop: '1px solid var(--saas-border)',
  },
  priceContainer: {
    display: 'flex',
    flexDirection: 'column',
  },
  originalPrice: {
    fontSize: '12px',
    color: 'var(--saas-text-muted)',
    textDecoration: 'line-through',
  },
  price: {
    fontSize: '22px',
    fontWeight: 'bold',
    color: 'var(--saas-accent)',
  },
  downloadBtn: {
    padding: '10px 20px',
    background: 'var(--saas-accent)',
    border: 'none',
    borderRadius: '8px',
    color: '#ffffff',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  downloadBtnDisabled: {
    background: 'var(--saas-border)',
    color: 'var(--saas-text-muted)',
    cursor: 'not-allowed',
  },
  statsBar: {
    display: 'flex',
    gap: '32px',
    padding: '20px',
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '12px',
    flexShrink: 0,
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
  },
  statValue: {
    fontSize: '24px',
    fontWeight: 'bold',
    color: 'var(--saas-accent)',
  },
  statLabel: {
    fontSize: '12px',
    color: 'var(--saas-text-muted)',
  },
};

export default DownloadsPage;
