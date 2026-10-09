import { getDemoQueryMetrics } from '@/lib/vercel-demo';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    return Response.json(await getDemoQueryMetrics(), {
      headers: { 'Cache-Control': 'no-store' },
    });
  } catch {
    return Response.json({ error: { code: 'METRICS_UNAVAILABLE', message: 'Demo metrics are temporarily unavailable.' } }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
}
