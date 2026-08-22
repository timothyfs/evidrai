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
  if (value.includes('not supported') || value.includes('false') || value.includes('contradicted')) return '#ff6b62';
  if (value.includes('partly') || value.includes('misleading') || value.includes('mixed')) return '#ffc057';
  if (value.includes('supported') || value.includes('likely')) return '#65d69a';
  return '#8aa3b7';
}

function isDefinitiveContradiction(verdict: string, confidence: string) {
  const label = verdict.toLowerCase();
  return confidence.toLowerCase() === 'high' && (label.includes('false') || label.includes('contradicted'));
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
  const decisiveContradiction = isDefinitiveContradiction(verdict, confidence);
  const headerList = await headers();
  const baseUrl = baseUrlFromHeaders(headerList);
  const logoUrl = `${baseUrl}/brand/evidrai-logo-full.jpg`;

  return new ImageResponse(
    (
      <div
        style={{
          alignItems: 'stretch',
          background: 'linear-gradient(135deg, #091c1d 0%, #102f31 45%, #eff7f4 45%, #fff7e9 100%)',
          color: '#102222',
          display: 'flex',
          fontFamily: 'Inter, Arial, sans-serif',
          height: '100%',
          padding: 42,
          width: '100%',
        }}
      >
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.96), rgba(244,250,247,0.92))',
            border: '1px solid rgba(255,255,255,0.72)',
            borderRadius: 32,
            boxShadow: '0 28px 90px rgba(3,18,18,0.34)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            overflow: 'hidden',
            padding: 38,
            position: 'relative',
            width: '100%',
          }}
        >
          <div style={{ background: '#102f31', display: 'flex', height: 18, left: 0, position: 'absolute', right: 0, top: 0 }} />
          <div style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between', paddingTop: 4 }}>
            <img alt="Evidrai" height="86" src={logoUrl} style={{ objectFit: 'contain' }} width="300" />
            <div
              style={{
                background: '#102f31',
                border: '1px solid rgba(255,255,255,0.18)',
                borderRadius: 999,
                boxShadow: '0 12px 28px rgba(16,47,49,0.18)',
                color: '#ffffff',
                display: 'flex',
                fontSize: 28,
                fontWeight: 800,
                padding: '13px 22px',
              }}
            >
              Verify before you share
            </div>
          </div>

          <div style={{ alignItems: 'center', display: 'flex', gap: 38 }}>
            <div style={{ display: 'flex', flex: '1 1 auto', flexDirection: 'column', gap: 18, minWidth: 0 }}>
              <div style={{ color: '#f3a536', display: 'flex', fontSize: 25, fontWeight: 950, letterSpacing: 1.3, textTransform: 'uppercase' }}>
                Evidence-backed claim check
              </div>
              <div style={{ color: '#102222', display: 'flex', fontSize: 55, fontWeight: 900, lineHeight: 1.04 }}>
                {truncateText(claim, 116)}
              </div>
              <div style={{ color: '#4d6363', display: 'flex', fontSize: 28, fontWeight: 700, lineHeight: 1.35 }}>
                {decisiveContradiction
                  ? 'Credible evidence directly contradicts this claim. Inspect the sources before it spreads.'
                  : 'A public trust signal for claims, sources, confidence, and caveats.'}
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 2 }}>
                {['Source trail', 'Confidence', 'Caveats'].map((item) => (
                  <div
                    key={item}
                    style={{
                      background: 'rgba(16,47,49,0.08)',
                      border: '1px solid rgba(16,47,49,0.12)',
                      borderRadius: 999,
                      color: '#274848',
                      display: 'flex',
                      fontSize: 22,
                      fontWeight: 850,
                      padding: '10px 15px',
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div
              style={{
                alignItems: 'center',
                background: 'linear-gradient(180deg, #102f31, #071a1b)',
                border: '1px solid rgba(255,255,255,0.14)',
                borderRadius: 30,
                boxShadow: '0 24px 58px rgba(10,32,33,0.34)',
                color: '#ffffff',
                display: 'flex',
                flex: '0 0 326px',
                flexDirection: 'column',
                padding: '26px 24px 28px',
              }}
            >
              <div style={{ color: '#f3a536', display: 'flex', fontSize: 24, fontWeight: 950, letterSpacing: 1, textTransform: 'uppercase' }}>
                Evidrai verdict
              </div>
              <svg height="196" viewBox="0 0 320 210" width="300">
                <path d="M 38 162 A 122 122 0 0 1 282 162" fill="none" stroke="rgba(255,255,255,0.13)" strokeLinecap="round" strokeWidth="38" />
                <path d="M 38 162 A 122 122 0 0 1 100 56" fill="none" stroke="#ff5d55" strokeLinecap="round" strokeWidth="38" />
                <path d="M 116 48 A 122 122 0 0 1 204 48" fill="none" stroke="#ffc247" strokeLinecap="round" strokeWidth="38" />
                <path d="M 220 56 A 122 122 0 0 1 282 162" fill="none" stroke="#63d995" strokeLinecap="round" strokeWidth="38" />
                <path d="M 63 162 A 97 97 0 0 1 257 162" fill="none" stroke="rgba(8,24,24,0.54)" strokeLinecap="round" strokeWidth="18" />
                <line stroke="#ffffff" strokeLinecap="round" strokeWidth="8" transform={`rotate(${needleAngle} 160 162)`} x1="160" x2="160" y1="162" y2="58" />
                <line stroke="#f3a536" strokeLinecap="round" strokeWidth="3" transform={`rotate(${needleAngle} 160 162)`} x1="160" x2="160" y1="162" y2="68" />
                <circle cx="160" cy="162" fill="#ffffff" r="16" />
                <circle cx="160" cy="162" fill="#102f31" r="7" />
              </svg>
              <div style={{ color: '#d9e5e5', display: 'flex', fontSize: 17, fontWeight: 850, justifyContent: 'space-between', marginTop: -20, width: 274 }}>
                <span>False</span>
                <span>Mixed</span>
                <span>Supported</span>
              </div>
              <div style={{ color, display: 'flex', fontSize: 39, fontWeight: 950, lineHeight: 1.05, textAlign: 'center' }}>
                {decisiveContradiction ? 'Definitively contradicted' : truncateText(verdict, 42)}
              </div>
              <div style={{ color: '#d9e5e5', display: 'flex', fontSize: 23, fontWeight: 750, marginTop: 8 }}>
                {decisiveContradiction ? 'High-confidence contradiction' : `${confidence} confidence`}
              </div>
            </div>
          </div>

          <div style={{ alignItems: 'center', background: '#102f31', borderRadius: 20, color: '#ffffff', display: 'flex', fontSize: 28, fontWeight: 900, justifyContent: 'space-between', padding: '20px 24px' }}>
            <span>Start verifying at evidrai.com</span>
            <span style={{ color: '#f3a536' }}>Turn trust into a visible signal</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
