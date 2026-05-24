import { headers } from 'next/headers';
import { API_BASE_URL, AssessmentResponse } from '../../../lib/api';

async function loadSharedReport(token: string): Promise<AssessmentResponse | null> {
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

function shareLinks(url: string, title: string) {
  return [
    ['Email', `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(url)}`],
    ['LinkedIn', `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`],
    ['Facebook', `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`],
    ['Reddit', `https://www.reddit.com/submit?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`],
    ['X', `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`],
    ['WhatsApp', `https://wa.me/?text=${encodeURIComponent(`${title} ${url}`)}`],
  ];
}

export default async function SharedReportPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const report = await loadSharedReport(token);
  if (!report) {
    return (
      <main>
        <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify</a></nav></header>
        <section className="card marketingPage"><p className="eyebrow">Shared report</p><h1>Report not available.</h1><p className="lead">The share link may be invalid, revoked, or unavailable.</p></section>
      </main>
    );
  }
  const title = `Evidrai report: ${report.verdict.label}`;
  const headerList = await headers();
  const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
  const proto = headerList.get('x-forwarded-proto') || 'https';
  const publicUrl = process.env.NEXT_PUBLIC_WEB_BASE_URL ? `${process.env.NEXT_PUBLIC_WEB_BASE_URL.replace(/\/$/, '')}/share/${token}` : host ? `${proto}://${host}/share/${token}` : `/share/${token}`;
  return (
    <main>
      <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify another claim</a></nav></header>
      <section className="card resultCard assessmentCard publicReport">
        <div className="resultHeader assessmentHeader">
          <div>
            <p className="eyebrow">Shared Evidrai report</p>
            <h1>{report.request.claim || 'Untitled claim'}</h1>
            <p className="resultSubcopy">Public read-only assessment. Evidence should be inspected, not just forwarded like internet confetti.</p>
          </div>
          <div className="verdict verdictPanel">
            <span>Verdict</span>
            <strong>{report.verdict.label}</strong>
            <small>{report.verdict.confidence} confidence</small>
          </div>
        </div>
        <div className="assessmentNarrative">
          {report.verdict.summary && <p className="summary">{report.verdict.summary}</p>}
          {report.verdict.key_caveat && <p className="caveat"><strong>Key caveat</strong>{report.verdict.key_caveat}</p>}
        </div>
        <div className="facts assessmentFacts"><span>Assessment ID: {report.assessment_id}</span><span>{formatDate(report.created_at)}</span><span>{report.mode}</span><span>{report.sources?.length || 0} sources</span></div>
        <section className="sharePanel resultSection">
          <p className="eyebrow">Share</p>
          <div className="shareActions">{shareLinks(publicUrl, title).map(([label, href]) => <a className="button secondary" href={href} key={label} rel="noreferrer" target="_blank">{label}</a>)}</div>
          <p className="muted">For Instagram, copy this page URL and paste it into a story sticker, caption, bio, or DM.</p>
        </section>
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
      </section>
    </main>
  );
}
