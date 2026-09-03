# Evidrai Enterprise Gateway Mode

Date: 2026-09-03
Status: Implementation plan

## Purpose

Enterprise Gateway Mode turns Evidrai from a claim-checking product into a control point between AI-generated output and consequential action.

Current Evidrai flow:

```text
claim or content -> evidence assessment -> report
```

Gateway flow:

```text
AI output / proposed action
-> Evidrai verification
-> customer policy evaluation
-> PASS / REVIEW / BLOCK
-> audit record and optional workflow callback
```

The verification core already exists. This track adds the gateway contract, decision policy, audit event, and integration surface needed for enterprise workflows.

## Scope

The first implementation should be a thin MVP:

- synchronous `POST /v1/gateway/verify`
- static built-in gateway policies
- consequence levels: `low`, `medium`, `high`
- decisions: `pass`, `review`, `block`
- deterministic mapping from assessment result to gateway decision
- persisted gateway audit record
- focused tests for response contract and decision mapping
- one finance briefing demo scenario

Out of scope for the first slice:

- full policy-builder UI
- full reviewer queue
- webhook delivery
- async gateway jobs
- customer-specific source registries
- billing and usage metering changes

## Existing Capabilities Reused

Evidrai already has:

- Fast and Deep assessment modes
- claim extraction and subclaim decomposition
- retrieval-backed evidence gathering
- source scoring for authority, relevance, directness, independence, recency, and bias risk
- contradiction checks
- amplification and narrative-cluster warnings
- rule-based verdict guardrails
- structured `AssessmentResponse`
- saved reports
- feedback capture
- API keys and scopes
- admin scoring-policy versions

Gateway Mode should wrap these capabilities rather than fork the verification engine.

## Gateway Request Contract

Initial endpoint:

```http
POST /v1/gateway/verify
```

Request:

```json
{
  "workflow_id": "investment-briefing-prod",
  "request_id": "external-request-123",
  "ai_output": "The Governor of the Bank of England warned that an AI hallucination could cause a global financial crash.",
  "proposed_action": {
    "type": "publish_briefing",
    "description": "Publish executive financial briefing"
  },
  "domain": "finance",
  "consequence_level": "high",
  "policy_id": "finance_default_v1",
  "cited_sources": [],
  "metadata": {}
}
```

Fields:

- `workflow_id`: caller-owned workflow identifier.
- `request_id`: caller-owned idempotency/correlation identifier.
- `ai_output`: model or agent output to verify.
- `proposed_action`: action that would happen if the output is accepted.
- `domain`: broad domain such as `finance`, `legal`, `comms`, `operations`, or `general`.
- `consequence_level`: `low`, `medium`, or `high`.
- `policy_id`: gateway policy to apply. Unknown policies should fall back safely.
- `cited_sources`: optional sources supplied by the upstream AI system.
- `metadata`: non-sensitive caller metadata.

## Gateway Response Contract

Response:

```json
{
  "schema_version": "gateway_decision.v1",
  "gateway_id": "gw_...",
  "created_at": "2026-09-03T12:00:00Z",
  "decision": "review",
  "decision_reason": "High-consequence workflow requires stronger support for material claims.",
  "recommended_next_step": "route_to_human_review",
  "policy_id": "finance_default_v1",
  "policy_version": 1,
  "workflow_id": "investment-briefing-prod",
  "request_id": "external-request-123",
  "assessment_id": "uuid",
  "triggered_rules": [
    {
      "rule_id": "high_consequence_unverified",
      "severity": "review",
      "message": "High-consequence outputs require at least likely-supported evidence."
    }
  ],
  "claims": [
    {
      "claim_id": "sc_1",
      "text": "The Governor of the Bank of England warned that an AI hallucination could cause a global financial crash.",
      "assessment": "Partly supported",
      "confidence": "Medium",
      "materiality": "material",
      "action_relevance": "review_relevant",
      "decision": "review",
      "reason": "The evidence supports broader AI-related financial risk, but not the specific hallucination/crash framing."
    }
  ],
  "blocking_claims": [],
  "review_claims": ["sc_1"],
  "allowed_actions": [],
  "assessment": {}
}
```

The existing `AssessmentResponse` remains the canonical verification record. The gateway response is the workflow decision wrapper.

## Gateway Policy Model

Gateway policy answers:

```text
Is the evidence sufficient for this proposed action?
```

This is separate from the existing scoring policy, which answers:

```text
How strong is this evidence?
```

Initial policy fields:

```json
{
  "policy_id": "finance_default_v1",
  "version": 1,
  "description": "Default finance gateway policy.",
  "rules": {
    "low": {
      "min_verdict": "Unverified",
      "min_confidence_score": 35,
      "min_evidence_strength_score": 0,
      "unverified_material_claim": "pass",
      "unsupported_material_claim": "review",
      "contradicted_material_claim": "block"
    },
    "medium": {
      "min_verdict": "Partly supported",
      "min_confidence_score": 50,
      "min_evidence_strength_score": 4,
      "unverified_material_claim": "review",
      "unsupported_material_claim": "review",
      "contradicted_material_claim": "block"
    },
    "high": {
      "min_verdict": "Likely supported",
      "min_confidence_score": 70,
      "min_evidence_strength_score": 7,
      "unverified_material_claim": "review",
      "unsupported_material_claim": "block",
      "contradicted_material_claim": "block"
    }
  }
}
```

## Decision Mapping

The first mapper should be deterministic and conservative.

Suggested mapping:

- `False / contradicted` material claim: `block`
- `Not supported by credible evidence` material claim: policy-defined, default `block` for high consequence
- `Weakly supported / likely incorrect` material claim: `review` or `block`
- `Unverified` material claim: `review` for medium/high consequence
- `Misleading framing` on a material claim: `review`
- `Partly supported` high-consequence material claim: `review`
- `Supported` or `Likely supported` above thresholds: `pass`

Decision severity order:

```text
pass < review < block
```

The overall decision is the highest-severity claim decision or triggered policy rule.

## Materiality MVP

The first implementation should infer materiality without a new model call.

Default:

- treat all extracted claim-breakdown items as `material`
- downgrade to `background` only when the claim is clearly context-only or rhetorical
- mark claims with quotes, numbers, named entities, regulatory/legal terms, financial terms, or causal language as material

Later:

- add a dedicated materiality classifier
- include `action_relevance`
- allow customer policy to define materiality by workflow type

## Audit Persistence

Persist one gateway audit record per request.

Initial local JSONL fallback:

```text
.evidrai_gateway/gateway_audit.jsonl
```

Record:

- gateway request
- gateway response
- assessment ID
- owner ID
- API key owner, if present
- policy ID/version
- triggered rules
- build/version
- created timestamp

Postgres migration can follow once the contract is stable.

## API Security

Initial gateway endpoint should require the same authenticated/API-key access pattern as assessment APIs.

Required API scope:

```text
gateway:write
```

For backwards compatibility during MVP testing, admin/master-authenticated users can call the endpoint. External API keys should require the explicit gateway scope.

## Tests

Minimum tests:

- supported high-confidence assessment maps to `pass`
- unverified high-consequence assessment maps to `review`
- contradicted material claim maps to `block`
- unknown policy falls back to default policy and records the fallback
- response includes `schema_version`, `gateway_id`, `decision`, `policy_id`, `assessment_id`, and `triggered_rules`
- API endpoint calls the existing assessment pipeline and persists an audit record

## Implementation Order

1. Add `evidrai/gateway_models.py`.
2. Add `evidrai/gateway.py`.
3. Add local gateway audit persistence.
4. Add `POST /v1/gateway/verify` in `api/main.py`.
5. Add API key scope `gateway:write`.
6. Add focused unit tests for decision mapping.
7. Add API contract tests.
8. Add docs and curl example to `docs/api-reference.md`.
9. Add finance briefing demo fixture.

## Success Criteria

The MVP is complete when a caller can submit an AI-generated financial briefing and proposed action, receive a deterministic `pass`, `review`, or `block` decision, and inspect the linked evidence assessment and triggered policy rules.

