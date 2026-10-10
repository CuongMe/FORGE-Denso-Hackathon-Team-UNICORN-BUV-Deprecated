import { getDemoVisualDetections } from '@/lib/vercel-demo';

export const dynamic = 'force-dynamic';

export async function GET(_request: Request, context: { params: Promise<{ docId: string }> }) {
  const { docId } = await context.params;
  const result = getDemoVisualDetections(docId);
  if (!result) return Response.json({ error: { code: 'VISUAL_DETECTION_UNAVAILABLE', message: 'Florence-2 detections are not available for this image.' } }, { status: 404 });
  return Response.json(result, { headers: { 'Cache-Control': 'public, max-age=86400, stale-while-revalidate=604800' } });
}
