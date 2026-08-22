'use client';

import type { CSSProperties } from 'react';
import { useEffect, useState } from 'react';
import type { AssessmentResponse, MeResponse } from '../../../lib/api';
import { createReportShare, getMe, getReport, setAccessToken } from '../../../lib/api';
import { getCurrentSession } from '../../../lib/auth';
import { downloadText, evidencePacketJson, fileSafe, journalistBriefMarkdown, reportMarkdown } from './export';

type ShareTarget = {
  title: string;
  text: string;
  url: string;
};

function formatDate(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function truncateText(value: string, max = 180) {
  const text = value.replace(/\s+/g, ' ').trim();
  return text.length > max ? `${text.slice(0, max - 1).trim()}…` : text;
}

function slugify(value: string, fallback: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 72) || fallback;
}

function shareTitle(report: AssessmentResponse) {
  return `Evidrai report: ${truncateText(report.request.claim || 'Evidence report', 96)} — ${report.verdict.label}`;
}

function reportShareText(report: AssessmentResponse) {
  return [
    `Evidrai report: ${truncateText(report.request.claim || 'Evidence report', 120)}`,
    `Verdict: ${report.verdict.label} (${report.verdict.confidence} confidence)`,
    report.verdict.summary ? truncateText(report.verdict.summary, 220) : '',
    `Sources reviewed: ${report.sources?.length || 0}`,
    'Share caveat: confidence is not certainty; inspect the evidence and caveats before reposting.',
  ].filter(Boolean).join('\n\n');
}

function claimShareText(report: AssessmentResponse, claim: NonNullable<AssessmentResponse['claim_breakdown']>[number]) {
  return [
    `Evidrai claim check: ${truncateText(claim.text || 'Claim', 140)}`,
    `Assessment: ${claim.assessment} (${claim.confidence})`,
    claim.rationale ? truncateText(claim.rationale, 220) : '',
    `From broader report: ${truncateText(report.request.claim || 'Evidence report', 120)}`,
  ].filter(Boolean).join('\n\n');
}

function shareChannels(target: ShareTarget) {
  const body = `${target.text}\n\n${target.url}`;
  const socialText = `${target.title}\n\n${target.text}`;
  return [
    { key: 'email', label: 'Email', href: `mailto:?subject=${encodeURIComponent(target.title)}&body=${encodeURIComponent(body)}` },
    { key: 'whatsapp', label: 'WhatsApp', href: `https://wa.me/?text=${encodeURIComponent(`${socialText}\n${target.url}`)}` },
    { key: 'linkedin', label: 'LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(target.url)}` },
    { key: 'x', label: 'X', href: `https://twitter.com/intent/tweet?url=${encodeURIComponent(target.url)}&text=${encodeURIComponent(socialText)}` },
    { key: 'facebook', label: 'Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(target.url)}` },
  ];
}

function scoreLabel(score?: number | null, max = 10) {
  if (typeof score !== 'number' || !Number.isFinite(score)) return '';
  const value = Math.abs(score);
  return `${value.toFixed(1)}/${max}`;
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
  if (label.includes('unverified') || label.includes('reported but unconfirmed')) return withinBucket(10, 32, 18);
  if (label.includes('partly') || label.includes('misleading') || label.includes('mixed')) return withinBucket(44, 62, 52);
  if (label.includes('weakly') || label.includes('weak overall') || label.includes('promising but incomplete')) return withinBucket(24, 42, 30);
  if (label.includes('likely')) return withinBucket(66, 86, 72);
  if (label.includes('supported')) return withinBucket(72, 94, 84);
  return 42;
}

export default function ReportViewer({ reportId }: { reportId: string }) {
  const [report, setReport] = useState<AssessmentResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [shareUrl, setShareUrl] = useState('');
  const [shareTarget, setShareTarget] = useState<ShareTarget | null>(null);
  const [notice, setNotice] = useState('');
  const [me, setMe] = useState<MeResponse | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setBusy(true);
      setError('');
      try {
        const session = await getCurrentSession();
        setAccessToken(session?.access_token || '');
        if (!session?.access_token) throw new Error('Sign in to view this report.');
        const [payload, profile] = await Promise.all([getReport(reportId), getMe().catch(() => null)]);
        if (active) {
          setReport(payload);
          setMe(profile);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load report');
      } finally {
        if (active) setBusy(false);
      }
    }
    load();
    return () => { active = false; };
  }, [reportId]);

  async function ensureShareUrl() {
    if (shareUrl) return shareUrl;
    setError('');
    setNotice('');
    const payload = await createReportShare(reportId, 'copy');
    const url = `${window.location.origin}/share/${payload.token}`;
    setShareUrl(url);
    return url;
  }

  async function openReportShare() {
    if (!report) return;
    try {
      const url = await ensureShareUrl();
      setShareTarget({ title: shareTitle(report), text: reportShareText(report), url });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create share link');
    }
  }

  async function openClaimShare(claim: NonNullable<AssessmentResponse['claim_breakdown']>[number], index: number) {
    if (!report) return;
    try {
      const url = `${await ensureShareUrl()}#${slugify(claim.id || claim.text, `claim-${index + 1}`)}`;
      setShareTarget({
        title: `Evidrai claim check: ${truncateText(claim.text || `Claim ${index + 1}`, 88)}`,
        text: claimShareText(report, claim),
        url,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create claim share');
    }
  }

  async function copyShareText() {
    if (!shareTarget) return;
    await navigator.clipboard?.writeText(`${shareTarget.text}\n\n${shareTarget.url}`);
    setNotice('Share text copied.');
  }

  async function copyExecutiveSummary() {
    if (!report) return;
    const summary = [
      `Evidrai verdict: ${report.verdict.label} (${report.verdict.confidence} confidence)`,
      report.verdict.summary,
      report.verdict.key_caveat ? `Key caveat: ${report.verdict.key_caveat}` : '',
      `Sources reviewed: ${report.sources?.length || 0}`,
    ].filter(Boolean).join('\n\n');
    await navigator.clipboard?.writeText(summary);
    setNotice('Executive summary copied.');
  }

  function downloadMarkdown() {
    if (!report) return;
    if (!canExport) return setNotice('Exports are available on Pro and Researcher / Journalist plans.');
    downloadText(`${fileSafe(report.request.claim)}-full-report.md`, reportMarkdown(report), 'text/markdown;charset=utf-8');
    setNotice('Markdown report downloaded.');
  }

  function downloadJournalistBrief() {
    if (!report) return;
    if (!canExport) return setNotice('Exports are available on Pro and Researcher / Journalist plans.');
    downloadText(`${fileSafe(report.request.claim)}-journalist-brief.md`, journalistBriefMarkdown(report), 'text/markdown;charset=utf-8');
    setNotice('Journalist brief downloaded.');
  }

  function downloadJson() {
    if (!report) return;
    if (!canExport) return setNotice('Exports are available on Pro and Researcher / Journalist plans.');
    downloadText(`${fileSafe(report.request.claim)}-evidence-packet.json`, evidencePacketJson(report), 'application/json;charset=utf-8');
    setNotice('Full evidence packet downloaded.');
  }

  const canExport = Boolean(me?.user?.features?.exports);

  if (busy) return <section className="card marketingPage"><p className="eyebrow">Report</p><h1>Loading report…</h1></section>;
  if (error || !report) return <section className="card marketingPage"><p className="eyebrow">Report</p><h1>Report not available.</h1><p className="lead">{error || 'This report could not be loaded.'}</p><a className="button secondary" href="/">Back to Evidrai</a></section>;

  const tone = verdictTone(report.verdict.label);
  const claimSupport = claimSupportPercent(report.verdict.label, report.verdict.evidence_strength_score);
  const claimSupportAngle = claimSupport * 1.8;

  return (
    <section className="card resultCard assessmentCard publicReport">
      <div className="printMasthead"><strong>Evidrai report</strong><span>{formatDate(report.created_at)}</span></div>
      <div className="resultHeader assessmentHeader">
        <div>
          <p className="eyebrow">Saved Evidrai report</p>
          <h1>{report.request.claim || 'Untitled claim'}</h1>
          <p className="resultSubcopy">Dedicated read-only report view. Share it, print it, or return to the workspace without cluttering the active assessment screen.</p>
          <div className="topReportActions printHidden">
            <button className="button" onClick={openReportShare} type="button">Share full report</button>
          </div>
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
          <small>{report.verdict.confidence} confidence</small>
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
          <span>{report.verdict.confidence || 'Unstated'} confidence · {report.sources?.length || 0} sources</span>
        </div>
      </div>
      <div className="assessmentNarrative">
        {report.verdict.summary && <p className="summary">{report.verdict.summary}</p>}
        {report.verdict.key_caveat && <p className="caveat"><strong>Key caveat</strong>{report.verdict.key_caveat}</p>}
      </div>
      <section className="reportAbstract">
        <div><span>Verdict</span><strong>{report.verdict.label}</strong></div>
        <div><span>Confidence</span><strong>{report.verdict.confidence}</strong></div>
        <div><span>Evidence score</span><strong>{scoreLabel(report.verdict.evidence_strength_score, 10) || 'Not scored'}</strong></div>
        <div><span>Sources</span><strong>{report.sources?.length || 0}</strong></div>
      </section>
      <div className="facts assessmentFacts"><span>Assessment ID: {report.assessment_id}</span><span>{formatDate(report.created_at)}</span><span>{report.mode}</span><span>{report.sources?.length || 0} sources</span></div>
      <section className="sharePanel resultSection">
        <p className="eyebrow">Share / export</p>
        <div className="shareActions">
          <button className="button secondary" onClick={() => window.print()} type="button">Print / Save PDF</button>
          <button className="button secondary" disabled={!canExport} onClick={downloadJournalistBrief} type="button">Export journalist brief</button>
          <button className="button secondary" disabled={!canExport} onClick={downloadMarkdown} type="button">Export full Markdown</button>
          <button className="button secondary" disabled={!canExport} onClick={downloadJson} type="button">Export evidence JSON</button>
          <button className="button secondary" onClick={copyExecutiveSummary} type="button">Copy summary</button>
          <button className="button secondary" onClick={openReportShare} type="button">Share full report</button>
          <a className="button secondary" href="/">Verify another claim</a>
        </div>
        {!canExport && <p className="muted">Exports are available on Pro and Researcher / Journalist plans.</p>}
        {notice && <p className="success">{notice}</p>}
        {shareUrl && <p className="success">Share link copied: <a href={shareUrl} rel="noreferrer" target="_blank">{shareUrl}</a></p>}
      </section>
      {Boolean(report.claim_breakdown?.length) && (
        <section className="resultSection reportBreakdownSection">
          <h2>Claim breakdown</h2>
          <div className="reportBreakdownGrid">
            {report.claim_breakdown.map((item, index) => (
              <article className="reportBreakdownCard" id={slugify(item.id || item.text, `claim-${index + 1}`)} key={item.id || item.text}>
                <div><strong>{item.text}</strong><span>{item.assessment} · {item.confidence}</span></div>
                {item.rationale && <p>{item.rationale}</p>}
                <button className="secondary compactShareButton printHidden" onClick={() => openClaimShare(item, index)} type="button">Share this claim</button>
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
              <div className="sourceTopline"><strong>{source.title || source.domain || 'Untitled source'}</strong><span>{source.source_type || 'source'}</span></div>
              <div className="sourceMetaRow"><span>{source.domain || 'Unknown domain'}</span>{source.stance && <span>{source.stance}</span>}{source.evidence_category && <span>{source.evidence_category}</span>}{scoreLabel(source.score, 5) && <span>Score {scoreLabel(source.score, 5)}</span>}</div>
              <p>{truncateText(source.summary || source.classification_reason || source.url || '', 260)}</p>
              {source.classification_reason && source.summary && <p className="muted">{truncateText(source.classification_reason, 220)}</p>}
              {source.url && <a href={source.url} rel="noreferrer" target="_blank">Open source</a>}
            </article>
          ))}
        </div>
      </section>
      {shareTarget && (
        <div className="shareDialogBackdrop printHidden" role="presentation" onClick={() => setShareTarget(null)}>
          <section className="shareDialog" role="dialog" aria-modal="true" aria-label="Share report" onClick={(event) => event.stopPropagation()}>
            <div className="shareDialogHeader">
              <div>
                <p className="eyebrow">Share</p>
                <h2>{shareTarget.title}</h2>
              </div>
              <button className="secondary" onClick={() => setShareTarget(null)} type="button">Close</button>
            </div>
            <div className="shareActions">
              {shareChannels(shareTarget).map((link) => <a className="button secondary" href={link.href} key={link.key} rel="noreferrer" target="_blank">{link.label}</a>)}
              <button className="button secondary" onClick={copyShareText} type="button">Copy text</button>
            </div>
            <div className="shareTextPreview compact"><label>Suggested share text<textarea readOnly value={shareTarget.text} onFocus={(event) => event.currentTarget.select()} /></label></div>
            <div className="shareLinkRow"><input readOnly value={shareTarget.url} onFocus={(event) => event.currentTarget.select()} /><a className="button secondary" href={shareTarget.url} target="_blank" rel="noreferrer">Open</a></div>
          </section>
        </div>
      )}
      <p className="printFooter">Generated by Evidrai. Assessment ID: {report.assessment_id}</p>
    </section>
  );
}
