import { describe, expect, it } from 'vitest';

import { CHAT_HISTORY_LIMIT, parseChatHistory, upsertChatHistory, type ChatHistoryEntry } from '@/lib/chat-history';

const entry = (id: string): ChatHistoryEntry => ({
  id,
  title: `Question ${id}`,
  updatedAt: '2026-10-11T10:00:00.000Z',
  messages: [{ id: `message-${id}`, role: 'user', content: `Question ${id}` }],
});

describe('local chat history', () => {
  it('ignores malformed storage and filters invalid entries', () => {
    expect(parseChatHistory('{broken')).toEqual([]);
    expect(parseChatHistory(JSON.stringify([entry('ok'), { ...entry('bad'), updatedAt: 'yesterday' }]))).toEqual([entry('ok')]);
  });

  it('updates the selected chat at the top and keeps history bounded', () => {
    const history = Array.from({ length: CHAT_HISTORY_LIMIT }, (_, index) => entry(String(index)));
    const updated = upsertChatHistory(history, entry('5'));
    expect(updated[0]?.id).toBe('5');
    expect(updated).toHaveLength(CHAT_HISTORY_LIMIT);
    expect(updated.filter((item) => item.id === '5')).toHaveLength(1);
  });
});
