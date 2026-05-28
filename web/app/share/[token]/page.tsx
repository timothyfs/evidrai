import type { Metadata } from 'next';
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

function claimTitle(report: AssessmentResponse) {
  return truncateText(report.request.claim || 'Evidence report', 96);
}

function reportSubject(report: AssessmentResponse) {
  return `Evidrai report: ${claimTitle(report)} — ${report.verdict.label}`;
}

function reportAbstract(report: AssessmentResponse, isSimple = false) {
  const parts = [`Evidrai assessed this claim as ${report.verdict.label.toLowerCase()} with ${report.verdict.confidence.toLowerCase()} confidence.`];
  if (report.verdict.summary) parts.push(truncateText(report.verdict.summary, 220));
  if (report.verdict.key_caveat) parts.push(`Key caveat: ${truncateText(report.verdict.key_caveat, 180)}`);
  if (!isSimple) parts.push(`The report reviewed ${report.sources?.length || 0} source${(report.sources?.length || 0) === 1 ? '' : 's'}.`);
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

function publicShareUrl(token: string, headerList: Headers) {
  const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
  const proto = headerList.get('x-forwarded-proto') || 'https';
  return process.env.NEXT_PUBLIC_WEB_BASE_URL ? `${process.env.NEXT_PUBLIC_WEB_BASE_URL.replace(/\/$/, '')}/share/${token}` : host ? `${proto}://${host}/share/${token}` : `/share/${token}`;
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
  return {
    title,
    description,
    openGraph: { title, description, url, type: 'article', siteName: 'Evidrai' },
    twitter: { card: 'summary_large_image', title, description },
  };
}

export default async function SharedReportPage({ params }: SharePageProps) {
  const { token } = await params;
  const payload = await loadSharedReport(token);
  if (!payload) {
    return (
      <main>
        <header className="siteHeader"><a className="brand logoBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-logo-full.jpg" alt="" /><img className="logoDark" src="/brand/evidrai-logo-full-dark.jpg" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify</a></nav></header>
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
  return (
    <main>
      <header className="siteHeader printHidden"><a className="brand logoBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-logo-full.jpg" alt="" /><img className="logoDark" src="/brand/evidrai-logo-full-dark.jpg" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify another claim</a></nav></header>
      <section className="card resultCard assessmentCard publicReport">
        <div className="printMasthead"><strong>Evidrai</strong><span>Evidence report</span></div>
        <div className="resultHeader assessmentHeader">
          <div>
            <p className="eyebrow">{isSimple ? 'Shared Evidrai verdict' : 'Shared Evidrai report'}</p>
            <h1>{report.request.claim || 'Untitled claim'}</h1>
            <p className="resultSubcopy">{isSimple ? 'A simple public Evidrai verdict card. Run your own check to inspect the full evidence trail.' : 'Public read-only assessment. Evidence should be inspected, not just forwarded like internet confetti.'}</p>
          </div>
          <div className="verdict verdictPanel">
            <span>Verdict</span>
            <strong>{report.verdict.label}</strong>
            <small>{report.verdict.confidence} confidence</small>
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
        {isSimple ? (
          <section className="resultSection evidenceSourcesSection">
            <h2>Want the evidence trail?</h2>
            <p className="muted">This free share is deliberately lightweight. Use Evidrai to run your own check and inspect sources, scoring, caveats, and claim breakdown.</p>
            <a className="button secondary printHidden" href="/">Verify this yourself</a>
          </section>
        ) : (
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
        )}
        <p className="printFooter">Shared report URL: {publicUrl}</p>
      </section>
    </main>
  );
}
