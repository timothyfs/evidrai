# Evidrai Architecture and Plumbing

Date: 2026-05-19  
Status: Current implementation reference  
Scope: Monorepo, Streamlit lab UI, FastAPI backend, Next.js frontend, persistence, auth, verification pipeline, deployment plumbing.

## 1. Executive summary

Evidrai is an evidence-assessment platform. It is not a chatbot wrapper. The core job is to take a claim, article URL, speech transcript, or YouTube/video source, extract checkable claims, retrieve and classify evidence, separate evidence from amplification, and return an inspectable assessment with verdict, confidence, caveats, sources, score signals, and feedback hooks.

The implementation is currently a modular monorepo:

```text
app.py                         Streamlit lab/prototype entrypoint
api/                           FastAPI backend and public service boundary
evidrai/                       Core verification engine and platform plumbing
web/                           Next.js/Vercel customer-facing frontend
docs/                          Architecture, deployment, API, scoring, tracker notes
migrations/                    Postgres schema migrations
scripts/                       Operational helper scripts
tests/                         Regression, API, auth, storage, pipeline, rule tests
```

The repo split should wait. The API contract, storage model, auth lifecycle, and evidence ledger are still evolving quickly enough that a modular monorepo gives better speed and lower coordination overhead.

## 2. Runtime surfaces

### 2.1 Next.js product frontend

Location: `web/`

Primary hosted surface: `https://evidrai.vercel.app`

Responsibilities:

- public landing/product/plans/about/team/contact pages
- authenticated Verify experience
- single claim assessment UI
- speech/video two-stage audit UI
- account/profile display
- admin link visibility for server-authorised admins
- report history and report loading
- feedback controls linked to saved assessment IDs
- dark/light presentation and assessment scorecard rendering

Important files:

```text
web/app/page.tsx               Main Verify/product app
web/app/admin/page.tsx         Admin user management UI
web/app/*/page.tsx             Static public pages
web/app/globals.css            Theme, result, scorecard, admin, mobile styling
web/lib/api.ts                 API client and frontend response types
web/lib/auth.ts                Supabase browser auth client helpers
```

Frontend API calls use `cache: no-store` so role/profile/report state is not accidentally reused stale across product/admin navigation.

### 2.2 FastAPI backend

Location: `api/main.py`

Primary hosted surface: Render backend, currently referred to by the frontend default as:

```text
https://evidrai.onrender.com
```

Responsibilities:

- stable HTTP API boundary
- request validation
- auth context resolution
- entitlement enforcement
- claim/speech/source/transcript endpoint orchestration
- serialising assessments into `AssessmentResponse`
- saving/loading reports
- saving/loading feedback
- admin profile management
- runtime diagnostics

FastAPI’s generated docs are available when running the API locally or remotely:

```text
GET /docs
GET /openapi.json
```

The canonical hand-written API reference is now `docs/api-reference.md`.

### 2.3 Streamlit lab UI

Location:

```text
app.py
evidrai/ui/render.py
```

Current role:

- internal lab/prototype surface
- fast testing of verification behaviour
- useful for debugging pipeline output and source scoring
- retained while the product UI matures

It should not be treated as the final customer product surface.

## 3. Core platform layers

### 3.1 API and contract layer

Files:

```text
api/main.py
evidrai/api_models.py
evidrai/enums.py
evidrai/errors.py
```

`api/main.py` owns routing and orchestration. `evidrai/api_models.py` owns the product-facing assessment contract.

The central product contract is:

```text
AssessmentResponse
  schema_version
  assessment_id
  created_at
  build
  mode
  owner_id
  request
  verdict
  claim_breakdown
  evidence_map
  sources
  reasoning
  debug
```

Single claim assessments and verified speech claims should both converge into this contract. That matters because reports, feedback, scorecards, and future share/export flows should not have to understand separate result shapes.

Recent implementation note: selected speech claims are now saved as proper `AssessmentResponse` reports and returned with `assessment_id` and embedded `assessment` payloads.

### 3.2 Verification engine

Files:

```text
evidrai/pipeline/verification.py
evidrai/models.py
prompts.py
evidrai/rules/verdict.py
```

The verification engine performs:

1. input construction
2. claim/subclaim extraction
3. query generation
4. retrieval, when configured
5. source scoring and classification
6. source summarisation
7. evidence packet construction
8. pendulum scoring
9. rule-based verdict arbitration
10. serialisation into API/UI payloads

Fast mode uses a lightweight pass. Deep mode uses retrieval-backed verification and requires Tavily configuration.

### 3.3 LLM client

File: `evidrai/clients/llm.py`

Provider style: OpenAI-compatible chat completions API.

Configuration:

```text
OPENAI_API_KEY                 required for model calls
OPENAI_BASE_URL                optional, default https://api.openai.com/v1
OPENAI_MODEL                   optional, default gpt-4o-mini
```

Behaviour:

- sends JSON-mode chat completions
- expects parseable JSON objects
- retries transient failures using scoring config retry settings
- maps auth/rate/provider failures into safe Evidrai errors

### 3.4 Search/retrieval client

File: `evidrai/clients/search.py`

Provider: Tavily.

Configuration:

```text
TAVILY_API_KEY                 required for Deep mode and deep speech verification
```

Behaviour:

- returns title, URL, content snippet, raw content, and published date where available
- Deep mode fails cleanly if Tavily is required but not configured
- Fast mode does not require Tavily

### 3.5 Source and URL ingestion

Files:

```text
evidrai/ingestion/url.py
evidrai/utils.py
```

Responsibilities:

- detect probable URLs
- fetch source URLs
- extract HTML title/meta/text
- produce readable excerpts
- generate candidate claims from source content
- support URL-only assessment flows

Current limitations:

- no full browser rendering
- limited handling of heavy JavaScript sites
- no first-class PDF pipeline yet
- paywalls and bot-blocking can prevent extraction

### 3.6 YouTube/transcript ingestion

File: `evidrai/transcripts.py`

Responsibilities:

- detect YouTube URLs
- clean pasted YouTube/browser transcripts
- extract YouTube captions where possible
- diagnose transcript backend availability and failures

Backends tracked by `/runtime`:

```text
youtube_transcript_api
yt_dlp
```

Product rule:

- URL-only YouTube extraction is best-effort.
- Pasted transcript remains the reliable fallback.
- Do not use browser cookies or `--cookies-from-browser` in Render/server context.

Known good test URL from product testing:

```text
https://youtu.be/cR5Dmj6GK88?is=byMagKFTQJoUPeOM
```

This worked for claim extraction and verification, but broader reliability remains open because cloud IP blocking can still affect other videos.

### 3.7 Rule engine and scoring

Files:

```text
evidrai/rules/verdict.py
docs/evidence-scoring-system.md
```

Core principles:

- amplification is not corroboration
- primary/direct evidence carries more weight than repeated secondary coverage
- independent evidence chains matter more than volume
- serious allegations require stronger substantiation
- context/background is separated from support
- confidence reflects available evidence, not certainty

The scoring model exposes:

- source score
- source scoring factors
- evidence strength score
- verdict label
- confidence label
- caveats and reasoning summaries

Absolute-claim handling is explicitly guarded by regression tests because terms such as `only`, `first`, `last`, `all`, `every`, and `no` need claim-level context.

### 3.8 Persistence and report ledger

Files:

```text
evidrai/reports.py
evidrai/feedback.py
evidrai/db.py
migrations/*.sql
```

Storage mode:

- local JSON fallback by default
- Postgres when `DATABASE_URL`, `POSTGRES_URL`, or `SUPABASE_DATABASE_URL` is configured

Report storage:

```text
ReportStore
  LocalReportStore
  PostgresReportStore
```

Feedback storage:

```text
FeedbackStore
  LocalFeedbackStore
  PostgresFeedbackStore
```

Postgres tables:

```text
assessments
  assessment_id
  created_at
  mode
  claim
  source_url
  verdict
  confidence
  owner_id
  payload
  updated_at

feedback
  feedback_id
  assessment_id
  captured_at
  rating
  payload

user_profiles
  owner_id
  email
  tier
  created_at
  updated_at
  trial_started_at
  trial_ends_at
  subscription_status
  payment_provider_customer_id

evidrai_schema_migrations
  migration ledger managed by evidrai/db.py
```

Migrations:

```text
001_create_assessments_feedback.sql
002_add_assessment_owner.sql
003_create_user_profiles.sql
004_user_profile_admin_trial_fields.sql
```

Apply with:

```bash
DATABASE_URL='postgresql://...' python scripts/apply_migrations.py
```

### 3.9 Auth, profile, and entitlements

Files:

```text
evidrai/auth.py
evidrai/entitlements.py
web/lib/auth.ts
web/app/admin/page.tsx
```

Auth modes:

1. Supabase Bearer token, preferred for signed-in users.
2. Anonymous browser/profile owner ID via `X-Evidrai-User-Id`, temporary fallback for anonymous/local flows.

Supabase JWT validation:

- prefers HS256 if `SUPABASE_JWT_SECRET` is configured and valid
- falls back to Supabase JWKS via `SUPABASE_URL` for modern asymmetric JWT projects

Product tiers:

```text
free
pro
researcher
```

Labels:

```text
Free
Pro
Researcher / Journalist
```

Admin access is deliberately separate from product tier. Admin is controlled by:

```text
EVIDRAI_MASTER_ADMIN_EMAILS
EVIDRAI_ADMIN_TOKEN          bootstrap fallback only
```

Current behaviour:

- master admin emails are admin-authorised server-side
- `/me` upgrades master admin emails to `researcher` if the stored product tier is lower
- frontend only shows admin UI links when `/me` returns `is_admin: true`

Important security rule:

- `SUPABASE_SERVICE_ROLE_KEY` and `EVIDRAI_ADMIN_TOKEN` belong only on the backend host.
- They must never be exposed as `NEXT_PUBLIC_*` frontend variables.

### 3.10 Feedback and review loop

Files:

```text
evidrai/feedback.py
web/app/page.tsx
api/main.py
```

Feedback is linked to saved assessment IDs. Current feedback operations:

- submit feedback for an assessment
- list feedback for an assessment
- load feedback by feedback ID
- optional Notion-backed review/task flow via integration tooling

Feedback is an input to the future regression-review loop. Durable product direction: useful feedback should be promotable into test fixtures/regression cases.

## 4. Request/data flows

### 4.1 Single claim assessment

```text
User -> Next.js Verify form
  -> web/lib/api.ts createAssessment()
  -> POST /assessments/fast or /assessments/deep
  -> api/main.py validates auth/profile/entitlements
  -> _run_claim_assessment()
  -> run_quick_pass() or run_claim_pipeline()
  -> serialize_assessment_response()
  -> save_report()
  -> AssessmentResponse returned
  -> AssessmentResult renders scorecard/evidence/feedback
```

### 4.2 URL-only assessment

```text
User supplies source_url with empty claim
  -> API calls _source_claim_from_url()
  -> source extracted via fetch_source_url()
  -> candidate claim text generated
  -> normal fast/deep assessment flow continues
```

### 4.3 Two-stage speech/video audit

```text
User supplies pasted transcript or YouTube URL
  -> POST /speech/extract
  -> transcript resolved/cleaned/extracted
  -> LLM extracts ranked checkable claims
  -> user selects claims
  -> POST /speech/verify
  -> each selected claim becomes normal audit input
  -> each checked claim is serialized into AssessmentResponse
  -> each checked claim is saved as a report
  -> response includes assessment_id and assessment per claim
  -> frontend renders shared AssessmentResult scorecard per claim
```

### 4.4 One-shot speech audit

```text
POST /speech/audit
  -> transcript extraction
  -> claim extraction
  -> verification for extracted claims
  -> checked claims saved as AssessmentResponse reports
  -> speech_audit.v1 payload returned
```

This endpoint is useful for programmatic use and legacy flows. The product UI should prefer two-stage audit for cost/token control.

### 4.5 Report history

```text
Frontend calls GET /reports
  -> owner resolved from Supabase JWT or X-Evidrai-User-Id
  -> list_reports(owner_id=...)
  -> summaries returned

User opens report
  -> GET /reports/{report_id}
  -> backend checks ownership unless master admin
  -> full AssessmentResponse returned
```

### 4.6 Feedback

```text
User submits feedback on AssessmentResult
  -> POST /assessments/{assessment_id}/feedback
  -> backend loads report
  -> feedback record stores rating/reasons/comment plus full assessment context
  -> feedback_id returned
```

### 4.7 Admin user management

```text
Admin signs in with authorised email
  -> Supabase JWT sent to backend
  -> /me returns is_admin true
  -> admin page calls /admin/users
  -> backend checks master admin email or bootstrap token
  -> admin can list, invite/create, tier-update, or delete local profiles
```

## 5. Deployment plumbing

### 5.1 Frontend: Vercel

Location: `web/`

Build:

```bash
cd web
npm run build
```

Important frontend environment variables:

```text
NEXT_PUBLIC_API_BASE_URL       e.g. https://evidrai.onrender.com
NEXT_PUBLIC_SUPABASE_URL       Supabase project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY  Supabase anon/public browser key
```

Never configure backend-only secrets in Vercel frontend variables.

### 5.2 Backend: Render/FastAPI

Entrypoints/config files:

```text
Procfile
Dockerfile.api
render.yaml
api/main.py
```

Typical runtime command:

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Important backend environment variables:

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
TAVILY_API_KEY
DATABASE_URL
SUPABASE_URL
SUPABASE_JWT_SECRET            optional for HS256 projects
SUPABASE_SERVICE_ROLE_KEY      admin invite/create only
EVIDRAI_MASTER_ADMIN_EMAILS
EVIDRAI_ADMIN_TOKEN            bootstrap fallback only
API_ALLOWED_ORIGINS
```

Backend deploy note: Render backend auto-deploy has previously been treated as manual/off because backend changes affect storage, migrations, CORS, and live endpoints. Confirm deployment status before assuming pushed backend commits are live.

### 5.3 Streamlit Cloud

Streamlit remains useful for lab/testing. Configure secrets in Streamlit secrets, not client-side browser variables.

## 6. Validation gates

Minimum before push:

```bash
PYTHONPATH=. .venv/bin/pytest -q
cd web && npm run build
```

Useful compile check:

```bash
python3 -m compileall api evidrai
```

API smoke helper:

```bash
python scripts/smoke_api.py
```

## 7. Current risks and open architecture gaps

1. **Async jobs**: Deep and speech audits can become long-running. Need job model/queue for production scale.
2. **Evidence ledger**: Current reports store JSON payloads. Future needs queryable evidence/source tables and source snapshots.
3. **Transcript reliability**: YouTube extraction is best-effort and sensitive to cloud-provider blocking.
4. **Source ingestion**: Needs stronger article extraction, PDF support, and possibly browser-rendered extraction.
5. **Review workflow**: Feedback exists, but regression promotion and reviewer labels are not fully productised.
6. **Provider abstraction**: Tavily and OpenAI-compatible clients exist, but multi-provider fallback is limited.
7. **Auth lifecycle**: Supabase auth is functional, but billing, trials, and subscription enforcement are scaffolding only.
8. **Observability**: Runtime diagnostics exist, but structured logs/metrics/tracing are not yet complete.

## 8. Golden rules

- Keep `AssessmentResponse` as the product contract unless deliberately versioning it.
- Save anything users may later review as a report with an `assessment_id`.
- Keep admin rights separate from product tiers.
- Keep backend secrets backend-only.
- Treat YouTube extraction as best-effort; pasted transcripts are the reliable fallback.
- Do not let source volume masquerade as corroboration.
- Before changing backend storage/auth/API behaviour, run backend tests and frontend build.
