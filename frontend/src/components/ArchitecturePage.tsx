import React from 'react';

const styles = {
  page: {
    padding: '32px 40px',
    maxWidth: 960,
    margin: '0 auto',
    color: 'var(--ink)',
    fontSize: 13,
    lineHeight: 1.6,
  } as React.CSSProperties,
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    background: 'var(--accent-soft)',
    color: 'var(--accent)',
    padding: '4px 12px',
    borderRadius: 20,
    fontSize: 11,
    fontWeight: 600,
    marginBottom: 14,
  } as React.CSSProperties,
  h1: {
    fontSize: 32,
    fontWeight: 700,
    color: 'var(--ink)',
    marginBottom: 12,
    letterSpacing: '-0.5px',
  } as React.CSSProperties,
  subtitle: {
    fontSize: 15,
    color: 'var(--muted)',
    lineHeight: 1.6,
    marginBottom: 28,
    maxWidth: 600,
  } as React.CSSProperties,
  infoBox: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 10,
    padding: '14px 18px',
    marginBottom: 32,
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    fontSize: 13,
    color: 'var(--muted)',
  } as React.CSSProperties,
  sectionTitle: {
    fontSize: 12,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '1px',
    color: 'var(--muted)',
    marginBottom: 16,
    marginTop: 32,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  } as React.CSSProperties,
  sectionLine: {
    flex: 1,
    height: 1,
    background: 'var(--line)',
  } as React.CSSProperties,
  row: {
    display: 'flex',
    gap: 12,
    justifyContent: 'center',
    flexWrap: 'wrap' as const,
  } as React.CSSProperties,
  arrow: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    padding: '6px 0',
  } as React.CSSProperties,
  arrowLabel: {
    fontSize: 10,
    color: 'var(--quiet)',
    letterSpacing: '0.5px',
    padding: '2px 0',
  } as React.CSSProperties,
  node: {
    padding: '10px 20px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    textAlign: 'center' as const,
    minWidth: 120,
    border: '1px solid',
    transition: 'all 0.15s',
    cursor: 'default',
  } as React.CSSProperties,
  nodeSmall: {
    padding: '7px 14px',
    fontSize: 11,
    minWidth: 100,
  } as React.CSSProperties,
  nodeCore: {
    padding: '14px 28px',
    fontSize: 15,
    minWidth: 260,
  } as React.CSSProperties,
  coreSub: {
    fontSize: 11,
    color: 'var(--muted)',
    fontWeight: 400,
    marginTop: 4,
  } as React.CSSProperties,
  pillar: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 6,
  } as React.CSSProperties,
  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 10,
    padding: 20,
    transition: 'all 0.15s',
  } as React.CSSProperties,
  cardGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: 12,
    marginBottom: 32,
  } as React.CSSProperties,
  cardTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--ink)',
    marginBottom: 6,
  } as React.CSSProperties,
  cardDesc: {
    fontSize: 12,
    color: 'var(--muted)',
    lineHeight: 1.5,
  } as React.CSSProperties,
  tag: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 600,
    marginTop: 10,
  } as React.CSSProperties,
  svgArrow: {
    width: 12,
    height: 12,
  } as React.CSSProperties,
};

const colors = {
  input: { bg: 'var(--bg-2)', border: 'var(--line)', text: 'var(--cyan)' },
  core: { bg: 'var(--accent-soft)', border: 'var(--accent)', text: 'var(--accent)' },
  memory: { bg: 'rgba(74,222,128,0.08)', border: 'rgba(74,222,128,0.3)', text: '#4ade80' },
  tool: { bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.3)', text: '#f87171' },
  provider: { bg: 'rgba(34,211,238,0.08)', border: 'rgba(34,211,238,0.3)', text: '#22d3ee' },
  output: { bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.3)', text: '#fbbf24' },
  process: { bg: 'rgba(74,222,128,0.06)', border: 'rgba(74,222,128,0.25)', text: '#a7f3d0' },
};

const tagColors: Record<string, { bg: string; color: string }> = {
  verde: { bg: 'rgba(74,222,128,0.12)', color: '#4ade80' },
  azul: { bg: 'rgba(96,165,250,0.12)', color: '#60a5fa' },
  roxo: { bg: 'rgba(192,132,252,0.12)', color: '#c084fc' },
  laranja: { bg: 'rgba(251,146,60,0.12)', color: '#fb923c' },
};

function Node({ label, sub, color, small, core }: {
  label: string;
  sub?: string;
  color: typeof colors.input;
  small?: boolean;
  core?: boolean;
}) {
  return (
    <div
      style={{
        ...styles.node,
        ...(small ? styles.nodeSmall : {}),
        ...(core ? styles.nodeCore : {}),
        background: color.bg,
        borderColor: color.border,
        color: color.text,
      }}
      title={sub}
    >
      {label}
      {sub && <div style={styles.coreSub}>{sub}</div>}
    </div>
  );
}

function Arrow({ label }: { label?: string }) {
  return (
    <div style={styles.arrow}>
      <div style={{ width: 2, height: 18, background: 'var(--line)' }} />
      {label && <div style={styles.arrowLabel}>{label}</div>}
      <svg style={styles.svgArrow} viewBox="0 0 12 12" fill="var(--quiet)">
        <polygon points="6,12 0,0 12,0" />
      </svg>
    </div>
  );
}

function BranchArrows() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0' }}>
      <svg width="360" height="36" viewBox="0 0 360 36">
        <line x1="180" y1="0" x2="180" y2="10" stroke="var(--line)" strokeWidth="2" />
        <line x1="180" y1="10" x2="50" y2="26" stroke="var(--line)" strokeWidth="1.5" />
        <line x1="180" y1="10" x2="180" y2="26" stroke="var(--line)" strokeWidth="1.5" />
        <line x1="180" y1="10" x2="310" y2="26" stroke="var(--line)" strokeWidth="1.5" />
        <polygon points="50,26 44,18 56,18" fill="var(--quiet)" />
        <polygon points="180,26 174,18 186,18" fill="var(--quiet)" />
        <polygon points="310,26 304,18 316,18" fill="var(--quiet)" />
      </svg>
    </div>
  );
}

function MergeArrows() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0' }}>
      <svg width="360" height="36" viewBox="0 0 360 36">
        <line x1="50" y1="6" x2="180" y2="26" stroke="var(--line)" strokeWidth="1.5" />
        <line x1="180" y1="6" x2="180" y2="26" stroke="var(--line)" strokeWidth="1.5" />
        <line x1="310" y1="6" x2="180" y2="26" stroke="var(--line)" strokeWidth="1.5" />
        <line x1="180" y1="26" x2="180" y2="36" stroke="var(--line)" strokeWidth="2" />
        <polygon points="180,36 174,28 186,28" fill="var(--quiet)" />
      </svg>
    </div>
  );
}

const features = [
  {
    icon: '\u{1F9E0}',
    title: 'Memoria Espiral',
    desc: 'Sistema de memoria em multiplas camadas: elastica (sessao), vetorial (FAISS), cerebro (aprendizado). Persiste conhecimento entre sessoes com consolidacao automatica.',
    tag: 'Persistente',
    tagColor: 'verde',
  },
  {
    icon: '\u{1F504}',
    title: 'Maquina de Estados',
    desc: 'Agentes seguem ciclo determinista: planejar \u2192 executar \u2192 verificar \u2192 aprender. Circuit breakers anti-loop previnem recursao infinita.',
    tag: 'Automatizado',
    tagColor: 'roxo',
  },
  {
    icon: '\u{1F50C}',
    title: 'Multi-Provedor LLM',
    desc: 'Alterne entre Ollama, Groq, OpenCode, MiMo, Gemini e OpenAI. Roteamento por agente com cadeia de fallback.',
    tag: '7 Provedores',
    tagColor: 'azul',
  },
  {
    icon: '\u{1F6E0}\uFE0F',
    title: 'Chamada de Ferramentas',
    desc: 'Explorador de arquivos, terminal, busca de codigo, executor Python, busca web. Agentes usam ferramentas autonomamente.',
    tag: '12+ Ferramentas',
    tagColor: 'laranja',
  },
  {
    icon: '\u{1F3A4}',
    title: 'Controle por Voz',
    desc: 'Web Speech API para entrada de voz em PT-BR. Edge TTS para saida de voz. Auto-envio, auto-reinicio, design de acessibilidade.',
    tag: 'Acessibilidade',
    tagColor: 'verde',
  },
  {
    icon: '\u{1F4CB}',
    title: 'Gerenciamento de Tarefas',
    desc: 'Checklists dinamicos com progresso em tempo real. Tarefas rastreadas via SSE com eventos task_plan e task_progress.',
    tag: 'Tempo Real',
    tagColor: 'roxo',
  },
];

export default function ArchitecturePage() {
  return (
    <div style={styles.page}>
      <div style={styles.badge}>Plataforma de IA Local</div>
      <h1 style={styles.h1}>Arquitetura</h1>
      <p style={styles.subtitle}>
        DEEP-OS e um Sistema Operacional de Agentes de IA rodando em <code>localhost</code>.
        Agentes orquestram ferramentas, memoria e LLMs multi-provedor para automatizar tarefas de engenharia de software.
      </p>

      <div style={styles.infoBox}>
        <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>\u2139</span>
        <span>
          Precisa de uma tarefa rapida? Use o <strong>Modo Chat</strong> para solicites conversacionais.
          Para trabalho complexo em multiplos passos, o <strong>Loop do Agente</strong> gerencia
          planejamento, execucao e aprendizado automaticamente. A memoria persiste entre sessoes.
        </span>
      </div>

      {/* Fluxo do Sistema */}
      <div style={styles.sectionTitle}>
        Fluxo do Sistema
        <div style={styles.sectionLine} />
      </div>

      {/* Diagrama */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0, marginBottom: 32 }}>
        {/* Entrada */}
        <div style={styles.row}>
          <Node label="Voz (STT)" color={colors.input} />
          <Node label="Entrada de Texto" color={colors.input} />
          <Node label="Terminal CLI" color={colors.input} />
          <Node label="Requisicao API" color={colors.input} />
        </div>

        <Arrow label="intencao do usuario" />

        {/* Nucleo */}
        <div style={styles.row}>
          <Node
            label="Orquestrador de Agentes"
            sub="Lifecycle \u00B7 Planejamento \u00B7 Roteamento"
            color={colors.core}
            core
          />
        </div>

        <BranchArrows />

        {/* Tres Pilares */}
        <div style={{ ...styles.row, gap: 20 }}>
          <div style={styles.pillar}>
            <Node label="Memoria Espiral" color={colors.memory} small />
            <Node label="Memoria Elastica" color={colors.memory} small />
            <Node label="Vetorial (FAISS)" color={colors.memory} small />
            <Node label="Cerebro / Aprendizado" color={colors.memory} small />
          </div>
          <div style={styles.pillar}>
            <Node label="Explorador de Arquivos" color={colors.tool} small />
            <Node label="Terminal (Shell)" color={colors.tool} small />
            <Node label="Busca de Codigo" color={colors.tool} small />
            <Node label="Executor Python" color={colors.tool} small />
          </div>
          <div style={styles.pillar}>
            <Node label="Ollama (Local)" color={colors.provider} small />
            <Node label="OpenCode (DeepSeek)" color={colors.provider} small />
            <Node label="Groq (Llama 3.3)" color={colors.provider} small />
            <Node label="MiMo \u00B7 Gemini \u00B7 OpenAI" color={colors.provider} small />
          </div>
        </div>

        <MergeArrows />

        {/* Processamento */}
        <div style={styles.row}>
          <Node
            label="Geracao de Resposta"
            sub="Streaming \u00B7 Tool Calls \u00B7 Task Plan"
            color={colors.process}
            core
          />
        </div>

        <Arrow label="resposta" />

        {/* Saida */}
        <div style={styles.row}>
          <Node label="Chat UI" color={colors.output} />
          <Node label="Voz (TTS)" color={colors.output} />
          <Node label="Checklist" color={colors.output} />
          <Node label="Diff de Codigo" color={colors.output} />
          <Node label="Alteracoes" color={colors.output} />
        </div>
      </div>

      {/* Capacidades */}
      <div style={styles.sectionTitle}>
        Capacidades Principais
        <div style={styles.sectionLine} />
      </div>

      <div style={styles.cardGrid}>
        {features.map((f) => (
          <div
            key={f.title}
            style={styles.card}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--accent-line)';
              (e.currentTarget as HTMLDivElement).style.background = 'var(--bg)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--line)';
              (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-2)';
            }}
          >
            <div style={styles.cardTitle}>{f.icon} {f.title}</div>
            <div style={styles.cardDesc}>{f.desc}</div>
            <span
              style={{
                ...styles.tag,
                background: tagColors[f.tagColor].bg,
                color: tagColors[f.tagColor].color,
              }}
            >
              {f.tag}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
