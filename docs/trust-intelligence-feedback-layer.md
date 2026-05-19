# Trust Intelligence Feedback Layer

Date: 2026-05-19  
Status: Foundation implemented, roadmap active  
Scope: architecture, schema, data flow, API, UX, analytics, ML readiness, multi-model strategy.

## 1. Strategic intent

Evidrai should evolve from a claim-checking application into a trust intelligence platform. LLMs provide reasoning and language capability, but Evidrai must own the credibility layer above the models:

- credibility intelligence
- trust calibration
- source evaluation
- evidence ranking
- contradiction handling
- narrative propagation tracking
- human trust interaction data

The long-term moat is not prompt quality. It is structured trust data, source reliability intelligence, credibility graph relationships, and the learning loop created by real users challenging real evidence.

## 2. Architecture proposal

The Trust Intelligence Feedback Layer sits between product interactions and future ML/graph systems.

```text
User actions
  -> claim checks / speech checks / report views / feedback / challenges
  -> Trust Intelligence capture layer
  -> structured Postgres tables + local JSONL fallback
  -> admin analytics / review queues
  -> feature extraction / graph export / ML datasets
  -> future credibility ranking and reasoning models
```

Core components:

1. **Assessment snapshot capture**
   - every saved `AssessmentResponse` becomes a `trust_claim_check`
   - sources are decomposed into `trust_evidence_sources`
   - narrative clusters and evidence maps are preserved

2. **Trust signal capture**
   - explicit user trust signals are stored as `trust_signal_events`
   - verdict acceptance/rejection is event-sourced
   - user challenges and counter-evidence are kept as structured training-quality records

3. **Source reliability observations**
   - source distrust/bias/persuasiveness signals become source reliability observations
   - this is not yet an automated reputation score, but it is the raw material for one

4. **Admin analytics**
   - early API endpoint exposes most common signals, disputed claims, and source reliability observations

5. **Future graph/ML pipeline**
   - schema preserves relationships so it can later feed graph databases, feature stores, embeddings, and credibility models

## 3. Database/schema design

Implemented migration:

```text
migrations/005_create_trust_intelligence.sql
```

Implemented tables:

### `trust_claim_checks`

One row per saved assessment.

Key fields:

- `assessment_id`
- `actor_hash`
- `claim`
- `source_url`
- `category`
- `mode`
- `verdict`
- `confidence`
- `evidence_strength_score`
- `topic`
- `sensitivity_tags`
- `narrative_clusters`
- `payload`

Purpose:

- queryable claim-check ledger
- future claim-pattern clustering
- confidence evolution and verdict history foundation

### `trust_evidence_sources`

One row per evidence source used in an assessment.

Key fields:

- `assessment_id`
- `source_id`
- `url`
- `domain`
- `title`
- `source_type`
- `stance`
- `evidence_category`
- `source_role`
- `narrative_cluster`
- `source_score`
- `scoring_factors`
- `payload`

Purpose:

- source lineage
- evidence relationship tracking
- domain/source reliability intelligence
- graph migration foundation

### `trust_signal_events`

Event-sourced trust interactions.

Key fields:

- `event_id`
- `assessment_id`
- `feedback_id`
- `actor_hash`
- `signal_type`
- `sentiment`
- `target_type`
- `target_id`
- `source_id`
- `claim_pattern`
- `narrative_cluster`
- `details`

Purpose:

- granular feedback history
- RLHF/RLHT-style training data
- verdict acceptance/rejection flows
- dispute/challenge analytics

### `trust_counter_evidence`

Structured user-submitted counter-evidence.

Key fields:

- `counter_evidence_id`
- `assessment_id`
- `feedback_id`
- `actor_hash`
- `url`
- `text_excerpt`
- `relationship`
- `status`
- `payload`

Purpose:

- challenge/rebuttal workflow
- future human review queue
- contradiction training examples

### `source_reliability_observations`

Raw observations that can later feed source reliability scores.

Key fields:

- `observation_id`
- `domain`
- `source_url`
- `source_id`
- `assessment_id`
- `feedback_id`
- `actor_hash`
- `signal_type`
- `reliability_delta`
- `details`

Purpose:

- source credibility evolution
- source reputation scoring
- source/domain trust trend analysis

## 4. Trust intelligence data flow

### Assessment save flow

```text
AssessmentResponse generated
  -> save_report(...)
  -> assessments table / local report store
  -> capture_assessment_snapshot(...)
  -> trust_claim_checks
  -> trust_evidence_sources
```

This means the trust layer receives data for:

- single claim checks
- saved speech/video claim assessments
- loaded/saved reports

The trust capture is non-blocking. If the trust layer fails, the user-facing assessment still saves.

### Feedback flow

```text
User submits feedback
  -> POST /assessments/{assessment_id}/feedback
  -> feedback record saved
  -> capture_feedback_trust_events(...)
  -> trust_signal_events
  -> trust_counter_evidence
  -> source_reliability_observations
```

Supported trust signals now include:

- `evidence_weak`
- `source_biased`
- `changed_view`
- `needs_primary_sourcing`
- `balanced_explanation`
- `manipulative_wording`
- `overconfident`
- `too_uncertain`
- `missed_context`
- `has_counter_evidence`
- `source_unreliable`
- `persuasive_explanation`

Verdict acceptance is stored as:

- `verdict_accepted`
- `verdict_rejected`
- `verdict_unsure`

## 5. API endpoint structure

Implemented/extended:

```text
POST /assessments/{assessment_id}/feedback
GET  /admin/trust/analytics
```

### Extended feedback request

```json
{
  "rating": "Useful",
  "reasons": ["Source quality"],
  "trust_signals": ["needs_primary_sourcing", "overconfident"],
  "accepted_verdict": "unsure",
  "challenge_text": "The assessment missed a primary source from the regulator.",
  "counter_evidence": [
    {"url": "https://example.com/primary-source", "text": "Relevant excerpt"}
  ],
  "persuasive_source_ids": ["src_1"],
  "distrusted_source_ids": ["src_3"],
  "comment": "Useful, but source 3 looked weak."
}
```

### Admin trust analytics

```http
GET /admin/trust/analytics?limit=20
```

Requires master admin access.

Returns:

- top trust signals
- most disputed claims
- source reliability observations

This is intentionally an API foundation before a richer dashboard.

Future endpoints:

```text
GET  /admin/trust/disputed-claims
GET  /admin/trust/source-reliability
GET  /admin/trust/narrative-clusters
GET  /admin/trust/confidence-drift
POST /assessments/{id}/counter-evidence
PATCH /admin/trust/review-events/{id}
```

## 6. Feedback UI/UX proposal

Implemented first step:

- richer trust signal checkboxes in the web feedback box
- verdict acceptance selector
- challenge text field
- counter-evidence URL field
- persuasive/distrusted source selection should be added next using source IDs from the assessment

Recommended next UX:

1. Replace generic feedback with three sections:
   - “How did the verdict land?”
   - “Which evidence did you trust or distrust?”
   - “What did Evidrai miss?”
2. Show source-level controls directly on source cards:
   - “Persuasive”
   - “Weak”
   - “Biased”
   - “Unreliable”
3. Add counter-evidence submission as a first-class mini-form:
   - URL
   - excerpt
   - relationship: contradicts / adds context / supports / questions source
4. For Researcher / Journalist tier, add review queue and export.

## 7. Internal analytics/admin design

Admin dashboard should eventually show:

- most disputed claims
- claims with low trust scores
- frequently challenged verdicts
- sources frequently marked biased/unreliable
- topics generating uncertainty
- narrative spread patterns
- counter-evidence trends
- repeated misinformation themes
- confidence drift over time
- source credibility evolution

Current API foundation:

- `GET /admin/trust/analytics`

Next admin UI:

- Add Trust Intelligence tab to admin page
- Cards:
  - disputed claims
  - top negative trust signals
  - source reliability observations
  - counter-evidence submissions
  - confidence drift candidates

## 8. Scalability considerations

Near term:

- Postgres JSONB keeps implementation simple and flexible
- event-style trust records preserve granularity
- local JSONL fallback keeps development simple
- all trust capture is non-blocking for product flow

Medium term:

- partition `trust_signal_events` by time if volume grows
- add materialised views for admin analytics
- add background jobs for source reliability aggregation
- add vector indexes for claim/source embedding search
- use object storage for full source snapshots

Graph migration path:

- keep relational tables as source of truth
- export graph edges from:
  - claim -> source
  - source -> domain
  - claim -> narrative cluster
  - feedback -> claim
  - feedback -> source
  - counter-evidence -> assessment
  - source -> source via shared narrative cluster/domain/reference

## 9. ML-readiness considerations

The trust layer is designed as training-quality infrastructure, not analytics-only logging.

Preserved features:

- original claim
- full assessment payload
- source-level evidence detail
- scoring factors
- verdict and confidence
- narrative clusters
- event history
- verdict acceptance/rejection
- challenge text
- counter-evidence
- source trust/distrust signals
- pseudonymous actor hash

Future ML outputs:

- confidence calibration model
- source reliability model
- contradiction detector
- narrative propagation detector
- manipulation/framing detector
- evidence ranking model
- trust prediction model

Future ML infrastructure:

- embeddings for claims, sources, feedback, and counter-evidence
- feature store from trust tables
- graph edge export
- training dataset builder
- human review labelling workflow
- multi-model disagreement datasets

## 10. Multi-model orchestration approach

Principle:

> Model providers are reasoning engines. Evidrai owns credibility memory, calibration, and evidence intelligence.

Architecture:

```text
Claim/evidence input
  -> retrieval/source layer
  -> credibility layer provides source priors, evidence history, narrative context
  -> one or more model providers reason over the same packet
  -> Evidrai compares outputs, contradiction handling, confidence, and source usage
  -> final assessment is calibrated by Evidrai trust intelligence
```

Model-agnostic requirements:

- keep provider metadata on every model call
- preserve prompts/results for internal evaluation when safe
- normalise model outputs into provider-independent contracts
- compare model disagreement on verdict/confidence/sources
- allow future Evidrai-trained model to become one provider among many

Future provider fields:

- provider
- model
- model_version
- prompt_template_version
- output_schema_version
- latency/cost
- verdict/confidence output
- source usage
- disagreement score

## 11. Roadmap toward a Credibility Reasoning Model

### Phase 1: Foundation, now

- structured trust snapshot tables
- trust signal events
- counter-evidence table
- source reliability observations
- extended feedback API/UI
- admin analytics API

### Phase 2: Product learning loop

- source-level feedback buttons
- admin Trust Intelligence dashboard
- reviewer workflow for counter-evidence
- export v1 for Researcher / Journalist
- early source reliability aggregation

### Phase 3: Credibility graph

- graph-compatible edge export
- narrative cluster tracking
- claim similarity/duplication detection
- source relationship mapping
- confidence drift reports

### Phase 4: ML datasets

- embedding pipeline
- training dataset builder
- benchmark/evaluation harness
- multi-model comparison records
- feedback-to-fixture promotion

### Phase 5: Credibility Reasoning Model

- train/rank evidence retrieval
- calibrate confidence from historical trust outcomes
- predict source reliability and manipulation risk
- model contradiction patterns
- use Evidrai trust intelligence as proprietary retrieval/context layer

## 12. Implementation summary

Implemented in this iteration:

- `migrations/005_create_trust_intelligence.sql`
- `evidrai/trust.py`
- automatic trust snapshot capture after report save
- automatic trust event capture after feedback save
- extended feedback API schema
- admin trust analytics API
- richer feedback UI hooks

Key design decision:

- trust capture is non-blocking. Product paths continue even if trust logging fails.

Next best implementation step:

- Add source-level persuasive/distrusted controls directly onto evidence source cards and connect them to `persuasive_source_ids` / `distrusted_source_ids`.
