import React from 'react';

interface Props {
  children: React.ReactNode;
}
interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px',
            fontFamily: 'monospace',
            background: 'var(--bg)',
            color: 'var(--ink)',
          }}
        >
          <h2 style={{ color: '#f44747', margin: '0 0 12px', fontSize: '16px' }}>
            ⚡ Erro no componente
          </h2>
          <p
            style={{
              color: 'var(--muted)',
              fontSize: '12px',
              maxWidth: 500,
              textAlign: 'center',
              margin: '0 0 16px',
            }}
          >
            {this.state.error?.message || 'Erro desconhecido'}
          </p>
          <button
            onClick={this.handleReset}
            style={{
              background: 'var(--accent)',
              color: 'var(--selection-fg)',
              border: 'none',
              borderRadius: '4px',
              padding: '8px 20px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: 'inherit',
            }}
          >
            Tentar novamente
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
