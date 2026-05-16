'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { API_BASE_URL, AssessmentResponse, ReportSummary, RuntimeStatus, createAssessment, getReport, getRuntime } from '../lib/api';

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

function formatDate(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function SourceList({ assessment }: { assessment: AssessmentResponse }) {
  if (!assessment.sources?.length) return <p className="muted">No sources returned for this assessment.</p>;
  return (
    <div className="sourceGrid">
      {assessment.sources.slice(0, 8).map((source) => (
        <article className="source" key={source.id}>
          <div className="sourceMeta">{source.source_type} · {source.stance} · score {Number(source.score || 0).toFixed(1)}</div>
          {source.url ? (
            <a href={source.url} target="_blank" rel="noreferrer" className="sourceTitle">{source.title || source.domain || source.url}</a>
          ) : (
            <strong className="sourceTitle">{source.title || 'Untitled source'}</strong>
          )}
          <p>{source.summary || source.classification_reason || 'No summary available.'}</p>
        </article>
      ))}
    </div>
  );
}

function AssessmentResult({ assessment }: { assessment: AssessmentResponse }) {
  const tone = verdictTone(assessment.verdict.label);
  return (
    <section className="card resultCard">
      <div className="resultHeader">
        <div>
          <p className="eyebrow">Assessment</p>
          <h2>{assessment.request.claim || 'Untitled claim'}</h2>
        </div>
        <div className={`verdict ${tone}`}>
          <strong>{assessment.verdict.label}</strong>
          <span>{assessment.verdict.confidence} confidence</span>
        </div>
      </div>

      {assessment.verdict.summary && <p className="summary">{assessment.verdict.summary}</p>}
      {assessment.verdict.key_caveat && <p className="caveat">Caveat: {assessment.verdict.key_caveat}</p>}

      <div className="facts">
        <span>ID: {assessment.assessment_id}</span>
        <span>Mode: {assessment.mode}</span>
        <span>Created: {formatDate(assessment.created_at)}</span>
      </div>

      {assessment.claim_breakdown?.length > 0 && (
        <details open>
          <summary>Claim breakdown</summary>
          <div className="breakdown">
            {assessment.claim_breakdown.map((item) => (
              <div key={item.id} className="breakdownItem">
                <strong>{item.text}</strong>
                <span>{item.dimension} · {item.assessment} · {item.confidence}</span>
                {item.rationale && <p>{item.rationale}</p>}
              </div>
            ))}
          </div>
        </details>
      )}

      <details open>
        <summary>Evidence sources</summary>
        <SourceList assessment={assessment} />
      </details>
    </section>
  );
}

export default function Home() {
  const [claim, setClaim] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [category, setCategory] = useState('auto-detect');
  const [mode, setMode] = useState<'fast' | 'deep'>('fast');
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [reportIdInput, setReportIdInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const ready = useMemo(() => claim.trim().length > 0 || sourceUrl.trim().length > 0, [claim, sourceUrl]);

  function rememberReport(result: AssessmentResponse) {
    const summary: ReportSummary = {
      assessment_id: result.assessment_id,
      created_at: result.created_at,
      mode: result.mode,
      claim: result.request.claim,
      verdict: result.verdict.label,
    };
    setReports((current) => {
      const next = [summary, ...current.filter((item) => item.assessment_id !== summary.assessment_id)].slice(0, 8);
      window.localStorage.setItem('evidrai_recent_reports', JSON.stringify(next));
      return next;
    });
  }

  useEffect(() => {
    getRuntime().then(setRuntime).catch((err) => setError(err.message));
    try {
      const saved = window.localStorage.getItem('evidrai_recent_reports');
      if (saved) setReports(JSON.parse(saved));
    } catch (err) {
      console.warn(err);
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setLoading(true);
    setError('');
    try {
      const result = await createAssessment({ claim, source_url: sourceUrl, category, mode });
      setAssessment(result);
      rememberReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed');
    } finally {
      setLoading(false);
    }
  }

  async function loadReport(id: string) {
    setLoading(true);
    setError('');
    try {
      const result = await getReport(id.trim());
      setAssessment(result);
      rememberReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load report');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">Evidrai</p>
          <h1>Check claims against evidence, not repetition.</h1>
          <p className="lead">A thin customer-facing frontend backed by the independent Evidrai API.</p>
        </div>
        <div className="statusPanel">
          <span>API: {API_BASE_URL}</span>
          <span>Build: {runtime?.build || 'checking...'}</span>
          <span>Storage: {runtime?.storage_backend || 'checking...'}</span>
          <span>OpenAI: {runtime?.openai_configured ? 'configured' : 'missing'}</span>
        </div>
      </section>

      <div className="layout">
        <section className="card">
          <form onSubmit={submit}>
            <label>
              Claim to assess
              <textarea value={claim} onChange={(event) => setClaim(event.target.value)} placeholder="Paste a claim, quote, headline, rumour, or factual assertion..." />
            </label>
            <label>
              Optional source URL
              <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://example.com/story" />
            </label>
            <div className="formRow">
              <label>
                Category
                <select value={category} onChange={(event) => setCategory(event.target.value)}>
                  {['auto-detect', 'politics', 'health', 'science', 'finance', 'history', 'general'].map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
              <label>
                Mode
                <select value={mode} onChange={(event) => setMode(event.target.value as 'fast' | 'deep')}>
                  <option value="fast">Fast</option>
                  <option value="deep">Deep</option>
                </select>
              </label>
            </div>
            <button disabled={!ready || loading}>{loading ? 'Checking…' : 'Check claim'}</button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>

        <aside className="card reports">
          <div className="sectionHeader">
            <h2>Your reports</h2>
          </div>
          <p className="muted">Reports created or loaded in this browser. Public test/admin reports are hidden.</p>
          <form className="loadForm" onSubmit={(event) => { event.preventDefault(); if (reportIdInput.trim()) loadReport(reportIdInput); }}>
            <label>
              Load by report ID
              <input value={reportIdInput} onChange={(event) => setReportIdInput(event.target.value)} placeholder="assessment_id" />
            </label>
            <button className="secondary" type="submit" disabled={!reportIdInput.trim() || loading}>Load report</button>
          </form>
          {reports.length === 0 ? <p className="muted">No reports in this browser yet. Run a check to start a local history.</p> : reports.slice(0, 8).map((report) => (
            <button className="reportItem" key={report.assessment_id} onClick={() => loadReport(report.assessment_id)} type="button">
              <strong>{report.verdict || 'Unverified'}</strong>
              <span>{report.claim || 'Untitled claim'}</span>
              <small>{formatDate(report.created_at)} · {report.mode}</small>
            </button>
          ))}
        </aside>
      </div>

      {assessment && <AssessmentResult assessment={assessment} />}
    </main>
  );
}
