# Evidrai API Contract v1 Draft

Date: 2026-05-14
Status: Draft for FastAPI migration

## Purpose

Define the first stable API/data contract for moving Evidrai from Streamlit-only prototype to a professional product architecture.

The contract should support:

- Fast assessments
- Deep assessments
- result retrieval
- persistent feedback
- reviewer labels
- regression case generation

---

## Principles

1. The API returns product-ready structured JSON, not UI-specific Streamlit state.
2. Every response includes build/schema metadata.
3. Fast and Deep share a common response shape.
4. Claim decomposition is first-class.
5. Evidence source roles are explicit.
6. Feedback can be joined back to the exact assessment output.
7. Review labels can turn feedback into regression cases.

---

## Endpoints

### Health

```http
GET /health
```

Response:

```json
{
  "ok": true,
  "build": "short-sha",
  "version": "api.v1"
}
```

### Create fast assessment

```http
POST /assessments/fast
```

Request:

```json
{
  "claim": "Nigel Farage failed to disclose a £5M gift.",
  "source_url": null,
  "category": "auto-detect",
  "use_lightweight_search": true
}
```

Response: `AssessmentResponse`

### Create deep assessment

```http
POST /assessments/deep
```

Request:

```json
{
  "claim": "Nigel Farage failed to disclose a £5M gift.",
  "source_url": null,
  "category": "auto-detect",
  "retrieval_provider": "tavily"
}
```

Response: `AssessmentResponse`

Future async version:

```http
POST /assessments/deep-jobs
GET /assessment-jobs/{job_id}
GET /assessments/{assessment_id}
```

### List reports

```http
GET /reports
GET /reports/{report_id}
```

`GET /reports` returns recent persisted report summaries. `GET /reports/{report_id}` returns the full `AssessmentResponse`.

### Submit feedback

```http
POST /assessments/{assessment_id}/feedback
```

Request:

```json
{
  "rating": "Partly useful",
  "reasons": ["Verdict clarity", "Too cautious"],
  "comment": "The factual claim seems supported but the app calls it unverified."
}
```

Response:

```json
{
  "ok": true,
  "feedback_id": "uuid",
  "assessment_id": "uuid",
  "destination": "local_jsonl",
  "message": "Saved to feedback log: .evidrai_feedback/feedback.jsonl"
}
```

### Retrieve feedback for an assessment

```http
GET /assessments/{assessment_id}/feedback
```

Response:

```json
{
  "ok": true,
  "assessment_id": "uuid",
  "feedback_count": 1,
  "feedback": []
}
```

### Review feedback

```http
PATCH /feedback/{feedback_id}/review
```

Request:

```json
{
  "expected_verdict": "Likely supported",
  "expected_confidence": "Medium",
  "error_type": ["legal_interpretive_nuance", "too_cautious"],
  "accepted_as_regression_case": true,
  "reviewer_notes": "Factual core supported; legal obligation remains contested."
}
```

Response:

```json
{
  "ok": true,
  "feedback_id": "uuid"
}
```

---

## AssessmentResponse

```json
{
  "schema_version": "assessment_response.v1",
  "assessment_id": "uuid",
  "created_at": "2026-05-14T11:00:00Z",
  "build": "040c8f1",
  "mode": "deep",
  "request": {
    "claim": "Nigel Farage failed to disclose a £5M gift.",
    "source_url": null,
    "category": "auto-detect",
    "settings": {
      "retrieval_provider": "tavily"
    }
  },
  "verdict": {
    "label": "Likely supported",
    "confidence": "Medium",
    "summary": "Evidence supports the factual core, while the legal disclosure obligation remains contested.",
    "key_caveat": "Whether the gift had to be declared under the relevant rules is unresolved.",
    "evidence_strength_score": 5.0
  },
  "claim_breakdown": [],
  "evidence_map": {},
  "sources": [],
  "reasoning": {},
  "debug": null
}
```

---

## ClaimBreakdownItem

```json
{
  "id": "sc_1_fact",
  "text": "A £5M gift existed.",
  "dimension": "factual_core",
  "assessment": "Supported",
  "confidence": "Medium",
  "rationale": "Multiple credible reports identify the amount and donor.",
  "supporting_source_ids": ["src_1", "src_2"],
  "contradicting_source_ids": []
}
```

Allowed `dimension`:

- `factual_core`
- `interpretation`
- `obligation`
- `wrongdoing`
- `context`

Allowed `assessment`:

- `Supported`
- `Likely supported`
- `Contested`
- `Unverified`
- `Not supported`
- `Unproven`

---

## EvidenceMap

```json
{
  "supports_factual_core": ["src_1", "src_2"],
  "contradicts_factual_core": [],
  "supports_interpretation": [],
  "disputes_interpretation": ["src_3"],
  "context_only": ["src_4"],
  "weak_or_irrelevant": []
}
```

---

## EvidenceSource

```json
{
  "id": "src_1",
  "title": "Watchdog weighs investigation into Farage’s undisclosed £5m gift",
  "url": "https://example.com/story",
  "domain": "example.com",
  "source_type": "secondary",
  "stance": "supports",
  "evidence_category": "credible_reporting",
  "source_role": "supports_factual_core",
  "score": 3.7,
  "summary": "The source reports that Farage received a £5M gift and that disclosure is under scrutiny.",
  "classification_reason": "Reports the gift and disclosure issue, but does not establish final legal breach."
}
```

---

## FeedbackRecord

```json
{
  "feedback_id": "uuid",
  "assessment_id": "uuid",
  "created_at": "timestamp",
  "rating": "useful|partly_useful|not_useful",
  "reasons": ["verdict_clarity"],
  "comment": "string",
  "expected_verdict": "Likely supported",
  "expected_confidence": "Medium",
  "review": {
    "error_type": ["legal_interpretive_nuance", "too_cautious"],
    "accepted_as_regression_case": true,
    "reviewer_notes": "string"
  }
}
```

---

## Implementation sequence

1. Add Pydantic models matching this contract inside `evidrai/api_models.py`. — Done
2. Add serializer from current `VerificationResult.to_dict()` into `AssessmentResponse`. — Done
3. Add FastAPI skeleton under `api/` or `services/api/`. — Done
4. Keep Streamlit rendering from the same serialized response. — In progress
5. Add fixture tests for response schema stability. — In progress
6. Move report and feedback persistence behind `ReportStore` / `FeedbackStore` interfaces. — Done for local JSON implementations
7. Add optional Postgres-backed `ReportStore` / `FeedbackStore` selected by `DATABASE_URL`. — Done

---

## Open questions

- Should Fast always use lightweight search by default when configured?
- Should Deep be async from day one of the API?
- Should assessment history require user identity immediately, or can it be anonymous session-based for v1?
- Should Notion remain a review sink, or should Postgres become source of truth with Notion as optional mirror?

Recommendation: Postgres should become source of truth once we leave Streamlit. Notion is excellent for review workflow, but not ideal as the primary product database.
