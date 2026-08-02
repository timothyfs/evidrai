# Evidrai API Stability Policy

Date: 2026-08-02
Status: Draft policy for external integrations

## Purpose

Evidrai APIs must remain stable for customers even when the backend architecture changes. External integrations should depend on documented contracts, not on storage tables, internal service boundaries, model providers, queue implementations, or frontend behaviour.

This policy applies to developer-facing API versions such as `api.v1` and future `/v1/...` routes.

## Stability Principles

1. Public API contracts are product contracts, not implementation contracts.
2. `AssessmentResponse` remains the canonical result shape for assessment APIs.
3. Backend architecture may change behind the API without breaking documented request/response fields.
4. New fields may be added, but existing documented fields must not be removed or repurposed inside the same major version.
5. Clients should tolerate unknown fields. Evidrai should not require clients to parse internal debug fields.
6. Errors must use stable machine-readable `detail.code` values for common failure modes.
7. Authentication mechanisms, scopes, rate limits, and quotas must be documented before enterprise use.

## Versioning Rules

### Non-breaking changes inside `v1`

Allowed:

- adding optional request fields
- adding response fields
- adding enum values when clients can safely ignore unknown values
- improving internal retrieval, scoring, model, queue, or storage implementation
- changing source providers as long as the documented response contract remains stable
- improving error messages while preserving stable `detail.code`

### Breaking changes

Require a new major version, for example `/v2`:

- removing or renaming documented response fields
- changing field meaning or units
- making optional request fields required
- changing authentication semantics in a way that breaks existing keys
- removing endpoint support
- changing stable error codes
- changing pagination, webhook signing, or idempotency semantics incompatibly

## Deprecation Rules

Enterprise-facing APIs should not be removed abruptly.

Default deprecation policy:

- announce deprecation in docs and release notes
- keep the old endpoint/version available for at least 12 months after notice
- provide a migration guide and side-by-side examples
- preserve security fixes on deprecated versions during the notice period
- offer customer-specific migration support for contracted integrations

Emergency exceptions are allowed only for security, legal, or abuse-control reasons.

## Backend Architecture Boundary

External clients must never depend on:

- database schema or table names
- Supabase internals
- Render/Vercel deployment topology
- model provider names
- search provider names
- queue/job backend details
- raw fetched source content
- internal debug traces
- admin-only endpoints

If these details are useful, expose them through explicit stable fields or documented diagnostics.

## Required Controls Before Broad Enterprise Use

Before offering external API access beyond controlled pilots:

1. API keys with hashed storage.
2. Scope enforcement per route.
3. `/v1/...` customer-facing route aliases.
4. Stable OpenAPI export reviewed against docs.
5. Idempotency keys for write/job creation endpoints.
6. Pagination contracts for list endpoints.
7. Rate limits and monthly quota enforcement.
8. Usage logging by API key and owner profile.
9. Webhook signing for async callbacks.
10. Contract tests that lock public request/response examples.

## Contract Test Requirement

Every public endpoint should have tests that verify:

- required fields remain present
- stable error codes remain unchanged
- unknown optional fields do not break requests
- API-key auth works for allowed scopes
- insufficient tier/scope failures return documented errors

These tests should fail loudly before any backend refactor ships.
