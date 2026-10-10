import { afterEach, describe, expect, it, vi } from 'vitest';

import { checkDemoRateLimit, getDemoDocument, getDemoDocuments, getDemoQueryMetrics, normalizeDemoQuestion, queryDemo, rankDemoChunks, recordDemoQueryMetric } from '@/lib/vercel-demo';
import { POST } from '@/app/api/query/route';
import { GET as getDocumentChunks } from '@/app/api/documents/[docId]/chunks/route';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('pre-indexed Vercel demo corpus', () => {
  it('contains every manifest-listed source with searchable chunks', () => {
    const documents = getDemoDocuments();
    expect(documents).toHaveLength(47);
    expect(documents.every((document) => document.chunk_count > 0)).toBe(true);
  });

  it('indexes the selected Japanese business document benchmark with source references', () => {
    const [result] = rankDemoChunks('以下の条件をすべて満たす輸送モードを特定せよ。', 1);
    expect(result?.chunk.doc_id).toBe('JA-BIZ-0001');
    expect(getDemoDocument('JA-BIZ-0001')?.chunks).toHaveLength(2);
  });

  it('ranks the safety poster for a matching question and preserves provenance', () => {
    const [result] = rankDemoChunks('bilingual forklift safety poster', 1);
    expect(result?.chunk.doc_id).toBe('IMG-SAFE-001');
    expect(result?.chunk.provenance.length).toBeGreaterThan(0);
  });

  it('uses verified Vietnamese text for the synthetic forklift poster', () => {
    const content = getDemoDocument('IMG-SAFE-001')?.chunks.map((chunk) => chunk.content).join(' ') ?? '';
    expect(content).toContain('Giới hạn tốc độ trong xưởng');
    expect(content).toContain('Dừng và báo cáo nếu đèn cảnh báo không hoạt động');
    expect(content).not.toContain('Gii hn tc');
  });

  it('normalizes and bounds user questions at the route boundary', () => {
    expect(normalizeDemoQuestion('  torque   control  ')).toBe('torque control');
    expect(() => normalizeDemoQuestion(' ')).toThrow();
    expect(() => normalizeDemoQuestion('x'.repeat(501))).toThrow();
  });

  it('sends the server-only key to Gemini and returns cited evidence', async () => {
    vi.stubEnv('GEMINI_API_KEY', 'test-only-key');
    vi.stubEnv('FORGE_GEMINI_INPUT_USD_PER_MILLION', '2.5');
    vi.stubEnv('FORGE_GEMINI_OUTPUT_USD_PER_MILLION', '10');
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
    expect(response.usage.estimated_cost_usd).toBe(0.000105);
    expect(response.trace.retrieval_ms).toBeGreaterThanOrEqual(0);
    expect(response.trace.rerank_ms).toBe(0);
    expect(response.trace.generation_ms).toBeGreaterThanOrEqual(0);
    expect(response.trace.latency_ms).toBeGreaterThanOrEqual(response.trace.generation_ms ?? 0);
  });

  it('answers a Vietnamese request in Vietnamese when its cited source is Japanese', async () => {
    vi.stubEnv('GEMINI_API_KEY', 'test-only-key');
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({
      candidates: [{ content: { parts: [{ text: 'Tài liệu mô tả quy trình kiểm tra hàng nhập. [E1]' }] } }],
    }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await queryDemo('@JA-BIZ-0063 giải thích');
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    const instruction = body.systemInstruction.parts[0].text;

    expect(instruction).toContain('answer Vietnamese questions about Japanese evidence in Vietnamese');
    expect(response.answer).toContain('Tài liệu mô tả');
    expect(response.citations[0]?.doc_id).toBe('JA-BIZ-0063');
    expect(response.trace.prompt_version).toBe('vercel-denso-grounded-v2');
  });

  it('runs spreadsheet totals through SQLite and cites the source table without calling Gemini', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);

    const response = await queryDemo('What is the sum of actual pcs in production log?');

    expect(response.aggregation).toMatchObject({
      operation: 'sum',
      value: 4820,
      source_doc_id: 'TBL-PROD-001',
      source_name: 'production_log.xlsx',
      column: 'Actual pcs',
      rows_considered: 7,
    });
    expect(response.trace.route).toBe('aggregation');
    expect(response.citations[0]?.doc_id).toBe('TBL-PROD-001');
    expect(response.trace.latency_ms).toBeGreaterThanOrEqual(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('counts matching spreadsheet rows with a SQL filter', async () => {
    const response = await queryDemo('How many inspection results are FAIL?');

    expect(response.aggregation).toMatchObject({
      operation: 'count',
      source_doc_id: 'TBL-QLT-001',
      filter_text: 'FAIL',
    });
    expect(response.aggregation?.value).toBe(3);
    expect(response.trace.route).toBe('aggregation');
  });

  it('treats "min" in a column label as a unit when the question requests a total', async () => {
    const response = await queryDemo('What is the total downtime min for maintenance history?');

    expect(response.aggregation).toMatchObject({
      operation: 'sum',
      value: 75,
      source_doc_id: 'TBL-MNT-001',
      column: 'Downtime min',
    });
  });

  it('stores privacy-safe query metrics in Redis and aggregates the seven-day window', async () => {
    vi.stubEnv('VERCEL', '1');
    vi.stubEnv('UPSTASH_REDIS_REST_URL', 'https://redis.example.test');
    vi.stubEnv('UPSTASH_REDIS_REST_TOKEN', 'test-only-token');
    const records = [
      { id: 'q2', created_at: '2026-10-09T10:00:00.000Z', latency_ms: 200, succeeded: 1, abstained: 0, citations: 1, prompt_tokens: 10, completion_tokens: 5, total_tokens: 15, estimated_cost_usd: 0.001 },
      { id: 'q1', created_at: '2026-10-09T09:00:00.000Z', latency_ms: 100, succeeded: 0, abstained: 0, citations: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, estimated_cost_usd: null },
    ];
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ result: 1 }))
      .mockResolvedValueOnce(Response.json({ result: records.map(record => JSON.stringify(record)) }));
    vi.stubGlobal('fetch', fetchMock);

    await recordDemoQueryMetric({ latency_ms: 125, succeeded: 1, abstained: 0, citations: 1, prompt_tokens: 10, completion_tokens: 5, total_tokens: 15, estimated_cost_usd: 0.001 });
    const metrics = await getDemoQueryMetrics();
    const writeCommand = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));

    expect(metrics.total_queries).toBe(2);
    expect(metrics.success_rate).toBe(0.5);
    expect(metrics.p50_latency_ms).toBe(100);
    expect(metrics.p95_latency_ms).toBe(200);
    expect(metrics.total_tokens).toBe(15);
    expect(metrics.estimated_cost_usd).toBeNull();
    expect(JSON.stringify(writeCommand)).not.toContain('question');
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
