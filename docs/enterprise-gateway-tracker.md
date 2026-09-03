# Evidrai Enterprise Gateway Tracker

Date: 2026-09-03
Owner: Monty / Tim
Status: MVP slice implemented

## Current Goal

Ship a thin Enterprise Gateway Mode MVP that wraps the existing Evidrai verification engine with a policy-controlled `pass`, `review`, or `block` decision.

## Milestone 1: Gateway Contract

### Add gateway request and response models
- Status: Done
- Priority: Critical
- Area: API / Contract
- Description: Define Pydantic models for `GatewayVerifyRequest`, `ProposedAction`, `GatewayDecisionResponse`, `GatewayClaimDecision`, and `TriggeredGatewayRule`.
- Acceptance criteria:
  - Models use `schema_version = gateway_decision.v1`.
  - Consequence level is constrained to `low`, `medium`, `high`.
  - Decision is constrained to `pass`, `review`, `block`.
  - Response links to an `AssessmentResponse` by `assessment_id`.

### Add synchronous gateway endpoint
- Status: Done
- Priority: Critical
- Area: API
- Description: Add `POST /v1/gateway/verify` using the existing Deep assessment pipeline.
- Acceptance criteria:
  - Endpoint accepts AI output and proposed action context.
  - Endpoint requires authentication/API-key access.
  - Endpoint returns a gateway decision wrapper plus linked assessment ID.

## Milestone 2: Policy Decision Layer

### Add built-in gateway policies
- Status: Done
- Priority: Critical
- Area: Policy
- Description: Add static built-in policies for `default_v1` and `finance_default_v1`.
- Acceptance criteria:
  - Policies define thresholds by consequence level.
  - Unknown policy IDs fall back safely.
  - Policy ID and version are returned in every decision.

### Add deterministic decision mapper
- Status: Done
- Priority: Critical
- Area: Policy / Rules
- Description: Map existing `AssessmentResponse` verdict, confidence, evidence strength, and claim breakdown into `pass`, `review`, or `block`.
- Acceptance criteria:
  - Contradicted material claims block.
  - High-consequence unverified claims review.
  - Supported high-confidence claims pass.
  - Triggered rules explain the decision.

### Add materiality MVP
- Status: Done
- Priority: High
- Area: Claim semantics
- Description: Infer basic claim materiality and action relevance without adding another model call.
- Acceptance criteria:
  - Claim decisions include `materiality`.
  - Quote, number, named-entity, finance, legal/regulatory, and causal claims are treated as material.
  - Non-actionable context can be labelled separately later.

## Milestone 3: Auditability

### Persist gateway audit records
- Status: Done
- Priority: High
- Area: Persistence / Audit
- Description: Add local JSONL gateway audit persistence with a later Postgres path.
- Acceptance criteria:
  - Each gateway request creates an audit record.
  - Record includes request, response, assessment ID, policy ID/version, owner ID, triggered rules, and build.
  - Audit persistence failure does not hide the gateway decision.

### Add API contract tests
- Status: Done
- Priority: High
- Area: Validation
- Description: Add focused tests for gateway models, mapper, endpoint, and audit persistence.
- Acceptance criteria:
  - Tests do not require API keys.
  - Tests cover pass, review, block, and unknown-policy fallback.
  - Existing tests still pass.

## Milestone 4: Documentation And Demo

### Document Enterprise Gateway Mode
- Status: Done
- Priority: High
- Area: Documentation
- Description: Capture the target architecture, MVP scope, contracts, policies, and implementation order.
- Acceptance criteria:
  - `docs/enterprise-gateway-mode.md` exists.
  - Document clearly separates existing verification core from new gateway product layer.

### Add API reference section
- Status: Done
- Priority: Medium
- Area: Documentation
- Description: Add `/v1/gateway/verify` to the API reference after the endpoint lands.
- Acceptance criteria:
  - Includes request and response examples.
  - Includes API key scope note.
  - Includes finance briefing example.

### Add finance briefing demo fixture
- Status: Backlog
- Priority: Medium
- Area: Demo / Validation
- Description: Add a Bailey-style overstatement example to demonstrate `review`.
- Acceptance criteria:
  - Demo shows supported, unsupported, and suggested correction concepts.
  - Demo can be used in smoke testing.

## Validation

Latest local validation:

- `.venv/bin/python -m pytest -q`: 175 passed, 1 urllib3/LibreSSL warning
- `.venv/bin/python -m compileall api evidrai prompts.py tests`: passed

## Later Backlog

### Add human review queue
- Status: Backlog
- Priority: Medium
- Area: Review workflow
- Description: Add reviewer assignment, approve/reject/correct states, reviewer notes, overrides, and export.

### Add async gateway jobs
- Status: Backlog
- Priority: Medium
- Area: Workflow integration
- Description: Add long-running gateway jobs for slower Deep verification flows.

### Add gateway webhooks
- Status: Backlog
- Priority: Medium
- Area: Integration
- Description: Emit `gateway.pass`, `gateway.review_required`, and `gateway.block` events to configured callbacks.

### Add admin policy UI
- Status: Backlog
- Priority: Medium
- Area: Admin
- Description: Manage gateway policies in the Admin UI once the static policy contract is proven.
