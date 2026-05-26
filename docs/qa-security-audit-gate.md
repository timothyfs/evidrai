# QA and security audit gate

Status: mandatory release gate logged from Tim feedback on 2026-05-26.

Before Evidrai posts or promotes new code beyond controlled internal testing, run a full QA and security audit. This is a hard gate, not an optional polish task.

## Release rule

No public/early-access push should be treated as ready until:

1. automated tests pass,
2. production smoke checks pass,
3. manual QA checklist passes,
4. security checklist passes,
5. known risks are logged with owner/status,
6. any blocker-severity issues are fixed or explicitly accepted by Tim.

## QA scope

### Core product flows

- Sign up with independent email.
- Sign in with email/password.
- Sign in with Google.
- Password reset flow.
- Turnstile appears only when needed and does not persist noisily.
- Fast assessment completes.
- Deep assessment completes for entitled user.
- Fast mode hides redundant evidence scorecard.
- Detail mode shows evidence score or diagnostic if missing.
- Evidence sections are collapsed by default.
- Source cards open in new tabs and keep result tab intact.
- Saved reports appear in account history.
- Report reload by ID works for owner.
- Cross-account report access is blocked.
- Share links work at expected access level.
- Speech/video transcript flow works.
- YouTube URL-only path shows clear best-effort/fallback language.

### Admin flows

- Admin access only appears for server-authorised admins.
- Non-admin users cannot load admin endpoints directly.
- User listing works.
- Invite/create user works.
- Tier update works.
- Delete profile works only with confirmation.
- Trust analytics page loads for admin only.

### UX/layout

- Desktop Chrome/Safari.
- Mobile/iPhone-width layout.
- Loading states and failure states.
- Empty states.
- Long claim/source titles.
- Multiple sources.
- No stale anonymous/local profile confusion after sign-out.

## Security scope

### Authentication and authorisation

- Anonymous users cannot run assessments.
- Anonymous users cannot list or load private reports.
- API endpoints enforce auth server-side, not only in frontend.
- Admin endpoints require master admin or backend-only admin token.
- Product tier does not grant admin rights.
- Cross-user report/job access is blocked.
- Supabase JWT validation works against live tokens.
- Password reset and invite flows do not leak account existence unnecessarily.

### Bot and abuse protection

- Turnstile frontend site key is configured.
- Turnstile backend secret is configured only on Render/API.
- Signed-in assessment requests without a valid Turnstile token are rejected when Turnstile is enabled.
- Rate limiting/quotas are reviewed before wider launch.
- Expensive endpoints cannot be anonymously scripted.

### Secrets and environment

- No secrets in frontend/Vercel public env except intended `NEXT_PUBLIC_*` values.
- `SUPABASE_SERVICE_ROLE_KEY`, `EVIDRAI_ADMIN_TOKEN`, OpenAI, Tavily, database, and Turnstile secret stay backend-only.
- No secrets committed to git.
- Logs and errors do not expose tokens, API keys, database URLs, or raw auth headers.
- `.env`, local stores, and generated trust data are not accidentally tracked.

### Data protection

- User emails and owner IDs are handled as sensitive customer data.
- Report ownership is enforced.
- Public share payload strips private owner/debug data where appropriate.
- Feedback/counter-evidence does not bypass ownership checks.
- Data deletion/suspension implications are understood before admin delete is used.

### API hardening

- CORS restricted to expected origins.
- Input validation on URLs, claims, transcript sizes, mode/tier fields.
- Error responses are safe and actionable.
- Admin APIs have no unauthorised fallback path.
- Public report token access is intentionally scoped.
- Dependency audit reviewed for frontend and backend.

### Infrastructure

- Render API health/runtime checked.
- Vercel frontend bundle/deploy checked.
- Database migrations reviewed and applied deliberately.
- Backups/rollback path known before larger releases.
- Production env vars documented and reviewed.

## Suggested commands

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py tests/test_auth.py -q
npm --prefix web run build
python scripts/smoke_production.py
```

With a signed-in test account token:

```bash
EVIDRAI_ACCESS_TOKEN='<supabase-access-token>' \
EVIDRAI_RUN_DEEP=1 \
EVIDRAI_RUN_SPEECH=1 \
python scripts/smoke_production.py
```

Also run dependency/security checks where tooling is available:

```bash
npm --prefix web audit
python -m pip list --outdated
```

## Severity levels

- **Blocker:** auth bypass, secret exposure, cross-user data leak, broken payment/security gate, production crash.
- **High:** broken core flow, misleading entitlement, admin exposure, bot protection bypass, persistent data corruption.
- **Medium:** degraded UX, missing diagnostic, incomplete admin action, unclear error.
- **Low:** copy/layout polish, non-blocking docs issue.

## Audit output

Each audit should produce a short release note with:

- date/time,
- commit hash,
- frontend URL/build,
- API build,
- tests run,
- pass/fail summary,
- open issues by severity,
- explicit release decision: `ship`, `ship with accepted risk`, or `do not ship`.
