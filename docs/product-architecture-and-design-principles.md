# Evidrai Product Architecture and Design Principles

Date: 2026-05-14
Status: Working product direction

## Executive summary

Evidrai should evolve from a Streamlit verification prototype into a professional evidence-assessment product with a clean product shell, a reusable verification API, persistent feedback/review loops, and a regression-driven improvement process.

Streamlit has done its job: it helped us prove the core loop quickly. It should now become the internal lab/debug surface, not the long-term customer-facing product experience.

The product goal is not simply to answer "true or false". Evidrai should help users understand:

- what is factually supported
- what is disputed or interpretive
- what remains unknown
- how strong the evidence is
- why the verdict is not stronger or weaker

This is especially important for simple claims with hidden nuance, such as:

> "Nigel Farage failed to disclose a £5M gift."

That single sentence can contain several different propositions:

1. A £5M gift existed.
2. It was not disclosed at a relevant time/place.
3. Rules required disclosure.
4. The non-disclosure implies wrongdoing.

A professional Evidrai result must separate those layers instead of forcing one verdict to carry all of them.

---

## Product design principles

### 1. Verdicts must be clear, but never flatten nuance

Users need a clear answer quickly, but trust depends on explaining the boundary of that answer.

Good pattern:

> Likely supported: reporting supports that the gift existed and was initially undisclosed. Whether this breached disclosure rules remains contested.

Bad pattern:

> Unverified.

Bad pattern:

> True.

The first answer is more useful because it separates factual support from legal interpretation.

### 2. Every result should separate four layers

For complex claims, the result should explicitly distinguish:

- **Factual core**: what happened or did not happen
- **Interpretation**: what the facts mean
- **Obligation/standard**: what rule, law, norm, or threshold applies
- **Wrongdoing/inference**: whether the evidence supports blame, intent, illegality, or misconduct

This should become a first-class product component, not buried in prose.

### 3. Evidence is not just a list of links

Sources should be grouped by function:

- supports factual core
- contradicts factual core
- supports interpretation
- disputes interpretation
- contextual only
- weak/noisy/irrelevant

A flat source list forces the user to do the reasoning themselves. Evidrai should show the evidence map.

### 3a. Independence beats amplification

Evidrai should not treat repetition as corroboration.

The system should distinguish:

- one claim repeated by many outlets
- one claim syndicated from the same wire story
- one claim laundered through social media, state media, or partisan commentary
- one claim independently confirmed by separate evidentiary chains

The product principle is:

> Amplification is not corroboration. Evidrai scores claims against independent evidentiary chains, not against volume, visibility, status, or repetition.

This matters because weak claims can look credible when bots, state-aligned outlets, partisan media, populist figures, or even reputable publications repeat the same unsupported source event. Reputable news organisations should improve confidence only when they add transparent reporting, named evidence, primary documents, or independently derived confirmation.

Implementation implications:

- Narrative clusters should be treated as evidence chains.
- Multiple sources in the same narrative cluster should decay in marginal value.
- Primary sources, official records, court filings, datasets, direct transcripts, and clearly attributed documents should carry more weight than repeated commentary.
- Political status, institutional office, media prominence, follower count, or social engagement should increase review priority, not truth score.
- The UI should warn users when a claim is widely repeated but has thin independent support.

Good pattern:

> Amplification warning: this claim appears in several sources, but they mostly trace back to the same allegation or narrative cluster. Evidrai treats this as visibility, not independent confirmation.

Bad pattern:

> Many sources say this, therefore it is likely true.

### 4. Confidence must explain its own limits

Confidence should answer: confidence in what?

Examples:

- High confidence that the event was reported by credible sources
- Medium confidence that the claim as worded is accurate
- Low confidence that wrongdoing is established

Avoid presenting confidence as a pseudo-probability.

### 5. Fast mode must be useful, not just cheap

Most users will use the easiest/default path. Therefore Fast mode cannot be blind.

Fast should:

- use lightweight search snippets when available
- avoid full deep summarisation cost
- clearly say it is provisional
- identify obvious evidence patterns
- recommend Deep when factual support and interpretation diverge

### 6. Deep mode should be the authoritative user-facing assessment

When Deep has run, the UI should make it obvious that Deep is the primary assessment. The initial Fast pass should be collapsed or marked as a trace.

### 7. The system must learn from disagreement

User disagreement is not noise. It is product telemetry.

Every feedback item should capture:

- user comment
- expected verdict
- expected confidence
- error type
- request settings
- full output payload
- whether it should become a regression case

Feedback should become tests, not just notes.

### 8. Internal uncertainty should become user clarity

If the system is uncertain because the claim is ambiguous, the UI should say what ambiguity matters.

Example:

> The factual claim appears supported. The unresolved question is whether the gift met the legal definition of a declarable donation.

This is clearer than saying the whole claim is unverified.

### 9. Professional UX should reduce cognitive load

The app should not look like a model dump. The user should see:

1. verdict card
2. claim decomposition
3. evidence map
4. key caveat
5. sources and details
6. feedback

Details should be available, but progressively disclosed.

### 10. Trust requires traceability

Every result should be reproducible and inspectable internally:

- input
- mode/settings
- model version/build
- retrieved sources
- source classifications
- rule engine stats
- final verdict arbitration
- user feedback

---

## Target user experience

### Ideal result page structure

#### 1. Verdict card

Top of page. No ambiguity.

Fields:

- Verdict
- Confidence
- One-sentence answer
- Key caveat
- Evidence strength visual

Example:

> **Likely supported · Medium confidence**
>
> Evidence supports that Farage received a £5M gift and that it was not initially disclosed in the relevant public register. Whether the gift was legally required to be declared remains contested.

#### 2. Claim breakdown

A structured decomposition table/cards:

| Subclaim | Assessment | Why |
| --- | --- | --- |
| £5M gift existed | Supported | Multiple credible reports identify donor and amount |
| Gift was initially undisclosed | Likely supported | Reports state it did not appear in the relevant register |
| Disclosure was legally required | Contested | Farage argues exemption/private security purpose |
| Wrongdoing established | Unproven | Investigation/complaint exists, not final ruling |

This is central to the product.

#### 3. Evidence map

Grouped evidence cards:

- Confirms factual core
- Raises legal/interpretive dispute
- Contradicts claim
- Context/noise

Each source card should show:

- title/domain
- source type
- stance
- score
- short reason for classification

#### 4. Why the verdict is not stronger

A concise explanation:

- no primary ruling yet
- obligation disputed
- no final standards finding

#### 5. What would change this assessment

Examples:

- official standards commissioner decision
- parliamentary register update
- Electoral Commission finding
- documentary proof of disclosure timing

#### 6. Feedback capture

A lightweight prompt:

- too weak
- too strong
- unclear
- missed source
- wrong source classification
- expected verdict/confidence
- free text

---

## Target technical architecture

### Near-term architecture

Keep current Python verification core, but separate product shell from verification engine.

```text
apps/
  streamlit-lab/             # internal/debug UI, can wrap current app.py
  web/                       # future Next.js frontend

services/
  api/                       # FastAPI service
    routes/
      assessments.py
      feedback.py
      health.py
    workers/
      deep_assessment.py

packages/
  evidrai-core/              # current Python package, product logic
    clients/
    pipeline/
    rules/
    models.py
    feedback.py

storage/
  migrations/
  fixtures/
  regression_cases/
```

Current repo does not need to jump to this exact monorepo immediately, but this is the direction.

### Component responsibilities

#### Frontend product app

Recommended: Next.js / React.

Responsibilities:

- polished UX
- mobile-first layout
- result cards
- feedback review flow
- user sessions/history later
- analytics instrumentation
- shareable assessment pages later

Does **not** own verdict logic.

#### API service

Recommended: FastAPI because the verification core is already Python.

Responsibilities:

- accept assessment requests
- orchestrate Fast and Deep workflows
- return typed JSON
- persist assessment records
- persist feedback
- expose review/regression endpoints
- handle auth/rate limits later

#### Verification core

Existing `evidrai/` package becomes `evidrai-core` in practice.

Responsibilities:

- claim analysis
- search query generation
- retrieval
- source scoring
- source summarisation
- evidence stats
- verdict rules
- verdict arbitration
- output schema validation

#### Background worker

Deep assessments can take 40+ seconds. Long-running work should eventually move out of request/response.

Responsibilities:

- deep retrieval jobs
- source summarisation
- periodic re-checks
- regression suite generation

#### Database

Recommended initial choice: Postgres via Supabase or managed Postgres.

Core tables:

- `assessments`
- `assessment_sources`
- `feedback`
- `review_labels`
- `regression_cases`
- `users` / `testers` later

SQLite is acceptable for local/dev, but Postgres is better once external testers increase.

---

## Proposed data model

### Assessment

```json
{
  "id": "uuid",
  "created_at": "timestamp",
  "build": "string",
  "mode": "fast|deep",
  "claim_input": "string",
  "source_url": "string|null",
  "normalized_claim": "string",
  "category": "string",
  "verdict": "string",
  "confidence": "string",
  "summary": "string",
  "key_caveat": "string",
  "evidence_strength_score": 5.0,
  "schema_version": "assessment.v1"
}
```

### Claim decomposition

```json
{
  "assessment_id": "uuid",
  "subclaim_id": "string",
  "text": "string",
  "dimension": "factual_core|interpretation|obligation|wrongdoing|context",
  "assessment": "supported|likely_supported|contested|unverified|not_supported",
  "confidence": "high|medium|low",
  "rationale": "string"
}
```

### Source

```json
{
  "assessment_id": "uuid",
  "url": "string",
  "title": "string",
  "domain": "string",
  "source_type": "primary|secondary|contextual|unknown",
  "stance": "supports|contradicts|mixed|context",
  "evidence_category": "direct_evidence|credible_reporting|expert_analysis|reported_allegation|contextual_signal|denial_or_rebuttal|irrelevant",
  "score": 3.7,
  "summary": "string",
  "classification_reason": "string"
}
```

### Feedback / review

```json
{
  "feedback_id": "uuid",
  "assessment_id": "uuid",
  "rating": "useful|partly_useful|not_useful",
  "reasons": ["verdict_clarity"],
  "comment": "string",
  "expected_verdict": "string|null",
  "expected_confidence": "string|null",
  "error_type": ["legal_interpretive_nuance", "too_cautious"],
  "accepted_as_regression_case": false,
  "reviewer_notes": "string"
}
```

---

## Architecture decision recommendations

### Frontend

Recommendation: **Next.js**.

Why:

- polished UI
- mobile-first components
- shareable pages
- good auth options
- easy deployment on Vercel
- works well with API backend

Alternative: React SPA. Simpler, but Next.js gives better routing and future share pages.

### Backend

Recommendation: **FastAPI**.

Why:

- existing code is Python
- typed Pydantic contracts
- easy OpenAPI docs
- good async/job integration
- smooth migration from Streamlit

### Database

Recommendation: **Postgres**, likely Supabase at first.

Why:

- structured feedback/review data
- assessment history
- source records
- eventual user accounts
- easy export for regression/ML

### Jobs

Phase 1: synchronous API for Fast, synchronous or long-poll Deep.

Phase 2: background jobs for Deep.

Options:

- RQ + Redis
- Celery + Redis
- Dramatiq
- Supabase queue/pg-boss later if staying Postgres-centric

Keep it simple until traffic requires more.

### Search/retrieval

Keep Tavily initially, but abstract provider interface.

Future providers:

- Tavily
- Brave Search
- SerpAPI
- direct URL/article extraction
- official source targeted search

---

## Migration roadmap

### Phase 0 — Stabilise current prototype

Goal: keep testers productive while designing the real product.

Tasks:

- Keep Streamlit running as lab UI
- Continue feedback capture into Notion
- Add review labels to feedback tasks
- Keep regression tests growing
- Improve build/version visibility

Exit criteria:

- All test feedback creates reviewable Notion tasks
- Key verdict failures become regression cases
- Current app remains usable

### Phase 1 — Define product contracts

Goal: freeze the API/data contracts before building frontend.

Tasks:

- Create `AssessmentResponse` schema
- Create `ClaimDecomposition` schema
- Create `EvidenceSource` schema
- Create `FeedbackRecord` schema
- Add fixture examples for 5 to 10 known cases

Exit criteria:

- UI can be built from stable JSON
- Regression cases can replay from fixtures

### Phase 2 — Build FastAPI wrapper

Goal: expose current pipeline as API.

Endpoints:

- `POST /assessments/fast`
- `POST /assessments/deep`
- `GET /assessments/{id}`
- `POST /assessments/{id}/feedback`
- `GET /health`

Exit criteria:

- Streamlit can optionally call API instead of direct functions
- API returns same outputs as current pipeline
- Feedback persists through API

### Phase 3 — Build professional web frontend

Goal: create the customer-facing product shell.

Pages:

- `/` input page
- `/assessment/[id]` result page
- `/review` internal feedback review page later

Components:

- VerdictCard
- ClaimBreakdown
- EvidenceMap
- SourceCard
- ConfidenceExplainer
- FeedbackPanel
- DebugPayloadPanel internal only

Exit criteria:

- UX is mobile-friendly
- Deep result is visually primary
- Claim decomposition is first-class
- Feedback is smooth and persistent

### Phase 4 — Feedback-to-regression loop

Goal: make user feedback improve the system deterministically.

Tasks:

- Export labelled Notion/Postgres feedback
- Create regression fixture generator
- Add test runner for accepted cases
- Track pass/fail by build

Exit criteria:

- A feedback item can become a regression test
- Known failures stay fixed
- Prompt/rule changes are measurable

### Phase 5 — Production hardening

Tasks:

- auth/invite codes
- rate limiting
- request logging
- secret management
- background jobs
- monitoring
- error budgets
- cost controls
- cache search/retrieval results

Exit criteria:

- safe for broader external testers
- robust enough for demo/customer conversations

---

## Immediate next steps

### 1. Create professional product wireframe

Produce a low-fidelity result-page design covering:

- verdict card
- claim decomposition
- evidence map
- caveats
- feedback

Output: `docs/ux-result-page-wireframe.md`

### 2. Define API schemas

Create Pydantic schema proposal for:

- assessment request
- assessment response
- feedback request
- review labels

Output: `docs/api-contract-v1.md`

### 3. Add claim decomposition output to pipeline

Current pipeline extracts subclaims but does not yet render a proper layered decomposition.

Add dimensions:

- factual_core
- interpretation
- obligation
- wrongdoing
- context

Output: UI component and response field.

### 4. Convert feedback into regression candidates

Add script:

`tools/feedback_to_regression.py`

Inputs:

- Notion/exported JSONL feedback
- accepted review labels

Outputs:

- regression fixture JSON files

### 5. Improve build label clarity

Current label uses a static prefix plus commit hash. Make it show:

`Build: <short-sha> · <commit title>`

This removes confusion about whether a deploy is current.

---

## Non-goals for now

Do not start with heavy ML/fine-tuning.

We do not yet have enough labelled data. The right sequence is:

1. capture feedback
2. label feedback
3. create regression cases
4. improve rules/prompts
5. then evaluate whether ML helps source classification, verdict recommendation, or claim decomposition

Do not prematurely add accounts, billing, or complex job infrastructure before the result UX and evidence model are right.

---

## Product quality bar

Before Evidrai becomes a broader public beta, it should satisfy:

- Users understand the verdict within 10 seconds
- Users can see what is supported vs disputed without reading every source
- Feedback disagreements are captured and reviewable
- Known failure cases are protected by regression tests
- The app can explain why a verdict is not stronger
- The product does not collapse legal/interpretive nuance into factual uncertainty
- Deep checks are traceable end-to-end
- Fast checks are useful enough for normal behaviour

That is the path from prototype to product.
