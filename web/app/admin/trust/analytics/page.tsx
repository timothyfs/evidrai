'use client';

import { useEffect, useState } from 'react';
import { AccountProfile, MeResponse, TrustAnalyticsResponse, getAnonymousAccountProfile, getMe, getTrustAnalytics, setAccessToken, setAccountProfile } from '../../../../lib/api';
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
              <button className="secondary" disabled={busy} onClick={handleSignOut} type="button">Sign out</button>
            </div>
          </section>

          {message && <p className={message.toLowerCase().includes('could not') || message.toLowerCase().includes('forbidden') ? 'error' : 'success'}>{message}</p>}

          <section className="analyticsGrid">
            <article className="card analyticsCard">
              <p className="eyebrow">Signals</p>
              <h2>Top trust signals</h2>
              {analytics?.top_signals?.length ? analytics.top_signals.map((item) => (
                <div className="analyticsRow" key={item.signal_type || item.value}>
                  <span>{signalName(item.signal_type || item.value || 'unknown')}</span>
                  <strong>{countLabel(item.count)}</strong>
                </div>
              )) : <p className="muted">No trust signals captured yet.</p>}
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Claims</p>
              <h2>Most disputed claims</h2>
              {analytics?.most_disputed_claims?.length ? analytics.most_disputed_claims.map((item) => (
                <div className="analyticsRow vertical" key={item.claim || item.value}>
                  <span>{item.claim || item.value || 'Unknown claim'}</span>
                  <strong>{countLabel(item.count)}</strong>
                </div>
              )) : <p className="muted">No disputed claims captured yet.</p>}
            </article>

            <article className="card analyticsCard">
              <p className="eyebrow">Sources</p>
              <h2>Reliability observations</h2>
              {analytics?.source_reliability_observations?.length ? analytics.source_reliability_observations.map((item) => (
                <div className="analyticsRow vertical" key={item.domain || item.source_url || JSON.stringify(item)}>
                  <span>{item.domain || item.source_url || 'Unknown source'}</span>
                  <small>{countLabel(item.observations)} observations · delta {String(item.reliability_delta ?? 'n/a')}</small>
                </div>
              )) : <p className="muted">No source reliability observations captured yet.</p>}
            </article>
          </section>

          {analytics && <JsonBlock title="Raw analytics response" payload={analytics} />}
        </>
      )}
    </main>
  );
}
