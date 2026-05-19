'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AccountProfile, MeResponse, TierName, UserProfile, deleteAdminUser, getAnonymousAccountProfile, inviteAdminUser, getMe, listAdminUsers, setAccessToken, setAccountProfile, setAdminUserTier } from '../../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, profileFromSession, signInWithEmailPassword, signInWithGoogle, signOut } from '../../lib/auth';

const TIER_OPTIONS = [
  { value: 'free', label: 'Free' },
  { value: 'pro', label: 'Pro' },
  { value: 'researcher', label: 'Researcher / Journalist' },
] as const;

function tierLabel(tier: TierName) {
  return TIER_OPTIONS.find((item) => item.value === tier)?.label || tier;
}

function statusTone(message: string) {
  const text = message.toLowerCase();
  if (!message) return '';
  if (text.includes('could not') || text.includes('failed') || text.includes('required') || text.includes('not configured')) return 'bad';
  if (text.includes('deleted')) return 'mixed';
  return 'good';
}

export default function AdminPage() {
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [manualOwnerId, setManualOwnerId] = useState('');
  const [manualEmail, setManualEmail] = useState('');
  const [manualTier, setManualTier] = useState<TierName>('free');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteTier, setInviteTier] = useState<TierName>('free');
  const [sendInvite, setSendInvite] = useState(true);
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

  async function deleteUser(user: UserProfile) {
    const label = user.email || user.owner_id;
    const confirmed = window.confirm(`Delete Evidrai profile for ${label}? This removes permissions/profile data only. The Supabase auth account is not deleted, and the user will reappear as Free if they sign in again.`);
    if (!confirmed) return;
    setBusy(true);
    setMessage('');
    try {
      const payload = await deleteAdminUser(user.owner_id);
      setUsers((current) => current.filter((item) => item.owner_id !== user.owner_id));
      setMessage(payload.deleted ? `Deleted profile for ${label}.` : `No profile existed for ${label}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not delete user profile.');
    } finally {
      setBusy(false);
    }
  }


  async function inviteUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const payload = await inviteAdminUser({ email: inviteEmail.trim(), tier: inviteTier, send_invite: sendInvite });
      setMessage(payload.message || `Created ${payload.email}.`);
      setInviteEmail('');
      setInviteTier('free');
      setSendInvite(true);
      await loadUsers();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not create or invite user.');
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
          <p className="lead">Manage product access without confusing customer tiers with admin rights. Users stay on Free, Pro, or Researcher / Journalist; admin access is separate and controlled server-side.</p>
        </div>
        <div className="statusPanel">
          <span>Account: {account?.label || 'checking...'}</span>
          <span>Product plan: {me?.user?.tier_label || 'not signed in'}</span>
          <span>Admin access: {isAdmin ? 'enabled' : 'not enabled'}</span>
          {isAdmin && <a href="/admin/trust/analytics">Trust analytics</a>}
          <a href="/">Back to product</a>
        </div>
      </section>

      {!isAdmin ? (
        <section className="card loginGate">
          <h2>Admin access required</h2>
          <p className="muted">Sign in with a server-authorised admin account. Product tiers do not grant admin access.</p>
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
              <h2>User access</h2>
              <p className="muted">{filteredUsers.length} shown · {users.length} total · product tiers only</p>
            </div>
            <div className="formRow compactActions">
              <button className="secondary" disabled={busy} onClick={loadUsers} type="button">Reload</button>
              <button className="secondary" disabled={busy} onClick={handleSignOut} type="button">Sign out</button>
            </div>
          </div>

          <section className="adminStats" aria-label="User summary">
            <div><span>Total users</span><strong>{users.length}</strong></div>
            <div><span>Free</span><strong>{users.filter((user) => user.tier === 'free').length}</strong></div>
            <div><span>Pro</span><strong>{users.filter((user) => user.tier === 'pro').length}</strong></div>
            <div><span>Researcher</span><strong>{users.filter((user) => user.tier === 'researcher').length}</strong></div>
          </section>

          <section className="adminGuardRails" aria-label="Admin guardrails">
            <div><strong>Product tiers</strong><span>Free, Pro, and Researcher / Journalist control user-facing limits.</span></div>
            <div><strong>Admin access</strong><span>Separate server-side permission. It is not a plan and cannot be granted here.</span></div>
            <div><strong>Secrets</strong><span>Service-role credentials stay on the backend only.</span></div>
          </section>

          <details open className="adminInviteBox">
            <summary><span>Invite or create user</span><small>Create auth access and assign an initial product tier</small></summary>
            <form onSubmit={inviteUser}>
              <label>User email<input value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} type="email" placeholder="new.user@example.com" /></label>
              <label>Initial product tier<select value={inviteTier} onChange={(event) => setInviteTier(event.target.value as TierName)}>{TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label className="checkPill"><input checked={sendInvite} onChange={(event) => setSendInvite(event.target.checked)} type="checkbox" /> Send invite email</label>
              <button disabled={busy || !inviteEmail.trim()} type="submit">{sendInvite ? 'Create user and send invite' : 'Create user without email'}</button>
            </form>
            <p className="muted">Runs through the backend admin API. The service-role key stays on Render and is never exposed to the browser.</p>
          </details>

          <label>
            Search users
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search email, user ID, product tier, subscription..." />
          </label>

          <div className="adminUserTable">
            <div className="adminUserHeader">
              <strong>User</strong>
              <strong>Product tier</strong>
              <strong>Change tier</strong>
              <strong>Profile</strong>
            </div>
            {filteredUsers.length === 0 ? <p className="muted">No users found. Users appear here after sign-in, invite creation, or profile creation by the API.</p> : filteredUsers.map((user) => (
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
                <button className="danger" disabled={busy || user.owner_id === account?.owner_id} onClick={() => deleteUser(user)} type="button">Delete</button>
              </article>
            ))}
          </div>

          <details>
            <summary><span>Manual update by user ID</span><small>Fallback for repairing a specific profile</small></summary>
            <form onSubmit={saveManualTier}>
              <label>User ID<input value={manualOwnerId} onChange={(event) => setManualOwnerId(event.target.value)} placeholder="Supabase user id" /></label>
              <label>Email<input value={manualEmail} onChange={(event) => setManualEmail(event.target.value)} placeholder="optional email" /></label>
              <label>Product tier<select value={manualTier} onChange={(event) => setManualTier(event.target.value as TierName)}>{TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <button disabled={busy || !manualOwnerId.trim()} type="submit">Set product tier manually</button>
            </form>
          </details>
        </section>
      )}
      {message && <p className={`adminMessage ${statusTone(message)}`}>{message}</p>}
    </main>
  );
}
