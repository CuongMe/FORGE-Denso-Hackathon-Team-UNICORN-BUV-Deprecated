import { getDemoDocument } from '@/lib/vercel-demo';

export const dynamic = 'force-dynamic';

export async function GET(_request: Request, context: { params: Promise<{ docId: string }> }) {
  const { docId } = await context.params;
  const result = getDemoDocument(docId);
  if (!result) return Response.json({ error: { code: 'DOCUMENT_NOT_FOUND', message: 'The document was not found.' } }, { status: 404 });
  return Response.json(result, { headers: { 'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400' } });
}
