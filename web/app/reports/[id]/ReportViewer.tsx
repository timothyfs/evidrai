'use client';

import { useEffect, useState } from 'react';
import type { AssessmentResponse } from '../../../lib/api';
import { createReportShare, getReport, setAccessToken } from '../../../lib/api';
import { getCurrentSession } from '../../../lib/auth';

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

export default function ReportViewer({ reportId }: { reportId: string }) {
  const [report, setReport] = useState<AssessmentResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [shareUrl, setShareUrl] = useState('');

  useEffect(() => {
    let active = true;
    async function load() {
      setBusy(true);
      setError('');
      try {
        const session = await getCurrentSession();
        setAccessToken(session?.access_token || '');
        if (!session?.access_token) throw new Error('Sign in to view this report.');
        const payload = await getReport(reportId);
        if (active) setReport(payload);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load report');
      } finally {
        if (active) setBusy(false);
      }
    }
    load();
    return () => { active = false; };
  }, [reportId]);

  async function shareReport() {
    setError('');
    try {
      const payload = await createReportShare(reportId, 'copy');
      const url = `${window.location.origin}/share/${payload.token}`;
      setShareUrl(url);
      await navigator.clipboard?.writeText(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create share link');
    }
  }

  if (busy) return <section className="card marketingPage"><p className="eyebrow">Report</p><h1>Loading report…</h1></section>;
  if (error || !report) return <section className="card marketingPage"><p className="eyebrow">Report</p><h1>Report not available.</h1><p className="lead">{error || 'This report could not be loaded.'}</p><a className="button secondary" href="/">Back to Evidrai</a></section>;

  return (
    <section className="card resultCard assessmentCard publicReport">
      <div className="resultHeader assessmentHeader">
        <div>
          <p className="eyebrow">Saved Evidrai report</p>
          <h1>{report.request.claim || 'Untitled claim'}</h1>
          <p className="resultSubcopy">Dedicated read-only report view. Share it, print it, or return to the workspace without cluttering the active assessment screen.</p>
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
        <p className="eyebrow">Share / export</p>
        <div className="shareActions">
          <button className="button secondary" onClick={() => window.print()} type="button">Print / Save PDF</button>
          <button className="button secondary" onClick={shareReport} type="button">Create public share link</button>
          <a className="button secondary" href="/">Verify another claim</a>
        </div>
        {shareUrl && <p className="success">Share link copied: <a href={shareUrl} rel="noreferrer" target="_blank">{shareUrl}</a></p>}
      </section>
      <section className="resultSection evidenceSourcesSection">
        <h2>Evidence sources</h2>
        <div className="sourceGrid">
          {(report.sources || []).map((source, index) => (
            <article className="sourceCard" key={source.id || source.url || index}>
              <div className="sourceTopline"><strong>{source.title || source.domain || 'Untitled source'}</strong><span>{source.source_type}</span></div>
              <p>{truncateText(source.summary || source.classification_reason || source.url || '')}</p>
              {source.url && <a href={source.url} rel="noreferrer" target="_blank">Open source</a>}
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
