import { checkDemoRateLimit, DemoInputError, DemoRateLimitError, DemoServiceError, normalizeDemoQuestion, queryDemo, recordDemoQueryMetric } from '@/lib/vercel-demo';

export const runtime = 'nodejs';
export const maxDuration = 30;

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: { code: 'INVALID_JSON', message: 'Request body must be valid JSON.' } }, { status: 400 });
  }
  const value = body && typeof body === 'object' ? (body as Record<string, unknown>).question : undefined;
  let question: string;
  try {
    question = normalizeDemoQuestion(value);
  } catch (error) {
    if (error instanceof DemoInputError) {
      return Response.json({ error: { code: 'INVALID_QUESTION', message: error.message } }, { status: 400 });
    }
    return Response.json({ error: { code: 'INVALID_QUESTION', message: 'Question must be a string between 2 and 500 characters.' } }, { status: 400 });
  }

  let queryStartedAt: number | null = null;
  try {
    const rateLimit = await checkDemoRateLimit(request);
    if (rateLimit.limited) {
      return Response.json({ error: { code: 'RATE_LIMITED', message: 'Demo query limit reached. Please try again later.' } }, { status: 429, headers: { 'Cache-Control': 'no-store', 'Retry-After': String(rateLimit.retryAfter) } });
    }
    queryStartedAt = performance.now();
    const response = await queryDemo(question);
    await recordDemoQueryMetric({
      latency_ms: Math.round(performance.now() - queryStartedAt),
      succeeded: 1,
      abstained: response.abstained || response.grounding === 'no_match' ? 1 : 0,
      citations: response.citations.length,
      prompt_tokens: response.usage.prompt_tokens,
      completion_tokens: response.usage.completion_tokens,
      total_tokens: response.usage.total_tokens,
      estimated_cost_usd: response.usage.estimated_cost_usd,
    });
    return Response.json(response, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (queryStartedAt !== null) {
      await recordDemoQueryMetric({ latency_ms: Math.round(performance.now() - queryStartedAt), succeeded: 0, abstained: 0, citations: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, estimated_cost_usd: null });
    }
    if (error instanceof DemoRateLimitError) {
      return Response.json({ error: { code: 'RATE_LIMIT_UNAVAILABLE', message: 'This demo is temporarily unable to accept queries.' } }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
    }
    const status = error instanceof DemoServiceError && error.message.includes('not configured') ? 503 : 502;
    return Response.json({ error: { code: status === 503 ? 'DEMO_NOT_CONFIGURED' : 'GENERATION_FAILED', message: error instanceof DemoServiceError ? error.message : 'The demo could not answer this query.' } }, { status, headers: { 'Cache-Control': 'no-store' } });
  }
}
