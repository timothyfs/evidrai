'use client';

import { FormEvent, useEffect, useState } from 'react';
import { AccountProfile, MeResponse, TierName, UserProfile, getAnonymousAccountProfile, getMe, listAdminUsers, setAccessToken, setAccountProfile, setAdminUserTier } from '../../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, profileFromSession, signInWithEmailPassword, signInWithGoogle, signOut } from '../../lib/auth';

function tierOptions() {
  return [
    { value: 'free', label: 'Free' },
    { value: 'pro', label: 'Pro' },
    { value: 'researcher', label: 'Researcher / Journalist' },
  ] as const;
}

export default function AdminPage() {
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [targetEmail, setTargetEmail] = useState('');
  const [tier, setTier] = useState<TierName>('free');
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const isAdmin = me?.is_admin;

  async function refreshMe() {
    const payload = await getMe();
    setMe(payload);
    setAccount((current) => current ? { ...current, plan: payload.user.tier_label } : current);
  }

  async function loadUsers() {
    setBusy(true);
    setMessage('');
    try {
      const payload = await listAdminUsers();
      setUsers(payload.users || []);
      setMessage(`Loaded ${payload.users?.length || 0} users.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not load users.');
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
        if (session) await refreshMe();
      })
      .catch((err) => setMessage(err.message));
    const unsubscribe = onAuthStateChange(async (session) => {
      setAccessToken(session?.access_token || '');
      const profile = profileFromSession(session, fallback);
      setAccount(profile);
      setAccountProfile(profile);
      if (session) await refreshMe();
      else setMe(null);
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (isAdmin) loadUsers();
  }, [isAdmin]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const session = await signInWithEmailPassword(email.trim(), password);
      setAccessToken(session?.access_token || '');
      await refreshMe();
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
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Google sign-in failed.');
      setBusy(false);
    }
  }

  async function saveTier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const payload = await setAdminUserTier({ owner_id: ownerId, email: targetEmail, tier });
      setMessage(`Updated ${payload.user.email || payload.user.owner_id} to ${payload.user.tier_label}.`);
      await loadUsers();
      await refreshMe();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not update tier.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSignOut() {
    setBusy(true);
    setMessage('');
    try {
      await signOut();
      setUsers([]);
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
          <h1>User management</h1>
          <p className="lead">The master admin can view users and set their visible product tier: Free, Pro, or Researcher / Journalist. Payments and 30-day trials can wire into the reserved subscription fields later.</p>
        </div>
        <div className="statusPanel">
          <span>Account: {account?.label || 'checking...'}</span>
          <span>Tier: {me?.user?.tier_label || 'not signed in'}</span>
          <a href="/">Back to product</a>
        </div>
      </section>

      {!isAdmin ? (
        <section className="card loginGate">
          <h2>Admin access required</h2>
          <p className="muted">Sign in as the master admin user. Product tiers do not grant admin access.</p>
          {authConfigured() ? (
            <div className="authActions">
              <button disabled={busy} onClick={googleSignIn} type="button">Continue with Google</button>
              <form className="emailLogin" onSubmit={signIn}>
                <label>Email<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="admin@example.com" /></label>
                <label>Password<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Password" /></label>
                <button className="secondary" disabled={busy || !email.trim() || password.length < 6} type="submit">Sign in</button>
              </form>
            </div>
          ) : <p className="error">Authentication is not configured.</p>}
        </section>
      ) : (
        <section className="card adminPanel">
          <div className="sectionHeader">
            <h2>Users</h2>
            <button className="secondary" disabled={busy} onClick={handleSignOut} type="button">Sign out</button>
          </div>
          <form onSubmit={saveTier}>
            <label>User ID<input value={ownerId} onChange={(event) => setOwnerId(event.target.value)} placeholder="Supabase user id" /></label>
            <label>Email<input value={targetEmail} onChange={(event) => setTargetEmail(event.target.value)} placeholder="optional email" /></label>
            <label>Tier<select value={tier} onChange={(event) => setTier(event.target.value as TierName)}>{tierOptions().map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <div className="formRow">
              <button disabled={busy || !ownerId.trim()} type="submit">Set tier</button>
              <button className="secondary" disabled={busy} onClick={loadUsers} type="button">Reload users</button>
            </div>
          </form>
          <div className="adminUsers">
            {users.map((user) => (
              <button key={user.owner_id} className="reportItem" type="button" onClick={() => { setOwnerId(user.owner_id); setTargetEmail(user.email || ''); setTier(user.tier); }}>
                <strong>{user.tier_label}</strong>
                <span>{user.email || user.owner_id}</span>
                <small>{user.owner_id}</small>
                <small>Subscription: {user.subscription_status || 'none'}{user.trial_ends_at ? ` · trial ends ${user.trial_ends_at}` : ''}</small>
              </button>
            ))}
          </div>
        </section>
      )}
      {message && <p className="muted">{message}</p>}
    </main>
  );
}
