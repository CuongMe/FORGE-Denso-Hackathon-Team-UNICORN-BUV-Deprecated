export type ChatHistoryMessage = {
  id: string;
  role: 'user' | 'assistant' | 'upload';
  content: string;
};

export type ChatHistoryEntry = {
  id: string;
  title: string;
  updatedAt: string;
  messages: ChatHistoryMessage[];
};

export const CHAT_HISTORY_KEY = 'forge-chat-history';
// shortcut: retain ten chats and forty messages each; use server-side paging if longer retention is needed.
export const CHAT_HISTORY_LIMIT = 10;
const MESSAGE_LIMIT = 40;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isHistoryMessage(value: unknown): value is ChatHistoryMessage {
  return isRecord(value)
    && typeof value.id === 'string' && value.id.length <= 120
    && ['user', 'assistant', 'upload'].includes(value.role as string)
    && typeof value.content === 'string';
}

export function parseChatHistory(serialized: string | null): ChatHistoryEntry[] {
  if (!serialized) return [];

  try {
    const parsed: unknown = JSON.parse(serialized);
    if (!Array.isArray(parsed)) return [];

    return parsed.flatMap((value) => {
      if (!isRecord(value)
        || typeof value.id !== 'string' || value.id.length > 120
        || typeof value.title !== 'string' || value.title.length > 200
        || typeof value.updatedAt !== 'string' || !Number.isFinite(Date.parse(value.updatedAt))
        || !Array.isArray(value.messages)) return [];

      const messages = value.messages.filter(isHistoryMessage).slice(-MESSAGE_LIMIT);
      return messages.length ? [{ id: value.id, title: value.title, updatedAt: value.updatedAt, messages }] : [];
    }).slice(0, CHAT_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function upsertChatHistory(history: ChatHistoryEntry[], entry: ChatHistoryEntry): ChatHistoryEntry[] {
  return [
    { ...entry, messages: entry.messages.slice(-MESSAGE_LIMIT) },
    ...history.filter((item) => item.id !== entry.id),
  ].slice(0, CHAT_HISTORY_LIMIT);
}
