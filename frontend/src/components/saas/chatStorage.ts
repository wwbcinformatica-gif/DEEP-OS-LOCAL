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
