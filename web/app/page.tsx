'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  API_BASE_URL,
  AccountProfile,
  AssessmentResponse,
  FeedbackRating,
  MeResponse,
  ReportSummary,
  RuntimeStatus,
  SpeechCheckedClaim,
  SpeechClaim,
  SpeechExtractionResult,
  SpeechVerificationResult,
  createAssessment,
  extractSpeechClaims,
  getMe,
  getAuthDiagnostics,
  getAccountProfile,
  getAnonymousAccountProfile,
  getReport,
  getRuntime,
  setAccessToken,
  setAccountProfile,
  submitFeedback,
  verifySpeechClaims,
} from '../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, profileFromSession, sendPasswordReset, signInWithEmailPassword, signInWithGoogle, signOut, signUpWithEmailPassword, updatePassword } from '../lib/auth';

const FRONTEND_BUILD = process.env.NEXT_PUBLIC_APP_BUILD || 'local';

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

function sourceHref(source: { url?: string }) {
  return source.url || '';
}

function SourceList({ assessment }: { assessment: AssessmentResponse }) {
  if (!assessment.sources?.length) return <p className="muted">No sources returned for this assessment.</p>;
  return (
    <div className="sourceGrid">
      {assessment.sources.slice(0, 8).map((source) => (
        <article className="source" key={source.id}>
          <div className="sourceMeta">{source.source_type} · {source.stance} · score {Number(source.score || 0).toFixed(1)}</div>
          {source.url ? (
            <a href={sourceHref(source)} target="_blank" rel="noreferrer" className="sourceTitle">{source.title || source.domain || source.url}</a>
          ) : (
            <strong className="sourceTitle">{source.title || 'Untitled source'}</strong>
          )}
          <p>{source.summary || source.classification_reason || 'No summary available.'}</p>
        </article>
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
      <p className="muted">Your feedback is linked to this exact assessment and helps improve verdict quality.</p>
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
          <p className="eyebrow">Speech / Video Audit</p>
          <h2>{extraction.title || 'Extracted claims'}</h2>
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

      <details open>
        <summary>1. Extracted claims: choose what to verify</summary>
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
          <summary>2. Verified claims</summary>
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
                    {(item.summary || item.tldr) && <p>{item.summary || item.tldr}</p>}
                    {item.sources?.length ? (
                      <div className="sourceGrid compact">
                        {item.sources.slice(0, 4).map((source, sourceIndex) => (
                          <article className="source" key={`${source.id || source.url}-${sourceIndex}`}>
                            <div className="sourceMeta">{source.source_type} · {source.stance || source.evidence_category}</div>
                            {source.url ? <a href={sourceHref(source)} target="_blank" rel="noreferrer" className="sourceTitle">{source.title || source.domain || source.url}</a> : <strong>{source.title || 'Source'}</strong>}
                            <p>{source.summary || source.classification_reason || 'No summary available.'}</p>
                          </article>
                        ))}
                      </div>
                    ) : <p className="muted">No sources returned for this checked claim.</p>}
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

function AccountPanel({
  account,
  authReady,
  email,
  password,
  setEmail,
  setPassword,
  authMessage,
  authBusy,
  onGoogle,
  onEmailPassword,
  onSignUp,
  onPasswordReset,
  onSignOut,
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
  onSignOut: () => void;
}) {
  const signedIn = Boolean(account?.owner_id && !account.owner_id.startsWith('anon_'));
  return (
    <section className="accountPanel">
      <div>
        <strong>{signedIn ? account?.label : 'Sign in required'}</strong>
        <span>{signedIn ? `${account?.plan || 'Free'} user` : 'Use Google or email/password to continue'}</span>
      </div>
      {signedIn ? (
        <button className="secondary" disabled={authBusy} onClick={onSignOut} type="button">Sign out</button>
      ) : authReady ? (
        <div className="authActions">
          <button className="secondary" disabled={authBusy} onClick={onGoogle} type="button">Continue with Google</button>
          <form className="emailLogin" onSubmit={onEmailPassword}>
            <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" type="email" />
            <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" type="password" />
            <button className="secondary" disabled={authBusy || !email.trim() || password.length < 6} type="submit">Sign in</button>
            <button className="secondary" disabled={authBusy || !email.trim() || password.length < 6} onClick={onSignUp} type="button">Create free account</button>
            <button className="linkButton" disabled={authBusy || !email.trim()} onClick={onPasswordReset} type="button">Set/reset password</button>
          </form>
        </div>
      ) : (
        <small>Auth env vars are not configured yet.</small>
      )}
      {authMessage && <small>{authMessage}</small>}
    </section>
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
      <p className="eyebrow">Account required</p>
      <h2>Sign in to use Evidrai</h2>
      <p className="muted">Reports, feedback, and usage limits are now tied to a user account. Anonymous access is disabled in the product UI.</p>
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

function FeatureMatrix({ me }: { me: MeResponse | null }) {
  if (!me?.feature_matrix?.tiers?.length) return null;
  const featureLabels: Record<string, string> = {
    fast_claims: 'Fast claim checks',
    deep_claims: 'Deep claim checks',
    speech_audit: 'Speech/video audit',
    feedback: 'Feedback',
    share_reports: 'Shareable reports',
    exports: 'Exports',
    evidence_ledger: 'Evidence ledger',
    source_snapshots: 'Source snapshots',
    api_access: 'API access',
  };
  const featureKeys = Object.keys(me.feature_matrix.tiers[0].features);
  return (
    <section className="card matrixCard">
      <h2>Feature matrix</h2>
      <div className="matrixGrid">
        <strong>Feature</strong>
        {me.feature_matrix.tiers.map((tier) => <strong key={tier.tier}>{tier.label}</strong>)}
        {featureKeys.map((feature) => [
          <span key={`${feature}-label`}>{featureLabels[feature] || feature}</span>,
          ...me.feature_matrix.tiers.map((tier) => <span key={`${feature}-${tier.tier}`}>{tier.features[feature] ? 'Yes' : 'No'}</span>),
        ])}
      </div>
    </section>
  );
}

function UserSummary({ account, me, onSignOut, authBusy }: { account: AccountProfile; me: MeResponse | null; onSignOut: () => void; authBusy: boolean }) {
  return (
    <section className="userSummary">
      <div>
        <span>User</span>
        <strong>{account.label}</strong>
      </div>
      <div>
        <span>User ID</span>
        <code>{account.owner_id}</code>
      </div>
      <div>
        <span>Type</span>
        <strong>{me?.user?.tier_label || account.plan}</strong>
      </div>
      {me?.user?.tier === 'admin' && <a className="button secondary" href="/admin">Admin</a>}
      <button className="secondary" disabled={authBusy} onClick={onSignOut} type="button">Sign out</button>
    </section>
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
  const [maxClaims, setMaxClaims] = useState(3);
  const [speechMode, setSpeechMode] = useState<'fast' | 'deep'>('fast');
  const [speechExtraction, setSpeechExtraction] = useState<SpeechExtractionResult | null>(null);
  const [selectedSpeechClaims, setSelectedSpeechClaims] = useState<string[]>([]);
  const [speechVerification, setSpeechVerification] = useState<SpeechVerificationResult | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordRecovery, setPasswordRecovery] = useState(false);
  const [authMessage, setAuthMessage] = useState('');
  const [authDiagnostics, setAuthDiagnostics] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [reportIdInput, setReportIdInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [verifyingSpeech, setVerifyingSpeech] = useState(false);
  const [error, setError] = useState('');

  const signedIn = Boolean(account?.owner_id && !account.owner_id.startsWith('anon_'));
  const userFeatures = me?.user?.features || {};
  const userLimits = me?.user?.limits || {};
  const canUseDeep = Boolean(userFeatures.deep_claims);
  const canUseSpeech = Boolean(userFeatures.speech_audit);
  const ready = useMemo(() => signedIn && (claim.trim().length > 0 || sourceUrl.trim().length > 0), [signedIn, claim, sourceUrl]);
  const speechReady = useMemo(() => signedIn && canUseSpeech && (speechTranscript.trim().length > 0 || speechSourceUrl.trim().length > 0), [signedIn, canUseSpeech, speechTranscript, speechSourceUrl]);

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
        if (session) refreshMe();
      })
      .catch((err) => setAuthMessage(err.message));
    const unsubscribe = onAuthStateChange((session) => {
      const currentFallback = session ? getAccountProfile() : getAnonymousAccountProfile();
      setAccessToken(session?.access_token || '');
      const profile = profileFromSession(session, currentFallback);
      setAccount(profile);
      setAccountProfile(profile);
      setAuthMessage(session ? 'Signed in.' : 'Signed out. Sign in again to use Evidrai.');
      if (session) refreshMe();
      else setMe(null);
    });
    if (typeof window !== 'undefined' && window.location.href.includes('type=recovery')) setPasswordRecovery(true);
    getRuntime().then(setRuntime).catch((err) => setError(err.message));
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
    setLoading(true);
    setError('');
    try {
      const requestedMode = canUseDeep ? mode : 'fast';
      const result = await createAssessment({ claim, source_url: sourceUrl, category, mode: requestedMode });
      setAssessment(result);
      setSpeechExtraction(null);
      setSpeechVerification(null);
      rememberReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed');
    } finally {
      setLoading(false);
    }
  }

  async function extractSpeech(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!speechReady) return;
    setLoading(true);
    setError('');
    setAssessment(null);
    setSpeechVerification(null);
    try {
      const result = await extractSpeechClaims({
        transcript: speechTranscript,
        source_url: speechSourceUrl,
        max_claims: Math.min(maxClaims, Number(userLimits.max_speech_claims || maxClaims)),
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
          <span>Frontend build: {FRONTEND_BUILD}</span>
          <span>API build: {runtime?.build || 'checking...'}</span>
          <span>Storage: {runtime?.storage_backend || 'checking...'}</span>
          <span>OpenAI: {runtime?.openai_configured ? 'configured' : 'missing'}</span>
          <span>Auth: {runtime?.auth_configured ? 'server verified' : 'not configured'}</span>
          <span>Account: {signedIn ? account?.owner_id.slice(0, 18) : 'sign in required'}</span>
        </div>
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

      {signedIn && account ? (
        <>
          <UserSummary account={account} me={me} onSignOut={handleSignOut} authBusy={authBusy} />
          <FeatureMatrix me={me} />
        </>
      ) : (
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

      {signedIn && <div className="layout">
        <section className="card">
          <div className="segmented modeSwitch" role="tablist" aria-label="Audit type">
            <button className={toolMode === 'claim' ? 'active' : ''} onClick={() => setToolMode('claim')} type="button">Single claim</button>
            <button className={toolMode === 'speech' ? 'active' : ''} disabled={!canUseSpeech} onClick={() => setToolMode('speech')} type="button">Speech / video audit</button>
          </div>

          {toolMode === 'claim' ? (
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
                    <option disabled={!canUseDeep} value="deep">Deep{canUseDeep ? '' : ' · Pro+'}</option>
                  </select>
                </label>
              </div>
              <button disabled={!ready || loading}>{loading ? 'Checking…' : 'Check claim'}</button>
            </form>
          ) : (
            <form onSubmit={extractSpeech}>
              <label>
                Transcript
                <textarea value={speechTranscript} onChange={(event) => setSpeechTranscript(event.target.value)} placeholder="Paste a speech, interview, podcast transcript, debate excerpt, or video transcript..." />
              </label>
              <label>
                Optional video/source URL
                <input value={speechSourceUrl} onChange={(event) => setSpeechSourceUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." />
              </label>
              <div className="formRow">
                <label>
                  Claims to extract
                  <select value={maxClaims} onChange={(event) => setMaxClaims(Number(event.target.value))}>
                    {Array.from({ length: Math.max(1, Math.min(20, Number(userLimits.max_speech_claims || 0))) }, (_, index) => index + 1).map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  Verification mode
                  <select value={speechMode} onChange={(event) => setSpeechMode(event.target.value as 'fast' | 'deep')}>
                    <option value="fast">Fast</option>
                    <option disabled={!canUseDeep} value="deep">Deep{canUseDeep ? '' : ' · Pro+'}</option>
                  </select>
                </label>
              </div>
              <button disabled={!speechReady || loading}>{loading ? 'Extracting claims…' : 'Extract claims'}</button>
              <p className="muted">Two-stage flow: extract/rank first, then choose claims to verify. Your tier allows up to {userLimits.max_speech_claims || 0} claims per audit.</p>
            </form>
          )}
          {error && <p className="error">{error}</p>}
        </section>

        <aside className="card reports">
          <AccountPanel
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
            onSignOut={handleSignOut}
          />
          <div className="sectionHeader">
            <h2>Your reports</h2>
          </div>
          <p className="muted">Reports created or loaded by this signed-in user.</p>
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
