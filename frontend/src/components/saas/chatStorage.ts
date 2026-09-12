/**
 * Tenant-scoped storage + conversation management for Charon/Jarvis
 * Each tenant gets isolated localStorage keys and separate conversations.
 */

export interface Conversation {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  /**
   * Workspace (raiz) a que a conversa pertence.
   *
   * Agrupa as conversas como o seletor de workspace do DSH: em vez de uma lista
   * solida de dezenas de conversas, elas ficam organizadas sob a raiz em que
   * foram feitas. Opcional para nao quebrar as conversas ja gravadas — quem nao
   * tem o campo entra no workspace padrao.
   */
  workspace?: string;
}

/** Workspace usado quando a conversa nao tem um definido. */
export const WORKSPACE_PADRAO = 'Geral';

/** Raizes disponiveis: as ja usadas + a padrao (sempre presente). */
export function getWorkspaces(): string[] {
  const usados = new Set<string>([WORKSPACE_PADRAO]);
  for (const c of getConversations()) {
    if (c.workspace) usados.add(c.workspace);
  }
  return [...usados].sort((a, b) => a.localeCompare(b, 'pt-BR'));
}

/** Define o workspace de uma conversa. */
export function setConversationWorkspace(convId: string, workspace: string): void {
  const convs = getConversations();
  const i = convs.findIndex(c => c.id === convId);
  if (i < 0) return;
  convs[i].workspace = (workspace || '').trim() || WORKSPACE_PADRAO;
  convs[i].updatedAt = Date.now();
  saveConversations(convs);
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

/**
 * Apaga TODAS as conversas do tenant (local) e devolve quantas chaves removeu.
 *
 * PEDIDO DO USUARIO: "todos os contexto de teste nao e relevante, pode deixar
 * tudo limpo para criar os historicos do zero".
 *
 * CUIDADO DELIBERADO: remove APENAS as chaves de conversa
 * (`chat_conversations`, `messages_*`, `transcripts_*`, `activity_*`).
 * NAO usa `localStorage.clear()`, que apagaria tambem `saas_token`,
 * `saas_api_key`, `jarvis_voice`, o tema e o workspace escolhido — ou seja,
 * deslogaria o usuario e perderia as configuracoes dele.
 *
 * E nao precisa limpar cache do navegador: o dado e do proprio tenant, e some
 * de forma cirurgica.
 */
export function limparHistoricoLocal(): number {
  const prefixo = `${getTenantId()}_`;
  const alvos: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k || !k.startsWith(prefixo)) continue;
    const resto = k.slice(prefixo.length);
    if (
      resto === CONVERSATIONS_KEY ||
      resto.startsWith('messages_') ||
      resto.startsWith('transcripts_') ||
      resto.startsWith('activity_')
    ) {
      alvos.push(k);
    }
  }
  for (const k of alvos) localStorage.removeItem(k);
  return alvos.length;
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

export function createConversation(firstMessage?: string, workspace?: string): Conversation {
  const conv: Conversation = {
    id: generateId(),
    name: firstMessage ? autoName(firstMessage) : 'Nova conversa',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    workspace: (workspace || '').trim() || WORKSPACE_PADRAO,
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
  const transcricoes = getTranscripts(convId);
  // O Charon NAO tem "mensagens de chat": a conversa dele e a TRANSCRICAO de
  // voz. Exigir mensagens aqui fazia o download da sessao do Charon falhar com
  // "sem mensagens salvas", mesmo com a conversa inteira transcrita na tela.
  if (msgs.length === 0 && transcricoes.length === 0) return '';

  const quando = new Date().toLocaleString('pt-BR');
  const total = msgs.length + transcricoes.length;
  const linhas: string[] = [
    `# ${nome || 'Conversa'}`,
    '',
    `_Exportado do DEEP-OS em ${quando} — ${total} registros_`,
    '',
    '---',
    '',
  ];

  for (const m of msgs) {
    const hora = new Date(m.timestamp).toLocaleString('pt-BR');
    const quem = m.role === 'user' ? 'Voce' : 'Jarvis';
    linhas.push(`## ${quem} — ${hora}`, '', m.content, '');
  }

  // Transcricao de voz (Charon). Vem DEPOIS das mensagens quando as duas
  // existem, e como conteudo principal quando e a unica coisa que ha.
  if (transcricoes.length > 0) {
    linhas.push(
      msgs.length > 0 ? '---' : '',
      msgs.length > 0 ? '' : '',
      '## Transcricao de voz (Charon)',
      '',
    );
    for (const t of transcricoes) {
      const quem = t.speaker === 'user' ? 'Voce' : 'Charon';
      linhas.push(`**${quem}** (${t.time})`, '', t.text, '');
    }
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
