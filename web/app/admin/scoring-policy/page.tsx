"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  AccountProfile,
  MeResponse,
  ScoringPolicy,
  getAdminScoringPolicy,
  getAnonymousAccountProfile,
  getMe,
  setAccessToken,
  setAccountProfile,
  updateAdminScoringPolicy,
} from "../../../lib/api";
import {
  authConfigured,
  getCurrentSession,
  onAuthStateChange,
  profileFromSession,
  signInWithEmailPassword,
  signInWithGoogle,
  signOut,
} from "../../../lib/auth";

const WEIGHT_KEYS = [
  "authority",
  "relevance",
  "directness",
  "independence",
  "recency",
  "bias_risk",
] as const;
const SOURCE_TYPE_KEYS = [
  "scientific",
  "government",
  "legal",
  "primary",
  "news",
  "secondary",
  "contextual",
] as const;

const WEIGHT_EXPLANATIONS: Record<(typeof WEIGHT_KEYS)[number], string> = {
  authority:
    "Baseline trust in the source type for this claim. Higher means the source is likely authoritative before claim-fit adjustments.",
  relevance:
    "How closely the source text matches the specific claim, based on term overlap and claim focus.",
  directness:
    "How close the source is to underlying evidence. Original records and direct evidence should beat commentary.",
  independence:
    "Whether the source adds a separate evidence chain rather than repeating the same article, briefing, or wire copy.",
  recency:
    "How temporally appropriate the source is. Newer helps current claims; historical claims may still need old primary records.",
  bias_risk:
    "Raw bias/incentive risk. This is inverted in the score, so lower risk increases the final source score.",
};

const SOURCE_TYPE_EXPLANATIONS: Record<
  (typeof SOURCE_TYPE_KEYS)[number],
  string
> = {
  scientific:
    "Recognised scientific, medical, research, standards, or peer-review/preprint domains such as NIH, WHO, Nature, Science, Lancet, NEJM, arXiv, medRxiv, and bioRxiv.",
  government:
    "Official government, public agency, statistics, health-service, or intergovernmental domains such as .gov, .gouv.fr, NHS, or OECD.",
  legal:
    "Legislation, parliament, court, judiciary, justice, or official legal-publication domains such as legislation.gov.uk or EUR-Lex.",
  primary:
    "Direct original evidence: filings, transcripts, datasets, recordings, source documents, or known counterexample records. Currently mostly reserved for explicitly identified records, not generic web domains.",
  news: "Recognised news publishers and wire/reporting outlets. Useful, but scored more cautiously because editorial framing and shared source chains can inflate confidence.",
  secondary:
    "Expert synthesis or reputable non-primary analysis that is not raw evidence. Kept for compatibility and future specialist classifiers; deterministic domain matching mostly uses news/contextual today.",
  contextual:
    "Default fallback for sources that do not match a recognised scientific, government, legal, or news domain. Can still be useful, but starts with lower priors.",
};

function statusTone(message: string) {
  const text = message.toLowerCase();
  if (!message) return "";
  if (
    text.includes("could not") ||
    text.includes("failed") ||
    text.includes("required") ||
    text.includes("not configured") ||
    text.includes("error")
  )
    return "bad";
  return "good";
}

export default function AdminScoringPolicyPage() {
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [scoringPolicy, setScoringPolicy] = useState<ScoringPolicy | null>(
    null,
  );
  const [scoringHistory, setScoringHistory] = useState<ScoringPolicy[]>([]);
  const [scoringDraft, setScoringDraft] = useState<ScoringPolicy | null>(null);
  const [scoringChangeNote, setScoringChangeNote] = useState("");

  const isAdmin = Boolean(me?.is_admin);
  const draftWeightSum = scoringDraft
    ? WEIGHT_KEYS.reduce(
        (sum, key) => sum + Number(scoringDraft.source_score_weights[key] || 0),
        0,
      )
    : 0;

  async function refreshMe() {
    const payload = await getMe();
    setMe(payload);
    setAccount((current) =>
      current ? { ...current, plan: payload.user.tier_label } : current,
    );
  }

  async function loadScoringPolicy() {
    setBusy(true);
    setMessage("");
    try {
      const payload = await getAdminScoringPolicy();
      setScoringPolicy(payload.policy);
      setScoringDraft(payload.policy);
      setScoringHistory(payload.history || []);
      setMessage(`Loaded scoring policy v${payload.policy.version}.`);
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Could not load scoring policy.",
      );
    } finally {
      setBusy(false);
    }
  }

  function updateScoringDraft(
    section:
      | "source_score_weights"
      | "source_type_authority"
      | "source_type_independence"
      | "source_type_bias_risk",
    key: string,
    value: string,
  ) {
    const numeric = Number(value);
    setScoringDraft((current) =>
      current
        ? {
            ...current,
            [section]: {
              ...current[section],
              [key]: Number.isFinite(numeric) ? numeric : 0,
            },
          }
        : current,
    );
  }

  async function saveScoringPolicy() {
    if (!scoringDraft) return;
    if (!scoringChangeNote.trim()) {
      setMessage(
        "A change note is required so scoring changes remain auditable.",
      );
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const payload = await updateAdminScoringPolicy({
        source_score_weights: scoringDraft.source_score_weights,
        source_type_authority: scoringDraft.source_type_authority,
        source_type_independence: scoringDraft.source_type_independence,
        source_type_bias_risk: scoringDraft.source_type_bias_risk,
        notes: scoringDraft.notes,
        change_note: scoringChangeNote.trim(),
      });
      setScoringPolicy(payload.policy);
      setScoringDraft(payload.policy);
      setScoringHistory(payload.history || []);
      setScoringChangeNote("");
      setMessage(`Saved scoring policy v${payload.policy.version}.`);
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Could not save scoring policy.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const session = await signInWithEmailPassword(email.trim(), password);
      setAccessToken(session?.access_token || "");
      await refreshMe();
      setMessage("Signed in.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function googleSignIn() {
    setBusy(true);
    setMessage("");
    try {
      await signInWithGoogle();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Google sign-in failed.");
      setBusy(false);
    }
  }

  async function handleSignOut() {
    setBusy(true);
    setMessage("");
    try {
      await signOut();
      setMe(null);
      setScoringPolicy(null);
      setScoringDraft(null);
      setScoringHistory([]);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sign-out failed.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const fallback = getAnonymousAccountProfile();
    setAccount(fallback);
    getCurrentSession()
      .then(async (session) => {
        setAccessToken(session?.access_token || "");
        const profile = profileFromSession(session, fallback);
        setAccount(profile);
        setAccountProfile(profile);
        if (session) await refreshMe();
      })
      .catch((err) => setMessage(err.message));
    const unsubscribe = onAuthStateChange(async (session) => {
      setAccessToken(session?.access_token || "");
      const profile = profileFromSession(session, fallback);
      setAccount(profile);
      setAccountProfile(profile);
      if (session) await refreshMe();
      else setMe(null);
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (isAdmin) loadScoringPolicy();
  }, [isAdmin]);

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">Evidrai Admin</p>
          <h1>Scoring policy</h1>
          <p className="lead">
            Tune source weights, source-type priors, and methodology notes with
            a versioned audit trail.
          </p>
        </div>
        <div className="statusPanel">
          <span>Account: {account?.label || "checking..."}</span>
          <span>Product plan: {me?.user?.tier_label || "not signed in"}</span>
          <span>Admin access: {isAdmin ? "enabled" : "not enabled"}</span>
          {isAdmin && <a href="/admin">User management</a>}
          {isAdmin && <a href="/admin/trust/analytics">Trust analytics</a>}
          <a href="/">Back to product</a>
        </div>
      </section>

      {!isAdmin ? (
        <section className="card loginGate">
          <h2>Admin access required</h2>
          <p className="muted">
            Sign in with a server-authorised admin account. Product tiers do not
            grant admin access.
          </p>
          {authConfigured() ? (
            <div className="authActions">
              <button disabled={busy} onClick={googleSignIn} type="button">
                Continue with Google
              </button>
              <form className="emailLogin" onSubmit={signIn}>
                <label>
                  Email
                  <input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    type="email"
                    placeholder="admin@example.com"
                  />
                </label>
                <label>
                  Password
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    type="password"
                    placeholder="Password"
                  />
                </label>
                <button
                  className="secondary"
                  disabled={busy || !email.trim() || password.length < 6}
                  type="submit"
                >
                  Sign in
                </button>
              </form>
            </div>
          ) : (
            <p className="error">Authentication is not configured.</p>
          )}
        </section>
      ) : (
        <section className="card adminPanel scoringPolicyEditor">
          <div className="sectionHeader">
            <div>
              <h2>Source scoring controls</h2>
              <p className="muted">
                Current policy v
                {scoringPolicy?.version || scoringDraft?.version || "—"} ·
                changes require a note.
              </p>
            </div>
            <div className="formRow compactActions">
              <button
                className="secondary"
                disabled={busy}
                onClick={loadScoringPolicy}
                type="button"
              >
                Reload
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={handleSignOut}
                type="button"
              >
                Sign out
              </button>
            </div>
          </div>

          {!scoringDraft ? (
            <div className="formRow compactActions">
              <button
                className="secondary"
                disabled={busy}
                onClick={loadScoringPolicy}
                type="button"
              >
                Load scoring policy
              </button>
            </div>
          ) : (
            <>
              <div
                className="adminGuardRails"
                aria-label="Scoring policy summary"
              >
                <div>
                  <strong>Active version</strong>
                  <span>
                    v{scoringPolicy?.version || scoringDraft.version} ·{" "}
                    {scoringPolicy?.updated_by || scoringDraft.updated_by}
                  </span>
                </div>
                <div>
                  <strong>Weight total</strong>
                  <span
                    className={
                      Math.abs(draftWeightSum - 1) < 0.001 ? "" : "warningText"
                    }
                  >
                    {draftWeightSum.toFixed(2)} target 1.00
                  </span>
                </div>
                <div>
                  <strong>Bias rule</strong>
                  <span>
                    Bias risk is inverted in scoring, so lower bias risk
                    increases trust.
                  </span>
                </div>
              </div>
              <div className="scoringExplainer">
                <strong>How source categories are determined</strong>
                <p>
                  Classification starts from the source domain using curated
                  allowlists in <code>evidrai/utils.py</code>. Scientific,
                  legal, and government checks run before news checks. If no
                  recognised domain matches, the source is treated as
                  contextual. “Primary” is reserved for direct records or
                  explicitly identified source documents, not ordinary news or
                  commentary.
                </p>
              </div>
              <div
                className="sourceTypeGuide"
                aria-label="Source type definitions"
              >
                {SOURCE_TYPE_KEYS.map((key) => (
                  <div key={key}>
                    <strong>{key}</strong>
                    <span>{SOURCE_TYPE_EXPLANATIONS[key]}</span>
                  </div>
                ))}
              </div>
              <div className="scoringGrid">
                <section>
                  <h3>Factor weights</h3>
                  {WEIGHT_KEYS.map((key) => (
                    <label key={key} title={WEIGHT_EXPLANATIONS[key]}>
                      {key.replace("_", " ")}
                      <small>{WEIGHT_EXPLANATIONS[key]}</small>
                      <input
                        min="0"
                        max="1"
                        step="0.01"
                        type="number"
                        value={scoringDraft.source_score_weights[key] ?? 0}
                        onChange={(event) =>
                          updateScoringDraft(
                            "source_score_weights",
                            key,
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  ))}
                </section>
                <section>
                  <h3>Authority score</h3>
                  {SOURCE_TYPE_KEYS.map((key) => (
                    <label key={key} title={SOURCE_TYPE_EXPLANATIONS[key]}>
                      {key}
                      <small>{SOURCE_TYPE_EXPLANATIONS[key]}</small>
                      <input
                        min="0"
                        max="5"
                        step="0.1"
                        type="number"
                        value={scoringDraft.source_type_authority[key] ?? 0}
                        onChange={(event) =>
                          updateScoringDraft(
                            "source_type_authority",
                            key,
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  ))}
                </section>
                <section>
                  <h3>Independence score</h3>
                  {SOURCE_TYPE_KEYS.map((key) => (
                    <label key={key} title={SOURCE_TYPE_EXPLANATIONS[key]}>
                      {key}
                      <small>{SOURCE_TYPE_EXPLANATIONS[key]}</small>
                      <input
                        min="0"
                        max="5"
                        step="0.1"
                        type="number"
                        value={scoringDraft.source_type_independence[key] ?? 0}
                        onChange={(event) =>
                          updateScoringDraft(
                            "source_type_independence",
                            key,
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  ))}
                </section>
                <section>
                  <h3>Bias risk</h3>
                  {SOURCE_TYPE_KEYS.map((key) => (
                    <label key={key} title={SOURCE_TYPE_EXPLANATIONS[key]}>
                      {key}
                      <small>{SOURCE_TYPE_EXPLANATIONS[key]}</small>
                      <input
                        min="0"
                        max="5"
                        step="0.1"
                        type="number"
                        value={scoringDraft.source_type_bias_risk[key] ?? 0}
                        onChange={(event) =>
                          updateScoringDraft(
                            "source_type_bias_risk",
                            key,
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  ))}
                </section>
              </div>
              <label className="notesField">
                Change note
                <textarea
                  value={scoringChangeNote}
                  onChange={(event) => setScoringChangeNote(event.target.value)}
                  placeholder="Why this scoring policy changed"
                />
              </label>
              <div className="formRow compactActions">
                <button
                  disabled={busy || !scoringChangeNote.trim()}
                  onClick={saveScoringPolicy}
                  type="button"
                >
                  Save scoring policy
                </button>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={loadScoringPolicy}
                  type="button"
                >
                  Reload
                </button>
              </div>
              <div className="adminIssueList scoringHistory">
                {scoringHistory.slice(0, 10).map((item) => (
                  <article key={item.version}>
                    <div>
                      <strong>v{item.version}</strong>
                      <span>
                        {item.updated_at} · {item.updated_by}
                      </span>
                    </div>
                    <p>{item.change_note || "No change note."}</p>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      )}
      {message && (
        <p className={`adminMessage ${statusTone(message)}`}>{message}</p>
      )}
    </main>
  );
}
