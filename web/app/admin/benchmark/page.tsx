'use client';

import { useEffect, useState } from 'react';
import { BenchmarkClaim, BenchmarkRunResponse, getBenchmarkDataset, getMe, runBenchmark, setAccessToken } from '../../../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, signInWithEmailPassword, signInWithGoogle } from '../../../lib/auth';

function pct(value?: number | null) {
  if (value === null || value === undefined) return 'n/a';
  return `${Math.round(value * 1000) / 10}%`;
}

function tone(message: string) {
  const lower = message.toLowerCase();
  if (lower.includes('failed') || lower.includes('forbidden') || lower.includes('could not')) return 'bad';
  if (lower.includes('running')) return 'mixed';
  return 'good';
}

export default function AdminBenchmarkPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [claims, setClaims] = useState<BenchmarkClaim[]>([]);
  const [run, setRun] = useState<BenchmarkRunResponse | null>(null);
  const [includeHeldOut, setIncludeHeldOut] = useState(false);
  const [limit, setLimit] = useState('5');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function refresh() {
    const me = await getMe();
    setIsAdmin(Boolean(me.is_admin));
    if (me.is_admin) {
      const dataset = await getBenchmarkDataset();
      setClaims(dataset.claims || []);
    }
  }

  useEffect(() => {
    getCurrentSession().then(async (session) => {
      setAccessToken(session?.access_token || '');
      if (session) await refresh();
    }).catch((err) => setMessage(err.message));
    return onAuthStateChange(async (session) => {
      setAccessToken(session?.access_token || '');
      setIsAdmin(false);
      if (session) await refresh();
    });
  }, []);

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const session = await signInWithEmailPassword(email.trim(), password);
      setAccessToken(session?.access_token || '');
      await refresh();
      setMessage('Signed in.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  }

  async function googleSignIn() {
    setBusy(true);
    setMessage('');
    try {
      await signInWithGoogle();
      setMessage('Redirecting to Google sign-in.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Google sign-in failed.');
      setBusy(false);
    }
  }

  async function startRun() {
    setBusy(true);
    setMessage('Running benchmark. This calls the live deep assessment path and may take a while.');
    try {
      const parsedLimit = Number.parseInt(limit, 10);
      const payload = await runBenchmark({
        include_held_out: includeHeldOut,
        limit: Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : undefined,
        fail_loud: true,
        model_version: 'render-live',
      });
      setRun(payload);
      setMessage(payload.ok ? `Benchmark complete: ${payload.scored_size} claims scored.` : `Benchmark finished with ${payload.failure_count} failures.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Benchmark run failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="adminPage">
      <section className="adminHero">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Calibration benchmark</h1>
          <p className="lead">Run the public calibration dataset through the same deep assessment path a user hits, then review calibration metrics before publishing.</p>
        </div>
        <nav className="adminNav"><a href="/admin">User admin</a><a href="/admin/scoring-policy">Scoring policy</a><a href="/admin/trust/analytics">Trust analytics</a></nav>
      </section>

      {!isAdmin && (
        <section className="card adminLogin">
          <h2>Admin sign-in</h2>
          <p className="muted">Sign in with a server-authorised admin account.</p>
          {authConfigured() ? <button type="button" onClick={googleSignIn} disabled={busy}>Continue with Google</button> : null}
          <form onSubmit={signIn}>
            <label>Email<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" /></label>
            <label>Password<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" /></label>
            <button type="submit" disabled={busy}>Sign in</button>
          </form>
        </section>
      )}

      {isAdmin && (
        <>
          <section className="card adminPanel">
            <h2>Run benchmark</h2>
            <div className="adminToolbar">
              <label><input type="checkbox" checked={includeHeldOut} onChange={(event) => setIncludeHeldOut(event.target.checked)} /> Include held-out set</label>
              <label>Limit<input value={limit} onChange={(event) => setLimit(event.target.value)} inputMode="numeric" /></label>
              <button type="button" onClick={startRun} disabled={busy}>Run live benchmark</button>
            </div>
            <p className="muted">Default limit is intentionally small. Clearing it runs every selected scorable claim and will create saved benchmark reports.</p>
          </section>

          {run && (
            <section className="card adminPanel">
              <h2>Latest run</h2>
              <section className="adminStats">
                <div><span>Claims</span><strong>{run.metrics.claim_count}</strong></div>
                <div><span>Accuracy</span><strong>{pct(run.metrics.accuracy)}</strong></div>
                <div><span>ECE</span><strong>{run.metrics.ece.toFixed(3)}</strong></div>
                <div><span>Brier</span><strong>{run.metrics.brier_score.toFixed(3)}</strong></div>
              </section>
              <div className="adminUserTable scalable">
                <div className="adminUserHeader scalable"><span>Bucket</span><span>Count</span><span>Confidence</span><span>Accuracy</span><span>Gap</span></div>
                {run.metrics.reliability_bins.map((bin) => (
                  <article className="adminUserRow scalable" key={bin.bucket}>
                    <span>{bin.bucket}</span><span>{bin.count}</span><span>{pct(bin.avg_confidence)}</span><span>{pct(bin.accuracy)}</span><span>{pct(bin.gap)}</span>
                  </article>
                ))}
              </div>
              {run.failures.length ? <p className="adminMessage bad">{run.failures.length} failures. First: {run.failures[0].claim_id} {run.failures[0].error}</p> : null}
            </section>
          )}

          <section className="card adminPanel">
            <h2>Dataset</h2>
            <p className="muted">{claims.length} claims loaded. Held-out labels are hidden in this admin dataset view unless scored by the backend.</p>
            <div className="adminIssueList">
              {claims.slice(0, 12).map((claim) => (
                <article key={claim.id}>
                  <strong>{claim.id} · {claim.domain} · {claim.split}</strong>
                  <p>{claim.claim}</p>
                  <small>{claim.label || 'held-out label hidden'} {claim.excluded_reason ? ` · excluded: ${claim.excluded_reason}` : ''}</small>
                </article>
              ))}
            </div>
          </section>
        </>
      )}

      {message && <p className={`adminMessage ${tone(message)}`}>{message}</p>}
    </main>
  );
}

