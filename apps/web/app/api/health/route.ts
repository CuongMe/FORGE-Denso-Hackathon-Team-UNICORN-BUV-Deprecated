import { getDemoHealth } from '@/lib/vercel-demo';

export const dynamic = 'force-dynamic';

export async function GET() {
  return Response.json(getDemoHealth(), { headers: { 'Cache-Control': 'no-store' } });
}
