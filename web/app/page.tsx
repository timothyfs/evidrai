'use client';

import type { CSSProperties, FormEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AccountProfile,
  AssessmentResponse,
  AssessmentSource,
  FeedbackRating,
  MeResponse,
  ReportSummary,
  SpeechCheckedClaim,
  SpeechClaim,
  SpeechExtractionResult,
  SpeechVerificationResult,
  createAssessmentJob,
  createReportShare,
  deleteReport,
  extractSpeechClaims,
  getMe,
  getAuthDiagnostics,
  getAccountProfile,
  listReports,
  getAnonymousAccountProfile,
  getReport,
  getAssessmentJob,
  setAccessToken,
  setAccountProfile,
  submitFeedback,
  updateReportMetadata,
  verifySpeechClaims,
} from '../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, profileFromSession, sendPasswordReset, signInWithEmailPassword, signInWithGoogle, signOut, signUpWithEmailPassword, updatePassword } from '../lib/auth';

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

type ThemeMode = 'dark' | 'light';

const PENDING_ASSESSMENT_JOB_KEY = 'evidrai_pending_assessment_job';
const RECENT_REPORTS_KEY = 'evidrai_recent_reports';

function scopedStorageKey(base: string, ownerId?: string | null) {
  const safeOwner = (ownerId || '').trim();
  return safeOwner ? `${base}:${safeOwner}` : '';
}

function readCachedReports(ownerId?: string | null): ReportSummary[] {
  if (typeof window === 'undefined') return [];
  const key = scopedStorageKey(RECENT_REPORTS_KEY, ownerId);
  if (!key) return [];
  try {
    const saved = window.localStorage.getItem(key);
    if (!saved) return [];
    const parsed = JSON.parse(saved);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && item.owner_id === ownerId) as ReportSummary[];
  } catch (err) {
    console.warn(err);
    return [];
  }
}

function writeCachedReports(ownerId: string | undefined | null, reports: ReportSummary[]) {
  if (typeof window === 'undefined') return;
  const key = scopedStorageKey(RECENT_REPORTS_KEY, ownerId);
  if (!key) return;
  const scoped = reports.filter((item) => item.owner_id === ownerId);
  window.localStorage.setItem(key, JSON.stringify(scoped));
}

function pendingJobStorageKey(ownerId?: string | null) {
  return scopedStorageKey(PENDING_ASSESSMENT_JOB_KEY, ownerId);
}
const REPORT_LABELS = [
  ['favourite', 'Favourite'],
  ['reviewed', 'Reviewed'],
  ['customer-facing', 'Customer-facing'],
  ['internal-only', 'Internal-only'],
  ['useful', 'Useful'],
  ['not-useful', 'Not useful'],
  ['needs-follow-up', 'Needs follow-up'],
] as const;
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || '';

function applyTheme(theme: ThemeMode) {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.theme = theme;
  window.localStorage.setItem('evidrai_theme', theme);
}

function isYouTubeUrl(value: string) {
  const text = value.toLowerCase();
  return text.includes('youtube.com') || text.includes('youtu.be');
}

function formatDate(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function sourceHref(source: { url?: string }) {
  return source.url || '';
}

function hostnameFromUrl(value?: string) {
  if (!value) return '';
  try {
    return new URL(value).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

function sourceDisplayName(source: AssessmentSource) {
  const host = (source.domain || hostnameFromUrl(source.url)).replace(/^www\./, '').toLowerCase();
  if (host.includes('theguardian.com')) return 'The Guardian';
  if (host.includes('lemonde.fr')) return 'Le Monde';
  if (host.includes('bbc.co.uk') || host.includes('bbc.com')) return 'bbc.co.uk';
  if (host) return host;
  return source.title || 'Unknown source';
}

function sourceDisplayLabel(index: number, source: AssessmentSource) {
  return `Source ${index + 1} · ${sourceDisplayName(source)}`;
}

function sourcePosition(assessment: AssessmentResponse, source: AssessmentSource) {
  const sources = assessment.sources || [];
  return Math.max(0, sources.findIndex((candidate) => (
    candidate === source ||
    (candidate.id && candidate.id === source.id) ||
    (candidate.url && candidate.url === source.url) ||
    (candidate.domain && candidate.domain === source.domain && candidate.title === source.title)
  )));
}

function confidencePercent(confidence?: string | null, fallbackScore?: number | null) {
  const text = (confidence || '').toLowerCase();
  if (text.includes('high')) return 86;
  if (text.includes('medium')) return 62;
  if (text.includes('low')) return 34;
  if (typeof fallbackScore === 'number' && Number.isFinite(fallbackScore)) return Math.max(8, Math.min(100, Math.round(fallbackScore * 10)));
  return 50;
}

function numericScore(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function normaliseScore(score?: number | null, max = 5) {
  if (typeof score !== 'number' || !Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(1, score / max));
}

function scoreTone(score?: number | null, max = 5) {
  const pct = normaliseScore(score, max);
  if (pct >= 0.85) return 'good';
  if (pct >= 0.65) return 'solid';
  if (pct >= 0.45) return 'mixed';
  if (pct >= 0.25) return 'weak';
  return 'bad';
}

function sourceQualityLabel(score?: number | null) {
  if (typeof score !== 'number' || !Number.isFinite(score)) return 'Unscored';
  if (score >= 4.5) return 'Very strong';
  if (score >= 3.75) return 'Strong';
  if (score >= 2.75) return 'Useful / mixed';
  if (score >= 1.75) return 'Weak';
  return 'Poor / indirect';
}

function stanceTone(stance?: string) {
  const value = (stance || '').toLowerCase();
  if (value.includes('support')) return 'good';
  if (value.includes('contradict')) return 'bad';
  if (value.includes('mixed')) return 'mixed';
  if (value.includes('context')) return 'context';
  return 'weak';
}

function sourceGroup(source: AssessmentSource) {
  const stance = (source.stance || source.evidence_category || source.source_role || '').toLowerCase();
  if (stance.includes('support') || stance.includes('corrobor')) return 'Corroborating';
  if (stance.includes('contradict') || stance.includes('refut') || stance.includes('against')) return 'Contradicting';
  if (stance.includes('context') || stance.includes('background')) return 'Context';
  return 'Relevant';
}

function groupSources(sources: AssessmentSource[]) {
  const groups = new Map<string, AssessmentSource[]>();
  sources.forEach((source) => {
    const group = sourceGroup(source);
    groups.set(group, [...(groups.get(group) || []), source]);
  });
  const order = ['Corroborating', 'Contradicting', 'Context', 'Relevant'];
  return order.filter((group) => groups.has(group)).map((group) => ({ group, sources: groups.get(group) || [] }));
}

function sourceStats(sources: AssessmentSource[]) {
  return groupSources(sources).map(({ group, sources: grouped }) => `${group}: ${grouped.length}`);
}

function sourceId(source: AssessmentSource, index: number) {
  return source.id || `src_${index + 1}`;
}

function sourceIndex(assessment: AssessmentResponse) {
  return new Map((assessment.sources || []).map((source, index) => [sourceId(source, index), source]));
}

function citedSourceIds(assessment: AssessmentResponse) {
  const ids = new Set<string>();
  assessment.claim_breakdown?.forEach((item) => {
    item.supporting_source_ids?.forEach((id) => ids.add(id));
    item.contradicting_source_ids?.forEach((id) => ids.add(id));
  });
  Object.values(assessment.evidence_map || {}).forEach((value) => {
    if (Array.isArray(value)) value.forEach((id) => typeof id === 'string' && ids.add(id));
  });
  return ids;
}

function evidenceStrengthLabel(score?: number | null, verdict?: string) {
  if (typeof score !== 'number' || !Number.isFinite(score)) return '';
  const magnitude = Math.abs(score);
  const contradicted = (verdict || '').toLowerCase().includes('contradict') || score < 0;
  if (contradicted) {
    if (magnitude >= 8) return 'Strong contradiction found';
    if (magnitude >= 5.5) return 'Moderate contradiction found';
    if (magnitude >= 3) return 'Limited contradiction found';
    return 'Weak contradiction signal';
  }
  if (magnitude >= 8) return 'Strong evidence base';
  if (magnitude >= 5.5) return 'Moderate evidence base';
  if (magnitude >= 3) return 'Limited evidence base';
  return 'Weak evidence base';
}

function reasoningEntries(reasoning: Record<string, unknown>) {
  return Object.entries(reasoning).filter(([, value]) => value !== null && value !== undefined && value !== '');
}

function formatReasoningValue(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)).join('\n');
  if (typeof value === 'object' && value) return JSON.stringify(value, null, 2);
  return String(value);
}

function FactorMeter({ label, value, max = 5, toneValue }: { label: string; value?: unknown; max?: number; toneValue?: unknown }) {
  const parsed = numericScore(value);
  const display = parsed === null ? null : Math.max(0, Math.min(max, parsed));
  const pct = display === null ? 0 : normaliseScore(display, max) * 100;
  const parsedTone = numericScore(toneValue);
  const toneSource = parsedTone === null ? display : parsedTone;
  return (
    <div className={`factorMeter ${display === null ? 'missing' : ''}`}>
      <div className="factorMeterLabel"><span>{label}</span><strong>{display === null ? 'Not captured' : `${display.toFixed(1)}/${max}`}</strong></div>
      <div className="factorMeterTrack" aria-label={display === null ? `${label}: not captured` : `${label}: ${display.toFixed(1)} out of ${max}`}><span className={display === null ? 'missing' : scoreTone(toneSource, max)} style={{ width: display === null ? '0%' : `${Math.max(4, pct)}%` }} /></div>
    </div>
  );
}

function ScoreOrb({ score, max = 5, label = 'Source score' }: { score?: number | null; max?: number; label?: string }) {
  const value = typeof score === 'number' && Number.isFinite(score) ? score : 0;
  const pct = normaliseScore(value, max);
  const degrees = Math.round(pct * 360);
  return (
    <div className={`scoreOrb ${scoreTone(value, max)}`} style={{ '--score-deg': `${degrees}deg` } as CSSProperties} aria-label={`${label}: ${value.toFixed(1)} out of ${max}`}>
      <strong>{value.toFixed(1)}</strong>
      <span>/{max}</span>
    </div>
  );
}

function EvidenceScorePanel({ assessment }: { assessment: AssessmentResponse }) {
  const evidenceScore = assessment.verdict.evidence_strength_score ?? null;
  if (typeof evidenceScore !== 'number' || !Number.isFinite(evidenceScore)) {
    return (
      <section className="scoreConstellation scoreConstellationMissing" aria-label="Evidence scoring missing">
        <div className="scoreConstellationHeader">
          <div>
            <p className="eyebrow">Evidence scorecard</p>
            <h3>Evidence score not calculated</h3>
          </div>
          <span>Diagnostic</span>
        </div>
        <p className="muted">Detail mode should produce an evidence strength score. This report is missing that value, so the scoring panel cannot be rendered.</p>
      </section>
    );
  }

  const sources = assessment.sources || [];
  const averageScore = sources.length ? sources.reduce((sum, source) => sum + Number(source.score || 0), 0) / sources.length : 0;
  const primaryCount = sources.filter((source) => (source.source_type || '').toLowerCase().includes('primary')).length;
  const contradictionCount = sources.filter((source) => sourceGroup(source) === 'Contradicting').length;
  const supportCount = sources.filter((source) => sourceGroup(source) === 'Corroborating').length;
  const displayEvidenceScore = Math.abs(evidenceScore);
  const contradicted = assessment.verdict.label.toLowerCase().includes('contradict') || evidenceScore < 0;
  const confidence = confidencePercent(assessment.verdict.confidence, displayEvidenceScore);
  return (
    <section className="scoreConstellation" aria-label="Evidence scoring overview">
      <div className="scoreConstellationHeader">
        <div>
          <p className="eyebrow">Evidence scorecard</p>
          <h3>{contradicted ? 'How strong is the contradiction?' : 'How strong is the evidence?'}</h3>
        </div>
        <span>Source-weighted, not volume-weighted</span>
      </div>
      <div className="scoreConstellationGrid">
        <article className="scoreHeroTile">
          <div className="scoreRingLarge" style={{ '--score-deg': `${Math.round(normaliseScore(displayEvidenceScore, 10) * 360)}deg` } as CSSProperties}>
            <strong>{typeof displayEvidenceScore === 'number' ? displayEvidenceScore.toFixed(1) : '—'}</strong>
            <span>/10 {contradicted ? 'contradiction' : 'evidence'}</span>
          </div>
          <p>{evidenceStrengthLabel(evidenceScore, assessment.verdict.label) || 'Evidence strength depends on source quality, directness, and contradiction.'}</p>
        </article>
        <div className="scoreMetricGrid">
          <div><span>Confidence</span><strong>{assessment.verdict.confidence || 'Unstated'}</strong><em>{confidence}% signal</em></div>
          <div><span>Avg source quality</span><strong>{averageScore.toFixed(1)}/5</strong><em>{sourceQualityLabel(averageScore)}</em></div>
          <div><span>Primary sources</span><strong>{primaryCount}/{sources.length}</strong><em>Direct evidence share</em></div>
          <div><span>Evidence mix</span><strong>{supportCount} / {contradictionCount}</strong><em>supporting / contradicting</em></div>
        </div>
      </div>
      <details className="scoreMethodDetails">
        <summary><span>Why these scores?</span><small>Open scoring logic</small></summary>
        <p>Evidence strength is directional: it can support a claim or support rejecting it. For contradicted claims, the score is shown as contradiction strength.</p>
        <p>Primary, direct, relevant and independent sources move the score more than repeated coverage or background context. Contradictions reduce confidence in the claim even when it is widely repeated.</p>
      </details>
    </section>
  );
}

function SourceCard({ assessmentId, source, compact = false, displayIndex = 0 }: { assessmentId: string; source: AssessmentSource; compact?: boolean; displayIndex?: number }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [scoringOpen, setScoringOpen] = useState(false);
  const [trustStatus, setTrustStatus] = useState('');
  const [trustBusy, setTrustBusy] = useState('');
  const score = numericScore(source.score) ?? 0;
  const role = source.source_role || source.evidence_category || source.stance || '';
  const factors = source.scoring_factors || {};
  const factorKeys = ['authority', 'relevance', 'directness', 'recency', 'bias_risk', 'independence'];
  const capturedFactorValues = factorKeys.map((key) => numericScore(factors[key])).filter((value): value is number => value !== null);
  const hasCapturedFactors = capturedFactorValues.length > 0 && capturedFactorValues.some((value) => value !== 0);
  const quality = sourceQualityLabel(score);
  const group = sourceGroup(source);
  const displayLabel = sourceDisplayLabel(displayIndex, source);
  const articleTitle = source.title && source.title !== sourceDisplayName(source) ? source.title : '';
  const detail = (
    <>
      <p>{source.summary || source.classification_reason || 'No source summary was returned.'}</p>
      {source.classification_reason && source.summary && <small className="sourceReason">Why this source matters: {source.classification_reason}</small>}
    </>
  );

  async function submitSourceSignal(kind: 'strong' | 'weak' | 'biased' | 'primary') {
    const sourceId = source.id || source.url || source.domain || source.title;
    const config = {
      strong: { label: 'Strong source', rating: 'Useful' as FeedbackRating, signals: ['persuasive_explanation'], persuasive: [sourceId], distrusted: [] as string[], comment: `Source-level signal: strong/persuasive source (${source.title || source.domain || sourceId}).` },
      weak: { label: 'Weak source', rating: 'Partly useful' as FeedbackRating, signals: ['evidence_weak'], persuasive: [] as string[], distrusted: [sourceId], comment: `Source-level signal: weak evidence source (${source.title || source.domain || sourceId}).` },
      biased: { label: 'Biased / unreliable', rating: 'Not useful' as FeedbackRating, signals: ['source_biased', 'source_unreliable'], persuasive: [] as string[], distrusted: [sourceId], comment: `Source-level signal: biased or unreliable source (${source.title || source.domain || sourceId}).` },
      primary: { label: 'Needs primary source', rating: 'Partly useful' as FeedbackRating, signals: ['needs_primary_sourcing'], persuasive: [] as string[], distrusted: [] as string[], comment: `Source-level signal: this evidence trail needs a stronger primary source near ${source.title || source.domain || sourceId}.` },
    }[kind];
    setTrustBusy(kind);
    setTrustStatus('');
    try {
      await submitFeedback({
        assessment_id: assessmentId,
        rating: config.rating,
        reasons: ['Source quality'],
        trust_signals: config.signals,
        persuasive_source_ids: config.persuasive,
        distrusted_source_ids: config.distrusted,
        comment: config.comment,
      });
      setTrustStatus(`Saved: ${config.label}.`);
    } catch (err) {
      setTrustStatus(err instanceof Error ? err.message : 'Could not save source signal.');
    } finally {
      setTrustBusy('');
    }
  }

  return (
    <article className={`source sourceCard scoredSource ${compact ? 'compactSource' : ''}`}>
      <div className="sourceScoreHeader">
        <div className="sourceTopline">
          <span>{source.source_type || 'Source'}</span>
          {role && <strong className={`stanceChip ${stanceTone(source.stance || role)}`}>{role}</strong>}
          <em>{quality}</em>
        </div>
        {score > 0 && <ScoreOrb score={score} />}
      </div>
      {source.url ? (
        <a href={sourceHref(source)} target="_blank" rel="noreferrer" className="sourceTitle" title={source.title || source.url}>{displayLabel}</a>
      ) : (
        <strong className="sourceTitle" title={source.title || undefined}>{displayLabel}</strong>
      )}
      <div className="sourceMetaRow">
        {articleTitle && <span className="sourceArticleTitle">{articleTitle}</span>}
        <span>{group}</span>
        {source.narrative_cluster && <span>Chain: {source.narrative_cluster}</span>}
      </div>
      <div className="sourceTrustActions" aria-label="Source feedback actions">
        <button disabled={Boolean(trustBusy)} onClick={() => submitSourceSignal('strong')} type="button">{trustBusy === 'strong' ? 'Saving…' : 'Strong source'}</button>
        <button disabled={Boolean(trustBusy)} onClick={() => submitSourceSignal('weak')} type="button">{trustBusy === 'weak' ? 'Saving…' : 'Weak source'}</button>
        <button disabled={Boolean(trustBusy)} onClick={() => submitSourceSignal('biased')} type="button">{trustBusy === 'biased' ? 'Saving…' : 'Biased / unreliable'}</button>
        <button disabled={Boolean(trustBusy)} onClick={() => submitSourceSignal('primary')} type="button">{trustBusy === 'primary' ? 'Saving…' : 'Needs primary'}</button>
      </div>
      {trustStatus && <p className={trustStatus.startsWith('Could not') ? 'error sourceTrustStatus' : 'success sourceTrustStatus'}>{trustStatus}</p>}
      {compact ? (
        <div className="sourceDetails sourceDisclosure">
          <button aria-expanded={detailsOpen} className="sourceToggle" onClick={() => setDetailsOpen((open) => !open)} type="button">
            <span>Source detail</span><small>{detailsOpen ? 'Hide' : 'Show'}</small>
          </button>
          {detailsOpen && <div className="sourceDisclosureBody">{detail}</div>}
        </div>
      ) : detail}
      <div className="sourceScoringDetails sourceDisclosure">
        <button aria-expanded={scoringOpen} className="sourceToggle" onClick={() => setScoringOpen((open) => !open)} type="button">
          <span>Why this source scored {score > 0 ? `${score.toFixed(1)}/5` : 'this way'}</span><small>{scoringOpen ? 'Hide' : 'Show'}</small>
        </button>
        {scoringOpen && (
          <div className="sourceDisclosureBody">
            <div className="sourceScoringContext">
              <span>{source.source_type || 'Source type unknown'}</span>
              <span>{group}</span>
              {role && <span>{role}</span>}
              {source.domain && <span>{source.domain}</span>}
            </div>
            <div className="factorGrid">
              <FactorMeter label="Source score" value={score} />
              {hasCapturedFactors && (
                <>
                  <FactorMeter label="Authority" value={factors.authority} />
                  <FactorMeter label="Relevance" value={factors.relevance} />
                  <FactorMeter label="Directness" value={factors.directness} />
                  <FactorMeter label="Recency" value={factors.recency} />
                  {'independence' in factors && <FactorMeter label="Independence" value={factors.independence} />}
                  <FactorMeter label="Bias risk" value={factors.bias_risk} toneValue={numericScore(factors.bias_risk) === null ? null : 5 - (numericScore(factors.bias_risk) || 0)} />
                </>
              )}
            </div>
            {!hasCapturedFactors && <p className="muted">This assessment has an overall source score, but did not capture a reliable factor breakdown for authority, relevance, directness, recency, or bias risk. Hiding empty 0.0 factor bars to avoid implying these were measured.</p>}
            {hasCapturedFactors && <p className="sourceScoringNote">Each bar uses the same 0–5 value shown beside it. For bias risk, a longer bar means more risk and the colour worsens as the value rises. The overall source score is the weighted contribution used for this claim.</p>}
          </div>
        )}
      </div>
    </article>
  );
}

function CounterEvidencePrompt({ assessment }: { assessment: AssessmentResponse }) {
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!url.trim() && !note.trim()) return;
    setBusy(true);
    setStatus('');
    try {
      await submitFeedback({
        assessment_id: assessment.assessment_id,
        rating: 'Partly useful',
        reasons: ['Missing source'],
        trust_signals: ['has_counter_evidence'],
        accepted_verdict: 'unsure',
        challenge_text: note.trim() || 'Counter-evidence submitted from evidence section.',
        counter_evidence: [{ url: url.trim(), text: note.trim(), relationship: 'counter_evidence' }],
        comment: 'Counter-evidence submitted from evidence section.',
      });
      setStatus('Counter-evidence saved. This will feed the trust review trail.');
      setUrl('');
      setNote('');
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not save counter-evidence.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="counterEvidencePrompt" onSubmit={submit}>
      <div>
        <strong>Got a stronger source?</strong>
        <p className="muted">Drop a primary source, contradiction, or useful context. This builds the counter-evidence trail.</p>
      </div>
      <div className="formRow">
        <label>URL<input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/primary-source" /></label>
        <label>Why it matters<input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Short note or excerpt" /></label>
      </div>
      <button disabled={busy || (!url.trim() && !note.trim())} type="submit">{busy ? 'Saving…' : 'Submit counter-evidence'}</button>
      {status && <p className={status.startsWith('Could not') ? 'error' : 'success'}>{status}</p>}
    </form>
  );
}

function SourceReferences({ assessment, ids }: { assessment: AssessmentResponse; ids: string[] }) {
  const byId = sourceIndex(assessment);
  if (!ids.length) return null;
  return (
    <div className="miniEvidenceMap">
      {ids.map((id) => {
        const source = byId.get(id);
        if (!source) return <span className="missingSourceRef" key={id}>Source reference missing details</span>;
        const label = sourceDisplayLabel(sourcePosition(assessment, source), source);
        return source.url ? (
          <a href={sourceHref(source)} key={id} rel="noreferrer" target="_blank" title={source.title || source.url}>{label}</a>
        ) : (
          <span key={id} title={source.title || undefined}>{label}</span>
        );
      })}
    </div>
  );
}

function SourceLinkPreview({ assessment }: { assessment: AssessmentResponse }) {
  const sources = assessment.sources || [];
  if (!sources.length) return <p className="muted">No source links were supplied for this assessment.</p>;
  return (
    <section className="suppliedSourcePreview" aria-label="Supplied source links">
      <div className="suppliedSourcePreviewHeader">
        <strong>Supplied sources</strong>
        <span>{sources.length} link{sources.length === 1 ? '' : 's'} returned</span>
      </div>
      <div className="miniEvidenceMap suppliedSourceLinks">
        {sources.map((source, index) => {
          const id = sourceId(source, index);
          const label = sourceDisplayLabel(index, source);
          return source.url ? (
            <a href={sourceHref(source)} key={`${id}-${source.url || index}`} rel="noreferrer" target="_blank" title={source.title || source.url}>{label}</a>
          ) : (
            <span className="missingSourceRef" key={`${id}-${index}`} title={source.title || undefined}>{label} · no URL supplied</span>
          );
        })}
      </div>
    </section>
  );
}

function SourceList({ assessment }: { assessment: AssessmentResponse }) {
  if (!assessment.sources?.length) return <p className="muted">No sources returned for this assessment.</p>;
  const citedIds = citedSourceIds(assessment);
  const pinned = assessment.sources.filter((source, index) => citedIds.has(sourceId(source, index)));
  const visible = [...pinned, ...assessment.sources].filter((source, index, all) => {
    const id = source.id || source.url || source.domain || source.title || String(index);
    return all.findIndex((candidate) => (candidate.id || candidate.url || candidate.domain || candidate.title) === id) === index;
  }).slice(0, Math.max(10, pinned.length));
  return (
    <div className="evidenceGroups">
      <CounterEvidencePrompt assessment={assessment} />
      {groupSources(visible).map(({ group, sources }) => (
        <section className="evidenceGroup" key={group}>
          <div className="evidenceGroupHeader">
            <h3>{group}</h3>
            <span>{sources.length} supplied source{sources.length === 1 ? '' : 's'}</span>
          </div>
          <div className="sourceGrid">
            {sources.map((source, index) => <SourceCard assessmentId={assessment.assessment_id} source={source} compact displayIndex={sourcePosition(assessment, source)} key={`${source.id || source.url}-${index}`} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

const feedbackReasons = [
  'Verdict clarity',
  'Confidence explanation',
  'Source quality',
  'Missing source',
  'Too much detail',
  'Not enough detail',
  'Visual presentation',
  'Other',
];

const trustSignalOptions = [
  ['evidence_weak', 'This evidence was weak'],
  ['source_biased', 'This source felt biased'],
  ['changed_view', 'This changed my view'],
  ['needs_primary_sourcing', 'This needs stronger primary sourcing'],
  ['balanced_explanation', 'This explanation felt balanced'],
  ['manipulative_wording', 'This wording felt emotionally manipulative'],
  ['overconfident', 'This feels overconfident'],
  ['too_uncertain', 'This feels too uncertain'],
  ['missed_context', 'This missed important context'],
  ['has_counter_evidence', 'I have counter-evidence'],
  ['source_unreliable', 'This source seems unreliable'],
  ['persuasive_explanation', 'This explanation was persuasive'],
] as const;

function FeedbackControls({ assessment }: { assessment: AssessmentResponse }) {
  const [rating, setRating] = useState<FeedbackRating>('Useful');
  const [reasons, setReasons] = useState<string[]>([]);
  const [trustSignals, setTrustSignals] = useState<string[]>([]);
  const [acceptedVerdict, setAcceptedVerdict] = useState<'accepted' | 'rejected' | 'unsure' | ''>('');
  const [challengeText, setChallengeText] = useState('');
  const [counterEvidenceUrl, setCounterEvidenceUrl] = useState('');
  const [counterEvidenceText, setCounterEvidenceText] = useState('');
  const [comment, setComment] = useState('');
  const [status, setStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function toggleReason(reason: string) {
    setReasons((current) => current.includes(reason) ? current.filter((item) => item !== reason) : [...current, reason]);
  }

  function toggleTrustSignal(signal: string) {
    setTrustSignals((current) => current.includes(signal) ? current.filter((item) => item !== signal) : [...current, signal]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setStatus('');
    try {
      const counterEvidence = counterEvidenceUrl.trim() || counterEvidenceText.trim() ? [{ url: counterEvidenceUrl.trim(), text: counterEvidenceText.trim() }] : [];
      const response = await submitFeedback({
        assessment_id: assessment.assessment_id,
        rating,
        reasons,
        trust_signals: trustSignals,
        accepted_verdict: acceptedVerdict,
        challenge_text: challengeText,
        counter_evidence: counterEvidence,
        comment,
      });
      setStatus(response.ok ? `Trust feedback saved. Thank you. ID: ${response.feedback_id}` : 'Feedback submitted, but response was unexpected.');
      setComment('');
      setReasons([]);
      setTrustSignals([]);
      setAcceptedVerdict('');
      setChallengeText('');
      setCounterEvidenceUrl('');
      setCounterEvidenceText('');
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not save feedback.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="feedbackBox">
      <h3>Trust feedback</h3>
      <p className="muted">Your feedback is linked to this exact assessment and becomes structured trust intelligence for improving evidence ranking, caveats, confidence, and source evaluation.</p>
      <form onSubmit={submit}>
        <div className="segmented" role="radiogroup" aria-label="Feedback rating">
          {(['Useful', 'Partly useful', 'Not useful'] as FeedbackRating[]).map((item) => (
            <button
              className={rating === item ? 'active' : ''}
              key={item}
              onClick={() => setRating(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
        <div className="feedbackSubsection">
          <strong>Did this change your view?</strong>
          <div className="segmented" role="radiogroup" aria-label="Verdict acceptance">
            <button className={acceptedVerdict === 'accepted' ? 'active' : ''} onClick={() => setAcceptedVerdict(acceptedVerdict === 'accepted' ? '' : 'accepted')} type="button">Yes</button>
            <button className={acceptedVerdict === 'rejected' ? 'active' : ''} onClick={() => setAcceptedVerdict(acceptedVerdict === 'rejected' ? '' : 'rejected')} type="button">No</button>
            <button className={acceptedVerdict === 'unsure' ? 'active' : ''} onClick={() => setAcceptedVerdict(acceptedVerdict === 'unsure' ? '' : 'unsure')} type="button">Still unsure</button>
          </div>
        </div>
        <div className="feedbackSubsection">
          <strong>Structured trust signals</strong>
          <div className="reasonGrid trustSignalGrid">
            {trustSignalOptions.map(([signal, label]) => (
              <label className="checkPill" key={signal}>
                <input checked={trustSignals.includes(signal)} onChange={() => toggleTrustSignal(signal)} type="checkbox" />
                {label}
              </label>
            ))}
          </div>
        </div>
        <div className="feedbackSubsection">
          <strong>General feedback tags</strong>
          <div className="reasonGrid">
            {feedbackReasons.map((reason) => (
              <label className="checkPill" key={reason}>
                <input checked={reasons.includes(reason)} onChange={() => toggleReason(reason)} type="checkbox" />
                {reason}
              </label>
            ))}
          </div>
        </div>
        <label>
          Challenge or missing context
          <textarea className="commentBox" value={challengeText} onChange={(event) => setChallengeText(event.target.value)} placeholder="What did Evidrai miss, overstate, understate, or frame poorly?" />
        </label>
        <div className="formRow">
          <label>
            Counter-evidence URL
            <input value={counterEvidenceUrl} onChange={(event) => setCounterEvidenceUrl(event.target.value)} placeholder="https://example.com/primary-source" />
          </label>
          <label>
            Counter-evidence note
            <input value={counterEvidenceText} onChange={(event) => setCounterEvidenceText(event.target.value)} placeholder="Short excerpt or why it matters" />
          </label>
        </div>
        <label>
          Optional comment
          <textarea className="commentBox" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Anything else useful, confusing, missing, or wrong?" />
        </label>
        <button disabled={submitting} type="submit">{submitting ? 'Saving trust feedback…' : 'Send trust feedback'}</button>
      </form>
      {status && <p className={status.startsWith('Could not') ? 'error' : 'success'}>{status}</p>}
    </section>
  );
}

function checkedClaimVerdict(claim: SpeechCheckedClaim) {
  return claim.verified_verdict || claim.verdict || claim.pendulum_band || 'Unverified';
}

function SpeechResult({
  extraction,
  selectedClaims,
  setSelectedClaims,
  verification,
  verifying,
  onVerify,
}: {
  extraction: SpeechExtractionResult;
  selectedClaims: string[];
  setSelectedClaims: (claims: string[]) => void;
  verification: SpeechVerificationResult | null;
  verifying: boolean;
  onVerify: () => void;
}) {
  function toggleClaim(id: string) {
    setSelectedClaims(selectedClaims.includes(id) ? selectedClaims.filter((item) => item !== id) : [...selectedClaims, id]);
  }

  return (
    <section className="card resultCard">
      <div className="resultHeader">
        <div>
          <p className="eyebrow">Stage 1 complete · claim extraction</p>
          <h2>{extraction.title || 'Extracted claims'}</h2>
          <p className="resultSubcopy">Evidrai found checkable claims in the transcript. Select the ones that matter, then verify those claims against grouped evidence.</p>
        </div>
        <div className="verdict weak">
          <strong>{extraction.claims.length} claims</strong>
          <span>{selectedClaims.length} selected</span>
        </div>
      </div>

      {extraction.summary && <p className="summary">{extraction.summary}</p>}
      <div className="facts">
        {extraction.speaker && <span>Speaker: {extraction.speaker}</span>}
        <span>Transcript used: {extraction.transcript_chars_used}/{extraction.transcript_chars_original} chars</span>
        {extraction.transcript_truncated && <span>Transcript truncated for token control</span>}
      </div>
      {extraction.extraction_notes?.length > 0 && <p className="caveat">{extraction.extraction_notes.join(' ')}</p>}

      <div className="selectionGuide">
        <strong>Choose claims to verify</strong>
        <p>Prioritise claims that are material, specific, and evidence-checkable. Skip rhetoric, repeated points, or claims that are not central to the audit.</p>
      </div>

      <details open>
        <summary>1. Extracted claims · choose what to verify</summary>
        <div className="claimPickList">
          {extraction.claims.map((claim, index) => (
            <label className="claimPick" key={claim.id || index}>
              <input
                checked={selectedClaims.includes(claim.id)}
                onChange={() => toggleClaim(claim.id)}
                type="checkbox"
              />
              <span>
                <strong>{claim.normalized_claim || claim.quote}</strong>
                <small>{[claim.priority, claim.checkability, claim.topic, claim.timestamp].filter(Boolean).join(' · ')}</small>
                {claim.quote && <em>“{claim.quote}”</em>}
                {claim.why_it_matters && <p>{claim.why_it_matters}</p>}
              </span>
            </label>
          ))}
        </div>
        <button disabled={selectedClaims.length === 0 || verifying} onClick={onVerify} type="button">
          {verifying ? 'Verifying selected claims…' : `Verify ${selectedClaims.length || ''} selected claim${selectedClaims.length === 1 ? '' : 's'}`}
        </button>
      </details>

      {verification && (
        <details open>
          <summary>2. Verified claims · evidence assessment</summary>
          <div className="checkedClaims">
            {verification.claims_checked.map((item, index) => {
              const label = checkedClaimVerdict(item);
              return (
                <article className="checkedClaim" key={`${item.audit_index || index}-${item.speech_claim?.id || index}`}>
                  <div className={`verdict mini ${verdictTone(label)}`}>
                    <strong>{label}</strong>
                    <span>{item.verified_confidence || item.confidence || 'confidence n/a'}</span>
                  </div>
                  <div>
                    <strong>{item.speech_claim?.normalized_claim || item.speech_claim?.quote || `Claim ${index + 1}`}</strong>
                    {item.assessment ? (
                      <div className="embeddedAssessment">
                        <AssessmentResult assessment={item.assessment} />
                      </div>
                    ) : (
                      <>
                        {(item.summary || item.tldr) && <p>{item.summary || item.tldr}</p>}
                        {item.sources?.length ? (
                          <div className="sourceGrid compact">
                            {item.sources.slice(0, 4).map((source, sourceIndex) => (
                              <SourceCard assessmentId={item.assessment_id || `speech-${index}`} source={source} compact displayIndex={sourceIndex} key={`${source.id || source.url}-${sourceIndex}`} />
                            ))}
                          </div>
                        ) : <p className="muted">No sources returned for this checked claim.</p>}
                      </>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </details>
      )}
    </section>
  );
}

function HeroPreview() {
  return (
    <aside className="heroPreview" aria-label="Evidence assessment preview">
      <div className="trustRing"><span></span></div>
      <div className="previewCard">
        <p className="eyebrow">Evidence-based assessment</p>
        <h2>Claim credibility preview</h2>
        <div className="confidenceBar"><span style={{ width: '72%' }} /></div>
        <p className="muted">Confidence reflects the available evidence base. It is not a guarantee of certainty.</p>
        <div className="previewSources">
          <span>3 corroborating sources</span>
          <span>1 context caveat</span>
          <span>Reasoning inspectable</span>
        </div>
      </div>
    </aside>
  );
}

function TrustSignals() {
  return (
    <div className="trustSignals">
      <span>AI-assisted, source-grounded analysis</span>
      <span>Reasoning is inspectable</span>
      <span>Confidence is not certainty</span>
    </div>
  );
}

function TrustLanguageStrip() {
  return (
    <section className="trustLanguageStrip" aria-label="How to read Evidrai results">
      <span><strong>Verdict</strong> Evidence-based, not popularity-based.</span>
      <span><strong>Confidence</strong> A signal of evidence quality, not certainty.</span>
      <span><strong>Sources</strong> Grouped by role: corroborating, contradicting, or context.</span>
      <span><strong>Reasoning</strong> Inspectable so caveats stay visible.</span>
    </section>
  );
}

function ProgressiveTrustJourney() {
  const steps = [
    { label: '1', title: 'Start precise', text: 'Submit one checkable claim so the system can separate evidence from background noise.' },
    { label: '2', title: 'Inspect source roles', text: 'See what supports, contradicts, or only adds context before accepting the verdict.' },
    { label: '3', title: 'Read the caveat', text: 'Confidence is a quality signal, not certainty. The key caveat explains what could still change.' },
    { label: '4', title: 'Share responsibly', text: 'Use the prepared share text so the verdict travels with its uncertainty, not as a naked score.' },
  ];
  return (
    <section className="progressiveTrustJourney" aria-label="Progressive trust journey">
      <div>
        <p className="eyebrow">Progressive trust journey</p>
        <h3>From claim to shareable evidence</h3>
      </div>
      <div className="trustJourneySteps">
        {steps.map((step) => (
          <article key={step.label}>
            <span>{step.label}</span>
            <strong>{step.title}</strong>
            <p>{step.text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function LoadingState({ type }: { type: 'claim' | 'speech' | 'report' | 'speech-verify' }) {
  const [activeStep, setActiveStep] = useState(0);
  const copy = {
    claim: {
      title: 'Checking the claim',
      steps: [
        'Isolating the factual claim',
        'Searching for relevant evidence',
        'Comparing support and contradiction',
        'Scoring confidence and caveats',
        'Preparing verdict and share text',
      ],
    },
    speech: { title: 'Extracting checkable claims', steps: ['Reading transcript', 'Separating claims from rhetoric', 'Ranking by checkability', 'Preparing selection list'] },
    report: { title: 'Loading report', steps: ['Retrieving assessment', 'Restoring evidence trail', 'Preparing verdict and caveats'] },
    'speech-verify': { title: 'Verifying selected claims', steps: ['Checking selected claims', 'Grouping sources by role', 'Preparing claim verdicts and caveats'] },
  }[type];

  useEffect(() => {
    setActiveStep(0);
    const timer = window.setInterval(() => {
      setActiveStep((current) => Math.min(current + 1, copy.steps.length - 1));
    }, type === 'claim' ? 2200 : 1800);
    return () => window.clearInterval(timer);
  }, [copy.steps.length, type]);

  const progress = Math.min(94, Math.round(((activeStep + 1) / copy.steps.length) * 100));

  return (
    <section className="loadingState" aria-live="polite">
      <div className="loadingOrb"><span></span></div>
      <div>
        <p className="eyebrow">Analysis in progress</p>
        <h3>{copy.title}</h3>
        <div className="analysisProgress" aria-label={`Analysis progress: ${progress}%`}>
          <div><span style={{ width: `${progress}%` }} /></div>
          <strong>{progress}%</strong>
        </div>
        <ol className="loadingSteps">
          {copy.steps.map((step, index) => (
            <li className={index < activeStep ? 'done' : index === activeStep ? 'active' : ''} key={step}>
              <span>{index < activeStep ? '✓' : index + 1}</span>
              {step}
            </li>
          ))}
        </ol>
        <p className="loadingHint">Current stage: {copy.steps[activeStep]}. Keep this page open while the check runs.</p>
      </div>
    </section>
  );
}

function useWakeLock(enabled: boolean) {
  useEffect(() => {
    if (!enabled || typeof navigator === 'undefined') return;
    let released = false;
    let sentinel: { release: () => Promise<void>; addEventListener?: (type: string, listener: () => void) => void } | null = null;
    const wakeLock = (navigator as Navigator & { wakeLock?: { request: (type: 'screen') => Promise<{ release: () => Promise<void>; addEventListener?: (type: string, listener: () => void) => void }> } }).wakeLock;

    async function requestLock() {
      if (!wakeLock || released || document.visibilityState !== 'visible') return;
      try {
        sentinel = await wakeLock.request('screen');
        sentinel.addEventListener?.('release', () => {
          sentinel = null;
        });
      } catch {
        // Wake Lock is best-effort. Unsupported browsers still get clearer retry guidance.
      }
    }

    function handleVisibilityChange() {
      if (document.visibilityState === 'visible') requestLock();
    }

    requestLock();
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      released = true;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (sentinel) sentinel.release().catch(() => undefined);
    };
  }, [enabled]);
}

function VerifyGuide({ mode, canUseDeep, canUseSpeech }: { mode: 'claim' | 'speech'; canUseDeep: boolean; canUseSpeech: boolean }) {
  return (
    <aside className="verifyGuide">
      <p className="eyebrow">What happens next</p>
      {mode === 'claim' ? (
        <ul>
          <li>We isolate the checkable factual claim.</li>
          <li>Evidence is grouped by source role, not raw volume.</li>
          <li>You get a verdict, confidence level, caveats, and inspectable reasoning. Confidence is not certainty.</li>
          {!canUseDeep && <li>Deep evidence checks unlock on Pro and Researcher tiers.</li>}
        </ul>
      ) : (
        <ul>
          <li>We extract candidate claims from the transcript first.</li>
          <li>You choose which claims deserve verification.</li>
          <li>Selected claims are checked individually with their own evidence trail.</li>
          {!canUseSpeech && <li>Speech/video audit is available on paid tiers.</li>}
        </ul>
      )}
    </aside>
  );
}

function SpeechAuditExplainer() {
  return (
    <section className="speechExplainer">
      <div>
        <p className="eyebrow">Two-stage audit</p>
        <h3>Extract first. Verify only what matters.</h3>
        <p>Evidrai does not blindly fact-check an entire transcript. It first identifies candidate factual claims, ranks them by checkability and importance, then lets you choose which claims deserve evidence review.</p>
      </div>
      <div className="speechFlowSteps">
        <span><strong>1</strong> Extract checkable claims</span>
        <span><strong>2</strong> Select the claims that matter</span>
        <span><strong>3</strong> Verify selected claims against evidence</span>
      </div>
    </section>
  );
}

const claimStarterExamples = [
  {
    label: 'Viral headline',
    claim: 'Electric vehicles are worse for the climate than petrol cars once battery production is included.',
    hint: 'Good for testing a broad public claim with lots of competing evidence.',
  },
  {
    label: 'Political claim',
    claim: 'The UK spends more on debt interest than on defence.',
    hint: 'Specific, measurable, and likely to need up-to-date public data.',
  },
  {
    label: 'AI rumour',
    claim: 'AI-generated images can always be detected by looking at hands and text.',
    hint: 'Useful for checking an overconfident internet rule of thumb.',
  },
];

const speechStarterExamples = [
  {
    label: 'Speech transcript',
    transcript: 'Paste a speech, interview, podcast, or YouTube transcript here. Evidrai will extract factual claims first, then let you choose which claims to verify.',
    hint: 'Best path: paste transcript text for reliable extraction.',
  },
  {
    label: 'YouTube URL',
    sourceUrl: 'https://www.youtube.com/watch?v=',
    hint: 'Experimental path: add a YouTube URL and Evidrai will try captions first.',
  },
];

function FirstRunGuide({ mode, onUseClaimExample, onUseSpeechExample }: { mode: 'claim' | 'speech'; onUseClaimExample: (claim: string) => void; onUseSpeechExample: (example: { transcript?: string; sourceUrl?: string }) => void }) {
  return (
    <section className="firstRunGuide" aria-label="Getting started">
      <p className="eyebrow">Try this first</p>
      {mode === 'claim' ? (
        <div className="guideSteps">
          <span><strong>1</strong> Paste one clear claim</span>
          <span><strong>2</strong> Choose fast or deep</span>
          <span><strong>3</strong> Inspect verdict, caveats, and sources</span>
        </div>
      ) : (
        <div className="guideSteps">
          <span><strong>1</strong> Paste transcript when possible</span>
          <span><strong>2</strong> Extract candidate claims</span>
          <span><strong>3</strong> Verify only selected claims</span>
        </div>
      )}
      <div className="starterExamples" aria-label="Example inputs">
        {(mode === 'claim' ? claimStarterExamples : speechStarterExamples).map((example) => (
          <button
            className="starterExample"
            key={example.label}
            onClick={() => mode === 'claim' ? onUseClaimExample('claim' in example ? example.claim : '') : onUseSpeechExample({ transcript: 'transcript' in example ? example.transcript : '', sourceUrl: 'sourceUrl' in example ? example.sourceUrl : '' })}
            type="button"
          >
            <strong>{example.label}</strong>
            <span>{example.hint}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function SpeechInputState({ transcript, sourceUrl, tryYouTubeCaptions }: { transcript: string; sourceUrl: string; tryYouTubeCaptions: boolean }) {
  if (transcript.trim()) {
    return <p className="speechState goodState">Transcript pasted. This is the most reliable path for speech/video analysis.</p>;
  }
  if (sourceUrl.trim() && tryYouTubeCaptions) {
    return <p className="speechState mixedState">No transcript pasted. Evidrai will try YouTube captions first, but hosting restrictions can block this. Manual transcript remains the reliable fallback.</p>;
  }
  if (sourceUrl.trim()) {
    return <p className="speechState weakState">URL provided, but automatic captions are off. Paste the transcript above for analysis.</p>;
  }
  return <p className="speechState weakState">Paste a transcript to start. YouTube URL-only extraction is experimental and may be blocked by YouTube.</p>;
}

function TurnstileCheck({ token, setToken, actionLabel = 'continue' }: { token: string; setToken: (value: string) => void; actionLabel?: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || typeof window === 'undefined') return;
    const scriptId = 'cloudflare-turnstile-script';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    const timer = window.setInterval(() => {
      const turnstile = (window as unknown as { turnstile?: { render: (el: HTMLElement, opts: Record<string, unknown>) => string; reset?: (widgetId: string) => void } }).turnstile;
      if (!turnstile || !containerRef.current) return;
      if (!widgetIdRef.current) {
        widgetIdRef.current = turnstile.render(containerRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (value: string) => setToken(value),
          'expired-callback': () => setToken(''),
          'error-callback': () => setToken(''),
        });
      } else if (!token && turnstile.reset) {
        turnstile.reset(widgetIdRef.current);
      }
      window.clearInterval(timer);
    }, 250);
    return () => window.clearInterval(timer);
  }, [setToken, token]);

  if (!TURNSTILE_SITE_KEY) return null;
  return (
    <div className={`botCheck ${token ? 'botCheckComplete' : ''}`}>
      <div ref={containerRef} />
      {!token && <p className="muted">Complete the bot check to {actionLabel}.</p>}
    </div>
  );
}

function LoginGate({
  account,
  authReady,
  email,
  setEmail,
  authMessage,
  authBusy,
  onGoogle,
  password,
  setPassword,
  onEmailPassword,
  onSignUp,
  onPasswordReset,
  botToken,
  setBotToken,
}: {
  account: AccountProfile | null;
  authReady: boolean;
  email: string;
  password: string;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  authMessage: string;
  authBusy: boolean;
  onGoogle: () => void;
  onEmailPassword: (event: FormEvent<HTMLFormElement>) => void;
  onSignUp: () => void;
  onPasswordReset: () => void;
  botToken: string;
  setBotToken: (value: string) => void;
}) {
  return (
    <section className="card loginGate" id="sign-in">
      <p className="eyebrow">Because trust needs evidence</p>
      <h2>Start verifying with Evidrai</h2>
      <p className="muted">Sign in to save assessments, inspect evidence trails, and use the verification tools included in your plan.</p>
      {authReady ? (
        <div className="authActions">
          <button disabled={authBusy} onClick={onGoogle} type="button">Continue with Google</button>
          <form className="emailLogin" onSubmit={onEmailPassword}>
            <label>
              Email
              <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" type="email" />
            </label>
            <label>
              Password
              <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Minimum 6 characters" type="password" />
            </label>
            <TurnstileCheck token={botToken} setToken={setBotToken} actionLabel="create an account" />
            <div className="formRow">
              <button className="secondary" disabled={authBusy || !email.trim() || password.length < 6} type="submit">Sign in</button>
              <button className="secondary" disabled={authBusy || !email.trim() || password.length < 6 || Boolean(TURNSTILE_SITE_KEY && !botToken)} onClick={onSignUp} type="button">Create free account</button>
              <button className="linkButton" disabled={authBusy || !email.trim()} onClick={onPasswordReset} type="button">Set/reset password</button>
            </div>
          </form>
        </div>
      ) : (
        <p className="error">Authentication is not configured for this deployment.</p>
      )}
      {authMessage && <p className="muted">{authMessage}</p>}
      {account?.owner_id?.startsWith('anon_') && <p className="muted">Browser profile ready, but login is required before checks can run.</p>}
    </section>
  );
}

function AccountMenu({ account, me, theme, onToggleTheme, onSignOut, authBusy }: { account: AccountProfile; me: MeResponse | null; theme: ThemeMode; onToggleTheme: () => void; onSignOut: () => void; authBusy: boolean }) {
  const label = account.label || 'Signed in';
  const displayName = label.includes('@') ? label.split('@')[0] : label;
  const planLabel = me?.user?.tier_label || (account.owner_id.startsWith('anon_') ? account.plan : 'Loading plan…');
  return (
    <details className="accountMenu">
      <summary>
        <span>{displayName}</span>
        <strong>{planLabel}</strong>
      </summary>
      <div className="accountMenuPanel">
        <p className="accountProfileLine"><span>Signed in as</span><strong>{label}</strong></p>
        <p><span>Plan</span><strong>{planLabel}</strong></p>
        <p><span>User ID</span><code>{account.owner_id}</code></p>
        {me?.is_admin && <p><span>Admin</span><strong>Enabled</strong></p>}
        {me?.is_admin && <a className="button secondary" href="/admin">Admin UI</a>}
        <button className="secondary" onClick={onToggleTheme} type="button">{theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}</button>
        <button className="secondary" disabled={authBusy} onClick={onSignOut} type="button">Sign out</button>
      </div>
    </details>
  );
}

function SiteHeader({ account, me, signedIn, theme, quickClaim, onQuickClaimChange, onQuickSubmit, quickDisabled, quickLoading, onToggleTheme, onSignOut, authBusy }: { account: AccountProfile | null; me: MeResponse | null; signedIn: boolean; theme: ThemeMode; quickClaim: string; onQuickClaimChange: (value: string) => void; onQuickSubmit: (event: FormEvent<HTMLFormElement>) => void; quickDisabled: boolean; quickLoading: boolean; onToggleTheme: () => void; onSignOut: () => void; authBusy: boolean }) {
  return (
    <header className="siteHeader">
      <div className="headerBrandCluster">
        <a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a>
      </div>
      <details className="navMenu">
        <summary aria-label="Open navigation"><span></span><span></span><span></span></summary>
        <nav>
          <a href="/">Verify</a>
          <a href="/product">Product</a>
          <a href="/plans">Plans</a>
          <a href="/about">About</a>
          <a href="/team">Team</a>
          <a href="/contact">Contact</a>
          {me?.is_admin && <a href="/admin">Admin</a>}
        </nav>
      </details>
      {signedIn ? (
        <form className="headerQuickCheck" onSubmit={onQuickSubmit}>
          <span aria-hidden="true">⌕</span>
          <input value={quickClaim} onChange={(event) => onQuickClaimChange(event.target.value)} placeholder="Quick claim check…" aria-label="Quick claim check" />
          <button disabled={quickDisabled} type="submit">{quickLoading ? 'Checking…' : 'Check'}</button>
        </form>
      ) : (
        <nav className="desktopNav" aria-label="Primary navigation">
          <a href="/">Verify</a>
          <a href="/product">Product</a>
          <a href="/plans">Plans</a>
          <a href="/about">About</a>
          <a href="/team">Team</a>
          <a href="/contact">Contact</a>
          {me?.is_admin && <a href="/admin">Admin</a>}
        </nav>
      )}
      <div className="headerSpacer" />
      {signedIn && account ? <AccountMenu account={account} me={me} theme={theme} onToggleTheme={onToggleTheme} onSignOut={onSignOut} authBusy={authBusy} /> : <a className="button secondary" href="#sign-in">Sign in</a>}
    </header>
  );
}


function truncateShareText(value: string, max = 140) {
  const text = value.replace(/\s+/g, ' ').trim();
  return text.length > max ? `${text.slice(0, max - 1).trim()}…` : text;
}

function shareSubject(assessment: AssessmentResponse) {
  const claim = truncateShareText(assessment.request.claim || 'Evidence report', 96);
  return `Evidrai report: ${claim} — ${assessment.verdict.label}`;
}

function shareAbstract(assessment: AssessmentResponse) {
  const parts = [`Evidrai assessed this claim as ${assessment.verdict.label.toLowerCase()} with ${assessment.verdict.confidence.toLowerCase()} confidence.`];
  if (assessment.verdict.summary) parts.push(truncateShareText(assessment.verdict.summary, 220));
  if (assessment.verdict.key_caveat) parts.push(`Key caveat: ${truncateShareText(assessment.verdict.key_caveat, 180)}`);
  parts.push(`The report reviewed ${assessment.sources?.length || 0} source${(assessment.sources?.length || 0) === 1 ? '' : 's'}.`);
  parts.push('Share caveat: confidence is not certainty; inspect the evidence and caveats before reposting.');
  return parts.join(' ');
}

function shareText(publicUrl: string, assessment: AssessmentResponse) {
  return `${shareSubject(assessment)}\n\n${shareAbstract(assessment)}\n\n${publicUrl}`;
}

function shareUrls(publicUrl: string, assessment: AssessmentResponse) {
  const title = shareSubject(assessment);
  const abstract = shareAbstract(assessment);
  const body = `${abstract}\n\n${publicUrl}`;
  const socialText = `${title}\n\n${abstract}`;
  return [
    { key: 'email', label: 'Email', href: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}` },
    { key: 'linkedin', label: 'LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(publicUrl)}` },
    { key: 'facebook', label: 'Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(publicUrl)}` },
    { key: 'reddit', label: 'Reddit', href: `https://www.reddit.com/submit?url=${encodeURIComponent(publicUrl)}&title=${encodeURIComponent(title)}` },
    { key: 'x', label: 'X', href: `https://twitter.com/intent/tweet?url=${encodeURIComponent(publicUrl)}&text=${encodeURIComponent(socialText)}` },
    { key: 'whatsapp', label: 'WhatsApp', href: `https://wa.me/?text=${encodeURIComponent(`${socialText}\n${publicUrl}`)}` },
  ];
}

function savedReportShareText(publicUrl: string, report: ReportSummary) {
  const claim = truncateShareText(report.claim || 'Evidence report', 96);
  const verdict = report.verdict || 'Unverified';
  return `Evidrai report: ${claim} — ${verdict}\n\nEvidrai assessed this saved report as ${verdict.toLowerCase()}. Share caveat: confidence is not certainty; inspect the evidence and caveats before reposting.\n\n${publicUrl}`;
}

function savedReportShareUrls(publicUrl: string, report: ReportSummary) {
  const claim = truncateShareText(report.claim || 'Evidence report', 96);
  const verdict = report.verdict || 'Unverified';
  const title = `Evidrai report: ${claim} — ${verdict}`;
  const abstract = `Evidrai assessed this saved report as ${verdict.toLowerCase()}. Share caveat: confidence is not certainty; inspect the evidence and caveats before reposting.`;
  const body = `${abstract}\n\n${publicUrl}`;
  const socialText = `${title}\n\n${abstract}`;
  return [
    { key: 'email', label: 'Email', href: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}` },
    { key: 'linkedin', label: 'LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(publicUrl)}` },
    { key: 'x', label: 'X', href: `https://twitter.com/intent/tweet?url=${encodeURIComponent(publicUrl)}&text=${encodeURIComponent(socialText)}` },
    { key: 'whatsapp', label: 'WhatsApp', href: `https://wa.me/?text=${encodeURIComponent(`${socialText}\n${publicUrl}`)}` },
  ];
}

function ShareReportControls({ assessment, canShare }: { assessment: AssessmentResponse; canShare: boolean }) {
  const [publicUrl, setPublicUrl] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function createShare(platform = 'copy') {
    setBusy(true);
    setMessage('');
    try {
      const payload = await createReportShare(assessment.assessment_id, platform);
      const url = `${window.location.origin}/share/${payload.token}`;
      setPublicUrl(url);
      let copied = false;
      if (platform === 'copy' && navigator.clipboard) {
        try {
          await navigator.clipboard.writeText(shareText(url, assessment));
          copied = true;
        } catch (copyErr) {
          console.warn('Could not copy share text automatically', copyErr);
        }
      }
      const shareType = payload.access_level === 'full' ? 'Full public report' : 'Simple public share';
      setMessage(copied ? `${shareType} text copied.` : `${shareType} link created. Copy the suggested text or link below.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not create share link');
    } finally {
      setBusy(false);
    }
  }

  const links = publicUrl ? shareUrls(publicUrl, assessment) : [];
  return (
    <section className="sharePanel resultSection">
      <div>
        <p className="eyebrow">Shareable report</p>
        <h3>Share this assessment</h3>
        <p className="muted">Free users can share a simple verdict/summary card. Pro users share the full evidence report.</p>
      </div>
      <div className="shareActions">
        <button className="secondary" disabled={busy} onClick={() => createShare('copy')} type="button">{busy ? 'Creating…' : publicUrl ? 'Copy share text' : 'Create share link'}</button>
        {publicUrl && links.map((link) => <a className="button secondary" href={link.href} key={link.key} rel="noreferrer" target="_blank">{link.label}</a>)}
      </div>
      {publicUrl && <div className="shareTextPreview"><label>Suggested share text<textarea readOnly value={shareText(publicUrl, assessment)} onFocus={(event) => event.currentTarget.select()} /></label></div>}
      {publicUrl && <div className="shareLinkRow"><input readOnly value={publicUrl} onFocus={(event) => event.currentTarget.select()} /><a className="button secondary" href={publicUrl} target="_blank" rel="noreferrer">Open</a></div>}
      {publicUrl && <p className="muted">The copy button now copies the prepared text plus link. Instagram still needs manual paste into a story sticker, caption, bio, or DM.</p>}
      {!canShare && <p className="muted">Free share is intentionally lightweight and branded for discovery. Upgrade to Pro for full evidence-source sharing.</p>}
      {message && <p className={message.toLowerCase().includes('could not') || message.toLowerCase().includes('feature') ? 'error' : 'muted'}>{message}</p>}
    </section>
  );
}

function AssessmentResult({ assessment, canShare = false }: { assessment: AssessmentResponse; canShare?: boolean }) {
  const tone = verdictTone(assessment.verdict.label);
  const confidence = confidencePercent(assessment.verdict.confidence, assessment.verdict.evidence_strength_score);
  const evidenceStrength = evidenceStrengthLabel(assessment.verdict.evidence_strength_score, assessment.verdict.label);
  const stats = sourceStats(assessment.sources || []);
  const reasoning = assessment.reasoning ? reasoningEntries(assessment.reasoning) : [];
  const isFastMode = assessment.mode.toLowerCase() === 'fast';
  return (
    <section className="card resultCard assessmentCard">
      <div className="resultHeader assessmentHeader">
        <div>
          <p className="eyebrow">Evidence-based assessment</p>
          <h2>{assessment.request.claim || 'Untitled claim'}</h2>
          <p className="resultSubcopy">Transparent, source-grounded analysis. Confidence reflects available evidence, not certainty.</p>
        </div>
        <div className={`verdict verdictPanel ${tone}`}>
          <span>Verdict</span>
          <strong>{assessment.verdict.label}</strong>
          <div className="confidenceMeter" aria-label={`${assessment.verdict.confidence} confidence`}><span style={{ width: `${confidence}%` }} /></div>
          <small>{assessment.verdict.confidence} confidence{evidenceStrength ? ` · ${evidenceStrength}` : ''}</small>
        </div>
      </div>

      <div className={`mobileVerdictBar ${tone}`} aria-label="Sticky verdict summary">
        <strong>{assessment.verdict.label}</strong>
        <span>{assessment.verdict.confidence || 'Unstated'} confidence · {assessment.sources?.length || 0} sources</span>
      </div>

      <div className="assessmentSnapshot" aria-label="Assessment summary">
        <div>
          <span>Verdict</span>
          <strong>{assessment.verdict.label}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{assessment.verdict.confidence || 'Unstated'}</strong>
        </div>
        <div>
          <span>Evidence</span>
          <strong>{assessment.sources?.length || 0} sources</strong>
        </div>
        <div>
          <span>Mode</span>
          <strong>{assessment.mode}</strong>
        </div>
      </div>

      {(assessment.verdict.summary || assessment.verdict.key_caveat || typeof assessment.reasoning?.claim_semantics === 'object' || typeof assessment.reasoning?.humour_summary === 'string') && (
        <div className="assessmentNarrative">
          {assessment.verdict.summary && <p className="summary">{assessment.verdict.summary}</p>}
          {typeof assessment.reasoning?.humour_summary === 'string' && assessment.reasoning.humour_summary.trim() && (
            <p className="absurdityCheck"><strong>Absurdity check</strong>{assessment.reasoning.humour_summary}</p>
          )}
          {assessment.verdict.key_caveat && <p className="caveat"><strong>Key caveat</strong>{assessment.verdict.key_caveat}</p>}
          {typeof assessment.reasoning?.claim_semantics === 'object' && assessment.reasoning.claim_semantics && 'precision_note' in assessment.reasoning.claim_semantics && Boolean((assessment.reasoning.claim_semantics as { precision_note?: string }).precision_note) && (
            <p className="caveat"><strong>Language precision</strong>{(assessment.reasoning.claim_semantics as { precision_note?: string }).precision_note}</p>
          )}
        </div>
      )}

      <div className="facts assessmentFacts">
        <span>Assessment ID: {assessment.assessment_id}</span>
        <span>{formatDate(assessment.created_at)}</span>
        {stats.length ? stats.map((item) => <span key={item}>{item}</span>) : <span>No evidence grouping available</span>}
      </div>

      <SourceLinkPreview assessment={assessment} />

      {!isFastMode && <EvidenceScorePanel assessment={assessment} />}

      {assessment.claim_breakdown?.length > 0 && (
        <details className="resultSection">
          <summary><span>Claim breakdown</span><small>Sub-claims, confidence, and rationale</small></summary>
          <div className="breakdown">
            {assessment.claim_breakdown.map((item) => (
              <div key={item.id} className="breakdownItem reasoningItem">
                <div>
                  <strong>{item.text}</strong>
                  <span>{item.dimension} · {item.assessment} · {item.confidence}</span>
                </div>
                {item.rationale && <p>{item.rationale}</p>}
                {(item.supporting_source_ids?.length > 0 || item.contradicting_source_ids?.length > 0) && (
                  <SourceReferences assessment={assessment} ids={[...(item.supporting_source_ids || []), ...(item.contradicting_source_ids || [])]} />
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      <details className="resultSection evidenceSourcesSection">
        <summary><span>Evidence sources</span><small>Grouped source evidence with links</small></summary>
        <SourceList assessment={assessment} />
      </details>

      {reasoning.length > 0 && (
        <details className="resultSection reasoningDetails">
          <summary><span>Inspectable reasoning</span><small>Audit trail behind the verdict</small></summary>
          <div className="reasoningGrid">
            {reasoning.map(([key, value]) => (
              <article className="reasoningBlock" key={key}>
                <strong>{key.replaceAll('_', ' ')}</strong>
                <pre>{formatReasoningValue(value)}</pre>
              </article>
            ))}
          </div>
        </details>
      )}

      <ShareReportControls assessment={assessment} canShare={canShare} />
      <FeedbackControls assessment={assessment} />
    </section>
  );
}

export default function Home() {
  const [toolMode, setToolMode] = useState<'claim' | 'speech'>('claim');
  const [claim, setClaim] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [category, setCategory] = useState('auto-detect');
  const [mode, setMode] = useState<'fast' | 'deep'>('fast');
  const [fastOutputStyle, setFastOutputStyle] = useState<'standard' | 'absurdity_humour'>('standard');
  const [speechTranscript, setSpeechTranscript] = useState('');
  const [speechSourceUrl, setSpeechSourceUrl] = useState('');
  const [tryYouTubeCaptions, setTryYouTubeCaptions] = useState(true);
  const [maxClaims, setMaxClaims] = useState(3);
  const [speechMode, setSpeechMode] = useState<'fast' | 'deep'>('fast');
  const [speechExtraction, setSpeechExtraction] = useState<SpeechExtractionResult | null>(null);
  const [selectedSpeechClaims, setSelectedSpeechClaims] = useState<string[]>([]);
  const [speechVerification, setSpeechVerification] = useState<SpeechVerificationResult | null>(null);
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordRecovery, setPasswordRecovery] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>('dark');
  const [authMessage, setAuthMessage] = useState('');
  const [authDiagnostics, setAuthDiagnostics] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [botToken, setBotToken] = useState('');
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [reportsOpen, setReportsOpen] = useState(false);
  const [reportShareLinks, setReportShareLinks] = useState<Record<string, string>>({});
  const [reportShareMessages, setReportShareMessages] = useState<Record<string, string>>({});
  const [sharingReportId, setSharingReportId] = useState('');
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [reportIdInput, setReportIdInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingKind, setLoadingKind] = useState<'claim' | 'speech' | 'report' | 'speech-verify'>('claim');
  const [verifyingSpeech, setVerifyingSpeech] = useState(false);
  const [error, setError] = useState('');
  useWakeLock(loading || verifyingSpeech);

  const signedIn = Boolean(account?.owner_id && !account.owner_id.startsWith('anon_'));
  const userFeatures = me?.user?.features || {};
  const userLimits = me?.user?.limits || {};
  const canUseDeep = Boolean(userFeatures.deep_claims);
  const canUseSpeech = Boolean(userFeatures.speech_audit);
  const canShareReports = Boolean(userFeatures.share_reports);
  const canLabelReports = me?.user?.tier === 'researcher';
  const botReady = !TURNSTILE_SITE_KEY || Boolean(botToken);
  const ready = useMemo(() => signedIn && botReady && (claim.trim().length > 0 || sourceUrl.trim().length > 0), [signedIn, botReady, claim, sourceUrl]);
  const speechReady = useMemo(() => signedIn && botReady && canUseSpeech && (speechTranscript.trim().length > 0 || (tryYouTubeCaptions && speechSourceUrl.trim().length > 0 && isYouTubeUrl(speechSourceUrl))), [signedIn, botReady, canUseSpeech, speechTranscript, speechSourceUrl, tryYouTubeCaptions]);

  function rememberReport(result: AssessmentResponse) {
    const summary: ReportSummary = {
      assessment_id: result.assessment_id,
      created_at: result.created_at,
      mode: result.mode,
      claim: result.request.claim,
      verdict: result.verdict.label,
      owner_id: result.owner_id,
      protected: false,
      labels: [],
    };
    setReports((current) => {
      const savedLimit = Number(userLimits.saved_reports || 100);
      const next = [summary, ...current.filter((item) => item.assessment_id !== summary.assessment_id)].slice(0, Math.max(savedLimit, current.length, 1));
      writeCachedReports(summary.owner_id || account?.owner_id, next);
      return next;
    });
  }

  async function refreshReports(ownerId = account?.owner_id || '') {
    if (!ownerId || ownerId.startsWith('anon_')) {
      setReports([]);
      return;
    }
    try {
      const serverReports = await listReports();
      const recent = serverReports.filter((item) => item.owner_id === ownerId);
      setReports(recent);
      writeCachedReports(ownerId, recent);
    } catch (err) {
      console.warn('Could not load saved reports', err);
      setReports(readCachedReports(ownerId));
    }
  }

  async function pollAssessmentJob(jobId: string) {
    setLoadingKind('claim');
    setLoading(true);
    setError('');
    try {
      for (;;) {
        const status = await getAssessmentJob(jobId);
        if (status.status === 'completed' && status.assessment) {
          setAssessment(status.assessment);
          setSpeechExtraction(null);
          setSpeechVerification(null);
          rememberReport(status.assessment);
          const key = pendingJobStorageKey(status.assessment.owner_id || account?.owner_id);
          if (key) window.localStorage.removeItem(key);
          refreshReports(status.assessment.owner_id || account?.owner_id || '');
          return;
        }
        if (status.status === 'failed') {
          const key = pendingJobStorageKey(account?.owner_id);
          if (key) window.localStorage.removeItem(key);
          throw new Error(status.error || 'Assessment job failed');
        }
        await new Promise((resolve) => setTimeout(resolve, document.visibilityState === 'visible' ? 2500 : 8000));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load assessment job');
    } finally {
      setLoading(false);
    }
  }

  async function refreshMe() {
    try {
      const payload = await getMe();
      setMe(payload);
      setAuthDiagnostics('');
      if (payload.user) {
        setAccount((current) => current ? { ...current, plan: payload.user.tier_label } : current);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not load user profile';
      setAuthMessage(message);
      try {
        const diagnostics = await getAuthDiagnostics();
        setAuthDiagnostics(JSON.stringify(diagnostics, null, 2));
      } catch (diagnosticErr) {
        setAuthDiagnostics(diagnosticErr instanceof Error ? diagnosticErr.message : 'Auth diagnostics failed');
      }
    }
  }

  useEffect(() => {
    const fallback = getAnonymousAccountProfile();
    setAccount(fallback);
    getCurrentSession()
      .then((session) => {
        setAccessToken(session?.access_token || '');
        const profile = profileFromSession(session, fallback);
        setAccount(profile);
        setAccountProfile(profile);
        if (session) {
          refreshMe();
          setReports(readCachedReports(profile.owner_id));
          refreshReports(profile.owner_id);
          const pendingKey = pendingJobStorageKey(profile.owner_id);
          const pendingJobId = pendingKey ? window.localStorage.getItem(pendingKey) : '';
          if (pendingJobId) pollAssessmentJob(pendingJobId);
        }
      })
      .catch((err) => setAuthMessage(err.message));
    const unsubscribe = onAuthStateChange((session) => {
      const currentFallback = session ? getAccountProfile() : getAnonymousAccountProfile();
      setAccessToken(session?.access_token || '');
      const profile = profileFromSession(session, currentFallback);
      setAccount(profile);
      setAccountProfile(profile);
      setAuthMessage(session ? 'Signed in.' : 'Signed out. Sign in again to use Evidrai.');
      if (session) {
        refreshMe();
        setReports(readCachedReports(profile.owner_id));
        refreshReports(profile.owner_id);
        const pendingKey = pendingJobStorageKey(profile.owner_id);
        const pendingJobId = pendingKey ? window.localStorage.getItem(pendingKey) : '';
        if (pendingJobId) pollAssessmentJob(pendingJobId);
      } else {
        setMe(null);
        setReports([]);
      }
    });
    if (typeof window !== 'undefined' && window.location.href.includes('type=recovery')) setPasswordRecovery(true);
    // Report history and pending jobs are intentionally loaded only after a signed-in
    // account is known. The old unscoped keys caused one browser profile to display
    // another user's cached report list after account switching.
    return unsubscribe;
  }, []);

  async function handleGoogleSignIn() {
    setAuthBusy(true);
    setAuthMessage('');
    try {
      await signInWithGoogle();
    } catch (err) {
      setAuthMessage(err instanceof Error ? err.message : 'Google sign-in failed');
      setAuthBusy(false);
    }
  }

  async function handleEmailPasswordSignIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthMessage('');
    try {
      const session = await signInWithEmailPassword(authEmail.trim(), authPassword);
      setAccessToken(session?.access_token || '');
      const profile = profileFromSession(session, getAnonymousAccountProfile());
      setAccount(profile);
      setAccountProfile(profile);
      setReports([]);
      setAuthMessage('Signed in.');
      await refreshMe();
      await refreshReports(profile.owner_id);
    } catch (err) {
      setAuthMessage(err instanceof Error ? err.message : 'Email sign-in failed');
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleEmailPasswordSignUp() {
    setAuthBusy(true);
    setAuthMessage('');
    try {
      if (TURNSTILE_SITE_KEY && !botToken) throw new Error('Complete the bot check before creating an account.');
      const session = await signUpWithEmailPassword(authEmail.trim(), authPassword);
      setAccessToken(session?.access_token || '');
      const profile = profileFromSession(session, getAnonymousAccountProfile());
      setAccount(profile);
      setAccountProfile(profile);
      setReports([]);
      setAuthMessage(session ? 'Free account created.' : 'Account created. Check your email to confirm before signing in.');
      await refreshMe();
      await refreshReports(profile.owner_id);
    } catch (err) {
      setAuthMessage(err instanceof Error ? err.message : 'Email sign-up failed');
    } finally {
      setAuthBusy(false);
    }
  }


  async function handlePasswordReset() {
    setAuthBusy(true);
    setAuthMessage('');
    try {
      await sendPasswordReset(authEmail.trim());
      setAuthMessage('Password reset email sent. Open the newest email, then set a new password here.');
    } catch (err) {
      setAuthMessage(err instanceof Error ? err.message : 'Password reset failed');
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleUpdatePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthMessage('');
    try {
      await updatePassword(newPassword);
      setPasswordRecovery(false);
      setNewPassword('');
      setAuthMessage('Password updated.');
      await refreshMe();
      await refreshReports(account?.owner_id || '');
    } catch (err) {
      setAuthMessage(err instanceof Error ? err.message : 'Could not update password');
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleSignOut() {
    setAuthBusy(true);
    setAuthMessage('');
    try {
      await signOut();
    } catch (err) {
      setAuthMessage(err instanceof Error ? err.message : 'Sign-out failed');
    } finally {
      setAuthBusy(false);
    }
  }

  function useClaimStarter(claimText: string) {
    setToolMode('claim');
    setClaim(claimText);
    setSourceUrl('');
    setError('');
  }

  function useSpeechStarter(example: { transcript?: string; sourceUrl?: string }) {
    setToolMode('speech');
    setSpeechTranscript(example.transcript || '');
    setSpeechSourceUrl(example.sourceUrl || '');
    setTryYouTubeCaptions(Boolean(example.sourceUrl));
    setSpeechExtraction(null);
    setSpeechVerification(null);
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setLoadingKind('claim');
    setLoading(true);
    setError('');
    try {
      const requestedMode = canUseDeep ? mode : 'fast';
      const requestedStyle = requestedMode === 'fast' ? fastOutputStyle : 'standard';
      const job = await createAssessmentJob({ claim, source_url: sourceUrl, category, mode: requestedMode, output_style: requestedStyle, bot_token: botToken });
      const key = pendingJobStorageKey(account?.owner_id);
      if (key) window.localStorage.setItem(key, job.job_id);
      setBotToken('');
      await pollAssessmentJob(job.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed');
      setLoading(false);
    }
  }

  async function extractSpeech(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!speechReady) return;
    setLoadingKind('speech');
    setLoading(true);
    setError('');
    setAssessment(null);
    setSpeechVerification(null);
    try {
      const result = await extractSpeechClaims({
        transcript: speechTranscript,
        source_url: speechSourceUrl,
        max_claims: Math.min(maxClaims, Number(userLimits.max_speech_claims || maxClaims)),
        try_youtube_captions: tryYouTubeCaptions,
        bot_token: botToken,
      });
      setBotToken('');
      setSpeechExtraction(result);
      setSelectedSpeechClaims(result.claims.map((item) => item.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Speech extraction failed');
    } finally {
      setLoading(false);
    }
  }

  async function verifySelectedSpeechClaims() {
    if (!speechExtraction) return;
    const claims: SpeechClaim[] = speechExtraction.claims.filter((item) => selectedSpeechClaims.includes(item.id));
    if (!claims.length) return;
    setLoadingKind('speech-verify');
    setVerifyingSpeech(true);
    setError('');
    try {
      const result = await verifySpeechClaims({ claims, source_url: speechSourceUrl || speechExtraction.source_url, verification_mode: canUseDeep ? speechMode : 'fast' });
      setBotToken('');
      setSpeechVerification(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Speech verification failed');
    } finally {
      setVerifyingSpeech(false);
    }
  }

  async function loadReport(id: string) {
    setLoadingKind('report');
    setLoading(true);
    setError('');
    try {
      const result = await getReport(id.trim());
      setAssessment(result);
      setSpeechExtraction(null);
      setSpeechVerification(null);
      rememberReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load report');
    } finally {
      setLoading(false);
    }
  }

  function openReportInNewTab(id: string) {
    if (!id || typeof window === 'undefined') return;
    window.open(`/reports/${encodeURIComponent(id)}`, '_blank', 'noopener,noreferrer');
  }

  async function toggleReportProtected(report: ReportSummary) {
    setError('');
    try {
      const payload = await updateReportMetadata(report.assessment_id, { protected: !report.protected });
      setReports((current) => current.map((item) => item.assessment_id === report.assessment_id ? { ...item, protected: Boolean(payload.report.protected) } : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update report');
    }
  }

  async function toggleReportLabel(report: ReportSummary, label: string) {
    setError('');
    const currentLabels = report.labels || [];
    const labels = currentLabels.includes(label) ? currentLabels.filter((item) => item !== label) : [...currentLabels, label];
    try {
      const payload = await updateReportMetadata(report.assessment_id, { labels });
      setReports((current) => current.map((item) => item.assessment_id === report.assessment_id ? { ...item, labels: payload.report.labels || [] } : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update report labels');
    }
  }

  async function shareSavedReport(report: ReportSummary, platform = 'copy') {
    setError('');
    setSharingReportId(report.assessment_id);
    setReportShareMessages((current) => ({ ...current, [report.assessment_id]: '' }));
    try {
      const payload = await createReportShare(report.assessment_id, platform);
      const url = `${window.location.origin}/share/${payload.token}`;
      setReportShareLinks((current) => ({ ...current, [report.assessment_id]: url }));
      let copied = false;
      if (navigator.clipboard) {
        try {
          await navigator.clipboard.writeText(savedReportShareText(url, report));
          copied = true;
        } catch (copyErr) {
          console.warn('Could not copy saved report share text automatically', copyErr);
        }
      }
      const shareType = payload.access_level === 'full' ? 'Full public report' : 'Simple public share';
      setReportShareMessages((current) => ({
        ...current,
        [report.assessment_id]: copied ? `${shareType} text copied.` : `${shareType} link created. Copy the suggested text or link below.`,
      }));
    } catch (err) {
      setReportShareMessages((current) => ({ ...current, [report.assessment_id]: err instanceof Error ? err.message : 'Could not create share link' }));
    } finally {
      setSharingReportId('');
    }
  }

  async function removeReport(report: ReportSummary) {
    if (typeof window !== 'undefined' && !window.confirm('Delete this saved report from your account history?')) return;
    setError('');
    try {
      await deleteReport(report.assessment_id);
      setReports((current) => current.filter((item) => item.assessment_id !== report.assessment_id));
      if (assessment?.assessment_id === report.assessment_id) setAssessment(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete report');
    }
  }

  function toggleTheme() {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      return next;
    });
  }

  return (
    <main>
      <SiteHeader account={account} me={me} signedIn={signedIn} theme={theme} quickClaim={claim} onQuickClaimChange={(value) => { setToolMode('claim'); setClaim(value); }} onQuickSubmit={submit} quickDisabled={!ready || loading} quickLoading={loading && loadingKind === 'claim'} onToggleTheme={toggleTheme} onSignOut={handleSignOut} authBusy={authBusy} />
      <section className={`hero appHero ${signedIn ? 'compactHero' : 'landingHero'}`}>
        <div>
          <p className="eyebrow">Because trust needs evidence</p>
          <h1>Check claims against evidence — not repetition.</h1>
          <p className="lead">Evidrai analyses claims, posts, articles, and videos using source credibility, corroboration, transparency, and AI-assisted evidence review.</p>
          {!signedIn && <TrustSignals />}
        </div>
        {!signedIn && <HeroPreview />}
      </section>

      {authDiagnostics && (
        <section className="card">
          <h2>Auth diagnostics</h2>
          <p className="muted">Safe metadata only. No token or secret is shown.</p>
          <pre>{authDiagnostics}</pre>
        </section>
      )}

      {passwordRecovery && signedIn && (
        <section className="card loginGate">
          <h2>Set a new password</h2>
          <p className="muted">You opened a password reset link. Set your new password, then continue normally.</p>
          <form onSubmit={handleUpdatePassword}>
            <label>New password<input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="Minimum 6 characters" type="password" /></label>
            <button disabled={authBusy || newPassword.length < 6} type="submit">Update password</button>
          </form>
        </section>
      )}

      {!signedIn && (
        <LoginGate
          account={account}
          authReady={authConfigured()}
          email={authEmail}
          password={authPassword}
          setEmail={setAuthEmail}
          setPassword={setAuthPassword}
          authMessage={authMessage}
          authBusy={authBusy}
          onGoogle={handleGoogleSignIn}
          onEmailPassword={handleEmailPasswordSignIn}
          onSignUp={handleEmailPasswordSignUp}
          onPasswordReset={handlePasswordReset}
          botToken={botToken}
          setBotToken={setBotToken}
        />
      )}

      {signedIn && <section className="workspaceIntro"><p>Evidence-based assessment · Sources grouped by role · Confidence is not certainty · Reasoning is inspectable</p></section>}
      {signedIn && <TrustLanguageStrip />}
      {signedIn && !assessment && !speechExtraction && <ProgressiveTrustJourney />}

      {signedIn && <div className="layout">
        <section className="card verifyCard">
          <div className="verifyHeader">
            <div>
              <p className="eyebrow">Verify</p>
              <h2>{toolMode === 'claim' ? 'Assess a claim' : 'Extract claims from speech or video'}</h2>
              <p className="muted">Start with a specific claim or source. Evidrai shows the evidence trail, caveats, and uncertainty — not just a score.</p>
            </div>
            <div className="segmented modeSwitch" role="tablist" aria-label="Audit type">
              <button className={toolMode === 'claim' ? 'active' : ''} onClick={() => setToolMode('claim')} type="button">Claim</button>
              <button className={toolMode === 'speech' ? 'active' : ''} disabled={!canUseSpeech} onClick={() => setToolMode('speech')} type="button">Speech / video</button>
            </div>
          </div>

          {!assessment && !speechExtraction && !loading && <FirstRunGuide mode={toolMode} onUseClaimExample={useClaimStarter} onUseSpeechExample={useSpeechStarter} />}

          {toolMode === 'claim' ? (
            <form className="verifyForm" onSubmit={submit}>
              <div className="primaryInput">
                <label>
                  Claim to assess
                  <textarea value={claim} onChange={(event) => setClaim(event.target.value)} placeholder="Paste a claim, quote, headline, rumour, or factual assertion..." />
                </label>
                <p className="fieldHint">Best results come from one clear, checkable factual claim. If you only have an article URL, add it below.</p>
              </div>
              <div className="secondaryInputs">
                <label>
                  Source URL <span>optional</span>
                  <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://example.com/story" />
                </label>
                <label>
                  Category
                  <select value={category} onChange={(event) => setCategory(event.target.value)}>
                    {['auto-detect', 'politics', 'health', 'science', 'finance', 'history', 'general'].map((item) => <option key={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  Mode
                  <select value={mode} onChange={(event) => setMode(event.target.value as 'fast' | 'deep')}>
                    <option value="fast">Fast assessment</option>
                    <option disabled={!canUseDeep} value="deep">Deep evidence review{canUseDeep ? '' : ' · Pro+'}</option>
                  </select>
                </label>
                <label>
                  Fast style
                  <select disabled={mode !== 'fast'} value={fastOutputStyle} onChange={(event) => setFastOutputStyle(event.target.value as 'standard' | 'absurdity_humour')}>
                    <option value="standard">Standard</option>
                    <option value="absurdity_humour">Absurdity check · experimental</option>
                  </select>
                </label>
              </div>
              <VerifyGuide mode="claim" canUseDeep={canUseDeep} canUseSpeech={canUseSpeech} />
              {(claim.trim() || sourceUrl.trim()) && !botToken && <TurnstileCheck token={botToken} setToken={setBotToken} actionLabel="check this claim" />}
              <button className="primaryAction" disabled={!ready || loading}>{loading && loadingKind === 'claim' ? 'Checking evidence…' : 'Check claim'}</button>
            </form>
          ) : (
            <form className="verifyForm" onSubmit={extractSpeech}>
              <div className="primaryInput">
                <label>
                  Transcript
                  <textarea value={speechTranscript} onChange={(event) => setSpeechTranscript(event.target.value)} placeholder="Paste a speech, interview, podcast transcript, debate excerpt, or video transcript..." />
                </label>
                <p className="fieldHint">Paste a transcript or provide a YouTube URL. Evidrai will extract candidate claims first; verification happens only after you choose the claims worth checking.</p>
              </div>
              <SpeechAuditExplainer />
              <div className="secondaryInputs">
                <label>
                  Video/source URL <span>optional context</span>
                  <input value={speechSourceUrl} onChange={(event) => setSpeechSourceUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." />
                </label>
                <label>
                  Claims to extract
                  <select value={maxClaims} onChange={(event) => setMaxClaims(Number(event.target.value))}>
                    {Array.from({ length: Math.max(1, Math.min(20, Number(userLimits.max_speech_claims || 0))) }, (_, index) => index + 1).map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  Verification mode
                  <select value={speechMode} onChange={(event) => setSpeechMode(event.target.value as 'fast' | 'deep')}>
                    <option value="fast">Fast assessment</option>
                    <option disabled={!canUseDeep} value="deep">Deep evidence review{canUseDeep ? '' : ' · Pro+'}</option>
                  </select>
                </label>
              </div>
              <div className="youtubeFallbackBox">
                <label className="checkPill"><input checked={tryYouTubeCaptions} onChange={(event) => setTryYouTubeCaptions(event.target.checked)} type="checkbox" /> Try automatic YouTube captions when transcript is empty</label>
                <p className="muted">URL-only audits are best-effort. If YouTube blocks caption access, paste the transcript above and run again.</p>
                <SpeechInputState transcript={speechTranscript} sourceUrl={speechSourceUrl} tryYouTubeCaptions={tryYouTubeCaptions} />
              </div>
              <VerifyGuide mode="speech" canUseDeep={canUseDeep} canUseSpeech={canUseSpeech} />
              {(speechTranscript.trim() || speechSourceUrl.trim()) && !speechExtraction && !botToken && <TurnstileCheck token={botToken} setToken={setBotToken} actionLabel="extract claims" />}
              <button className="primaryAction" disabled={!speechReady || loading}>{loading && loadingKind === 'speech' ? 'Extracting claims…' : 'Extract claims'}</button>
              {!speechTranscript.trim() && speechSourceUrl.trim() && tryYouTubeCaptions && <p className="fieldHint">No transcript pasted, so Evidrai will try to extract captions from the URL first.</p>}
              {!speechTranscript.trim() && speechSourceUrl.trim() && !tryYouTubeCaptions && <p className="fieldHint">Paste the transcript above, or enable automatic YouTube captions for a best-effort URL-only attempt.</p>}
              <p className="muted">Your plan allows up to {userLimits.max_speech_claims || 0} claims per audit.</p>
            </form>
          )}
          {(loading || verifyingSpeech) && <LoadingState type={verifyingSpeech ? 'speech-verify' : loadingKind} />}
          {error && <p className="error errorState">{error}</p>}
        </section>

        <details className="card reports" open={reportsOpen} onToggle={(event) => setReportsOpen(event.currentTarget.open)}>
          <summary className="reportsSummary">
            <span>Your reports</span>
            <small className="reportsDesktopCount">{reports.length} saved to your account</small>
            <small className="reportsMobileCount">{reports.length} saved · separate history</small>
          </summary>
          <div className="reportsBody">
            <p className="muted">Reports are saved to your account and mirrored locally as a fallback.</p>
            <form className="loadForm" onSubmit={(event) => { event.preventDefault(); if (reportIdInput.trim()) loadReport(reportIdInput); }}>
              <label>
                Load by report ID
                <input value={reportIdInput} onChange={(event) => setReportIdInput(event.target.value)} placeholder="assessment_id" />
              </label>
              <button className="secondary" type="submit" disabled={!reportIdInput.trim() || loading}>Load report</button>
            </form>
            {reports.length === 0 ? <p className="muted">No saved reports yet. Run a check to start your account history.</p> : reports.map((report) => (
              <article className="reportItem" key={report.assessment_id}>
                <button className="reportMain" onClick={() => openReportInNewTab(report.assessment_id)} type="button">
                  <strong>{report.verdict || 'Unverified'}{report.protected ? ' · protected' : ''}</strong>
                  <span>{report.claim || 'Untitled claim'}</span>
                  <small>{formatDate(report.created_at)} · {report.mode}</small>
                  {canLabelReports && Boolean((report.labels || []).length) && <small>{(report.labels || []).map((label) => REPORT_LABELS.find(([value]) => value === label)?.[1] || label).join(' · ')}</small>}
                </button>
                {canLabelReports && <div className="reportLabels">
                  {REPORT_LABELS.map(([value, label]) => <button className={(report.labels || []).includes(value) ? 'labelPill active' : 'labelPill'} key={value} onClick={() => toggleReportLabel(report, value)} type="button">{label}</button>)}
                </div>}
                <div className="reportActions">
                  <button className="secondary" onClick={() => openReportInNewTab(report.assessment_id)} type="button">View</button>
                  <button className="secondary" onClick={() => loadReport(report.assessment_id)} type="button">Load here</button>
                  <button className="secondary" disabled={sharingReportId === report.assessment_id} onClick={() => shareSavedReport(report)} type="button">{sharingReportId === report.assessment_id ? 'Creating…' : reportShareLinks[report.assessment_id] ? 'Copy share text' : 'Share'}</button>
                  <button className="secondary" onClick={() => toggleReportProtected(report)} type="button">{report.protected ? 'Allow cycling' : 'Do not delete'}</button>
                  <button className="secondary dangerAction" onClick={() => removeReport(report)} type="button">Delete</button>
                </div>
                {reportShareLinks[report.assessment_id] && <div className="savedReportShare">
                  <div className="shareTextPreview compact"><label>Suggested share text<textarea readOnly value={savedReportShareText(reportShareLinks[report.assessment_id], report)} onFocus={(event) => event.currentTarget.select()} /></label></div>
                  <div className="shareLinkRow"><input readOnly value={reportShareLinks[report.assessment_id]} onFocus={(event) => event.currentTarget.select()} /><a className="button secondary" href={reportShareLinks[report.assessment_id]} target="_blank" rel="noreferrer">Open</a></div>
                  <div className="reportActions">{savedReportShareUrls(reportShareLinks[report.assessment_id], report).map((link) => <a className="button secondary" href={link.href} key={link.key} rel="noreferrer" target="_blank">{link.label}</a>)}</div>
                </div>}
                {reportShareMessages[report.assessment_id] && <p className={reportShareMessages[report.assessment_id].toLowerCase().includes('could not') || reportShareMessages[report.assessment_id].toLowerCase().includes('failed') ? 'error' : 'success'}>{reportShareMessages[report.assessment_id]}</p>}
              </article>
            ))}
          </div>
        </details>
      </div>}

      {signedIn && assessment && <AssessmentResult assessment={assessment} canShare={canShareReports} />}
      {signedIn && speechExtraction && (
        <SpeechResult
          extraction={speechExtraction}
          selectedClaims={selectedSpeechClaims}
          setSelectedClaims={setSelectedSpeechClaims}
          verification={speechVerification}
          verifying={verifyingSpeech}
          onVerify={verifySelectedSpeechClaims}
        />
      )}
    </main>
  );
}
