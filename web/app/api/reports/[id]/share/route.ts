import { NextRequest } from 'next/server';
import { API_BASE_URL } from '../../../../../lib/api';

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const authorization = request.headers.get('authorization');
  const ownerId = request.headers.get('x-evidrai-user-id');
  if (authorization) headers.Authorization = authorization;
  if (ownerId) headers['X-Evidrai-User-Id'] = ownerId;

  try {
    const upstream = await fetch(`${API_BASE_URL}/reports/${encodeURIComponent(id)}/share?include_debug=true`, {
      method: 'POST',
      headers,
      body: body || '{}',
      cache: 'no-store',
    });
    const text = await upstream.text();
    const contentType = upstream.headers.get('content-type') || 'application/json';
    if (!upstream.ok) {
      let detail: unknown = text;
      try {
        detail = JSON.parse(text);
      } catch {
        // Keep text detail.
      }
      return Response.json({
        detail: {
          code: 'share_upstream_error',
          message: `Share API returned ${upstream.status}`,
          upstream_status: upstream.status,
          upstream_detail: detail,
        },
      }, { status: upstream.status });
    }
    return new Response(text, {
      status: upstream.status,
      headers: { 'Content-Type': contentType },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Share proxy failed';
    return Response.json({ detail: { code: 'share_proxy_error', message } }, { status: 502 });
  }
}
