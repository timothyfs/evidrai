'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AccountProfile, MeResponse, TierName, UserProfile, getAnonymousAccountProfile, getMe, listAdminUsers, setAccessToken, setAccountProfile, setAdminUserTier } from '../../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, profileFromSession, signInWithEmailPassword, signInWithGoogle, signOut } from '../../lib/auth';

const TIER_OPTIONS = [
  { value: 'free', label: 'Free' },
  { value: 'pro', label: 'Pro' },
  { value: 'researcher', label: 'Researcher / Journalist' },
] as const;

function tierLabel(tier: TierName) {
  return TIER_OPTIONS.find((item) => item.value === tier)?.label || tier;
}

export default function AdminPage() {
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [manualOwnerId, setManualOwnerId] = useState('');
  const [manualEmail, setManualEmail] = useState('');
  const [manualTier, setManualTier] = useState<TierName>('free');
  const [search, setSearch] = useState('');
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const isAdmin = Boolean(me?.is_admin);
  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return users;
    return users.filter((user) => [user.email, user.owner_id, user.tier_label, user.subscription_status].some((value) => (value || '').toLowerCase().includes(query)));
  }, [search, users]);

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

  async function updateUserTier(user: UserProfile, nextTier: TierName) {
    if (nextTier === user.tier) return;
    setBusy(true);
    setMessage('');
    try {
      const payload = await setAdminUserTier({ owner_id: user.owner_id, email: user.email, tier: nextTier });
      setUsers((current) => current.map((item) => item.owner_id === payload.user.owner_id ? payload.user : item));
      setMessage(`Updated ${payload.user.email || payload.user.owner_id} to ${payload.user.tier_label}.`);
      await refreshMe();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not update tier.');
    } finally {
      setBusy(false);
    }
  }

  async function saveManualTier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const payload = await setAdminUserTier({ owner_id: manualOwnerId, email: manualEmail, tier: manualTier });
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
          <p className="lead">The master admin can view users and set their visible product tier: Free, Pro, or Researcher / Journalist.</p>
        </div>
        <div className="statusPanel">
          <span>Account: {account?.label || 'checking...'}</span>
          <span>Plan: {me?.user?.tier_label || 'not signed in'}</span>
          <span>Admin: {isAdmin ? 'yes' : 'no'}</span>
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
            <div>
              <h2>Users</h2>
              <p className="muted">{filteredUsers.length} shown · {users.length} total</p>
            </div>
            <div className="formRow compactActions">
              <button className="secondary" disabled={busy} onClick={loadUsers} type="button">Reload</button>
              <button className="secondary" disabled={busy} onClick={handleSignOut} type="button">Sign out</button>
            </div>
          </div>

          <label>
            Search users
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search email, user ID, tier, subscription..." />
          </label>

          <div className="adminUserTable">
            <div className="adminUserHeader">
              <strong>User</strong>
              <strong>Current tier</strong>
              <strong>Set permission</strong>
            </div>
            {filteredUsers.length === 0 ? <p className="muted">No users found. Users appear here after they sign in and the API creates their profile.</p> : filteredUsers.map((user) => (
              <article className="adminUserRow" key={user.owner_id}>
                <div>
                  <strong>{user.email || 'No email captured'}</strong>
                  <small>{user.owner_id}</small>
                  <small>Subscription: {user.subscription_status || 'none'}{user.trial_ends_at ? ` · trial ends ${user.trial_ends_at}` : ''}</small>
                </div>
                <strong>{user.tier_label}</strong>
                <select disabled={busy} value={user.tier} onChange={(event) => updateUserTier(user, event.target.value as TierName)}>
                  {TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </article>
            ))}
          </div>

          <details>
            <summary>Manual update by user ID</summary>
            <form onSubmit={saveManualTier}>
              <label>User ID<input value={manualOwnerId} onChange={(event) => setManualOwnerId(event.target.value)} placeholder="Supabase user id" /></label>
              <label>Email<input value={manualEmail} onChange={(event) => setManualEmail(event.target.value)} placeholder="optional email" /></label>
              <label>Tier<select value={manualTier} onChange={(event) => setManualTier(event.target.value as TierName)}>{TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <button disabled={busy || !manualOwnerId.trim()} type="submit">Set tier manually</button>
            </form>
          </details>
        </section>
      )}
      {message && <p className="muted">{message}</p>}
    </main>
  );
}
