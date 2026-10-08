import { afterEach, describe, expect, it, vi } from 'vitest';

import { checkDemoRateLimit, getDemoDocuments, normalizeDemoQuestion, queryDemo, rankDemoChunks } from '@/lib/vercel-demo';
import { POST } from '@/app/api/query/route';
import { GET as getDocumentChunks } from '@/app/api/documents/[docId]/chunks/route';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('pre-indexed Vercel demo corpus', () => {
  it('contains every manifest-listed source with searchable chunks', () => {
    const documents = getDemoDocuments();
    expect(documents).toHaveLength(17);
    expect(documents.every((document) => document.chunk_count > 0)).toBe(true);
  });

  it('ranks the safety poster for a matching question and preserves provenance', () => {
    const [result] = rankDemoChunks('bilingual forklift safety poster', 1);
    expect(result?.chunk.doc_id).toBe('IMG-SAFE-001');
    expect(result?.chunk.provenance.length).toBeGreaterThan(0);
  });

  it('normalizes and bounds user questions at the route boundary', () => {
    expect(normalizeDemoQuestion('  torque   control  ')).toBe('torque control');
    expect(() => normalizeDemoQuestion(' ')).toThrow();
    expect(() => normalizeDemoQuestion('x'.repeat(501))).toThrow();
  });

  it('sends the server-only key to Gemini and returns cited evidence', async () => {
    vi.stubEnv('GEMINI_API_KEY', 'test-only-key');
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      candidates: [{ content: { parts: [{ text: 'Use the posted forklift safety guidance. [E1]' }] } }],
      usageMetadata: { promptTokenCount: 10, candidatesTokenCount: 8, totalTokenCount: 18 },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await queryDemo('bilingual forklift safety poster');
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).not.toContain('test-only-key');
    expect(new Headers(init?.headers).get('x-goog-api-key')).toBe('test-only-key');
    expect(response.citations[0]?.doc_id).toBe('IMG-SAFE-001');
    expect(response.usage.total_tokens).toBe(18);
  });

  it('does not call Gemini when the query only matches common words', async () => {
    vi.stubEnv('GEMINI_API_KEY', 'test-only-key');
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);

    const response = await queryDemo('what is the');

    expect(fetchMock).not.toHaveBeenCalled();
    expect(response.grounding).toBe('no_match');
    expect(response.citations).toHaveLength(0);
  });

  it('returns only evidence labels used by the answer', async () => {
    vi.stubEnv('GEMINI_API_KEY', 'test-only-key');
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      candidates: [{ content: { parts: [{ text: 'The target is 9.5 ± 0.5 N·m. [E1]' }] } }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const response = await queryDemo('What is the target torque for M6 bolts?');

    expect(response.citations).toHaveLength(1);
    expect(response.citations[0]?.doc_id).toBe('WI-ASSY-001');
  });

  it('abstains instead of presenting an uncited model answer as grounded', async () => {
    vi.stubEnv('GEMINI_API_KEY', 'test-only-key');
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      candidates: [{ content: { parts: [{ text: 'The target is 9.5 N·m.' }] } }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const response = await queryDemo('What is the target torque for M6 bolts?');

    expect(response.abstained).toBe(true);
    expect(response.grounding).toBe('no_match');
    expect(response.citations).toHaveLength(0);
    expect(response.answer).not.toContain('9.5');
  });

  it('enforces shared per-IP and daily limits for deployed requests', async () => {
    vi.stubEnv('VERCEL', '1');
    vi.stubEnv('UPSTASH_REDIS_REST_URL', 'https://redis.example.test');
    vi.stubEnv('UPSTASH_REDIS_REST_TOKEN', 'test-only-token');
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ result: [9, 13] }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await checkDemoRateLimit(new Request('https://forge.example/api/query', {
      headers: { 'x-vercel-forwarded-for': '203.0.113.5' },
    }));

    expect(result.limited).toBe(true);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('https://redis.example.test/');
    expect(JSON.stringify(fetchMock.mock.calls[0]?.[1]?.body)).not.toContain('203.0.113.5');
  });

  it('fails closed on Vercel when the shared rate-limit store is not configured', async () => {
    vi.stubEnv('VERCEL', '1');
    vi.stubEnv('UPSTASH_REDIS_REST_URL', '');
    vi.stubEnv('UPSTASH_REDIS_REST_TOKEN', '');

    await expect(checkDemoRateLimit(new Request('https://forge.example/api/query'))).rejects.toThrow();
  });

  it('blocks over-limit deployed questions before calling Gemini', async () => {
    vi.stubEnv('VERCEL', '1');
    vi.stubEnv('UPSTASH_REDIS_REST_URL', 'https://redis.example.test');
    vi.stubEnv('UPSTASH_REDIS_REST_TOKEN', 'test-only-token');
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ result: [9, 13] }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await POST(new Request('https://forge.example/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-vercel-forwarded-for': '203.0.113.5' },
      body: JSON.stringify({ question: 'What is the target torque for M6 bolts?' }),
    }));

    expect(response.status).toBe(429);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('keeps deployed Gemini queries closed until the shared limiter is configured', async () => {
    vi.stubEnv('VERCEL', '1');
    vi.stubEnv('UPSTASH_REDIS_REST_URL', '');
    vi.stubEnv('UPSTASH_REDIS_REST_TOKEN', '');
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);

    const response = await POST(new Request('https://forge.example/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'What is the target torque for M6 bolts?' }),
    }));

    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('returns processed source chunks for the Documents tab', async () => {
    const response = await getDocumentChunks(new Request('https://forge.example/api/documents/WI-ASSY-001/chunks'), {
      params: Promise.resolve({ docId: 'WI-ASSY-001' }),
    });
    const result = await response.json();

    expect(response.status).toBe(200);
    expect(result.chunks).toHaveLength(5);
    expect(result.chunks[3].content).toContain('9.5');
  });
});
