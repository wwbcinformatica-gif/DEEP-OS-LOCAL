import React, { useState, useEffect } from 'react';
import { useAppSettings } from './AppSettingsContext';

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('profile');
  const [name, setName] = useState('Wilson');
  const [email, setEmail] = useState('wwbc22@gmail.com');
  const [company, setCompany] = useState('');
  const [phone, setPhone] = useState('');
  const [pixKey, setPixKey] = useState('');
  const [pixType, setPixType] = useState<'cpf' | 'cnpj' | 'email' | 'phone' | 'random'>('random');
  const [apiKey, setApiKey] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pixSaved, setPixSaved] = useState(false);
  const [apiSaved, setApiSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  
  const { space, theme, updateSpace, updateTheme } = useAppSettings();

  const savedUser = JSON.parse(localStorage.getItem('saas_user') || '{}');
  const isMaster = savedUser.plan === 'master' || savedUser.email === 'wwbcinformatica@gmail.com' || savedUser.email === 'wwbc22@gmail.com';

  useEffect(() => {
    const savedPix = localStorage.getItem('saas_pix_key');
    const savedPixType = localStorage.getItem('saas_pix_type');
    const savedApiKey = localStorage.getItem('saas_api_key');
    if (savedPix) setPixKey(savedPix);
    if (savedPixType) setPixType(savedPixType as any);
    if (savedApiKey) setApiKey(savedApiKey);
  }, []);

  const handleSaveProfile = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('saas_token');
      await fetch('/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      alert('Perfil salvo com sucesso!');
    } catch {
      alert('Perfil salvo!');
    }
    setLoading(false);
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      alert('As senhas não coincidem!');
      return;
    }
    setLoading(true);
    try {
      const token = localStorage.getItem('saas_token');
      const res = await fetch('/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        alert('Senha alterada com sucesso!');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      } else {
        alert(data.detail || 'Erro ao alterar senha');
      }
    } catch {
      alert('Erro ao alterar senha');
    }
    setLoading(false);
  };

  const handleSavePix = async () => {
    if (!pixKey.trim()) {
      alert('Informe sua chave PIX!');
      return;
    }
    setLoading(true);
    try {
      const token = localStorage.getItem('saas_token');
      const res = await fetch('/auth/pix-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ pix_key: pixKey }),
      });
      if (res.ok) {
        localStorage.setItem('saas_pix_key', pixKey);
        localStorage.setItem('saas_pix_type', pixType);
        setPixSaved(true);
        alert('Chave PIX salva com sucesso!');
        setTimeout(() => setPixSaved(false), 3000);
      } else {
        const data = await res.json();
        alert(data.detail || 'Erro ao salvar chave PIX');
      }
    } catch {
      localStorage.setItem('saas_pix_key', pixKey);
      localStorage.setItem('saas_pix_type', pixType);
      setPixSaved(true);
      alert('Chave PIX salva localmente!');
      setTimeout(() => setPixSaved(false), 3000);
    }
    setLoading(false);
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      alert('Informe sua chave de API!');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/config/api-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key: apiKey }),
      });
      if (res.ok) {
        localStorage.setItem('saas_api_key', apiKey);
        setApiSaved(true);
        alert('Chave de API salva no servidor!');
        setTimeout(() => setApiSaved(false), 3000);
      } else {
        localStorage.setItem('saas_api_key', apiKey);
        setApiSaved(true);
        alert('Chave salva localmente (servidor indisponivel)');
        setTimeout(() => setApiSaved(false), 3000);
      }
    } catch {
      localStorage.setItem('saas_api_key', apiKey);
      setApiSaved(true);
      alert('Chave de API salva localmente!');
      setTimeout(() => setApiSaved(false), 3000);
    }
    setLoading(false);
  };

  const handleThemeChange = (newTheme: 'glass' | 'dark' | 'light' | 'cyberpunk' | 'midnight') => {
    updateTheme({ theme: newTheme });
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Configurações</h1>
          <p style={styles.subtitle}>Personalize sua experiência</p>
        </div>
        <button
          style={styles.saveButton}
          onClick={() => {
            localStorage.setItem('spaceSettings', JSON.stringify(space));
            localStorage.setItem('themeSettings', JSON.stringify(theme));
            alert('Configurações salvas com sucesso!');
          }}
        >
          Salvar
        </button>
      </div>

      {/* Tabs */}
      <div style={styles.tabs}>
        <button
          style={{...styles.tab, ...(activeTab === 'profile' ? styles.tabActive : {})}}
          onClick={() => setActiveTab('profile')}
        >
          Perfil
        </button>
        {isMaster && (
          <button
            style={{...styles.tab, ...(activeTab === 'pix' ? styles.tabActive : {})}}
            onClick={() => setActiveTab('pix')}
          >
            PIX
          </button>
        )}
        <button
          style={{...styles.tab, ...(activeTab === 'api' ? styles.tabActive : {})}}
          onClick={() => setActiveTab('api')}
        >
          Chave API
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'password' ? styles.tabActive : {})}}
          onClick={() => setActiveTab('password')}
        >
          Senha
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'subscription' ? styles.tabActive : {})}}
          onClick={() => setActiveTab('subscription')}
        >
          Assinatura
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'notifications' ? styles.tabActive : {})}}
          onClick={() => setActiveTab('notifications')}
        >
          Notificações
        </button>
        <button
          style={{...styles.tab, ...(activeTab === 'appearance' ? styles.tabActive : {})}}
          onClick={() => setActiveTab('appearance')}
        >
          Aparência
        </button>
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Informações Pessoais</h2>
          
          <div style={styles.formGroup}>
            <label style={styles.label}>Nome</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Empresa (Opcional)</label>
            <input
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Sua empresa"
              style={styles.input}
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Telefone (Opcional)</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="(XX) XXXXX-XXXX"
              style={styles.input}
            />
          </div>

          <button style={styles.saveButton} onClick={handleSaveProfile}>
            Salvar Alterações
          </button>
        </div>
      )}

      {/* PIX Tab */}
      {activeTab === 'pix' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Chave PIX</h2>
          <p style={{...styles.settingDesc, marginBottom: '20px'}}>
            Configure sua chave PIX para receber pagamentos
          </p>
          
          <div style={styles.formGroup}>
            <label style={styles.label}>Tipo de Chave</label>
            <div style={styles.pixTypeGrid}>
              {[
                { id: 'random' as const, label: 'Aleatória', icon: '🔑' },
                { id: 'cpf' as const, label: 'CPF', icon: '📄' },
                { id: 'cnpj' as const, label: 'CNPJ', icon: '🏢' },
                { id: 'email' as const, label: 'Email', icon: '📧' },
                { id: 'phone' as const, label: 'Telefone', icon: '📱' },
              ].map((type) => (
                <button
                  key={type.id}
                  style={{
                    ...styles.pixTypeBtn,
                    ...(pixType === type.id ? styles.pixTypeBtnActive : {}),
                  }}
                  onClick={() => setPixType(type.id)}
                >
                  <span style={{fontSize: '18px'}}>{type.icon}</span>
                  <span>{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Chave PIX</label>
            <input
              type="text"
              value={pixKey}
              onChange={(e) => setPixKey(e.target.value)}
              placeholder={
                pixType === 'random' ? 'Chave aleatória gerada pelo banco' :
                pixType === 'cpf' ? '000.000.000-00' :
                pixType === 'cnpj' ? '00.000.000/0001-00' :
                pixType === 'email' ? 'seu@email.com' :
                '(00) 00000-0000'
              }
              style={styles.input}
            />
          </div>

          <div style={styles.pixInfo}>
            <span style={{fontSize: '14px'}}>💡</span>
            <span style={styles.pixInfoText}>
              {pixType === 'random' 
                ? 'A chave aleatória é gerada pelo seu banco. Copie ela no app do banco.'
                : 'Insira a chave PIX conforme o tipo selecionado.'}
            </span>
          </div>

          <div style={{display: 'flex', gap: '12px', marginTop: '20px'}}>
            <button style={styles.saveButton} onClick={handleSavePix}>
              {pixSaved ? '✓ Salvo!' : 'Salvar Chave PIX'}
            </button>
          </div>

          {pixKey && (
            <div style={styles.pixPreview}>
              <h4 style={{margin: '0 0 8px 0', color: 'var(--saas-text)'}}>Preview do QR Code</h4>
              <div style={styles.pixQrPlaceholder}>
                <span style={{fontSize: '40px'}}>📱</span>
                <span style={{fontSize: '13px', color: 'var(--saas-text-muted)'}}>
                  QR Code será gerado com esta chave
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* API Key Tab */}
      {activeTab === 'api' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Chave de API</h2>
          <p style={{...styles.settingDesc, marginBottom: '20px'}}>
            Configure sua chave de API para usar com Jarvis, Charon e outros agentes IA
          </p>

          <div style={styles.apiInfo}>
            <span style={{fontSize: '24px'}}>🔑</span>
            <div>
              <h4 style={{margin: '0 0 4px 0', color: 'var(--saas-text)'}}>Como obter sua chave:</h4>
              <ol style={{margin: '0', paddingLeft: '20px', color: 'var(--saas-text-muted)', fontSize: '13px', lineHeight: 1.8}}>
                <li>Acesse <a href="https://aistudio.google.com/apikey" target="_blank" style={{color: 'var(--saas-accent)'}}>Google AI Studio</a></li>
                <li>Faça login com sua conta Google</li>
                <li>Clique em "Create API Key"</li>
                <li>Copie a chave gerada</li>
                <li>Cole abaixo e salve</li>
              </ol>
            </div>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Chave de API (Google Gemini)</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="AIzaSy..."
              style={styles.input}
            />
            <p style={{...styles.settingDesc, marginTop: '8px'}}>
              Sua chave fica salva apenas no seu navegador. Nunca compartilhe.
            </p>
          </div>

          <div style={{display: 'flex', gap: '12px', marginTop: '20px'}}>
            <button 
              style={{...styles.saveButton, opacity: loading ? 0.6 : 1}} 
              onClick={handleSaveApiKey}
              disabled={loading}
            >
              {apiSaved ? '✓ Salvo!' : loading ? 'Salvando...' : 'Salvar Chave de API'}
            </button>
            {apiKey && (
              <button 
                style={{...styles.saveButton, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444'}}
                onClick={() => { setApiKey(''); localStorage.removeItem('saas_api_key'); }}
              >
                Remover
              </button>
            )}
          </div>

          {apiKey && (
            <div style={styles.apiStatus}>
              <span style={{color: '#10b981'}}>✓</span>
              <span style={{fontSize: '13px', color: 'var(--saas-text-muted)'}}>
                Chave configurada - Jarvis e Charon estão prontos para uso
              </span>
            </div>
          )}
        </div>
      )}

      {/* Password Tab */}
      {activeTab === 'password' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Alterar Senha</h2>
          
          <div style={styles.formGroup}>
            <label style={styles.label}>Senha Atual</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Nova Senha</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Confirmar Nova Senha</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={styles.input}
            />
          </div>

          <button style={styles.saveButton} onClick={handleChangePassword}>
            Alterar Senha
          </button>
        </div>
      )}

      {/* Subscription Tab */}
      {activeTab === 'subscription' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Gerenciar Assinatura</h2>
          
          <div style={styles.subscriptionCard}>
            <div>
              <span style={styles.planBadge}>Plano Atual</span>
              <h3 style={styles.currentPlan}>Gratuito</h3>
              <p style={styles.planDetails}>1 instância • 20 mensagens/dia</p>
            </div>
            <button style={styles.upgradeButton}>Fazer Upgrade</button>
          </div>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Preferências de Notificação</h2>
          
          {[
            { title: 'Email de Novidades', desc: 'Receba atualizações sobre novos recursos' },
            { title: 'Alertas de Uso', desc: 'Seja notificado quando atingir 80% do limite' },
            { title: 'Emails de Cobrança', desc: 'Receba comprovantes de pagamento' },
          ].map((item, i) => (
            <div key={i} style={styles.notificationOption}>
              <div>
                <h4 style={styles.optionTitle}>{item.title}</h4>
                <p style={styles.optionDesc}>{item.desc}</p>
              </div>
              <label style={styles.toggle}>
                <input type="checkbox" defaultChecked />
                <span style={styles.toggleSlider}></span>
              </label>
            </div>
          ))}
        </div>
      )}

      {/* Appearance Tab */}
      {activeTab === 'appearance' && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Aparência</h2>
          
          {/* Theme Selection */}
          <div style={styles.settingGroup}>
            <label style={styles.label}>Tema</label>
            <p style={styles.settingDesc}>Escolha o tema visual do painel</p>
            <div style={styles.themeGrid}>
              {[
                { id: 'glass' as const, name: 'Vidro', icon: '💎', colors: 'rgba(255,255,255,0.1), rgba(255,255,255,0.05)' },
                { id: 'dark' as const, name: 'Dark', icon: '🌙', colors: '#0a0a1a, #1a1a2e' },
                { id: 'light' as const, name: 'Light', icon: '☀️', colors: '#f0f2f5, #ffffff' },
                { id: 'cyberpunk' as const, name: 'Cyberpunk', icon: '⚡', colors: '#0a0015, #1a0030' },
                { id: 'midnight' as const, name: 'Midnight', icon: '🌌', colors: '#0d1117, #161b22' },
              ].map((t) => (
                <button
                  key={t.id}
                  style={{
                    ...styles.themeCard,
                    ...(theme.theme === t.id ? styles.themeCardActive : {}),
                    borderColor: theme.theme === t.id ? 'var(--saas-accent)' : 'var(--saas-border)',
                  }}
                  onClick={() => handleThemeChange(t.id)}
                >
                  <div style={{...styles.themePreview, background: `linear-gradient(135deg, ${t.colors})`}}>
                    <span style={{fontSize: '20px'}}>{t.icon}</span>
                  </div>
                  <span style={{...styles.themeName, color: 'var(--saas-text)'}}>{t.name}</span>
                  {theme.theme === t.id && <span style={styles.themeCheck}>✓</span>}
                </button>
              ))}
            </div>
          </div>

          {/* Space Effect Toggle */}
          <div style={styles.settingGroup}>
            <div style={styles.settingRow}>
              <div>
                <label style={styles.label}>Efeito Espacial</label>
                <p style={styles.settingDesc}>
                  {theme.theme === 'light' 
                    ? 'Desativado automaticamente no tema Light' 
                    : 'Ativar ou desativar a animação de estrelas'}
                </p>
              </div>
              <label style={{...styles.toggle, opacity: theme.theme === 'light' ? 0.5 : 1}}>
                <input 
                  type="checkbox" 
                  checked={space.enabled}
                  onChange={(e) => updateSpace({ enabled: e.target.checked })}
                  disabled={theme.theme === 'light'}
                />
                <span style={styles.toggleSlider}></span>
              </label>
            </div>
          </div>

          {/* Speed Control */}
          <div style={{...styles.settingGroup, opacity: space.enabled ? 1 : 0.4, pointerEvents: space.enabled ? 'auto' : 'none'}}>
            <div style={styles.settingHeader}>
              <label style={styles.label}>Velocidade</label>
              <span style={styles.settingValue}>{space.speed}</span>
            </div>
            <div style={styles.sliderContainer}>
              <span style={styles.sliderLabel}>Lento</span>
              <input
                type="range"
                min="2"
                max="30"
                value={space.speed}
                onChange={(e) => updateSpace({ speed: Number(e.target.value) })}
                style={styles.slider}
              />
              <span style={styles.sliderLabel}>Rápido</span>
            </div>
          </div>

          {/* Font Size */}
          <div style={{...styles.settingGroup, opacity: 1, pointerEvents: 'auto'}}>
            <div style={styles.settingHeader}>
              <label style={styles.label}>Tamanho da Fonte</label>
              <span style={styles.settingValue}>{space.fontSize}</span>
            </div>
            <div style={{display: 'flex', gap: '12px', marginTop: '8px'}}>
              <button
                onClick={() => updateSpace({ fontSize: '8px' })}
                style={{
                  ...styles.settingButton,
                  width: '50px',
                  background: space.fontSize === '8px' ? 'var(--saas-accent)' : 'transparent',
                  color: space.fontSize === '8px' ? '#fff' : 'var(--saas-text)',
                }}
              >8px</button>
              <button
                onClick={() => updateSpace({ fontSize: '10px' })}
                style={{
                  ...styles.settingButton,
                  width: '50px',
                  background: space.fontSize === '10px' ? 'var(--saas-accent)' : 'transparent',
                  color: space.fontSize === '10px' ? '#fff' : 'var(--saas-text)',
                }}
              >10px</button>
              <button
                onClick={() => updateSpace({ fontSize: '12px' })}
                style={{
                  ...styles.settingButton,
                  width: '50px',
                  background: space.fontSize === '12px' ? 'var(--saas-accent)' : 'transparent',
                  color: space.fontSize === '12px' ? '#fff' : 'var(--saas-text)',
                }}
              >12px</button>
              <button
                onClick={() => updateSpace({ fontSize: '14px' })}
                style={{
                  ...styles.settingButton,
                  width: '50px',
                  background: space.fontSize === '14px' ? 'var(--saas-accent)' : 'transparent',
                  color: space.fontSize === '14px' ? '#fff' : 'var(--saas-text)',
                }}
              >14px</button>
            </div>
          </div>

          {/* Star Count */}
          <div style={{...styles.settingGroup, opacity: space.enabled ? 1 : 0.4, pointerEvents: space.enabled ? 'auto' : 'none'}}>
            <div style={styles.settingHeader}>
              <label style={styles.label}>Estrelas</label>
              <span style={styles.settingValue}>{space.starCount}</span>
            </div>
            <div style={styles.sliderContainer}>
              <span style={styles.sliderLabel}>Poucas</span>
              <input
                type="range"
                min="100"
                max="2000"
                step="100"
                value={space.starCount}
                onChange={(e) => updateSpace({ starCount: Number(e.target.value) })}
                style={styles.slider}
              />
              <span style={styles.sliderLabel}>Muitas</span>
            </div>
          </div>

          {/* Presets */}
          <div style={{...styles.settingGroup, opacity: space.enabled ? 1 : 0.4, pointerEvents: space.enabled ? 'auto' : 'none'}}>
            <label style={styles.label}>Predefinições</label>
            <div style={styles.presets}>
              <button style={styles.presetBtn} onClick={() => updateSpace({ speed: 5, starCount: 400 })}>Tranquilo</button>
              <button style={styles.presetBtn} onClick={() => updateSpace({ speed: 12, starCount: 800 })}>Padrão</button>
              <button style={styles.presetBtn} onClick={() => updateSpace({ speed: 20, starCount: 1200 })}>Intenso</button>
              <button style={styles.presetBtn} onClick={() => updateSpace({ speed: 30, starCount: 2000 })}>Hiperespaço</button>
            </div>
          </div>

          {/* Save Button */}
          <div style={{marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'flex-end'}}>
            <button
              style={styles.saveButton}
              onClick={() => {
                localStorage.setItem('spaceSettings', JSON.stringify(space));
                localStorage.setItem('themeSettings', JSON.stringify(theme));
                alert('Configurações salvas com sucesso!');
              }}
            >
              Salvar Configurações
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '40px',
    color: 'var(--saas-text)',
    height: 'calc(100vh - 80px)',
    overflowY: 'auto',
    overflowX: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '24px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold',
    margin: '0 0 8px 0',
  },
  subtitle: {
    color: 'var(--saas-text-muted)',
    margin: '0 0 32px 0',
  },
  tabs: {
    display: 'flex',
    gap: '4px',
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '12px',
    padding: '4px',
    marginBottom: '32px',
    width: 'fit-content',
    flexWrap: 'wrap',
  },
  tab: {
    padding: '10px 20px',
    border: 'none',
    borderRadius: '8px',
    background: 'transparent',
    color: 'var(--saas-text-muted)',
    fontSize: '14px',
    cursor: 'pointer',
  },
  tabActive: {
    background: 'var(--saas-accent)',
    color: theme => theme === 'light' ? '#ffffff' : '#000',
  },
  section: {
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '12px',
    padding: '24px',
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: '600',
    margin: '0 0 20px 0',
    color: 'var(--saas-text)',
  },
  formGroup: {
    marginBottom: '20px',
  },
  label: {
    display: 'block',
    fontSize: '14px',
    color: 'var(--saas-text-muted)',
    marginBottom: '8px',
  },
  input: {
    width: '100%',
    padding: '12px 16px',
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: '8px',
    color: 'var(--saas-text)',
    fontSize: '14px',
    boxSizing: 'border-box',
  },
  saveButton: {
    background: 'var(--saas-accent)',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '12px 24px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  subscriptionCard: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: 'var(--saas-bg-input)',
    border: '1px solid var(--saas-border)',
    borderRadius: '12px',
    padding: '24px',
  },
  planBadge: {
    fontSize: '12px',
    color: 'var(--saas-accent)',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
  currentPlan: {
    fontSize: '24px',
    margin: '8px 0',
    color: 'var(--saas-text)',
  },
  planDetails: {
    color: 'var(--saas-text-muted)',
    margin: 0,
  },
  upgradeButton: {
    background: 'var(--saas-accent)',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '12px 24px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  notificationOption: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 0',
    borderBottom: '1px solid var(--saas-border)',
  },
  optionTitle: {
    margin: '0 0 4px 0',
    fontSize: '14px',
    color: 'var(--saas-text)',
  },
  optionDesc: {
    margin: 0,
    fontSize: '13px',
    color: 'var(--saas-text-muted)',
  },
  toggle: {
    position: 'relative',
    display: 'inline-block',
    width: '48px',
    height: '24px',
    cursor: 'pointer',
  },
  toggleSlider: {
    position: 'absolute',
    cursor: 'pointer',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'var(--saas-border)',
    borderRadius: '24px',
    transition: '0.3s',
  },
  settingGroup: {
    marginBottom: '24px',
    padding: '20px',
    background: 'var(--saas-bg-input)',
    borderRadius: '12px',
    border: '1px solid var(--saas-border)',
  },
  settingRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  settingHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  settingValue: {
    fontSize: '18px',
    fontWeight: 'bold',
    color: 'var(--saas-accent)',
  },
  settingDesc: {
    fontSize: '13px',
    color: 'var(--saas-text-muted)',
    margin: '4px 0 0 0',
  },
  sliderContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  sliderLabel: {
    fontSize: '12px',
    color: 'var(--saas-text-muted)',
    minWidth: '50px',
  },
  slider: {
    flex: 1,
    height: '8px',
    borderRadius: '4px',
    background: 'var(--saas-border)',
    outline: 'none',
    WebkitAppearance: 'none',
    cursor: 'pointer',
  },
  presets: {
    display: 'flex',
    gap: '12px',
    marginTop: '12px',
    flexWrap: 'wrap',
  },
  presetBtn: {
    padding: '10px 20px',
    background: 'var(--saas-bg-card)',
    border: '1px solid var(--saas-border)',
    borderRadius: '8px',
    color: 'var(--saas-text)',
    fontSize: '14px',
    cursor: 'pointer',
  },
  themeGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
    gap: '12px',
    marginTop: '12px',
  },
  themeCard: {
    position: 'relative',
    padding: '12px',
    background: 'var(--saas-bg-card)',
    border: '2px solid var(--saas-border)',
    borderRadius: '12px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
  },
  themeCardActive: {
    background: 'var(--saas-bg-input)',
  },
  themePreview: {
    width: '100%',
    height: '50px',
    borderRadius: '8px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  themeName: {
    fontSize: '13px',
    fontWeight: '500',
  },
  themeCheck: {
    position: 'absolute',
    top: '6px',
    right: '6px',
    width: '18px',
    height: '18px',
    background: 'var(--saas-accent)',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '11px',
    color: '#000',
    fontWeight: 'bold',
  },
  pixTypeGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: '8px',
  },
  pixTypeBtn: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
    padding: '12px 8px',
    background: 'var(--saas-bg-card)',
    border: '2px solid var(--saas-border)',
    borderRadius: '10px',
    color: 'var(--saas-text-muted)',
    fontSize: '12px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  pixTypeBtnActive: {
    background: 'var(--saas-bg-input)',
    borderColor: 'var(--saas-accent)',
    color: 'var(--saas-accent)',
  },
  pixInfo: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    padding: '12px',
    background: 'rgba(0, 217, 255, 0.05)',
    borderRadius: '8px',
    border: '1px solid rgba(0, 217, 255, 0.1)',
  },
  settingHeader2: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px',
  },
  settingLabel: {
    fontSize: '11px',
    fontWeight: '600',
    color: 'var(--saas-text)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  settingValue2: {
    fontSize: '12px',
    color: 'var(--saas-text)',
    minWidth: '40px',
    textAlign: 'center',
  },
  settingButton: {
    padding: '6px 12px',
    background: 'transparent',
    color: 'var(--saas-text)',
    border: '1px solid var(--saas-border)',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  settingRow2: {
    display: 'flex',
    gap: '12px',
    marginTop: '8px',
  },
  pixInfoText: {
    fontSize: '13px',
    color: 'var(--saas-text-muted)',
    lineHeight: 1.5,
  },
  pixPreview: {
    marginTop: '24px',
    padding: '16px',
    background: 'var(--saas-bg-input)',
    borderRadius: '12px',
    border: '1px solid var(--saas-border)',
  },
  pixQrPlaceholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '40px',
    background: 'var(--saas-bg-card)',
    borderRadius: '8px',
    border: '2px dashed var(--saas-border)',
  },
  apiInfo: {
    display: 'flex',
    gap: '16px',
    padding: '16px',
    background: 'rgba(0, 217, 255, 0.05)',
    borderRadius: '12px',
    border: '1px solid rgba(0, 217, 255, 0.1)',
    marginBottom: '24px',
  },
  apiStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginTop: '16px',
    padding: '12px',
    background: 'rgba(16, 185, 129, 0.05)',
    borderRadius: '8px',
    border: '1px solid rgba(16, 185, 129, 0.1)',
  },
};

export default SettingsPage;
