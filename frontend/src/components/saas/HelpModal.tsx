import React, { useState } from 'react';

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const HelpModal: React.FC<HelpModalProps> = ({ isOpen, onClose }) => {
  const [activeSection, setActiveSection] = useState('charon');

  if (!isOpen) return null;

  const sections = [
    { id: 'charon', title: 'Charon (Voz)', icon: '⚡' },
    { id: 'jarvis', title: 'Jarvis (Chat)', icon: '🤖' },
    { id: 'documents', title: 'Documentos', icon: '📄' },
    { id: 'instances', title: 'Instancias', icon: '⚡' },
    { id: 'faq', title: 'Perguntas Frequentes', icon: '❓' },
  ];

  const renderContent = () => {
    switch (activeSection) {
      case 'charon':
        return (
          <div>
            <h3 style={styles.helpTitle}>Charon - Assistente de Voz</h3>
            <p style={styles.helpText}>
              O Charon e um assistente de IA por voz que pode executar tarefas, pesquisar na web, criar documentos e muito mais.
            </p>

            <div style={styles.helpSection}>
              <h4>Como usar:</h4>
              <ol style={styles.helpList}>
                <li>Clique em <strong>"Charon"</strong> no menu lateral</li>
                <li>Clique em <strong>"Conectar Charon"</strong> para ativar o microfone</li>
                <li>Fale normalmente - o Charon escuta e responde por voz</li>
                <li>Você também pode digitar mensagens no campo de texto</li>
              </ol>
            </div>

            <div style={styles.helpSection}>
              <h4>O que o Charon pode fazer:</h4>
              <ul style={styles.helpList}>
                <li><strong>Pesquisar na web</strong> - informações atualizadas</li>
                <li><strong>Criar documentos</strong> - txt, markdown, html, json</li>
                <li><strong>Gerar código</strong> - scripts e programas</li>
                <li><strong>Calcular</strong> - matemática e conversões</li>
                <li><strong>Lembretes</strong> - agendar tarefas</li>
                <li><strong>Resumir textos</strong> - artigos e páginas</li>
              </ul>
            </div>

            <div style={styles.helpSection}>
              <h4>Configurações importantes:</h4>
              <ul style={styles.helpList}>
                <li><strong>Sua chave de API Gemini</strong> - necessária para o Charon funcionar</li>
                <li><strong>Nome do assistente</strong> - personalize como ele é chamado</li>
                <li><strong>Seu nome</strong> - para o Charon te chamar pelo nome</li>
                <li><strong>Voz</strong> - escolha entre vozes masculinas e femininas</li>
              </ul>
            </div>

            <div style={styles.proTip}>
              <strong>Dica:</strong> O Charon salva automaticamente o histórico de conversas. Você pode criar várias conversas clicando em "+" no topo do painel direito.
            </div>
          </div>
        );

      case 'jarvis':
        return (
          <div>
            <h3 style={styles.helpTitle}>Jarvis - Assistente de Chat</h3>
            <p style={styles.helpText}>
              O Jarvis e um assistente de IA por texto com suporte a múltiplos provedores e modelos.
            </p>

            <div style={styles.helpSection}>
              <h4>Como usar:</h4>
              <ol style={styles.helpList}>
                <li>Clique em <strong>"Jarvis"</strong> no menu lateral</li>
                <li>Selecione o <strong>provedor</strong> (Gemini, OpenRouter, OpenAI, etc.)</li>
                <li>Selecione o <strong>modelo</strong> desejado</li>
                <li>Digite sua mensagem e pressione Enter</li>
              </ol>
            </div>

            <div style={styles.helpSection}>
              <h4>Provedores disponíveis:</h4>
              <ul style={styles.helpList}>
                <li><strong>Gemini</strong> - Google (gratuito com limite)</li>
                <li><strong>OpenRouter</strong> - Acesso a vários modelos</li>
                <li><strong>OpenAI</strong> - GPT-4, GPT-3.5</li>
                <li><strong>Groq</strong> - Modelos open source rápidos</li>
                <li><strong>NVIDIA</strong> - Modelos de IA</li>
              </ul>
            </div>

            <div style={styles.helpSection}>
              <h4>Funcionalidades:</h4>
              <ul style={styles.helpList}>
                <li><strong>Reconhecimento de voz</strong> - clique no ícone de microfone</li>
                <li><strong>Leitura por voz</strong> - as respostas são lidas em voz alta</li>
                <li><strong>Histórico</strong> - conversas são salvas automaticamente</li>
                <li><strong>Múltiplas conversas</strong> - clique em "+" para criar nova</li>
              </ul>
            </div>

            <div style={styles.proTip}>
              <strong>Dica:</strong> Configure sua chave de API nas configurações (ícone ⚙️) para usar o Jarvis.
            </div>
          </div>
        );

      case 'documents':
        return (
          <div>
            <h3 style={styles.helpTitle}>Criando Documentos</h3>
            <p style={styles.helpText}>
              Tanto o Charon quanto o Jarvis podem criar documentos para você. Os arquivos são salvos no servidor e ficam disponíveis para download.
            </p>

            <div style={styles.helpSection}>
              <h4>Como pedir um documento:</h4>
              <div style={styles.helpExample}>
                <p style={{ margin: '4px 0' }}>"Crie um documento markdown com um plano de marketing"</p>
                <p style={{ margin: '4px 0' }}>"Salve isso em um arquivo txt"</p>
                <p style={{ margin: '4px 0' }}>"Gere um relatório em markdown"</p>
                <p style={{ margin: '4px 0' }}>"Crie um arquivo json com esses dados"</p>
              </div>
            </div>

            <div style={styles.helpSection}>
              <h4>Formatos suportados:</h4>
              <ul style={styles.helpList}>
                <li><strong>.md</strong> - Markdown (recomendado para textos formatados)</li>
                <li><strong>.txt</strong> - Texto simples</li>
                <li><strong>.html</strong> - Página web</li>
                <li><strong>.json</strong> - Dados estruturados</li>
              </ul>
            </div>

            <div style={styles.helpSection}>
              <h4>Após criar o documento:</h4>
              <ol style={styles.helpList}>
                <li>O Charon/Jarvis salva o arquivo no servidor</li>
                <li>Um <strong>link de download</strong> é gerado automaticamente</li>
                <li>Clique no link para baixar o arquivo</li>
                <li>O arquivo também aparece na seção <strong>"Downloads"</strong> do menu</li>
              </ol>
            </div>

            <div style={styles.helpSection}>
              <h4>Acesse seus documentos:</h4>
              <ul style={styles.helpList}>
                <li>Vá em <strong>"Downloads"</strong> no menu lateral</li>
                <li>Veja todos os documentos criados</li>
                <li>Baixe qualquer arquivo clicando nele</li>
              </ul>
            </div>

            <div style={styles.helpWarning}>
              <strong>Importante:</strong> No servidor (VPS), os documentos são salvos em <code>/root/DEEP-OS/downloads</code>. O download funciona diretamente pelo navegador.
            </div>
          </div>
        );

      case 'instances':
        return (
          <div>
            <h3 style={styles.helpTitle}>Gerenciando Instancias</h3>
            <p style={styles.helpText}>
              Instancias sao ambientes isolados onde seus agentes de IA rodam. Cada instancia pode ter um modelo diferente.
            </p>

            <div style={styles.helpSection}>
              <h4>Criar nova instancia:</h4>
              <ol style={styles.helpList}>
                <li>Clique em "Instancia" no menu lateral</li>
                <li>Clique em "Nova Instancia"</li>
                <li>Escolha um nome para a instancia</li>
                <li>Selecione o provedor e modelo de IA</li>
                <li>Clique em "Criar"</li>
              </ol>
            </div>

            <div style={styles.helpSection}>
              <h4>Limites por plano:</h4>
              <ul style={styles.helpList}>
                <li><strong>Colaborador (gratuito):</strong> 1 instancia</li>
                <li><strong>Mensal:</strong> 3 instancias</li>
                <li><strong>Trimestral:</strong> 5 instancias</li>
                <li><strong>Anual:</strong> 10 instancias</li>
              </ul>
            </div>

            <div style={styles.helpSection}>
              <h4>Gerenciar instancias:</h4>
              <ul style={styles.helpList}>
                <li><strong>Iniciar/Pausar</strong> - controle quando o agente está ativo</li>
                <li><strong>Configurar</strong> - altere nome, modelo e comportamento</li>
                <li><strong>Excluir</strong> - remova instancias que não usa mais</li>
              </ul>
            </div>
          </div>
        );

      case 'faq':
        return (
          <div>
            <h3 style={styles.helpTitle}>Perguntas Frequentes</h3>

            <div style={styles.faqItem}>
              <strong>Preciso de chave de API para usar?</strong>
              <p>Sim. Você precisa de uma chave de API do Google Gemini (gratuita) para usar o Charon e Jarvis. Configure em Configurações.</p>
            </div>

            <div style={styles.faqItem}>
              <strong>Os documentos ficam salvos?</strong>
              <p>Sim. Todos os documentos criados ficam salvos no servidor e disponíveis na seção "Downloads".</p>
            </div>

            <div style={styles.faqItem}>
              <strong>Posso usar em multiplos dispositivos?</strong>
              <p>Sim! Acesse de qualquer navegador. Seus dados são salvos por usuário.</p>
            </div>

            <div style={styles.faqItem}>
              <strong>O Charon funciona sem microfone?</strong>
              <p>Sim! Você pode digitar mensagens no campo de texto. O microfone é opcional.</p>
            </div>

            <div style={styles.faqItem}>
              <strong>Como altero meu plano?</strong>
              <p>Acesse "Planos" no menu e escolha o novo plano.</p>
            </div>

            <div style={styles.faqItem}>
              <strong>Posso cancelar a qualquer momento?</strong>
              <p>Sim, sem multa. Mantém acesso até o fim do período.</p>
            </div>

            <div style={styles.faqItem}>
              <strong>Meus dados estão seguros?</strong>
              <p>Sim! Cada usuário tem seus dados isolados. Use criptografia e isolamento completo.</p>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <h2 style={styles.modalTitle}>Central de Ajuda</h2>
          <button style={styles.closeButton} onClick={onClose}>X</button>
        </div>
        
        <div style={styles.modalBody}>
          <div style={styles.helpSidebar}>
            {sections.map((section) => (
              <button
                key={section.id}
                style={{
                  ...styles.helpNavItem,
                  ...(activeSection === section.id ? styles.helpNavItemActive : {}),
                }}
                onClick={() => setActiveSection(section.id)}
              >
                <span>{section.icon}</span>
                <span>{section.title}</span>
              </button>
            ))}
          </div>
          
          <div style={styles.helpContent}>
            {renderContent()}
          </div>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '20px',
  },
  modal: {
    background: '#1a1a2e',
    borderRadius: '16px',
    width: '100%',
    maxWidth: '800px',
    maxHeight: '80vh',
    overflow: 'hidden',
    border: '1px solid rgba(255, 255, 255, 0.1)',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 24px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
  },
  modalTitle: {
    margin: 0,
    fontSize: '20px',
    fontWeight: 'bold',
    color: '#ffffff',
  },
  closeButton: {
    background: 'rgba(255, 255, 255, 0.1)',
    border: 'none',
    borderRadius: '8px',
    color: '#ffffff',
    width: '32px',
    height: '32px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  modalBody: {
    display: 'flex',
    minHeight: '400px',
  },
  helpSidebar: {
    width: '200px',
    borderRight: '1px solid rgba(255, 255, 255, 0.1)',
    padding: '16px 0',
  },
  helpNavItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    width: '100%',
    padding: '12px 16px',
    border: 'none',
    background: 'transparent',
    color: '#a0a0a0',
    cursor: 'pointer',
    textAlign: 'left',
    fontSize: '14px',
  },
  helpNavItemActive: {
    background: 'rgba(0, 217, 255, 0.1)',
    color: '#00d9ff',
    borderLeft: '3px solid #00d9ff',
  },
  helpContent: {
    flex: 1,
    padding: '24px',
    overflowY: 'auto',
    color: '#ffffff',
  },
  helpTitle: {
    fontSize: '18px',
    fontWeight: 'bold',
    marginTop: 0,
    marginBottom: '16px',
    color: '#00d9ff',
  },
  helpText: {
    color: '#a0a0a0',
    lineHeight: 1.6,
    marginBottom: '20px',
  },
  helpSection: {
    marginBottom: '24px',
  },
  helpList: {
    paddingLeft: '20px',
    color: '#a0a0a0',
    lineHeight: 1.8,
  },
  helpExample: {
    background: 'rgba(0, 217, 255, 0.05)',
    border: '1px solid rgba(0, 217, 255, 0.2)',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#a0a0a0',
    fontStyle: 'italic',
  },
  helpWarning: {
    background: 'rgba(245, 158, 11, 0.1)',
    border: '1px solid rgba(245, 158, 11, 0.3)',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#f59e0b',
    fontSize: '14px',
  },
  proTip: {
    background: 'rgba(139, 92, 246, 0.1)',
    border: '1px solid rgba(139, 92, 246, 0.3)',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#a78bfa',
    fontSize: '14px',
  },
  faqItem: {
    marginBottom: '16px',
    paddingBottom: '16px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  },
};

export default HelpModal;
