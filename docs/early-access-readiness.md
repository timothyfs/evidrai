# Evidrai Early Access Readiness

Date: 2026-05-19  
Status: Active readiness checklist  
Owner: Tim / Monty  
Stage: Controlled early access, not prototype

## 1. Stage decision

Evidrai has moved beyond prototype. The current product has enough live plumbing to be treated as **controlled early access**:

- standalone web UI
- login/account model
- admin and tier management
- persisted reports
- feedback capture
- single-claim verification
- two-stage speech/video workflow
- evidence scorecards and source scoring
- backend API boundary
- architecture and API documentation

The operating question changes from “does this prototype work?” to:

> Can selected users use Evidrai reliably, understand its limits, and give useful feedback without being misled about unfinished capability?

## 2. Early access positioning

Recommended external language:

- “Early access”
- “Invite-only”
- “Evidence assessment for claims, articles, and speech/video transcripts”
- “Built to separate evidence from repetition”
- “Known limitations are visible and actively being worked through”

Avoid:

- “prototype” for invited users unless explaining history
- “production-grade investigative platform”
- “fully automated fact-checking”
- “guaranteed YouTube analysis”
- any claim that Researcher / Journalist includes complete ledger, snapshots, API, or export workflows until those are actually implemented

## 3. Current feature reality by tier

This section compares currently listed features in `evidrai/entitlements.py` and `/plans` with implemented product capability.

### 3.1 Free

Listed features:

- Fast claim checks
- Feedback
- limited saved report history

Readiness: **Mostly ready**

Implemented:

- Fast claim assessment endpoint and UI
- login-gated Verify UI
- feedback capture linked to assessment IDs
- report storage/listing/loading
- report limit exposed in tier metadata

Gaps / risks:

- usage counting and monthly enforcement are not implemented yet
- saved-report limit is advertised in metadata but not enforced in storage layer
- onboarding copy should be explicit that Free is for lightweight evaluation

Early access decision:

- Safe to offer to invited users.
- Do not imply hard monthly quota enforcement until quota tracking exists.

### 3.2 Pro

Listed features:

- Fast claim checks
- Deep claim checks
- Speech/video audit
- Feedback
- Shareable reports
- Exports
- higher saved report and usage limits

Readiness: **Partially ready**

Implemented:

- Deep verification endpoint and UI path when entitlement allows it
- speech/video two-stage flow: extract claims, select claims, verify selected claims
- persisted reports for single claims and verified speech claims
- feedback capture
- evidence scorecard UI

Gaps / risks:

- shareable reports are listed but no stable public/share endpoint exists
- exports are listed but there is no polished user-facing export workflow in the web UI
- monthly usage limits are listed but not enforced
- speech/video depends on transcript availability; YouTube URL extraction remains best-effort
- deep mode depends on backend Tavily configuration

Early access decision:

- Pro can be used for internal/invite-only testing.
- Plans page should not over-promise “Shareable reports” or “Exports” as finished features unless those are either hidden, labelled “coming soon”, or implemented.

### 3.3 Researcher / Journalist

Listed features:

- Fast claim checks
- Deep claim checks
- Speech/video audit
- Feedback
- Shareable reports
- Exports
- Evidence ledger
- Source snapshots
- API access
- high saved report and usage limits

Readiness: **Not ready as currently described**

Implemented:

- higher tier exists in auth/profile/admin model
- master admin users are upgraded to this tier
- higher limits are exposed in `/me` and `/tiers`
- core assessment payload contains evidence/source detail that could become a ledger
- architecture/API docs exist for implementation and internal use

Material gaps:

- Evidence ledger is not a separate product workflow or queryable evidence table yet
- Source snapshots are not captured as durable, immutable source snapshots
- API access is documented, but not productised with API keys, external auth, rate limits, developer onboarding, or external terms
- Exports are not polished as a user-facing Researcher / Journalist capability
- Share/report workflow is not fully implemented
- higher monthly limits are not enforced by a quota system

Early access decision:

- Keep the tier for Tim/admin/test users.
- For external users, describe it as **Researcher / Journalist preview** or hide unfinished feature claims.
- Do not advertise ledger, source snapshots, or API access as live customer capabilities until implemented or clearly labelled “coming soon”.

## 4. Feature readiness table

| Capability | Current status | Early access action |
|---|---:|---|
| Login / account identity | Ready enough | Test Google/email flows on production |
| Admin user/tier management | Ready enough | Keep admin-only; verify master admin behaviour |
| Fast claim checks | Ready enough | Add smoke tests with known claims |
| Deep claim checks | Ready if Tavily configured | Confirm Render env and production response |
| URL/article extraction | Partial | Keep as supported but imperfect; track failures |
| YouTube URL transcript extraction | Partial / best-effort | Label clearly; pasted transcript is fallback |
| Pasted transcript speech audit | Ready enough | Add early access test script |
| Speech claim selection | Ready enough | Validate mobile UX |
| Saved reports | Ready enough | Confirm per-user report loading |
| Report sharing | Gap | Implement or remove from live plan copy |
| Export workflow | Gap / internal only | Implement web export button or mark coming soon |
| Feedback capture | Ready enough | Add review process for feedback triage |
| Evidence ledger | Gap | Define v1 ledger model before marketing it |
| Source snapshots | Gap | Define source snapshot table/storage before marketing it |
| API access | Internal only | Productise API keys/rate limits/docs before external claim |
| Monthly quotas/limits | Gap | Implement usage counters or avoid precise quota promises |
| Mobile UI | Improving | Continue reducing clutter; reports now separated on mobile |
| Release notes | Gap | Add simple public/internal release notes |
| Known limitations | Gap | Add visible early-access limitations page/section |

## 5. Required early access workstreams

### A. Product truth / plan cleanup

Goal: align what the product says with what it actually does.

Tasks:

1. Update Plans page so unfinished capabilities are labelled “coming soon” or hidden.
2. Split Researcher / Journalist into:
   - available now: higher limits, speech/video, deep verification, saved reports
   - coming soon: evidence ledger, source snapshots, API access, polished exports
3. Add early-access limitation copy for YouTube extraction, quotas, and evidence interpretation.
4. Avoid “admin” as a customer-facing tier.

Acceptance criteria:

- No plan card implies a missing capability is live.
- Researcher / Journalist remains attractive without overclaiming.
- Early access users understand pasted transcript is the reliable speech/video path.

### B. Feature verification matrix

Goal: prove listed features work on deployed Vercel + Render, not just locally.

Tasks:

1. Create smoke-test script for production API endpoints:
   - `/runtime`
   - `/tiers`
   - `/me`
   - `/assessments/fast`
   - `/assessments/deep`
   - `/speech/extract`
   - `/speech/verify`
   - `/reports`
2. Test with at least one user per tier.
3. Record actual results in a readiness log.
4. Check mobile browser layout on iPhone-sized viewport.

Acceptance criteria:

- Every feature visible in the UI has a passing production smoke test or is labelled as not ready.
- Researcher / Journalist gaps are explicitly tracked.

### C. Researcher / Journalist capability build-out

Goal: make the top tier real rather than aspirational.

MVP options:

1. **Evidence ledger v1**
   - Add queryable evidence/source records derived from `AssessmentResponse.sources`.
   - Store source role, stance, score, domain, title, URL, assessment ID, and timestamp.
   - Add simple UI tab/section: “Evidence ledger”.

2. **Source snapshots v1**
   - Store fetched article excerpt/raw text hash at assessment time.
   - Preserve retrieval timestamp and extraction metadata.
   - Show “snapshot captured” when available.

3. **Exports v1**
   - Add JSON export from saved report in web UI.
   - Add Markdown summary export for journalist/researcher workflow.

4. **API access v1**
   - Do not expose broadly yet.
   - First implement API keys, usage logging, and rate limit guardrails.

Recommended sequence:

1. Exports v1
2. Evidence ledger v1
3. Source snapshots v1
4. API access v1

Exports are the fastest useful Researcher / Journalist win.

### D. Early access onboarding

Tasks:

1. Create a short invite/onboarding message.
2. Create a “how to test” guide:
   - one normal claim
   - one article URL
   - one pasted transcript
   - one YouTube URL, with caveat
3. Create feedback prompts:
   - Did the verdict make sense?
   - Did the evidence feel trustworthy?
   - Was anything overconfident?
   - What would stop you using this?
4. Create release notes for early access users.

Acceptance criteria:

- A user can be invited without Tim needing to explain the whole product manually.
- Feedback arrives in a format that can become tasks/regression tests.

### E. Operational readiness

Tasks:

1. Confirm production deploy status after every push.
2. Confirm Render backend environment variables:
   - OpenAI configured
   - Tavily configured
   - Supabase configured
   - Postgres configured
   - admin emails configured
3. Confirm no backend-only secrets exist in Vercel public env.
4. Add a simple release checklist.
5. Add a known limitations section/page.

Acceptance criteria:

- Tim can invite users with confidence that the live app matches the repo state.

### F. Admin UI scale-up

Goal: make admin usable beyond the first small early-access cohort.

Tasks:

1. Add admin user search, filtering, and pagination.
2. Add group/bulk edit flows for tier, invite resend, company assignment, and future suspend/reactivate.
3. Add support actions: update profile where safe, trigger password reset, resend confirmation/invite email, and resend welcome email.
4. Add granular customer permissions and feature flags at user/account level.
5. Introduce company/business accounts with multiple users under one billable account.
6. Wire billing state into users/company accounts, including subscription status, billing owner, trials, and payment provider IDs.
7. Add audit logging for access and billing-impacting admin actions.

Reference: `docs/admin-ui-scale-roadmap.md`.

Acceptance criteria:

- Admin can manage expanding user cohorts without scanning a flat list.
- Admin can support users without manual Supabase console work.
- Business accounts can group multiple users on one billable account.
- Billing and access state are visible, auditable, and source-of-truth-driven.

## 6. Immediate next tasks

Priority order:

1. **Fix tier feature truthfulness**
   - Update `web/app/plans/page.tsx` so Researcher / Journalist does not present ledger/snapshots/API as live unless marked coming soon.

2. **Add export v1**
   - Saved report JSON download in the web UI.
   - Optional Markdown summary export next.

3. **Add early-access limitations copy**
   - Especially YouTube best-effort extraction and quota enforcement gaps.

4. **Create production smoke checklist/script**
   - Validate deployed Vercel + Render with real auth/tier users.

5. **Define Researcher / Journalist v1 scope**
   - Exports + saved evidence records first; source snapshots/API later.

## 7. Decision log

- 2026-05-19: Tim stated Evidrai is now beyond prototype and entering early access.
- 2026-05-19: Tim flagged tier capability gaps, especially Researcher / Journalist. Decision: align plan copy and readiness work with actual implemented capability before broader invitations.
