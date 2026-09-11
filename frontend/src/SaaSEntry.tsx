/**
 * Entry point para o modo SaaS do DEEP-OS
 * Este arquivo é usado quando o sistema opera como plataforma de aluguel
 */
import React from 'react';
import { createRoot } from 'react-dom/client';
import { SaaSApp } from './components/saas';
import './styles.css';

// Aplica o tema escuro por padrão
document.documentElement.setAttribute('data-theme', 'dark');

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(
    <React.StrictMode>
      <SaaSApp />
    </React.StrictMode>
  );
}
