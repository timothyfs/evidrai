'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AccountProfile, MeResponse, SupportIssue, TierName, UserProfile, bulkAdminUsers, deleteAdminUser, getAnonymousAccountProfile, inviteAdminUser, getMe, listAdminUsers, listSupportIssues, sendAdminPasswordReset, setAccessToken, setAccountProfile, setAdminUserTier, updateAdminUserPassword, updateAdminUserProfile, resendAdminInvite } from '../../lib/api';
import { authConfigured, getCurrentSession, onAuthStateChange, profileFromSession, signInWithEmailPassword, signInWithGoogle, signOut } from '../../lib/auth';

const TIER_OPTIONS = [
  { value: 'free', label: 'Free' },
  { value: 'pro', label: 'Pro' },
  { value: 'researcher', label: 'Researcher / Journalist' },
] as const;

const ADMIN_COLUMNS = [
  { key: 'selected', label: '' },
  { key: 'email', label: 'User' },
  { key: 'company_name', label: 'Company / organisation' },
  { key: 'billing_account_name', label: 'Billing group' },
  { key: 'tier_label', label: 'Product tier' },
  { key: 'admin_access', label: 'Admin access' },
  { key: 'subscription_status', label: 'Subscription' },
  { key: 'actions', label: 'Actions' },
] as const;

type AdminColumnKey = typeof ADMIN_COLUMNS[number]['key'];
type SortKey = Exclude<AdminColumnKey, 'selected' | 'actions'>;
type SortState = { key: SortKey; direction: 'asc' | 'desc' };
type Filters = Partial<Record<SortKey, string>>;

const sortableColumns = new Set<AdminColumnKey>(['email', 'company_name', 'billing_account_name', 'tier_label', 'admin_access', 'subscription_status']);

function valueFor(user: UserProfile, key: SortKey) {
  if (key === 'admin_access') return user.admin_access ? 'enabled' : 'none';
  if (key === 'company_name') return user.company_name || user.organisation_name || '';
  return String(user[key as keyof UserProfile] || '');
}

function statusTone(message: string) {
  const text = message.toLowerCase();
  if (!message) return '';
  if (text.includes('could not') || text.includes('failed') || text.includes('required') || text.includes('not configured') || text.includes('error')) return 'bad';
  if (text.includes('deleted')) return 'mixed';
  return 'good';
}

function blankDetails(user?: UserProfile) {
  return {
    email: user?.email || '',
    company_name: user?.company_name || '',
    organisation_name: user?.organisation_name || '',
    billing_account_name: user?.billing_account_name || '',
    billing_account_id: user?.billing_account_id || '',
    admin_notes: user?.admin_notes || '',
  };
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
  const [globalSearch, setGlobalSearch] = useState('');
  const [filters, setFilters] = useState<Filters>({});
  const [sort, setSort] = useState<SortState>({ key: 'email', direction: 'asc' });
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkTier, setBulkTier] = useState<TierName>('pro');
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [supportIssues, setSupportIssues] = useState<SupportIssue[]>([]);
  const [editing, setEditing] = useState<string>('');
  const [details, setDetails] = useState<Record<string, ReturnType<typeof blankDetails>>>({});
  const [tempPasswords, setTempPasswords] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const isAdmin = Boolean(me?.is_admin);

  const filteredUsers = useMemo(() => {
    const query = globalSearch.trim().toLowerCase();
    const next = users.filter((user) => {
      const globalMatch = !query || [user.email, user.owner_id, user.tier_label, user.subscription_status, user.company_name, user.organisation_name, user.billing_account_name, user.billing_account_id, user.admin_access ? 'admin enabled' : 'admin none']
        .some((value) => String(value || '').toLowerCase().includes(query));
      const columnMatch = (Object.entries(filters) as Array<[SortKey, string]>).every(([key, filter]) => {
        const clean = filter.trim().toLowerCase();
        return !clean || valueFor(user, key).toLowerCase().includes(clean);
      });
      return globalMatch && columnMatch;
    });
    return [...next].sort((a, b) => {
      const left = valueFor(a, sort.key).toLowerCase();
      const right = valueFor(b, sort.key).toLowerCase();
      const result = left.localeCompare(right);
      return sort.direction === 'asc' ? result : -result;
    });
  }, [users, globalSearch, filters, sort]);

  const selectedUsers = selected.map((ownerId) => users.find((user) => user.owner_id === ownerId)).filter(Boolean) as UserProfile[];
  const allVisibleSelected = filteredUsers.length > 0 && filteredUsers.every((user) => selected.includes(user.owner_id));
  const editingUser = users.find((user) => user.owner_id === editing) || null;

  async function refreshMe() {
    const payload = await getMe();
    setMe(payload);
    setAccount((current) => current ? { ...current, plan: payload.user.tier_label } : current);
  }

  async function loadSupportIssues() {
    setBusy(true);
    setMessage('');
    try {
      const payload = await listSupportIssues(25);
      setSupportIssues(payload.issues || []);
      setMessage(`Loaded ${payload.count || 0} support issues.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not load support issues.');
    } finally {
      setBusy(false);
    }
  }

  async function loadUsers() {
    setBusy(true);
    setMessage('');
    try {
      const payload = await listAdminUsers();
      setUsers(payload.users || []);
      setSelected((current) => current.filter((ownerId) => payload.users?.some((user) => user.owner_id === ownerId)));
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

  function toggleSort(key: AdminColumnKey) {
    if (!sortableColumns.has(key)) return;
    const nextKey = key as SortKey;
    setSort((current) => current.key === nextKey ? { key: nextKey, direction: current.direction === 'asc' ? 'desc' : 'asc' } : { key: nextKey, direction: 'asc' });
  }

  function toggleSelected(ownerId: string) {
    setSelected((current) => current.includes(ownerId) ? current.filter((item) => item !== ownerId) : [...current, ownerId]);
  }

  function toggleAllVisible() {
    if (allVisibleSelected) setSelected((current) => current.filter((ownerId) => !filteredUsers.some((user) => user.owner_id === ownerId)));
    else setSelected((current) => Array.from(new Set([...current, ...filteredUsers.map((user) => user.owner_id)])));
  }

  function updateLocalUser(user: UserProfile) {
    setUsers((current) => current.map((item) => item.owner_id === user.owner_id ? user : item));
  }

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
      updateLocalUser(payload.user);
      setMessage(`Updated ${payload.user.email || payload.user.owner_id} to ${payload.user.tier_label}.`);
      await refreshMe();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not update tier.');
    } finally {
      setBusy(false);
    }
  }

  async function saveUserDetails(user: UserProfile) {
    setBusy(true);
    setMessage('');
    try {
      const payload = await updateAdminUserProfile({ owner_id: user.owner_id, ...(details[user.owner_id] || blankDetails(user)) });
      updateLocalUser(payload.user);
      setEditing('');
      setMessage(`Updated profile details for ${payload.user.email || payload.user.owner_id}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not update profile details.');
    } finally {
      setBusy(false);
    }
  }

  async function sendReset(user: UserProfile) {
    if (!user.email) {
      setMessage('Cannot send password reset without an email address.');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      const payload = await sendAdminPasswordReset({ owner_id: user.owner_id, email: user.email });
      setMessage(payload.message || `Password reset sent to ${user.email}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not send password reset.');
    } finally {
      setBusy(false);
    }
  }

  async function setTemporaryPassword(user: UserProfile) {
    const nextPassword = tempPasswords[user.owner_id] || '';
    if (nextPassword.length < 8) {
      setMessage('Temporary password must be at least 8 characters.');
      return;
    }
    const confirmed = window.confirm(`Set a temporary password for ${user.email || user.owner_id}? Share it out-of-band and make them reset it.`);
    if (!confirmed) return;
    setBusy(true);
    setMessage('');
    try {
      const payload = await updateAdminUserPassword({ owner_id: user.owner_id, email: user.email, password: nextPassword });
      setTempPasswords((current) => ({ ...current, [user.owner_id]: '' }));
      setMessage(payload.message || 'Password updated.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not update password.');
    } finally {
      setBusy(false);
    }
  }

  async function resendInvite(user: UserProfile) {
    if (!user.email) {
      setMessage('Cannot resend invite without an email address.');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      const payload = await resendAdminInvite({ owner_id: user.owner_id, email: user.email });
      setMessage(payload.message || `Invite resent to ${user.email}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not resend invite.');
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
      setSelected((current) => current.filter((ownerId) => ownerId !== user.owner_id));
      setMessage(payload.deleted ? `Deleted profile for ${label}.` : `No profile existed for ${label}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not delete user profile.');
    } finally {
      setBusy(false);
    }
  }

  async function applyBulkTier() {
    if (selected.length === 0) return;
    setBusy(true);
    setMessage('');
    try {
      const payload = await bulkAdminUsers({ owner_ids: selected, action: 'set_tier', tier: bulkTier });
      if (payload.users) setUsers((current) => current.map((item) => payload.users?.find((user) => user.owner_id === item.owner_id) || item));
      setMessage(`Updated ${payload.users?.length || selected.length} users to ${TIER_OPTIONS.find((item) => item.value === bulkTier)?.label || bulkTier}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not update selected users.');
    } finally {
      setBusy(false);
    }
  }

  async function bulkDeleteProfiles() {
    if (selected.length === 0) return;
    const confirmed = window.confirm(`Delete ${selected.length} selected Evidrai profiles? Supabase auth accounts are not deleted.`);
    if (!confirmed) return;
    setBusy(true);
    setMessage('');
    try {
      const payload = await bulkAdminUsers({ owner_ids: selected, action: 'delete_profiles' });
      const deletedIds = new Set((payload.deleted || []).filter((item) => item.deleted).map((item) => item.owner_id));
      setUsers((current) => current.filter((user) => !deletedIds.has(user.owner_id)));
      setSelected([]);
      setMessage(`Deleted ${deletedIds.size} profiles.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not delete selected users.');
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
      setSelected([]);
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
          <p className="lead">Manage product access, account grouping, and operational user actions. Product tiers stay separate from server-controlled admin access.</p>
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
              <p className="muted">{filteredUsers.length} shown · {users.length} total · {selected.length} selected</p>
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
            <div><span>Companies</span><strong>{new Set(users.map((user) => user.company_name || user.organisation_name).filter(Boolean)).size}</strong></div>
            <div><span>Admins</span><strong>{users.filter((user) => user.admin_access).length}</strong></div>
          </section>

          <section className="adminGuardRails" aria-label="Admin guardrails">
            <div><strong>Product permissions</strong><span>Bulk-edit Free, Pro, and Researcher / Journalist access here.</span></div>
            <div><strong>Admin access</strong><span>Shown for visibility, but still controlled by the server allowlist.</span></div>
            <div><strong>Billing grouping</strong><span>Company and billing group fields prepare for organisation contracts and consolidated billing.</span></div>
          </section>

          <details className="adminInviteBox">
            <summary><span>Support issues</span><small>Bug and help reports submitted from the product</small></summary>
            <div className="formRow compactActions"><button className="secondary" disabled={busy} onClick={loadSupportIssues} type="button">Load latest issues</button></div>
            <div className="adminIssueList">
              {supportIssues.length === 0 ? <p className="muted">No support issues loaded.</p> : supportIssues.map((issue) => {
                const support = issue.assessment_output?.support_issue || {};
                return (
                  <article key={issue.feedback_id || issue.issue_id}>
                    <div><strong>{support.subject || issue.comment || 'Untitled issue'}</strong><span>{support.issue_type || 'issue'} · {support.severity || 'normal'} · {issue.captured_at || ''}</span></div>
                    <p>{support.description || issue.comment}</p>
                    <small>{support.page_url || issue.source_url || 'No page URL'}{issue.owner_id ? ` · ${issue.owner_id}` : ''}</small>
                  </article>
                );
              })}
            </div>
          </details>

          <details open className="adminInviteBox">
            <summary><span>Invite or create user</span><small>Create auth access and assign an initial product tier</small></summary>
            <form onSubmit={inviteUser}>
              <label>User email<input value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} type="email" placeholder="new.user@example.com" /></label>
              <label>Initial product tier<select value={inviteTier} onChange={(event) => setInviteTier(event.target.value as TierName)}>{TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label className="checkPill"><input checked={sendInvite} onChange={(event) => setSendInvite(event.target.checked)} type="checkbox" /> Send invite email</label>
              <button disabled={busy || !inviteEmail.trim()} type="submit">{sendInvite ? 'Create user and send invite' : 'Create user without email'}</button>
            </form>
          </details>

          <section className="adminToolbar">
            <label>Global search<input value={globalSearch} onChange={(event) => setGlobalSearch(event.target.value)} placeholder="Search across users, company, billing group, tier..." /></label>
            <div className="bulkActions">
              <label>Bulk tier<select disabled={busy || selected.length === 0} value={bulkTier} onChange={(event) => setBulkTier(event.target.value as TierName)}>{TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <button className="secondary" disabled={busy || selected.length === 0} onClick={applyBulkTier} type="button">Apply to selected</button>
              <button className="danger" disabled={busy || selected.length === 0} onClick={bulkDeleteProfiles} type="button">Delete selected profiles</button>
            </div>
          </section>

          <div className="adminUserTable scalable">
            <div className="adminUserHeader scalable">
              {ADMIN_COLUMNS.map((column) => (
                <strong key={column.key}>
                  {column.key === 'selected' ? <input checked={allVisibleSelected} onChange={toggleAllVisible} type="checkbox" aria-label="Select all visible users" /> : (
                    <button className="columnHeaderButton" disabled={!sortableColumns.has(column.key)} onClick={() => toggleSort(column.key)} type="button">
                      {column.label}{sort.key === column.key ? (sort.direction === 'asc' ? ' ↑' : ' ↓') : ''}
                    </button>
                  )}
                </strong>
              ))}
              <span />
              {ADMIN_COLUMNS.map((column) => (
                <span key={`${column.key}-filter`}>
                  {sortableColumns.has(column.key) && <input value={filters[column.key as SortKey] || ''} onChange={(event) => setFilters((current) => ({ ...current, [column.key]: event.target.value }))} placeholder={`Filter ${column.label.toLowerCase()}`} />}
                </span>
              ))}
            </div>

            {filteredUsers.length === 0 ? <p className="muted">No users found. Users appear here after sign-in, invite creation, or profile creation by the API.</p> : filteredUsers.map((user) => {
              return (
                <article className="adminUserRow scalable" key={user.owner_id}>
                  <input checked={selected.includes(user.owner_id)} onChange={() => toggleSelected(user.owner_id)} type="checkbox" aria-label={`Select ${user.email || user.owner_id}`} />
                  <div>
                    <strong>{user.email || 'No email captured'}</strong>
                    <small>{user.owner_id}</small>
                  </div>
                  <div><strong>{user.company_name || user.organisation_name || '—'}</strong><small>{user.organisation_name || user.company_name || 'No organisation set'}</small></div>
                  <div><strong>{user.billing_account_name || '—'}</strong><small>{user.billing_account_id || 'No billing account ID'}</small></div>
                  <select disabled={busy} value={user.tier} onChange={(event) => updateUserTier(user, event.target.value as TierName)}>
                    {TIER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                  <div className={user.admin_access ? 'adminAccessBadge enabled' : 'adminAccessBadge'}><strong>{user.admin_access ? 'Enabled' : 'None'}</strong><small>{user.admin_access ? 'Allowlist' : 'Not admin'}</small></div>
                  <small>{user.subscription_status || 'none'}{user.trial_ends_at ? ` · trial ends ${user.trial_ends_at}` : ''}</small>
                  <select className="rowActionSelect" disabled={busy} value="" aria-label={`Actions for ${user.email || user.owner_id}`} onChange={(event) => {
                    const action = event.target.value;
                    event.target.value = '';
                    if (action === 'details') {
                      setEditing(editing === user.owner_id ? '' : user.owner_id);
                      setDetails((current) => ({ ...current, [user.owner_id]: current[user.owner_id] || blankDetails(user) }));
                    }
                    if (action === 'reset') sendReset(user);
                    if (action === 'invite') resendInvite(user);
                    if (action === 'delete') deleteUser(user);
                  }}>
                    <option value="">Actions…</option>
                    <option value="details">Edit details</option>
                    <option disabled={!user.email} value="reset">Send password reset</option>
                    <option disabled={!user.email} value="invite">Resend invite</option>
                    <option disabled={user.owner_id === account?.owner_id} value="delete">Delete profile</option>
                  </select>
                </article>
              );
            })}
          </div>

          {editingUser && (() => {
            const edit = details[editingUser.owner_id] || blankDetails(editingUser);
            return (
              <section className="adminUserDetailsEditor" aria-label="Edit user details">
                <div className="editorHeader">
                  <div>
                    <strong>Edit details</strong>
                    <small>{editingUser.email || editingUser.owner_id}</small>
                  </div>
                  <button className="secondary" disabled={busy} onClick={() => setEditing('')} type="button">Close</button>
                </div>
                <label>Email<input value={edit.email} onChange={(event) => setDetails((current) => ({ ...current, [editingUser.owner_id]: { ...edit, email: event.target.value } }))} /></label>
                <label>Company name<input value={edit.company_name} onChange={(event) => setDetails((current) => ({ ...current, [editingUser.owner_id]: { ...edit, company_name: event.target.value } }))} /></label>
                <label>Organisation name<input value={edit.organisation_name} onChange={(event) => setDetails((current) => ({ ...current, [editingUser.owner_id]: { ...edit, organisation_name: event.target.value } }))} /></label>
                <label>Billing account name<input value={edit.billing_account_name} onChange={(event) => setDetails((current) => ({ ...current, [editingUser.owner_id]: { ...edit, billing_account_name: event.target.value } }))} /></label>
                <label>Billing account ID<input value={edit.billing_account_id} onChange={(event) => setDetails((current) => ({ ...current, [editingUser.owner_id]: { ...edit, billing_account_id: event.target.value } }))} /></label>
                <label>Temporary password<input value={tempPasswords[editingUser.owner_id] || ''} onChange={(event) => setTempPasswords((current) => ({ ...current, [editingUser.owner_id]: event.target.value }))} type="password" placeholder="Set temporary password" /></label>
                <label className="notesField">Admin notes<textarea value={edit.admin_notes} onChange={(event) => setDetails((current) => ({ ...current, [editingUser.owner_id]: { ...edit, admin_notes: event.target.value } }))} /></label>
                <div className="rowActions wide">
                  <button disabled={busy} onClick={() => saveUserDetails(editingUser)} type="button">Save details</button>
                  <button className="secondary" disabled={busy || (tempPasswords[editingUser.owner_id] || '').length < 8} onClick={() => setTemporaryPassword(editingUser)} type="button">Set temporary password</button>
                </div>
              </section>
            );
          })()}

          <details>
            <summary><span>Manual update by user ID</span><small>Fallback for repairing a specific product-tier profile</small></summary>
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
