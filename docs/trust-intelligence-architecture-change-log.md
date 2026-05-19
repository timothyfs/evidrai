# Trust Intelligence Architecture Changes

Date: 2026-05-19  
Status: Implemented foundation  
Related docs:

- `docs/trust-intelligence-feedback-layer.md`
- `docs/architecture-and-plumbing.md`
- `docs/api-reference.md`

## Summary

Evidrai now has the first foundation of a Trust Intelligence layer.

Previously, feedback was mainly a saved user comment linked to an assessment. The new architecture turns assessments, sources, verdict reactions, user challenges, and counter-evidence into structured trust data that can later support:

- source reliability scoring
- disputed-claim tracking
- confidence calibration
- narrative cluster analysis
- counter-evidence review workflows
- future credibility-model training
- multi-model trust orchestration

The important design decision is that this layer sits alongside the product flow. It captures intelligence without blocking normal assessment, report, or feedback behaviour.

## What changed

### 1. New trust capture module

Added:

```text
evidrai/trust.py
```

This module owns the Trust Intelligence capture logic:

- converts saved assessments into trust snapshots
- decomposes evidence sources into queryable records
- converts feedback into trust signal events
- records counter-evidence submissions
- records raw source reliability observations
- provides a local JSONL fallback when Postgres is not configured
- provides a Postgres implementation when `DATABASE_URL` is configured
- exposes a small analytics summary function for admin use

### 2. New database migration

Added:

```text
migrations/005_create_trust_intelligence.sql
```

New tables:

```text
trust_claim_checks
trust_evidence_sources
trust_signal_events
trust_counter_evidence
source_reliability_observations
```

These tables keep the raw trust intelligence separate from the existing `assessments` and `feedback` tables.

### 3. Report saving now captures trust snapshots

Changed:

```text
evidrai/reports.py
```

Flow now:

```text
AssessmentResponse generated
  -> save_report()
  -> existing ReportStore persists the assessment
  -> trust layer captures an assessment snapshot
  -> trust layer captures each evidence source
```

This happens automatically for saved assessments, including speech/video claim assessments.

The capture is non-blocking. If the trust layer fails, the report still saves.

### 4. Feedback saving now captures trust signal events

Changed:

```text
evidrai/feedback.py
```

Feedback records now support richer fields:

```text
trust_signals
accepted_verdict
challenge_text
counter_evidence
persuasive_source_ids
distrusted_source_ids
owner_id
```

Flow now:

```text
User submits feedback
  -> feedback record saved normally
  -> trust layer converts feedback into event records
  -> source trust/distrust signals become reliability observations
```

Again, capture is non-blocking. Feedback still saves even if trust capture fails.

### 5. Feedback API was extended

Changed:

```text
api/main.py
```

Extended endpoint:

```http
POST /assessments/{assessment_id}/feedback
```

It still accepts the old fields:

```json
{
  "rating": "Useful",
  "reasons": ["Source quality"],
  "comment": "Useful, but caveat could be clearer."
}
```

It now also accepts:

```json
{
  "trust_signals": ["needs_primary_sourcing", "overconfident"],
  "accepted_verdict": "unsure",
  "challenge_text": "The answer needs a primary source.",
  "counter_evidence": [
    {"url": "https://example.com/primary-source", "text": "Relevant excerpt"}
  ],
  "persuasive_source_ids": ["src_1"],
  "distrusted_source_ids": ["src_3"]
}
```

### 6. Admin analytics endpoint added

Added:

```http
GET /admin/trust/analytics?limit=20
```

This requires master admin access.

It returns early trust intelligence summaries:

- top trust signals
- most disputed claims
- source reliability observations

This is deliberately small. It is a foundation for a future admin Trust Intelligence dashboard, not the full dashboard itself.

### 7. Web feedback UI was expanded

Changed:

```text
web/app/page.tsx
web/lib/api.ts
web/app/globals.css
```

The feedback box is now “Trust feedback”, not just “Was this useful?”

It captures:

- usefulness rating
- verdict acceptance/rejection/uncertainty
- structured trust signals
- general feedback tags
- challenge/missing-context text
- counter-evidence URL/note
- optional comment

The UI sends the richer payload to the same feedback endpoint.

## How it works end to end

### Assessment path

```text
User submits a claim / URL / speech claim
  -> FastAPI creates AssessmentResponse
  -> save_report(assessment)
  -> ReportStore saves assessment to local storage or Postgres
  -> evidrai.trust.capture_assessment_snapshot(assessment)
  -> trust_claim_checks receives one claim-check snapshot
  -> trust_evidence_sources receives one row per evidence source
  -> API returns the normal assessment response
```

The user does not see any delay or separate trust step.

### Feedback path

```text
User submits Trust Feedback
  -> POST /assessments/{assessment_id}/feedback
  -> API loads original saved assessment
  -> build_feedback_record(...) adds assessment context and trust fields
  -> save_feedback(record)
  -> FeedbackStore saves the feedback record
  -> evidrai.trust.capture_feedback_trust_events(record)
  -> trust_signal_events receives event rows
  -> trust_counter_evidence receives submitted counter-evidence
  -> source_reliability_observations receives source trust/distrust observations
  -> API returns feedback_id
```

The original assessment payload is kept with the feedback so future review or regression workflows have the full context.

## Storage behaviour

### Local development

If `DATABASE_URL` is not configured:

```text
reports -> local report store
feedback -> .evidrai_feedback/feedback.jsonl
trust events -> .evidrai_trust/trust_events.jsonl
```

This keeps local development simple and avoids requiring Postgres for every test run.

### Production / Postgres

If `DATABASE_URL` is configured:

```text
reports -> assessments table
feedback -> feedback table
trust snapshots/events -> trust_* tables
```

Migrations are run through the existing migration system in `evidrai/db.py`.

## Data privacy design

The trust layer does not store raw user identity as the main actor key.

Instead:

```text
owner_id -> pseudonymous actor_hash
```

Implemented in:

```text
evidrai.trust.pseudonymous_actor_id()
```

This preserves the ability to analyse repeated trust patterns without making the trust tables primarily identity-led.

Current caveat: the full assessment payload may still contain `owner_id` inside nested JSON because it preserves the original assessment response. Before external analytics export or ML dataset publication, add a sanitisation/export step.

## Failure model

Trust capture is intentionally best-effort and non-blocking.

Examples:

- if Postgres trust insert fails, report saving still succeeds
- if trust event capture fails, feedback saving still succeeds
- the user-facing product path is protected from trust analytics failures

This is implemented with guarded calls in:

```text
evidrai/reports.py
save_report()

evidrai/feedback.py
save_feedback()
```

## Why this architecture matters

This changes Evidrai from a stateless verification surface into a system that can learn where trust breaks down.

It starts collecting structured answers to questions like:

- Which verdicts do users reject?
- Which claims are repeatedly disputed?
- Which sources are persuasive or distrusted?
- Which topics produce uncertainty?
- Where does Evidrai need stronger primary sourcing?
- Which narrative clusters recur across claims?
- Which evidence patterns change user views?

That is the foundation for the longer-term Evidrai moat: proprietary trust intelligence rather than just model output formatting.

## Current limitations

This is a foundation, not the finished intelligence layer.

Not yet implemented:

- source-level buttons on each evidence card
- admin Trust Intelligence dashboard UI
- reviewed/accepted counter-evidence workflow
- source reliability aggregation into live source priors
- confidence calibration model
- graph export
- embeddings for claim/source/feedback similarity
- multi-model disagreement tracking
- training dataset builder

## Next recommended steps

1. Add source-level feedback controls directly to evidence source cards.
2. Build the admin Trust Intelligence dashboard using `/admin/trust/analytics`.
3. Add a counter-evidence review queue.
4. Add source reliability aggregation from raw observations.
5. Add export pipeline for Researcher / Journalist tiers.
6. Add a graph/ML export job once enough real usage data exists.
