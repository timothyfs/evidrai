# Evidrai API Integration v1

Date: 2026-08-02
Status: First implementation slice

## Goal

Package the existing Evidrai API surface as a developer-facing integration layer for trusted customers, starting with Researcher / Journalist accounts.

The product already has FastAPI endpoints for assessments, reports, speech/video audits, feedback, diagnostics, and admin operations. This track adds the missing integration wrapper: API keys, scopes, versioned documentation, usage controls, and eventually webhooks.

Durability is governed by [API Stability Policy](api-stability-policy.md). External integrations must be insulated from backend architecture changes.

## Initial Use Cases

1. Run claim checks from another app, workflow, or browser extension.
2. Submit transcripts or YouTube/source URLs and extract checkable claims.
3. Verify selected extracted claims and retrieve structured results.
4. Retrieve saved reports for embedding in downstream workflows.
5. Later: submit long-running jobs and receive webhook callbacks.

## Authentication

External integrations use:

```http
X-Evidrai-Api-Key: evd_live_...
Content-Type: application/json
```

API keys are stored hashed at rest. Plaintext keys are returned once when an admin creates the key.

API-key access is currently gated by the existing tier feature flag:

```text
researcher.features.api_access = true
```

Free and Pro profiles do not receive API access by default.

## Admin Key Management

Admin-only endpoints:

```http
GET /admin/api-keys?owner_id=<user-id>
POST /admin/api-keys
DELETE /admin/api-keys/{key_id}
```

Create request:

```json
{
  "owner_id": "supabase-user-id",
  "name": "CRM integration",
  "scopes": ["assessments:write", "reports:read", "speech:write"]
}
```

Create response includes `api_key` once. Persist only the hashed key server-side.

## First Supported Customer Endpoints

The first integration layer should support the existing product endpoints:

```http
POST /assessments/fast
POST /assessments/deep
POST /assessment-jobs/{mode}
GET /assessment-jobs/{job_id}
POST /speech/extract
POST /speech/verify
GET /reports
GET /reports/{report_id}
```

The canonical response contract remains `AssessmentResponse`.

## Scope Model

Initial scopes are enforced per route:

```text
assessments:write
speech:write
reports:read
```

Requests using an API key without the required scope return `403` with `detail.code = "insufficient_api_scope"`.

## Next Steps

1. Add `/v1/...` aliases for customer-facing endpoints.
2. Add usage metering by API key and owner profile.
3. Add monthly quota enforcement using tier limits.
4. Add developer documentation with curl examples.
5. Add webhook callbacks for async jobs.
6. Expose API key creation/revocation in the Admin UI.
