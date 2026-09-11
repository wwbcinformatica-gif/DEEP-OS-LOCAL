import React, { useState, useEffect } from 'react';
import AuthPage from './AuthPage';
import PricingPage from './PricingPage';
import Sidebar from './Sidebar';
import InstancesPage from './InstancesPage';
import SettingsPage from './SettingsPage';
import HelpModal from './HelpModal';
import SpaceBackground from './SpaceBackground';
import AdminDashboard from './AdminDashboard';
import DownloadsPage from './DownloadsPage';
import JarvisPage from './JarvisPage';
import CharonPage from './CharonPage';
import ChatBotPage from './ChatBotPage';
import PixPage from './PixPage';
import MyPlansPage from './MyPlansPage';
import MyDownloadsPage from './MyDownloadsPage';
import { AppSettingsProvider } from './AppSettingsContext';

interface User {
  id: string;
  name: string;
  email: string;
  plan: string;
  status: string;
}

const SaaSApp: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [currentPage, setCurrentPage] = useState('plans');
  const [showHelp, setShowHelp] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('saas_token');
    const savedUser = localStorage.getItem('saas_user');
    
    if (token && savedUser) {
      setIsAuthenticated(true);
      setUser(JSON.parse(savedUser));
      // Atualiza dados do usuario do backend (plano pode ter mudado via admin)
      refreshUserProfile(token);
    }

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebarOpen) setSidebarOpen(false);
    };
    window.addEventListener('keydown', handleEsc);

    return () => {
      window.removeEventListener('keydown', handleEsc);
    };
  }, [sidebarOpen]);

  const refreshUserProfile = async (token: string) => {
    try {
      const res = await fetch('/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        const updatedUser = {
          id: data.id,
          name: data.name,
          email: data.email,
          plan: data.plan,
          status: data.status,
        };
        setUser(updatedUser);
        localStorage.setItem('saas_user', JSON.stringify(updatedUser));
      }
    } catch (e) {
      // Silently ignore - usa dados do localStorage
    }
  };

  const handleAuth = (token: string, userData: any) => {
    setIsAuthenticated(true);
    setUser(userData);
  };

  const handleNavigate = (page: string) => {
    if (page === 'help') {
      setShowHelp(true);
    } else {
      setCurrentPage(page);
      setSidebarOpen(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('saas_token');
    localStorage.removeItem('saas_user');
    setIsAuthenticated(false);
    setUser(null);
    setCurrentPage('plans');
  };

  if (!isAuthenticated) {
    return (
      <AppSettingsProvider>
        <SpaceBackground />
        <AuthPage onAuth={handleAuth} />
      </AppSettingsProvider>
    );
  }

  const renderContent = () => {
    switch (currentPage) {
      case 'plans':
        return <PricingPage />;
      case 'my-plans':
        return <MyPlansPage />;
      case 'my-downloads':
        return <MyDownloadsPage />;
      case 'instances':
        return <InstancesPage />;
      case 'settings':
        return <SettingsPage />;
      case 'downloads':
        return <DownloadsPage />;
      case 'jarvis':
        return <JarvisPage />;
      case 'charon':
        return <CharonPage />;
      case 'admin':
        return <AdminDashboard onLogout={() => setCurrentPage('plans')} />;
      case 'commands':
        return (
          <div style={styles.placeholder}>
            <span style={styles.placeholderIcon}>📜</span>
            <h2>Commands</h2>
            <p>Gerencie comandos personalizados para seus agentes</p>
            <div style={styles.comingSoon}>Em breve</div>
          </div>
        );
      case 'triggers':
        return (
          <div style={styles.placeholder}>
            <span style={styles.placeholderIcon}>🔥</span>
            <h2>Gatilhos</h2>
            <p>Configure gatilhos automaticos para acoes</p>
            <div style={styles.comingSoon}>Em breve</div>
          </div>
        );
      case 'chatbot':
        return <ChatBotPage />;
      case 'leads':
        return (
          <div style={styles.placeholder}>
            <span style={styles.placeholderIcon}>📊</span>
            <h2>Radar de Leads</h2>
            <p>Monitore e capture leads automaticamente</p>
            <div style={styles.betaBadge}>BETA</div>
          </div>
        );
      case 'reports':
        return (
          <div style={styles.placeholder}>
            <span style={styles.placeholderIcon}>📈</span>
            <h2>Relatórios</h2>
            <p>Visualize metricas e analises detalhadas</p>
            <div style={styles.comingSoon}>Em breve</div>
          </div>
        );
      case 'announcements':
        return (
          <div style={styles.placeholder}>
            <span style={styles.placeholderIcon}>📢</span>
            <h2>Comunicados</h2>
            <p>Veja as ultimas novidades e comunicados</p>
            <div style={styles.comingSoon}>Em breve</div>
          </div>
        );
      case 'pix':
        return <PixPage user={user || undefined} />;
      default:
        return <PricingPage />;
    }
  };

  return (
    <AppSettingsProvider>
      <div style={styles.appContainer}>
        <SpaceBackground />
        
        <button
          className="mobile-menu-btn"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          {sidebarOpen ? '✕' : '☰'}
        </button>
        
        {sidebarOpen && (
          <div
            className="mobile-overlay"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        
        <Sidebar
          currentPage={currentPage}
          onNavigate={handleNavigate}
          user={user || undefined}
          isOpen={sidebarOpen}
        />
        <main className={`saas-main-content ${currentPage === 'charon' || currentPage === 'jarvis' ? '' : 'scrollable'}`}>
          {renderContent()}
        </main>
        
        <HelpModal isOpen={showHelp} onClose={() => setShowHelp(false)} />
      </div>
    </AppSettingsProvider>
  );
};

const styles: Record<string, React.CSSProperties> = {
  appContainer: {
    display: 'flex',
    minHeight: '100dvh',
    position: 'relative',
    zIndex: 1,
  },
  placeholder: {
    padding: '60px 40px',
    textAlign: 'center',
    color: '#ffffff',
  },
  placeholderIcon: {
    fontSize: '64px',
    display: 'block',
    marginBottom: '24px',
  },
  comingSoon: {
    display: 'inline-block',
    marginTop: '24px',
    padding: '8px 16px',
    background: 'rgba(0, 217, 255, 0.1)',
    borderRadius: '8px',
    color: '#00d9ff',
    fontSize: '14px',
    fontWeight: '500',
  },
  betaBadge: {
    display: 'inline-block',
    marginTop: '24px',
    padding: '8px 16px',
    background: 'rgba(16, 185, 129, 0.1)',
    borderRadius: '8px',
    color: '#10b981',
    fontSize: '14px',
    fontWeight: '500',
  },
};

export default SaaSApp;
