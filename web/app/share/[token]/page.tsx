import type { Metadata } from 'next';
import type { CSSProperties } from 'react';
import { headers } from 'next/headers';
import { API_BASE_URL } from '../../../lib/api';
import type { AssessmentResponse, PublicReportResponse } from '../../../lib/api';
import PrintButton from './PrintButton';

async function loadSharedReport(token: string): Promise<PublicReportResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/public/reports/${encodeURIComponent(token)}`, { cache: 'no-store' });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function formatDate(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function truncateText(value: string, max = 140) {
  const text = value.replace(/\s+/g, ' ').trim();
  return text.length > max ? `${text.slice(0, max - 1).trim()}…` : text;
}

function slugify(value: string, fallback: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 72) || fallback;
}

function claimTitle(report: AssessmentResponse) {
  return truncateText(report.request.claim || 'Evidence report', 96);
}

function reportSubject(report: AssessmentResponse) {
  return `Evidrai report: ${claimTitle(report)} — ${report.verdict.label}`;
}

function isDefinitiveContradiction(verdict?: string | null, confidence?: string | null) {
  const label = (verdict || '').toLowerCase();
  return (confidence || '').toLowerCase() === 'high' && (label.includes('false') || label.includes('contradicted'));
}

function confidenceDisplay(verdict?: string | null, confidence?: string | null) {
  return isDefinitiveContradiction(verdict, confidence) ? 'High-confidence contradiction' : `${confidence || 'Unstated'} confidence`;
}

function reportAbstract(report: AssessmentResponse, isSimple = false) {
  const decisiveContradiction = isDefinitiveContradiction(report.verdict.label, report.verdict.confidence);
  const parts = [decisiveContradiction
    ? 'Evidrai assessed this claim as definitively contradicted by the reviewed evidence.'
    : `Evidrai assessed this claim as ${report.verdict.label.toLowerCase()} with ${report.verdict.confidence.toLowerCase()} confidence.`];
  if (report.verdict.summary) parts.push(truncateText(report.verdict.summary, 220));
  if (report.verdict.key_caveat) parts.push(`Key caveat: ${truncateText(report.verdict.key_caveat, 180)}`);
  if (!isSimple) parts.push(`The report reviewed ${report.sources?.length || 0} source${(report.sources?.length || 0) === 1 ? '' : 's'}.`);
  parts.push('Share caveat: confidence is not certainty; inspect the evidence and caveats before reposting.');
  return parts.join(' ');
}

function shareLinks(url: string, title: string, abstract: string) {
  const body = `${abstract}\n\n${url}`;
  const socialText = `${title}\n\n${abstract}`;
  return [
    ['Email', `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`],
    ['LinkedIn', `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`],
    ['Facebook', `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`],
    ['Reddit', `https://www.reddit.com/submit?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`],
    ['X', `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(socialText)}`],
    ['WhatsApp', `https://wa.me/?text=${encodeURIComponent(`${socialText}\n${url}`)}`],
  ];
}

const verdictClass: Record<string, string> = {
  Supported: 'good',
  'Likely supported': 'good',
  'Partly supported': 'mixed',
  Unverified: 'weak',
  'Not supported by credible evidence': 'bad',
  'False / contradicted': 'bad',
  'Misleading framing': 'mixed',
};

function verdictTone(label: string) {
  return verdictClass[label] || 'weak';
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

function publicShareUrl(token: string, headerList: Headers) {
  const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
  const proto = headerList.get('x-forwarded-proto') || 'https';
  return process.env.NEXT_PUBLIC_WEB_BASE_URL ? `${process.env.NEXT_PUBLIC_WEB_BASE_URL.replace(/\/$/, '')}/share/${token}` : host ? `${proto}://${host}/share/${token}` : `/share/${token}`;
}

function publicShareImageUrl(token: string, headerList: Headers) {
  return `${publicShareUrl(token, headerList).replace(/\/$/, '')}/opengraph-image`;
}

type SharePageProps = { params: Promise<{ token: string }> };

export async function generateMetadata({ params }: SharePageProps): Promise<Metadata> {
  const { token } = await params;
  const payload = await loadSharedReport(token);
  if (!payload) {
    return {
      title: 'Shared Evidrai report not available',
      description: 'This Evidrai share link may be invalid, revoked, or unavailable.',
    };
  }
  const isSimple = payload.access_level !== 'full';
  const title = reportSubject(payload.assessment);
  const description = reportAbstract(payload.assessment, isSimple);
  const headerList = await headers();
  const url = publicShareUrl(token, headerList);
  const imageUrl = publicShareImageUrl(token, headerList);
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url,
      type: 'article',
      siteName: 'Evidrai',
      images: [{ url: imageUrl, width: 1200, height: 630, alt: `${payload.assessment.verdict.label} Evidrai verification result` }],
    },
    twitter: { card: 'summary_large_image', title, description, images: [imageUrl] },
  };
}

export default async function SharedReportPage({ params }: SharePageProps) {
  const { token } = await params;
  const payload = await loadSharedReport(token);
  if (!payload) {
    return (
      <main>
        <header className="siteHeader"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify</a></nav></header>
        <section className="card marketingPage"><p className="eyebrow">Shared report</p><h1>Report not available.</h1><p className="lead">The share link may be invalid, revoked, or unavailable.</p></section>
      </main>
    );
  }
  const report = payload.assessment;
  const isSimple = payload.access_level !== 'full';
  const title = reportSubject(report);
  const abstract = reportAbstract(report, isSimple);
  const headerList = await headers();
  const publicUrl = publicShareUrl(token, headerList);
  const tone = verdictTone(report.verdict.label);
  const claimSupport = claimSupportPercent(report.verdict.label, report.verdict.evidence_strength_score);
  const claimSupportAngle = claimSupport * 1.8;
  return (
    <main>
      <header className="siteHeader printHidden"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify another claim</a></nav></header>
      <section className="card resultCard assessmentCard publicReport">
        <div className="printMasthead"><strong>Evidrai</strong><span>Evidence report</span></div>
        <div className="resultHeader assessmentHeader">
          <div>
            <p className="eyebrow">{isSimple ? 'Shared Evidrai verdict' : 'Shared Evidrai report'}</p>
            <h1>{report.request.claim || 'Untitled claim'}</h1>
            <p className="resultSubcopy">{isSimple ? 'A simple public Evidrai verdict card. Run your own check to inspect the full evidence trail.' : 'Public read-only assessment. Evidence should be inspected, not just forwarded like internet confetti.'}</p>
          </div>
          <div className={`verdict verdictPanel ${tone}`}>
            <span>Claim support</span>
            <div
              className="claimSupportDial"
              role="meter"
              aria-label={`Claim support: ${report.verdict.label}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={claimSupport}
              style={{ '--claim-support-angle': `${claimSupportAngle}deg` } as CSSProperties}
            >
              <div className="claimSupportNeedle" />
            </div>
            <strong>{report.verdict.label}</strong>
            <div className="claimSupportScale" aria-hidden="true"><span>Low</span><span>Mixed</span><span>High</span></div>
            <small>{confidenceDisplay(report.verdict.label, report.verdict.confidence)}</small>
          </div>
        </div>
        <div className={`mobileVerdictBar ${tone}`} aria-label="Sticky verdict summary">
          <div
            className="claimSupportDial mobileClaimSupportDial"
            role="meter"
            aria-label={`Claim support: ${report.verdict.label}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={claimSupport}
            style={{ '--claim-support-angle': `${claimSupportAngle}deg` } as CSSProperties}
          >
            <div className="claimSupportNeedle" />
          </div>
          <div>
            <strong>Claim support: {report.verdict.label}</strong>
            <span>{confidenceDisplay(report.verdict.label, report.verdict.confidence)} · {isSimple ? 'Simple share' : `${report.sources?.length || 0} sources`}</span>
          </div>
        </div>
        <div className="reportAbstract">
          <p className="eyebrow">Abstract</p>
          <p>{abstract}</p>
        </div>
        <div className="assessmentNarrative">
          {report.verdict.summary && <p className="summary">{report.verdict.summary}</p>}
          {typeof report.reasoning?.humour_summary === 'string' && report.reasoning.humour_summary.trim() && <p className="absurdityCheck"><strong>Absurdity check</strong>{report.reasoning.humour_summary}</p>}
          {report.verdict.key_caveat && <p className="caveat"><strong>Key caveat</strong>{report.verdict.key_caveat}</p>}
        </div>
        <div className="facts assessmentFacts"><span>Assessment ID: {report.assessment_id}</span><span>{formatDate(report.created_at)}</span><span>{report.mode}</span>{isSimple ? <span>Simple share</span> : <span>{report.sources?.length || 0} sources</span>}</div>
        <section className="sharePanel resultSection printHidden">
          <p className="eyebrow">Share / export</p>
          <div className="shareActions">
            <PrintButton />
            {shareLinks(publicUrl, title, abstract).map(([label, href]) => <a className="button secondary" href={href} key={label} rel="noreferrer" target="_blank">{label}</a>)}
          </div>
          <p className="muted">PDF export uses your browser print dialog. Choose “Save as PDF”. For Instagram, copy this page URL and paste it into a story sticker, caption, bio, or DM.</p>
        </section>
        <section className="shareSignupCta resultSection printHidden">
          <div>
            <p className="eyebrow">Verify before you share</p>
            <h2>Turn trust into a visible signal.</h2>
            <p>Run your own Evidrai check, inspect the source trail, then share a branded result that carries the verdict, confidence, and caveats with it.</p>
            <div className="shareSignupProof" aria-label="Evidrai trust verification features">
              <span>Evidence trail</span>
              <span>Confidence signal</span>
              <span>Share-ready verdict</span>
            </div>
          </div>
          <a className="button" href="/#sign-in">Start verifying claims</a>
        </section>
        {isSimple ? (
          <section className="resultSection evidenceSourcesSection">
            <h2>Want the evidence trail?</h2>
            <p className="muted">This free share is deliberately lightweight. Use Evidrai to run your own check and inspect sources, scoring, caveats, and claim breakdown.</p>
            <a className="button secondary printHidden" href="/">Verify this yourself</a>
          </section>
        ) : (
          <>
            {Boolean(report.claim_breakdown?.length) && (
              <section className="resultSection reportBreakdownSection">
                <h2>Claim breakdown</h2>
                <div className="reportBreakdownGrid">
                  {report.claim_breakdown.map((item, index) => (
                    <article className="reportBreakdownCard" id={slugify(item.id || item.text, `claim-${index + 1}`)} key={item.id || item.text}>
                      <div><strong>{item.text}</strong><span>{item.assessment} · {item.confidence}</span></div>
                      {item.rationale && <p>{item.rationale}</p>}
                    </article>
                  ))}
                </div>
              </section>
            )}
            <section className="resultSection evidenceSourcesSection">
              <h2>Evidence sources</h2>
              <div className="sourceGrid">
                {(report.sources || []).map((source, index) => (
                  <article className="sourceCard" key={source.id || source.url || index}>
                    <div className="sourceTopline"><strong>{source.title || source.domain || 'Untitled source'}</strong><span>{source.source_type}</span></div>
                    <p>{source.summary || source.classification_reason || source.url}</p>
                    {source.url && <a href={source.url} rel="noreferrer" target="_blank">Open source</a>}
                  </article>
                ))}
              </div>
            </section>
          </>
        )}
        <p className="printFooter">Shared report URL: {publicUrl}</p>
      </section>
    </main>
  );
}
