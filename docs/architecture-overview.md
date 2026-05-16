# Evidrai Architecture Overview

Date: 2026-05-16
Status: Current implementation map

## What Evidrai is becoming

Evidrai is moving from a Streamlit prototype into an evidence-assessment platform.

The product thesis:

> Evidrai extracts claims, checks them against independent evidentiary chains, separates evidence from amplification, and produces inspectable verdicts with clear caveats.

The architecture is intentionally still a modular monorepo. A repo split should wait until the API contract, frontend lifecycle, deployment target, and ownership boundaries are stable.

---

## Current platform layers

```text
app.py / Streamlit UI
  Internal lab UI and fast product iteration surface.

api/
  FastAPI service wrapper and external API boundary.

evidrai/
  Reusable verification engine, ingestion, models, contracts, exports, errors, and rules.

docs/
  Architecture, API contract, product design, tracker, and deployment notes.

tests/
  API, rule-engine, pipeline, ingestion, transcript, feedback, and contract regression tests.

future web/
  Future Next.js customer-facing frontend, not built yet.
```

---

## Implemented capabilities

### 1. Streamlit prototype UI

Location:

- `app.py`
- `evidrai/ui/render.py`

Current modes:

- Single Claim Check
- Speech / Video Audit
- URL-only assessment via source extraction
- Developer debug panel
- Assessment JSON download

The Streamlit UI remains the lab/debug surface. It is not the final customer-facing frontend.

---

### 2. Verification API

Location:

- `api/main.py`
- `evidrai/api_models.py`

Implemented endpoints:

```http
GET  /health
POST /claims/check          legacy compatibility endpoint
POST /assessments/fast      contract-shaped fast assessment
POST /assessments/deep      contract-shaped deep assessment
POST /speech/audit
POST /sources/extract
```

The newer `/assessments/*` endpoints return `AssessmentResponse` rather than Streamlit-shaped payloads.

The legacy `/claims/check` endpoint still exists, but now embeds a contract-shaped `assessment` object inside the old response.

---

### 3. Assessment response contract

Location:

- `evidrai/api_models.py`
- `docs/api-contract-v1.md`

Main response shape:

```text
AssessmentResponse
  schema_version
  assessment_id
  created_at
  build
  mode
  request
  verdict
  claim_breakdown
  evidence_map
  sources
  reasoning
  debug
```

This is the bridge from prototype to platform. Future frontend, exports, fixtures, reports, and persistence should all use this shape or a versioned successor.

---

### 4. Typed pipeline and trace boundary

Location:

- `evidrai/models.py`
- `evidrai/pipeline/verification.py`

Implemented typed boundaries:

- claim analysis packet
- retrieval packet
- evidence packet
- source packet
- pendulum packet
- rule engine packet
- pipeline result model
- pipeline trace model

The trace exposes:

- normalized claim
- subclaims
- search queries
- retrieved URLs
- source classifications
- scoring factors
- rule-engine output
- downgrade/arbitration rationale

This makes the result inspectable rather than just “the model said so”.

---

### 5. Ingestion layer

Location:

- `evidrai/ingestion/url.py`

Implemented:

- fetch URL
- extract title
- extract meta description
- convert HTML to readable text
- generate excerpt
- generate candidate claims
- return `source_extract.v1`

Used by:

- `POST /sources/extract`
- URL-only assessments in API and Streamlit

Current limitation: extraction is simple HTML parsing. It does not yet handle heavy JavaScript rendering, paywalls, PDFs, or complex article boilerplate perfectly.

---

### 6. Retrieval and evidence scoring

Location:

- `evidrai/clients/search.py`
- `evidrai/pipeline/verification.py`
- `evidrai/rules/verdict.py`

Current provider:

- Tavily

Current flow:

1. claim/subclaim extraction
2. search query generation
3. Tavily retrieval
4. source scoring
5. source summarisation/classification
6. evidence packet creation
7. pendulum scoring
8. rule-based verdict arbitration
9. final assessment serialization

Backlog:

- multiple search providers
- source reputation registry
- stronger evidence-chain clustering

---

### 7. Rule engine and guard rails

Location:

- `evidrai/rules/verdict.py`

Implemented concepts:

- amplification is not corroboration
- allegation/context does not equal evidence
- primary evidence gets stronger weight
- serious claims require stronger substantiation
- soft/opinion claims are handled differently
- model verdicts are aligned/downgraded by rules when needed

This is one of the important product moats.

---

### 8. Enums and normalisation

Location:

- `evidrai/enums.py`

Implemented normalisers for:

- verdict labels
- confidence labels
- claim support labels
- evidence categories
- source roles

Purpose:

- prevent schema drift
- constrain model output
- make API responses stable

---

### 9. Export and regression packet

Location:

- `evidrai/export.py`

Implemented:

- assessment export payload
- assessment export JSON
- Streamlit download button in developer panel

Export includes:

- request
- verdict
- claim breakdown
- sources
- reasoning
- debug trace
- schema/export version

Export excludes:

- API keys
- secrets
- raw fetched source content

This becomes the foundation for saved reports, regression fixtures, and review workflows.

---

### 10. Error handling

Location:

- `evidrai/errors.py`
- `api/main.py`
- `evidrai/clients/llm.py`
- `evidrai/clients/search.py`

Implemented error classes:

- `ConfigurationError`
- `LLMRequestError`
- `SearchRequestError`
- source extraction errors

API errors now return structured details for provider/config failures.

UI shows safe user-facing errors, with developer detail only in debug mode.

---

## Current data flow

### Deep claim assessment

```text
User claim / URL
  ↓
optional URL extraction
  ↓
claim analysis / subclaims
  ↓
query generation
  ↓
Tavily retrieval
  ↓
source scoring
  ↓
source summarisation/classification
  ↓
evidence packet
  ↓
pendulum + rule engine
  ↓
AssessmentResponse + debug trace
  ↓
Streamlit/API/export
```

### URL-only assessment

```text
URL
  ↓
/sources/extract or internal extractor
  ↓
title / description / text / candidate claims
  ↓
first candidate claim used as assessment input
  ↓
normal fast/deep verification pipeline
```

### Speech/video audit

```text
Transcript or YouTube URL
  ↓
transcript cleaning / caption extraction
  ↓
claim extraction
  ↓
run deep pipeline per selected claim
  ↓
speech audit report
```

---

## Tests currently covering the architecture

Location:

- `tests/test_api.py`
- `tests/test_contract_enums_export.py`
- `tests/test_ingestion_url.py`
- `tests/test_pipeline_results.py`
- `tests/test_rule_engine.py`
- `tests/test_speech_audit.py`
- `tests/test_transcripts.py`
- `tests/test_feedback.py`

Current validation state at last checkpoint:

- 42 tests passing
- compile check passing
- API smoke check passing

---

## Recent architecture commits

```text
e8b7cf8 Add URL source extraction
bb8496c Harden assessment contract and exports
5f83f0b Add assessment response and pipeline trace
bd815ba Start typed pipeline result boundary
c1a5242 Add phase 1 platform API
```

---

## What is still missing

### Near-term backlog

1. Multiple search providers
2. Source reputation registry
3. Persist user feedback
4. Saved assessment history
5. Report IDs and `GET /reports/{id}`
6. Better article extraction for difficult pages
7. Future Next.js frontend

### Larger platform pieces

- Postgres persistence
- object storage for source snapshots and transcript artefacts
- background workers for long audits
- async job endpoints
- auth/user accounts
- shareable reports
- challenge verdict workflow

---

## Practical next step

The next architectural move should be persistence:

1. Add report IDs to assessments.
2. Store exported `AssessmentResponse` packets locally first.
3. Add `GET /reports/{id}`.
4. Add feedback records linked to assessment IDs.
5. Later move the same contract into Postgres.

That turns Evidrai from a stateless verifier into an evidence ledger.
