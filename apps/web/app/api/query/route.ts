import { checkDemoRateLimit, DemoInputError, DemoRateLimitError, DemoServiceError, normalizeDemoQuestion, queryDemo } from '@/lib/vercel-demo';

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

  try {
    const rateLimit = await checkDemoRateLimit(request);
    if (rateLimit.limited) {
      return Response.json({ error: { code: 'RATE_LIMITED', message: 'Demo query limit reached. Please try again later.' } }, { status: 429, headers: { 'Cache-Control': 'no-store', 'Retry-After': String(rateLimit.retryAfter) } });
    }
    return Response.json(await queryDemo(question), { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof DemoRateLimitError) {
      return Response.json({ error: { code: 'RATE_LIMIT_UNAVAILABLE', message: 'This demo is temporarily unable to accept queries.' } }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
    }
    const status = error instanceof DemoServiceError && error.message.includes('not configured') ? 503 : 502;
    return Response.json({ error: { code: status === 503 ? 'DEMO_NOT_CONFIGURED' : 'GENERATION_FAILED', message: error instanceof DemoServiceError ? error.message : 'The demo could not answer this query.' } }, { status, headers: { 'Cache-Control': 'no-store' } });
  }
}
