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
    const upstream = await fetch(`${API_BASE_URL}/reports/${encodeURIComponent(id)}/share`, {
      method: 'POST',
      headers,
      body: body || '{}',
      cache: 'no-store',
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('content-type') || 'application/json' },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Share proxy failed';
    return Response.json({ detail: { code: 'share_proxy_error', message } }, { status: 502 });
  }
}
