'use client';

import type { CSSProperties, FormEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
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
  createAssessment,
  extractSpeechClaims,
  getMe,
  getAuthDiagnostics,
  getAccountProfile,
  listReports,
  getAnonymousAccountProfile,
  getReport,
  setAccessToken,
  setAccountProfile,
  submitFeedback,
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

function confidencePercent(confidence?: string | null, fallbackScore?: number | null) {
  const text = (confidence || '').toLowerCase();
  if (text.includes('high')) return 86;
  if (text.includes('medium')) return 62;
  if (text.includes('low')) return 34;
  if (typeof fallbackScore === 'number' && Number.isFinite(fallbackScore)) return Math.max(8, Math.min(100, Math.round(fallbackScore * 10)));
  return 50;
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

function FactorMeter({ label, value, max = 5, invert = false }: { label: string; value?: number | null; max?: number; invert?: boolean }) {
  const raw = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  const display = Math.max(0, Math.min(max, raw));
  const pct = invert ? (1 - normaliseScore(display, max)) * 100 : normaliseScore(display, max) * 100;
  return (
    <div className="factorMeter">
      <div className="factorMeterLabel"><span>{label}</span><strong>{display.toFixed(1)}/{max}</strong></div>
      <div className="factorMeterTrack"><span className={scoreTone(invert ? max - display : display, max)} style={{ width: `${Math.max(4, pct)}%` }} /></div>
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
  const sources = assessment.sources || [];
  const averageScore = sources.length ? sources.reduce((sum, source) => sum + Number(source.score || 0), 0) / sources.length : 0;
  const primaryCount = sources.filter((source) => (source.source_type || '').toLowerCase().includes('primary')).length;
  const contradictionCount = sources.filter((source) => sourceGroup(source) === 'Contradicting').length;
  const supportCount = sources.filter((source) => sourceGroup(source) === 'Corroborating').length;
  const evidenceScore = assessment.verdict.evidence_strength_score ?? null;
  const displayEvidenceScore = typeof evidenceScore === 'number' ? Math.abs(evidenceScore) : null;
  const contradicted = assessment.verdict.label.toLowerCase().includes('contradict') || (typeof evidenceScore === 'number' && evidenceScore < 0);
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

function SourceCard({ source, compact = false }: { source: AssessmentSource; compact?: boolean }) {
  const score = Number(source.score || 0);
  const role = source.source_role || source.evidence_category || source.stance || '';
  const factors = source.scoring_factors || {};
  const hasFactors = Object.values(factors).some((value) => typeof value === 'number' && value > 0);
  const quality = sourceQualityLabel(score);
  const group = sourceGroup(source);
  const detail = (
    <>
      <p>{source.summary || source.classification_reason || 'No source summary was returned.'}</p>
      {source.classification_reason && source.summary && <small className="sourceReason">Why this source matters: {source.classification_reason}</small>}
    </>
  );
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
        <a href={sourceHref(source)} target="_blank" rel="noreferrer" className="sourceTitle">{source.title || source.domain || source.url}</a>
      ) : (
        <strong className="sourceTitle">{source.title || 'Untitled source'}</strong>
      )}
      <div className="sourceMetaRow">
        {source.domain && <span>{source.domain}</span>}
        <span>{group}</span>
        {source.narrative_cluster && <span>Chain: {source.narrative_cluster}</span>}
      </div>
      {compact ? <details className="sourceDetails"><summary>Source detail</summary>{detail}</details> : detail}
      <details className="sourceScoringDetails">
        <summary><span>Why this score?</span><small>{score > 0 ? `${score.toFixed(1)}/5` : 'Scoring detail'}</small></summary>
        {hasFactors ? (
          <div className="factorGrid">
            <FactorMeter label="Authority" value={factors.authority} />
            <FactorMeter label="Relevance" value={factors.relevance} />
            <FactorMeter label="Directness" value={factors.directness} />
            <FactorMeter label="Recency" value={factors.recency} />
            {'independence' in factors && <FactorMeter label="Independence" value={factors.independence} />}
            <FactorMeter label="Bias risk" value={factors.bias_risk} invert />
          </div>
        ) : (
          <p className="muted">Detailed scoring factors are not available for this source yet. The visible score is the source's weighted contribution to this claim.</p>
        )}
        <p className="sourceScoringNote">High-scoring sources are not just reputable. They must be relevant, direct, and useful for this exact claim.</p>
      </details>
    </article>
  );
}

function SourceList({ assessment }: { assessment: AssessmentResponse }) {
  if (!assessment.sources?.length) return <p className="muted">No sources returned for this assessment.</p>;
  return (
    <div className="evidenceGroups">
      {groupSources(assessment.sources.slice(0, 10)).map(({ group, sources }) => (
        <section className="evidenceGroup" key={group}>
          <div className="evidenceGroupHeader">
            <h3>{group}</h3>
            <span>{sources.length} source{sources.length === 1 ? '' : 's'}</span>
          </div>
          <div className="sourceGrid">
            {sources.map((source, index) => <SourceCard source={source} compact key={`${source.id || source.url}-${index}`} />)}
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

function FeedbackControls({ assessment }: { assessment: AssessmentResponse }) {
  const [rating, setRating] = useState<FeedbackRating>('Useful');
  const [reasons, setReasons] = useState<string[]>([]);
  const [comment, setComment] = useState('');
  const [status, setStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function toggleReason(reason: string) {
    setReasons((current) => current.includes(reason) ? current.filter((item) => item !== reason) : [...current, reason]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setStatus('');
    try {
      const response = await submitFeedback({ assessment_id: assessment.assessment_id, rating, reasons, comment });
      setStatus(response.ok ? `Feedback saved. Thank you. ID: ${response.feedback_id}` : 'Feedback submitted, but response was unexpected.');
      setComment('');
      setReasons([]);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not save feedback.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="feedbackBox">
      <h3>Was this useful?</h3>
      <p className="muted">Your feedback is linked to this exact assessment and helps improve evidence quality, caveats, and explanation clarity.</p>
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
        <div className="reasonGrid">
          {feedbackReasons.map((reason) => (
            <label className="checkPill" key={reason}>
              <input checked={reasons.includes(reason)} onChange={() => toggleReason(reason)} type="checkbox" />
              {reason}
            </label>
          ))}
        </div>
        <label>
          Optional comment
          <textarea className="commentBox" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="What was useful, confusing, missing, or wrong?" />
        </label>
        <button disabled={submitting} type="submit">{submitting ? 'Saving…' : 'Send feedback'}</button>
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
                              <SourceCard source={source} compact key={`${source.id || source.url}-${sourceIndex}`} />
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

function LoadingState({ type }: { type: 'claim' | 'speech' | 'report' | 'speech-verify' }) {
  const copy = {
    claim: { title: 'Checking the claim', steps: ['Isolating the factual claim', 'Finding relevant evidence', 'Grouping sources by role', 'Preparing caveats and verdict'] },
    speech: { title: 'Extracting checkable claims', steps: ['Reading transcript', 'Separating claims from rhetoric', 'Ranking by checkability', 'Preparing selection list'] },
    report: { title: 'Loading report', steps: ['Retrieving assessment', 'Restoring evidence trail', 'Preparing verdict and caveats'] },
    'speech-verify': { title: 'Verifying selected claims', steps: ['Checking selected claims', 'Grouping sources by role', 'Preparing claim verdicts and caveats'] },
  }[type];
  return (
    <section className="loadingState" aria-live="polite">
      <div className="loadingOrb"><span></span></div>
      <div>
        <p className="eyebrow">Analysis in progress</p>
        <h3>{copy.title}</h3>
        <div className="loadingSteps">
          {copy.steps.map((step) => <span key={step}>{step}</span>)}
        </div>
      </div>
    </section>
  );
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

function FirstRunGuide({ mode }: { mode: 'claim' | 'speech' }) {
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
}) {
  return (
    <section className="card loginGate">
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
            <div className="formRow">
              <button className="secondary" disabled={authBusy || !email.trim() || password.length < 6} type="submit">Sign in</button>
              <button className="secondary" disabled={authBusy || !email.trim() || password.length < 6} onClick={onSignUp} type="button">Create free account</button>
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
  return (
    <details className="accountMenu">
      <summary>
        <span>{displayName}</span>
        <strong>{me?.user?.tier_label || account.plan}</strong>
      </summary>
      <div className="accountMenuPanel">
        <p className="accountProfileLine"><span>Signed in as</span><strong>{label}</strong></p>
        <p><span>Plan</span><strong>{me?.user?.tier_label || account.plan}</strong></p>
        <p><span>User ID</span><code>{account.owner_id}</code></p>
        {me?.is_admin && <p><span>Admin</span><strong>Enabled</strong></p>}
        {me?.is_admin && <a className="button secondary" href="/admin">Admin UI</a>}
        <button className="secondary" onClick={onToggleTheme} type="button">{theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}</button>
        <button className="secondary" disabled={authBusy} onClick={onSignOut} type="button">Sign out</button>
      </div>
    </details>
  );
}

function SiteHeader({ account, me, signedIn, theme, onToggleTheme, onSignOut, authBusy }: { account: AccountProfile | null; me: MeResponse | null; signedIn: boolean; theme: ThemeMode; onToggleTheme: () => void; onSignOut: () => void; authBusy: boolean }) {
  return (
    <header className="siteHeader">
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
      <a className="brand" href="/">Evidrai</a>
      <div className="headerSpacer" />
      {signedIn && account ? <AccountMenu account={account} me={me} theme={theme} onToggleTheme={onToggleTheme} onSignOut={onSignOut} authBusy={authBusy} /> : <a className="button secondary" href="/">Sign in</a>}
    </header>
  );
}

function AssessmentResult({ assessment }: { assessment: AssessmentResponse }) {
  const tone = verdictTone(assessment.verdict.label);
  const confidence = confidencePercent(assessment.verdict.confidence, assessment.verdict.evidence_strength_score);
  const evidenceStrength = evidenceStrengthLabel(assessment.verdict.evidence_strength_score, assessment.verdict.label);
  const stats = sourceStats(assessment.sources || []);
  const reasoning = assessment.reasoning ? reasoningEntries(assessment.reasoning) : [];
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

      {(assessment.verdict.summary || assessment.verdict.key_caveat) && (
        <div className="assessmentNarrative">
          {assessment.verdict.summary && <p className="summary">{assessment.verdict.summary}</p>}
          {assessment.verdict.key_caveat && <p className="caveat"><strong>Key caveat</strong>{assessment.verdict.key_caveat}</p>}
        </div>
      )}

      <div className="facts assessmentFacts">
        <span>Assessment ID: {assessment.assessment_id}</span>
        <span>{formatDate(assessment.created_at)}</span>
        {stats.length ? stats.map((item) => <span key={item}>{item}</span>) : <span>No evidence grouping available</span>}
      </div>

      <EvidenceScorePanel assessment={assessment} />

      {assessment.claim_breakdown?.length > 0 && (
        <details open className="resultSection">
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
                  <div className="miniEvidenceMap">
                    {item.supporting_source_ids?.length > 0 && <span>{item.supporting_source_ids.length} supporting source{item.supporting_source_ids.length === 1 ? '' : 's'}</span>}
                    {item.contradicting_source_ids?.length > 0 && <span>{item.contradicting_source_ids.length} contradicting source{item.contradicting_source_ids.length === 1 ? '' : 's'}</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      <details open className="resultSection">
        <summary><span>Evidence sources</span><small>Grouped by role in the assessment</small></summary>
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
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [reportIdInput, setReportIdInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingKind, setLoadingKind] = useState<'claim' | 'speech' | 'report' | 'speech-verify'>('claim');
  const [verifyingSpeech, setVerifyingSpeech] = useState(false);
  const [error, setError] = useState('');

  const signedIn = Boolean(account?.owner_id && !account.owner_id.startsWith('anon_'));
  const userFeatures = me?.user?.features || {};
  const userLimits = me?.user?.limits || {};
  const canUseDeep = Boolean(userFeatures.deep_claims);
  const canUseSpeech = Boolean(userFeatures.speech_audit);
  const ready = useMemo(() => signedIn && (claim.trim().length > 0 || sourceUrl.trim().length > 0), [signedIn, claim, sourceUrl]);
  const speechReady = useMemo(() => signedIn && canUseSpeech && (speechTranscript.trim().length > 0 || (tryYouTubeCaptions && speechSourceUrl.trim().length > 0 && isYouTubeUrl(speechSourceUrl))), [signedIn, canUseSpeech, speechTranscript, speechSourceUrl, tryYouTubeCaptions]);

  function rememberReport(result: AssessmentResponse) {
    const summary: ReportSummary = {
      assessment_id: result.assessment_id,
      created_at: result.created_at,
      mode: result.mode,
      claim: result.request.claim,
      verdict: result.verdict.label,
      owner_id: result.owner_id,
    };
    setReports((current) => {
      const next = [summary, ...current.filter((item) => item.assessment_id !== summary.assessment_id)].slice(0, 8);
      window.localStorage.setItem('evidrai_recent_reports', JSON.stringify(next));
      return next;
    });
  }

  async function refreshReports() {
    try {
      const serverReports = await listReports();
      const recent = serverReports.slice(0, 8);
      setReports(recent);
      if (typeof window !== 'undefined') window.localStorage.setItem('evidrai_recent_reports', JSON.stringify(recent));
    } catch (err) {
      console.warn('Could not load saved reports', err);
      try {
        const saved = window.localStorage.getItem('evidrai_recent_reports');
        if (saved) setReports(JSON.parse(saved));
      } catch (localErr) {
        console.warn(localErr);
      }
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
          refreshReports();
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
        refreshReports();
      } else {
        setMe(null);
        setReports([]);
      }
    });
    if (typeof window !== 'undefined' && window.location.href.includes('type=recovery')) setPasswordRecovery(true);
    try {
      const saved = window.localStorage.getItem('evidrai_recent_reports');
      if (saved) setReports(JSON.parse(saved));
    } catch (err) {
      console.warn(err);
    }
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
      setAuthMessage('Signed in.');
      await refreshMe();
      await refreshReports();
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
      const session = await signUpWithEmailPassword(authEmail.trim(), authPassword);
      setAccessToken(session?.access_token || '');
      setAuthMessage(session ? 'Free account created.' : 'Account created. Check your email to confirm before signing in.');
      await refreshMe();
      await refreshReports();
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
      await refreshReports();
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setLoadingKind('claim');
    setLoading(true);
    setError('');
    try {
      const requestedMode = canUseDeep ? mode : 'fast';
      const result = await createAssessment({ claim, source_url: sourceUrl, category, mode: requestedMode });
      setAssessment(result);
      setSpeechExtraction(null);
      setSpeechVerification(null);
      rememberReport(result);
      refreshReports();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed');
    } finally {
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
      });
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

  function toggleTheme() {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      return next;
    });
  }

  return (
    <main>
      <SiteHeader account={account} me={me} signedIn={signedIn} theme={theme} onToggleTheme={toggleTheme} onSignOut={handleSignOut} authBusy={authBusy} />
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
        />
      )}

      {signedIn && <section className="workspaceIntro"><p>Evidence-based assessment · Sources grouped by role · Confidence is not certainty · Reasoning is inspectable</p></section>}
      {signedIn && <TrustLanguageStrip />}

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

          {!assessment && !speechExtraction && !loading && <FirstRunGuide mode={toolMode} />}

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
              </div>
              <VerifyGuide mode="claim" canUseDeep={canUseDeep} canUseSpeech={canUseSpeech} />
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
              <button className="primaryAction" disabled={!speechReady || loading}>{loading && loadingKind === 'speech' ? 'Extracting claims…' : 'Extract claims'}</button>
              {!speechTranscript.trim() && speechSourceUrl.trim() && tryYouTubeCaptions && <p className="fieldHint">No transcript pasted, so Evidrai will try to extract captions from the URL first.</p>}
              {!speechTranscript.trim() && speechSourceUrl.trim() && !tryYouTubeCaptions && <p className="fieldHint">Paste the transcript above, or enable automatic YouTube captions for a best-effort URL-only attempt.</p>}
              <p className="muted">Your plan allows up to {userLimits.max_speech_claims || 0} claims per audit.</p>
            </form>
          )}
          {(loading || verifyingSpeech) && <LoadingState type={verifyingSpeech ? 'speech-verify' : loadingKind} />}
          {error && <p className="error errorState">{error}</p>}
        </section>

        <details className="card reports" open>
          <summary className="reportsSummary">
            <span>Your reports</span>
            <small>{reports.length} saved to your account</small>
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
            {reports.length === 0 ? <p className="muted">No saved reports yet. Run a check to start your account history.</p> : reports.slice(0, 8).map((report) => (
              <button className="reportItem" key={report.assessment_id} onClick={() => loadReport(report.assessment_id)} type="button">
                <strong>{report.verdict || 'Unverified'}</strong>
                <span>{report.claim || 'Untitled claim'}</span>
                <small>{formatDate(report.created_at)} · {report.mode}</small>
              </button>
            ))}
          </div>
        </details>
      </div>}

      {signedIn && assessment && <AssessmentResult assessment={assessment} />}
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
