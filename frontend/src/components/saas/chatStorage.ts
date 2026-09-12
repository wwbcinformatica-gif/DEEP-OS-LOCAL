/**
 * Tenant-scoped storage + conversation management for Charon/Jarvis
 * Each tenant gets isolated localStorage keys and separate conversations.
 */

export interface Conversation {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
}

export interface TranscriptEntry {
  speaker: string;
  text: string;
  time: string;
}

// ─── Tenant-scoped localStorage ──────────────────────────────────

function getTenantId(): string {
  try {
    const user = JSON.parse(localStorage.getItem('saas_user') || '{}');
    return user.id || 'default';
  } catch {
    return 'default';
  }
}

export function tenantGet(key: string): string | null {
  return localStorage.getItem(`${getTenantId()}_${key}`);
}

export function tenantSet(key: string, value: string): void {
  localStorage.setItem(`${getTenantId()}_${key}`, value);
}

export function tenantRemove(key: string): void {
  localStorage.removeItem(`${getTenantId()}_${key}`);
}

// ─── Conversations ───────────────────────────────────────────────

const CONVERSATIONS_KEY = 'chat_conversations';

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

function autoName(firstMessage: string): string {
  const clean = firstMessage.replace(/[^a-zA-Z0-9À-ú\s]/g, '').trim();
  const words = clean.split(/\s+/).slice(0, 5).join(' ');
  return words || 'Nova conversa';
}

export function getConversations(): Conversation[] {
  try {
    const raw = tenantGet(CONVERSATIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveConversations(convs: Conversation[]): void {
  tenantSet(CONVERSATIONS_KEY, JSON.stringify(convs));
}

export function createConversation(firstMessage?: string): Conversation {
  const conv: Conversation = {
    id: generateId(),
    name: firstMessage ? autoName(firstMessage) : 'Nova conversa',
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  const all = getConversations();
  all.unshift(conv);
  saveConversations(all);
  return conv;
}

export function renameConversation(id: string, name: string): void {
  const all = getConversations();
  const conv = all.find(c => c.id === id);
  if (conv) {
    conv.name = name;
    conv.updatedAt = Date.now();
    saveConversations(all);
  }
}

export function deleteConversation(id: string): void {
  const all = getConversations().filter(c => c.id !== id);
  saveConversations(all);
  tenantRemove(`transcripts_${id}`);
  tenantRemove(`activity_${id}`);
}

// ─── Transcripts per conversation ────────────────────────────────

export function getTranscripts(convId: string): TranscriptEntry[] {
  try {
    const raw = tenantGet(`transcripts_${convId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveTranscripts(convId: string, entries: TranscriptEntry[]): void {
  tenantSet(`transcripts_${convId}`, JSON.stringify(entries.slice(-300)));
}

export function getActivityLog(convId: string): TranscriptEntry[] {
  try {
    const raw = tenantGet(`activity_${convId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveActivityLog(convId: string, entries: TranscriptEntry[]): void {
  tenantSet(`activity_${convId}`, JSON.stringify(entries.slice(-150)));
}

// ─── Mensagens do chat por conversa ──────────────────────────────
//
// BUG RELATADO: "ao clicar no historico nao volta para o historico, nao aparece
// nenhuma informacao do historico salvo".
//
// CAUSA: estas duas funcoes NAO EXISTIAM. O projeto salvava apenas os
// `transcripts` (o log de VOZ do Charon). As mensagens do chat do Jarvis nunca
// eram gravadas em lugar nenhum — a conversa era criada e batizada com o texto
// da primeira mensagem, mas o CONTEUDO dela se perdia ao recarregar a pagina.
// Nao havia historico para mostrar porque ele nunca foi salvo.
export interface ChatMessageStored {
  id: string;
  role: 'user' | 'jarvis';
  content: string;
  /** ISO string: o tipo Date nao sobrevive ao JSON. */
  timestamp: string;
}

export function getMessages(convId: string): ChatMessageStored[] {
  try {
    const raw = tenantGet(`messages_${convId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveMessages(convId: string, mensagens: ChatMessageStored[]): void {
  try {
    // Limite de 200 mensagens: o localStorage tem poucos MB e uma conversa
    // longa com respostas grandes estoura a cota (o tenantSet captura o erro,
    // mas ai a gravacao para de funcionar em silencio).
    tenantSet(`messages_${convId}`, JSON.stringify(mensagens.slice(-200)));
  } catch {
    /* cota cheia: nao derruba o chat por causa do historico */
  }
}

/**
 * Texto da conversa em Markdown, para exportar/estudar.
 *
 * Existe a pedido do usuario: "colocar um download no historico para salvar o
 * estudo ou pesquisa". O formato escolhido e Markdown porque abre legivel em
 * qualquer editor, cola bem em anotacoes e nao depende de programa nenhum.
 */
export function conversationToMarkdown(
  convId: string,
  nome: string,
): string {
  const msgs = getMessages(convId);
  if (msgs.length === 0) return '';

  const quando = new Date().toLocaleString('pt-BR');
  const linhas: string[] = [
    `# ${nome || 'Conversa'}`,
    '',
    `_Exportado do DEEP-OS em ${quando} — ${msgs.length} mensagens_`,
    '',
    '---',
    '',
  ];

  for (const m of msgs) {
    const hora = new Date(m.timestamp).toLocaleString('pt-BR');
    const quem = m.role === 'user' ? 'Voce' : 'Jarvis';
    linhas.push(`## ${quem} — ${hora}`, '', m.content, '');
  }

  // Os transcripts de voz (Charon) entram como anexo quando existirem
  const transcricoes = getTranscripts(convId);
  if (transcricoes.length > 0) {
    linhas.push('---', '', '## Transcricao de voz', '');
    for (const t of transcricoes) {
      linhas.push(`- **${t.speaker === 'user' ? 'Voce' : 'Charon'}** (${t.time}): ${t.text}`);
    }
    linhas.push('');
  }

  return linhas.join('\n');
}

/** Dispara o download de um texto como arquivo .md */
export function baixarTexto(nomeArquivo: string, conteudo: string): void {
  const blob = new Blob([conteudo], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  // Nome seguro para arquivo: sem acento, sem caractere proibido no Windows
  const limpo = (nomeArquivo || 'conversa')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9._-]+/g, '_')
    .slice(0, 60) || 'conversa';
  const data = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `${limpo}_${data}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Legacy migration ────────────────────────────────────────────

export function migrateLegacyData(): string | null {
  // Move old non-scoped data to a conversation if exists
  try {
    const oldTranscripts = localStorage.getItem('charon_transcripts');
    const oldActivity = localStorage.getItem('charon_activity');
    if (oldTranscripts) {
      const entries: TranscriptEntry[] = JSON.parse(oldTranscripts);
      if (entries.length > 0) {
        const conv = createConversation(entries[0]?.text);
        saveTranscripts(conv.id, entries);
        if (oldActivity) {
          saveActivityLog(conv.id, JSON.parse(oldActivity));
        }
        // Clean old keys
        localStorage.removeItem('charon_transcripts');
        localStorage.removeItem('charon_activity');
        return conv.id;
      }
    }
  } catch {}
  return null;
}
