'use client';

import { useEffect, useState } from 'react';
import { AccountProfile, MeResponse, TrustAnalyticsResponse, backfillTrustAnalytics, getAnonymousAccountProfile, getMe, getTrustAnalytics, setAccessToken, setAccountProfile } from '../../../../lib/api';
import { getCurrentSession, onAuthStateChange, profileFromSession, signInWithGoogle, signOut } from '../../../../lib/auth';

function countLabel(value: unknown) {
  return typeof value === 'number' ? value.toLocaleString() : String(value || '0');
}

function signalName(value: string) {
  return value.replaceAll('_', ' ');
}

function JsonBlock({ title, payload }: { title: string; payload: unknown }) {
  return (
    <details className="resultSection">
      <summary><span>{title}</span><small>Show raw JSON</small></summary>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </details>
  );
}

export default function TrustAnalyticsPage() {
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [analytics, setAnalytics] = useState<TrustAnalyticsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const isAdmin = Boolean(me?.is_admin);

  async function refreshMe() {
    const payload = await getMe();
    setMe(payload);
    setAccount((current) => current ? { ...current, plan: payload.user.tier_label } : current);
    return payload;
  }

  async function loadAnalytics() {
    setBusy(true);
    setMessage('');
    try {
      const payload = await getTrustAnalytics(20);
      setAnalytics(payload);
      setMessage('Trust analytics loaded.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not load trust analytics.');
    } finally {
      setBusy(false);
    }
  }

  async function backfillFromReports() {
    setBusy(true);
    setMessage('');
    try {
      const payload = await backfillTrustAnalytics(1000);
      if (payload.analytics) setAnalytics(payload.analytics);
      else await loadAnalytics();
      setMessage(`Backfilled ${payload.captured}/${payload.reports_seen} saved reports into trust analytics${payload.failed ? `; ${payload.failed} failed` : ''}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not backfill trust analytics.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const fallback = getAnonymousAccountProfile();
    setAccount(fallback);
    getCurrentSession()
      .then(async (session) => {
        setAccessToken(session?.access_token || '');
        const profile = profileFromSession(session, fallback);
        setAccount(profile);
        setAccountProfile(profile);
        if (session) {
          const profilePayload = await refreshMe();
          if (profilePayload.is_admin) await loadAnalytics();
        }
      })
      .catch((err) => setMessage(err.message));
    const unsubscribe = onAuthStateChange(async (session) => {
      setAccessToken(session?.access_token || '');
      const profile = profileFromSession(session, fallback);
      setAccount(profile);
      setAccountProfile(profile);
      if (session) {
        const profilePayload = await refreshMe();
        if (profilePayload.is_admin) await loadAnalytics();
      } else {
        setMe(null);
        setAnalytics(null);
      }
    });
    return unsubscribe;
  }, []);

  async function googleSignIn() {
    setBusy(true);
    setMessage('');
    try {
      await signInWithGoogle();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Google sign-in failed.');
      setBusy(false);
    }
  }

  async function handleSignOut() {
    setBusy(true);
    setMessage('');
    try {
      await signOut();
      setAnalytics(null);
      setMe(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Sign-out failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">Evidrai Admin</p>
          <h1>Trust intelligence analytics</h1>
          <p className="lead">Early internal view of structured feedback signals, disputed claims, and source reliability observations captured by the Trust Intelligence layer.</p>
        </div>
        <div className="statusPanel">
          <span>Account: {account?.label || 'checking...'}</span>
          <span>Admin access: {isAdmin ? 'enabled' : 'not enabled'}</span>
          <span>Backend: {analytics?.backend || 'not loaded'}</span>
          <a href="/admin">User admin</a>
          <a href="/">Back to product</a>
        </div>
      </section>

      {!isAdmin ? (
        <section className="card loginGate">
          <h2>Admin sign-in required</h2>
          <p className="muted">This page calls the protected backend endpoint <code>/admin/trust/analytics</code>. Sign in with an authorised admin account first.</p>
          <button disabled={busy} onClick={googleSignIn} type="button">Continue with Google</button>
          {message && <p className="error">{message}</p>}
        </section>
      ) : (
        <>
          <section className="card adminToolbar">
            <div>
              <h2>Trust analytics</h2>
              <p className="muted">This is a foundation view, not the final dashboard. It summarises the new trust-event tables/API without exposing secrets.</p>
            </div>
            <div className="formRow">
              <button disabled={busy} onClick={loadAnalytics} type="button">{busy ? 'Refreshing…' : 'Refresh analytics'}</button>
              <button className="secondary" disabled={busy} onClick={backfillFromReports} type="button">Backfill saved reports</button>
              <button className="secondary" disabled={busy} onClick={handleSignOut} type="button">Sign out</button>
            </div>
          </section>

          {message && <p className={message.toLowerCase().includes('could not') || message.toLowerCase().includes('forbidden') ? 'error' : 'success'}>{message}</p>}

          <section className="analyticsGrid">
            <article className="card analyticsCard">
              <p className="eyebrow">Backfilled corpus</p>
              <h2>Saved report coverage</h2>
              <div className="analyticsRow"><span>Claim checks</span><strong>{countLabel(analytics?.summary?.claim_checks)}</strong></div>
              <div className="analyticsRow"><span>Evidence sources</span><strong>{countLabel(analytics?.summary?.evidence_sources)}</strong></div>
              <div className="analyticsRow vertical"><span>Trust signals</span><strong>{countLabel(analytics?.summary?.trust_signals)}</strong><small>{analytics?.summary?.trust_signals ? 'Captured from source buttons and trust feedback.' : 'Awaiting source-button or trust-feedback submissions.'}</small></div>
              <div className="analyticsRow vertical"><span>Counter-evidence</span><strong>{countLabel(analytics?.summary?.counter_evidence)}</strong><small>{analytics?.summary?.counter_evidence ? 'User-submitted challenges captured.' : 'No user-submitted counter-evidence yet.'}</small></div>
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Claims</p>
              <h2>Recent claim checks</h2>
              {analytics?.recent_claim_checks?.length ? analytics.recent_claim_checks.map((item) => (
                <div className="analyticsRow vertical" key={item.assessment_id}>
                  <span>{item.claim || item.assessment_id}</span>
                  <small>{[item.verdict, item.confidence].filter(Boolean).join(' · ') || 'No verdict label'}</small>
                </div>
              )) : <p className="muted">No claim snapshots captured yet. Use Backfill saved reports.</p>}
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Evidence</p>
              <h2>Top source domains</h2>
              {analytics?.top_source_domains?.length ? analytics.top_source_domains.map((item) => (
                <div className="analyticsRow" key={item.domain || item.value}>
                  <span>{item.domain || item.value || 'Unknown domain'}</span>
                  <strong>{countLabel(item.count)}</strong>
                </div>
              )) : <p className="muted">No source domains captured yet.</p>}
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Verdicts</p>
              <h2>Verdict distribution</h2>
              {analytics?.verdict_distribution?.length ? analytics.verdict_distribution.map((item) => (
                <div className="analyticsRow" key={item.verdict || item.value}>
                  <span>{item.verdict || item.value || 'Unknown verdict'}</span>
                  <strong>{countLabel(item.count)}</strong>
                </div>
              )) : <p className="muted">No verdict distribution captured yet.</p>}
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Signals</p>
              <h2>Top trust signals</h2>
              {analytics?.top_signals?.length ? analytics.top_signals.map((item) => (
                <div className="analyticsRow" key={item.signal_type || item.value}>
                  <span>{signalName(item.signal_type || item.value || 'unknown')}</span>
                  <strong>{countLabel(item.count)}</strong>
                </div>
              )) : <p className="muted">No feedback trust signals captured yet. Use the source-card buttons or Trust feedback form on an assessment.</p>}
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Disputes</p>
              <h2>Most disputed claims</h2>
              {analytics?.most_disputed_claims?.length ? analytics.most_disputed_claims.map((item) => (
                <div className="analyticsRow vertical" key={item.claim || item.value}>
                  <span>{item.claim || item.value || 'Unknown claim'}</span>
                  <strong>{countLabel(item.count)}</strong>
                </div>
              )) : <p className="muted">No disputed claims captured yet. This requires rejected verdicts, challenge text, or submitted counter-evidence.</p>}
            </article>
          </section>

          {analytics && <JsonBlock title="Raw analytics response" payload={analytics} />}
        </>
      )}
    </main>
  );
}
