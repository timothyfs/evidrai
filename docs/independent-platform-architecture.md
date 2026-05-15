# Evidrai Independent Platform Architecture

Date: 2026-05-15
Status: Phase 1 implementation plan

## Recommendation: keep one repo for now

Do **not** create a new repository yet.

Keep the current repo, but split the project internally into clear platform layers:

```text
app.py / Streamlit UI      Internal lab and prototype surface
api/                       FastAPI service wrapper and API contracts
evidrai/                   Reusable verification engine and product logic
docs/                      Product, architecture, and methodology docs
tests/                     Regression, rule-engine, and API tests
future web/                Next.js customer-facing frontend
```

A new repo should happen later, once the API and package boundaries are stable. Splitting too early would create coordination overhead while the product shape is still moving quickly.

Create a separate repo only when at least two of these are true:

- the API contract is stable enough for an independent frontend team/process
- the frontend has its own build/deploy lifecycle
- Evidrai core is packaged as a versioned Python package
- there is a production deployment target with separate service ownership
- access control, CI/CD, and environment management need independent governance

Until then, the best path is a **modular monorepo**.

## Platform goal

Evidrai should evolve from a Streamlit verification prototype into an independent evidence-assessment platform.

The platform should not be positioned as an AI chatbot or opinion engine. It should be an evidence product:

> Evidrai extracts claims, checks them against independent evidentiary chains, separates evidence from amplification, and produces inspectable verdicts with clear caveats.

## Target architecture

### 1. Product layer

User-facing experience.

Initial surfaces:

- Streamlit lab/prototype UI, retained for fast iteration
- future Next.js public app

Core product modes:

- Single Claim Check
- Speech / Video Audit
- Article / URL Audit
- Saved Reports
- Feedback / Challenge Verdict

The product layer should show:

- verdict
- confidence
- claim decomposition
- evidence map
- amplification warning
- source links and classifications
- why the verdict is not stronger or weaker
- user feedback and challenge flow

### 2. Verification API

A backend service that exposes the Evidrai engine through stable endpoints.

Phase 1 endpoints:

- `GET /health`
- `POST /claims/check`
- `POST /speech/audit`

Later endpoints:

- `GET /reports/{id}`
- `POST /sources/extract`
- `POST /feedback`
- `POST /verdicts/{id}/challenge`
- `GET /reports/{id}/evidence`

The API should own:

1. request validation
2. claim extraction
3. retrieval orchestration
4. source classification
5. evidence-chain clustering
6. amplification checks
7. verdict arbitration
8. response serialization
9. report persistence later

### 3. Evidence infrastructure

The durable trust layer.

Future components:

- Postgres for claims, reports, users, feedback, source snapshots
- object storage for transcripts, raw evidence packets, and media-derived artefacts
- background workers for speech/video/article audits
- queue for long-running jobs
- source snapshotting for reproducibility
- regression suite promoted from real feedback
- search provider abstraction beyond Tavily

## Design principle: evidence ledger, not AI answer

Every result should be inspectable and reproducible.

A production Evidrai report should retain:

- original input
- normalized claim
- subclaims
- retrieved sources
- source classifications
- narrative clusters
- amplification warning
- rule-engine stats
- final verdict
- confidence rationale
- model/provider/build metadata
- user feedback and challenge status

The long-term moat is not the model call. It is the evidence ledger and review loop.

## Phase 1 scope

Phase 1 creates a FastAPI wrapper around the existing core pipeline without replacing Streamlit.

Deliverables:

- `api/main.py`
- request/response models
- `GET /health`
- `POST /claims/check`
- `POST /speech/audit`
- API tests using FastAPI TestClient
- README documentation for running the API locally

Out of scope for Phase 1:

- auth
- persistence
- background workers
- separate frontend
- production deployment
- report sharing
- user accounts

## Phase 2 scope

- Add result persistence
- Assign report IDs
- Store source packets and rule-engine metadata
- Add `GET /reports/{id}`
- Add feedback endpoint
- Add minimal admin/review queue

## Phase 3 scope

- Build Next.js frontend
- Keep Streamlit as internal lab/debug UI
- Add shareable report pages
- Add challenge verdict workflow

## Phase 4 scope

- Background jobs for long audits
- uploaded audio/video transcription
- article extraction
- better source snapshotting
- regression promotion workflow

## Deployment direction

Early platform deployment should be boring:

- FastAPI container
- Postgres
- object storage later
- Render/Fly/Railway initially
- move to AWS/GCP only when scale/security requires it

## Immediate implementation choice

Implement Phase 1 in the existing repo. This keeps momentum, preserves the Streamlit prototype, and starts the proper API boundary without premature repo sprawl.
