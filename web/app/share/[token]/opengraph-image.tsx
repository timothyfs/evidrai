import { ImageResponse } from 'next/og';
import { headers } from 'next/headers';
import { API_BASE_URL } from '../../../lib/api';
import type { PublicReportResponse } from '../../../lib/api';

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = 'image/png';

type ImageProps = { params: Promise<{ token: string }> };

async function loadSharedReport(token: string): Promise<PublicReportResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/public/reports/${encodeURIComponent(token)}`, { cache: 'no-store' });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function truncateText(value: string, max = 132) {
  const text = value.replace(/\s+/g, ' ').trim();
  return text.length > max ? `${text.slice(0, max - 1).trim()}...` : text;
}

function claimSupportPercent(verdict: string, score?: number | null) {
  const boundedScore = typeof score === 'number' && Number.isFinite(score)
    ? Math.max(0, Math.min(10, Math.abs(score)))
    : null;
  const withinBucket = (min: number, max: number, fallback: number, inverted = false) => {
    if (boundedScore === null) return fallback;
    const ratio = boundedScore / 10;
    const value = inverted ? max - ratio * (max - min) : min + ratio * (max - min);
    return Math.round(Math.max(min, Math.min(max, value)));
  };
  const label = (verdict || '').toLowerCase();
  if (label.includes('not supported') || label.includes('false') || label.includes('contradicted')) return withinBucket(8, 28, 12, true);
  if (label.includes('partly') || label.includes('misleading') || label.includes('mixed')) return withinBucket(44, 62, 52);
  if (label.includes('weakly') || label.includes('weak overall') || label.includes('promising but incomplete')) return withinBucket(24, 42, 30);
  if (label.includes('likely')) return withinBucket(66, 86, 72);
  if (label.includes('supported')) return withinBucket(72, 94, 84);
  return 42;
}

function verdictColor(label: string) {
  const value = label.toLowerCase();
  if (value.includes('not supported') || value.includes('false') || value.includes('contradicted')) return '#d95656';
  if (value.includes('partly') || value.includes('misleading') || value.includes('mixed')) return '#d6a347';
  if (value.includes('supported') || value.includes('likely')) return '#4fbd85';
  return '#8aa3b7';
}

function baseUrlFromHeaders(headerList: Headers) {
  const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
  const proto = headerList.get('x-forwarded-proto') || 'https';
  return process.env.NEXT_PUBLIC_WEB_BASE_URL?.replace(/\/$/, '') || (host ? `${proto}://${host}` : 'https://www.evidrai.com');
}

export default async function Image({ params }: ImageProps) {
  const { token } = await params;
  const payload = await loadSharedReport(token);
  const report = payload?.assessment;
  const claim = report?.request.claim || 'Evidence report';
  const verdict = report?.verdict.label || 'Verification result';
  const confidence = report?.verdict.confidence || 'Evidrai';
  const support = claimSupportPercent(verdict, report?.verdict.evidence_strength_score);
  const needleAngle = -90 + support * 1.8;
  const color = verdictColor(verdict);
  const headerList = await headers();
  const baseUrl = baseUrlFromHeaders(headerList);
  const logoUrl = `${baseUrl}/brand/evidrai-logo-full.jpg`;

  return new ImageResponse(
    (
      <div
        style={{
          alignItems: 'stretch',
          background: 'linear-gradient(135deg, #f6fbfb 0%, #e8f0f0 48%, #f9f6ef 100%)',
          color: '#142424',
          display: 'flex',
          fontFamily: 'Inter, Arial, sans-serif',
          height: '100%',
          padding: 54,
          width: '100%',
        }}
      >
        <div
          style={{
            background: 'rgba(255,255,255,0.88)',
            border: '1px solid rgba(48,68,68,0.12)',
            borderRadius: 34,
            boxShadow: '0 24px 80px rgba(26,44,44,0.16)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            overflow: 'hidden',
            padding: 42,
            width: '100%',
          }}
        >
          <div style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between' }}>
            <img alt="Evidrai" height="86" src={logoUrl} style={{ objectFit: 'contain' }} width="300" />
            <div
              style={{
                border: '1px solid rgba(20,36,36,0.14)',
                borderRadius: 999,
                color: '#496363',
                display: 'flex',
                fontSize: 27,
                fontWeight: 800,
                padding: '12px 20px',
              }}
            >
              Trust verification
            </div>
          </div>

          <div style={{ alignItems: 'center', display: 'flex', gap: 44 }}>
            <div style={{ display: 'flex', flex: '1 1 auto', flexDirection: 'column', gap: 22, minWidth: 0 }}>
              <div style={{ color: '#587070', display: 'flex', fontSize: 26, fontWeight: 900, letterSpacing: 1.6, textTransform: 'uppercase' }}>
                Shared evidence result
              </div>
              <div style={{ color: '#102222', display: 'flex', fontSize: 55, fontWeight: 900, lineHeight: 1.04 }}>
                {truncateText(claim, 116)}
              </div>
              <div style={{ color: '#4d6363', display: 'flex', fontSize: 28, fontWeight: 700, lineHeight: 1.35 }}>
                Verify claims before they travel. Inspect the evidence, confidence, and caveats with Evidrai.
              </div>
            </div>

            <div
              style={{
                alignItems: 'center',
                background: '#102222',
                borderRadius: 30,
                color: '#ffffff',
                display: 'flex',
                flex: '0 0 326px',
                flexDirection: 'column',
                padding: '26px 24px 28px',
              }}
            >
              <div style={{ color: '#b9cbcb', display: 'flex', fontSize: 24, fontWeight: 850, textTransform: 'uppercase' }}>
                Dial result
              </div>
              <svg height="196" viewBox="0 0 320 210" width="300">
                <path d="M 38 162 A 122 122 0 0 1 282 162" fill="none" stroke="rgba(255,255,255,0.16)" strokeLinecap="round" strokeWidth="32" />
                <path d="M 38 162 A 122 122 0 0 1 282 162" fill="none" pathLength="100" stroke="#d95656" strokeDasharray="31 69" strokeLinecap="round" strokeWidth="32" />
                <path d="M 38 162 A 122 122 0 0 1 282 162" fill="none" pathLength="100" stroke="#d6a347" strokeDasharray="25 75" strokeDashoffset="-36" strokeLinecap="round" strokeWidth="32" />
                <path d="M 38 162 A 122 122 0 0 1 282 162" fill="none" pathLength="100" stroke="#4fbd85" strokeDasharray="31 69" strokeDashoffset="-69" strokeLinecap="round" strokeWidth="32" />
                <line stroke="#ffffff" strokeLinecap="round" strokeWidth="8" transform={`rotate(${needleAngle} 160 162)`} x1="160" x2="160" y1="162" y2="58" />
                <circle cx="160" cy="162" fill="#ffffff" r="16" />
              </svg>
              <div style={{ color, display: 'flex', fontSize: 39, fontWeight: 950, lineHeight: 1.05, textAlign: 'center' }}>
                {truncateText(verdict, 42)}
              </div>
              <div style={{ color: '#d9e5e5', display: 'flex', fontSize: 23, fontWeight: 750, marginTop: 8 }}>
                {confidence} confidence
              </div>
            </div>
          </div>

          <div style={{ alignItems: 'center', borderTop: '1px solid rgba(48,68,68,0.12)', color: '#496363', display: 'flex', fontSize: 28, fontWeight: 850, justifyContent: 'space-between', paddingTop: 26 }}>
            <span>Start verifying at evidrai.com</span>
            <span>Because trust needs evidence</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
