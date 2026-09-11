import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface SpaceSettings {
  enabled: boolean;
  speed: number;
  starCount: number;
  fontSize: '8px' | '10px' | '12px' | '14px';
}

interface ThemeSettings {
  theme: 'glass' | 'dark' | 'light' | 'cyberpunk' | 'midnight';
}

interface AppSettingsContextType {
  space: SpaceSettings;
  theme: ThemeSettings;
  updateSpace: (newSettings: Partial<SpaceSettings>) => void;
  updateTheme: (newSettings: Partial<ThemeSettings>) => void;
}

const AppSettingsContext = createContext<AppSettingsContextType | undefined>(undefined);

export const useAppSettings = () => {
  const context = useContext(AppSettingsContext);
  if (!context) {
    throw new Error('useAppSettings must be used within AppSettingsProvider');
  }
  return context;
};

export const useSpaceSettings = () => {
  const { space, updateSpace } = useAppSettings();
  return { settings: space, updateSettings: updateSpace };
};

export const AppSettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [space, setSpace] = useState<SpaceSettings>(() => {
    const saved = localStorage.getItem('spaceSettings');
    return saved ? JSON.parse(saved) : { enabled: true, speed: 12, starCount: 800, fontSize: '12px' };
  });

  const [theme, setTheme] = useState<ThemeSettings>(() => {
    const saved = localStorage.getItem('themeSettings');
    return saved ? JSON.parse(saved) : { theme: 'glass' };
  });

  const updateSpace = (newSettings: Partial<SpaceSettings>) => {
    setSpace(prev => {
      const updated = { ...prev, ...newSettings };
      localStorage.setItem('spaceSettings', JSON.stringify(updated));
      return updated;
    });
  };

  const updateTheme = (newSettings: Partial<ThemeSettings>) => {
    setTheme(prev => {
      const updated = { ...prev, ...newSettings };
      localStorage.setItem('themeSettings', JSON.stringify(updated));
      
      // Auto-disable space effect when light theme is selected
      if (newSettings.theme === 'light') {
        setSpace(s => {
          const newSpace = { ...s, enabled: false };
          localStorage.setItem('spaceSettings', JSON.stringify(newSpace));
          return newSpace;
        });
      }
      
      return updated;
    });
  };

  useEffect(() => {
    const root = document.documentElement;
    root.style.fontSize = space.fontSize;
    document.body.style.fontSize = space.fontSize;
    document.body.style.lineHeight = '1.5';
    let style = document.getElementById('dynamic-font-size') as HTMLStyleElement;
    if (!style) {
      style = document.createElement('style');
      style.id = 'dynamic-font-size';
      document.head.appendChild(style);
    }
    const fs = space.fontSize;
    style.textContent = `
      html, body, #root {
        font-size: ${fs} !important;
      }
      .saas-sidebar, .saas-sidebar * {
        font-size: ${fs} !important;
      }
      [style*="font-size"] {
        font-size: ${fs} !important;
      }
    `;
  }, [space.fontSize]);

  useEffect(() => {
    const root = document.documentElement;
    root.removeAttribute('data-theme');

    switch (theme.theme) {
      case 'glass':
        document.body.style.background = '#0a0a1a';
        root.style.setProperty('--saas-bg', 'transparent');
        root.style.setProperty('--saas-bg-card', 'rgba(255, 255, 255, 0.08)');
        root.style.setProperty('--saas-bg-sidebar', 'rgba(10, 10, 18, 0.6)');
        root.style.setProperty('--saas-bg-input', 'rgba(255, 255, 255, 0.05)');
        root.style.setProperty('--saas-text', '#ffffff');
        root.style.setProperty('--saas-text-muted', 'rgba(255, 255, 255, 0.7)');
        root.style.setProperty('--saas-border', 'rgba(255, 255, 255, 0.15)');
        root.style.setProperty('--saas-accent', '#00d9ff');
        root.style.setProperty('--saas-accent-rgb', '0, 217, 255');
        root.style.setProperty('--saas-glass-blur', '20px');
        root.style.setProperty('--saas-shadow', '0 8px 32px rgba(0, 0, 0, 0.3)');
        break;
        
      case 'dark':
        document.body.style.background = '#0a0a1a';
        root.style.setProperty('--saas-bg', '#0a0a1a');
        root.style.setProperty('--saas-bg-card', 'rgba(20, 20, 35, 0.95)');
        root.style.setProperty('--saas-bg-sidebar', 'rgba(10, 10, 18, 0.98)');
        root.style.setProperty('--saas-bg-input', 'rgba(255, 255, 255, 0.05)');
        root.style.setProperty('--saas-text', '#ffffff');
        root.style.setProperty('--saas-text-muted', '#a0a0a0');
        root.style.setProperty('--saas-border', 'rgba(255, 255, 255, 0.1)');
        root.style.setProperty('--saas-accent', '#00d9ff');
        root.style.setProperty('--saas-accent-rgb', '0, 217, 255');
        root.style.setProperty('--saas-glass-blur', '0px');
        root.style.setProperty('--saas-shadow', '0 4px 20px rgba(0, 0, 0, 0.5)');
        break;
        
      case 'light':
        document.body.style.background = '#f0f2f5';
        root.style.setProperty('--saas-bg', '#f0f2f5');
        root.style.setProperty('--saas-bg-card', '#ffffff');
        root.style.setProperty('--saas-bg-sidebar', '#ffffff');
        root.style.setProperty('--saas-bg-input', '#f5f5f5');
        root.style.setProperty('--saas-text', '#1a1a2e');
        root.style.setProperty('--saas-text-muted', '#666666');
        root.style.setProperty('--saas-border', '#e0e0e0');
        root.style.setProperty('--saas-accent', '#007acc');
        root.style.setProperty('--saas-accent-rgb', '0, 122, 204');
        root.style.setProperty('--saas-glass-blur', '0px');
        root.style.setProperty('--saas-shadow', '0 4px 20px rgba(0, 0, 0, 0.08)');
        break;
        
      case 'cyberpunk':
        document.body.style.background = '#0a0015';
        root.style.setProperty('--saas-bg', 'transparent');
        root.style.setProperty('--saas-bg-card', 'rgba(255, 0, 100, 0.08)');
        root.style.setProperty('--saas-bg-sidebar', 'rgba(10, 0, 20, 0.7)');
        root.style.setProperty('--saas-bg-input', 'rgba(255, 0, 100, 0.05)');
        root.style.setProperty('--saas-text', '#ff0066');
        root.style.setProperty('--saas-text-muted', 'rgba(255, 0, 100, 0.7)');
        root.style.setProperty('--saas-border', 'rgba(255, 0, 100, 0.3)');
        root.style.setProperty('--saas-accent', '#ff0066');
        root.style.setProperty('--saas-accent-rgb', '255, 0, 102');
        root.style.setProperty('--saas-glass-blur', '20px');
        root.style.setProperty('--saas-shadow', '0 8px 32px rgba(255, 0, 100, 0.2)');
        break;
        
      case 'midnight':
        document.body.style.background = '#0d1117';
        root.style.setProperty('--saas-bg', 'transparent');
        root.style.setProperty('--saas-bg-card', 'rgba(13, 17, 23, 0.8)');
        root.style.setProperty('--saas-bg-sidebar', 'rgba(13, 17, 23, 0.7)');
        root.style.setProperty('--saas-bg-input', 'rgba(255, 255, 255, 0.05)');
        root.style.setProperty('--saas-text', '#c9d1d9');
        root.style.setProperty('--saas-text-muted', '#8b949e');
        root.style.setProperty('--saas-border', 'rgba(48, 54, 61, 0.8)');
        root.style.setProperty('--saas-accent', '#58a6ff');
        root.style.setProperty('--saas-accent-rgb', '88, 166, 255');
        root.style.setProperty('--saas-glass-blur', '15px');
        root.style.setProperty('--saas-shadow', '0 8px 32px rgba(0, 0, 0, 0.4)');
        break;
    }
  }, [theme]);

  return (
    <AppSettingsContext.Provider value={{ space, theme, updateSpace, updateTheme }}>
      {children}
    </AppSettingsContext.Provider>
  );
};
