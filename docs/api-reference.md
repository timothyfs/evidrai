# Evidrai API Reference

Date: 2026-05-19  
API version: `api.v1`  
Backend entrypoint: `api/main.py`  
Canonical product result: `AssessmentResponse` from `evidrai/api_models.py`

## 1. Base URLs

Local development:

```text
http://127.0.0.1:8000
```

Current production backend convention:

```text
https://evidrai.onrender.com
```

Frontend default is defined in `web/lib/api.ts`:

```ts
NEXT_PUBLIC_API_BASE_URL || 'https://evidrai.onrender.com'
```

## 2. Interactive docs

FastAPI-generated docs are available when the API is running:

```http
GET /docs
GET /openapi.json
```

This file is the hand-written product/API reference. If the OpenAPI output and this file disagree, inspect `api/main.py` and update this file.

## 3. Authentication and ownership

### 3.1 Headers

Most user-scoped endpoints accept either a Supabase Bearer token or a temporary anonymous owner header.

```http
Authorization: Bearer <supabase-access-token>
X-Evidrai-User-Id: <browser-or-user-owner-id>
Content-Type: application/json
```

Resolution order:

1. If a valid Bearer token is present, the backend uses the token `sub` as `owner_id` and token `email` as profile email.
2. If no Bearer token is present, the backend uses `X-Evidrai-User-Id` as an anonymous owner fallback.
3. If neither is present, the request is anonymous.

### 3.2 Supabase token verification

Implemented in `evidrai/auth.py`.

- If `SUPABASE_JWT_SECRET` is configured and validates, HS256 verification is used.
- If HS256 fails or no JWT secret is configured, the backend verifies via Supabase JWKS using `SUPABASE_URL`.

### 3.3 Product tiers

Implemented in `evidrai/entitlements.py`.

```text
free        Fast claim checks, feedback, limited report history
pro         Fast + Deep, speech/video, share/export capability
researcher  Researcher / Journalist label, higher limits, ledger/export/API feature flags
```

Admin is not a product tier. Admin access is controlled separately.

### 3.4 Admin authorisation

Admin routes require one of:

- authenticated Supabase user whose email is in `EVIDRAI_MASTER_ADMIN_EMAILS`
- `X-Evidrai-Admin-Token` matching backend-only `EVIDRAI_ADMIN_TOKEN`

Backend-only secrets must not be exposed through frontend `NEXT_PUBLIC_*` variables.

## 4. Error format

Most application errors return HTTP status plus a `detail` field. Some errors are strings; structured Evidrai errors return an object similar to:

```json
{
  "detail": {
    "code": "feature_not_available",
    "message": "Your Free plan does not include this feature."
  }
}
```

Frontend code normalises some known user-facing errors, especially YouTube transcript blocking.

## 5. Runtime and metadata endpoints

### 5.1 Root

```http
GET /
```

Response:

```json
{
  "ok": true,
  "service": "evidrai-api",
  "api_version": "api.v1",
  "build": "phase-1-api-059fba3",
  "docs": "/docs",
  "health": "/health"
}
```

### 5.2 Version

```http
GET /version
```

Response:

```json
{
  "ok": true,
  "service": "evidrai-api",
  "api_version": "api.v1",
  "build": "phase-1-api-059fba3"
}
```

### 5.3 Health

```http
GET /health
```

Returns the same runtime status shape as `/runtime`.

### 5.4 Runtime

```http
GET /runtime
```

Response:

```json
{
  "ok": true,
  "api_version": "api.v1",
  "build": "phase-1-api-059fba3",
  "openai_configured": true,
  "tavily_configured": true,
  "storage_backend": "postgres",
  "auth_configured": true,
  "admin_configured": true,
  "transcript_backends": {
    "youtube_transcript_api": true,
    "yt_dlp": true,
    "yt_dlp_version": "2026.03.17"
  }
}
```

`transcript_backends` fields depend on installed packages and runtime detection.

## 6. Auth/profile/tier endpoints

### 6.1 Auth diagnostics

```http
GET /auth/diagnostics
Authorization: Bearer <token>
```

Purpose: safe token/config diagnostics without exposing secrets.

Response when no Bearer token is supplied:

```json
{
  "ok": true,
  "has_bearer": false,
  "diagnostics": {}
}
```

Response when token is present:

```json
{
  "ok": true,
  "has_bearer": true,
  "verified": true,
  "diagnostics": {
    "token_alg": "ES256",
    "token_kid_present": true,
    "token_issuer": "https://.../auth/v1",
    "token_subject_present": true,
    "token_email_present": true,
    "configured_supabase_url": "https://...",
    "jwt_secret_configured": false
  },
  "claims": {
    "subject_present": true,
    "email_present": true
  }
}
```

### 6.2 Tiers

```http
GET /tiers
```

Response:

```json
{
  "ok": true,
  "schema_version": "feature_matrix.v1",
  "tiers": [
    {
      "tier": "free",
      "label": "Free",
      "description": "Fast individual claim checks with limited saved report history.",
      "features": {
        "fast_claims": true,
        "deep_claims": false,
        "speech_audit": false,
        "feedback": true,
        "share_reports": false,
        "exports": false,
        "evidence_ledger": false,
        "source_snapshots": false,
        "api_access": false
      },
      "limits": {
        "saved_reports": 10,
        "max_speech_claims": 0,
        "monthly_fast_checks": 25,
        "monthly_deep_checks": 0,
        "monthly_speech_audits": 0
      }
    }
  ]
}
```

Also returns `pro` and `researcher` tiers.

### 6.3 Current user/profile

```http
GET /me
Authorization: Bearer <token>
```

Response:

```json
{
  "ok": true,
  "authenticated": true,
  "is_admin": true,
  "user": {
    "owner_id": "supabase-user-id",
    "email": "timfsmithson@gmail.com",
    "tier": "researcher",
    "subscription_status": "none",
    "trial_started_at": "",
    "trial_ends_at": "",
    "payment_provider_customer_id": "",
    "tier_label": "Researcher / Journalist",
    "features": {
      "fast_claims": true,
      "deep_claims": true,
      "speech_audit": true,
      "feedback": true,
      "share_reports": true,
      "exports": true,
      "evidence_ledger": true,
      "source_snapshots": true,
      "api_access": true
    },
    "limits": {
      "saved_reports": 2000,
      "max_speech_claims": 20,
      "monthly_fast_checks": 5000,
      "monthly_deep_checks": 1000,
      "monthly_speech_audits": 250
    }
  },
  "feature_matrix": {
    "schema_version": "feature_matrix.v1",
    "tiers": []
  }
}
```

If the signed-in email is in `EVIDRAI_MASTER_ADMIN_EMAILS`, `/me` returns `is_admin: true` and ensures the product tier is at least `researcher`.

## 7. Admin endpoints

### 7.1 List users

```http
GET /admin/users?limit=100
Authorization: Bearer <admin-token>
```

Response:

```json
{
  "ok": true,
  "users": [
    {
      "owner_id": "...",
      "email": "user@example.com",
      "tier": "pro",
      "tier_label": "Pro",
      "features": {},
      "limits": {}
    }
  ],
  "feature_matrix": {
    "schema_version": "feature_matrix.v1",
    "tiers": []
  }
}
```

### 7.2 Set user tier

```http
PATCH /admin/users/tier
Authorization: Bearer <admin-token>
```

Request:

```json
{
  "owner_id": "supabase-user-id-or-anon-owner",
  "tier": "researcher",
  "email": "user@example.com"
}
```

Response:

```json
{
  "ok": true,
  "user": {
    "owner_id": "...",
    "email": "user@example.com",
    "tier": "researcher",
    "tier_label": "Researcher / Journalist",
    "features": {},
    "limits": {}
  }
}
```

### 7.3 Invite or create user

```http
POST /admin/users/invite
Authorization: Bearer <admin-token>
```

Requires backend `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_URL`.

To send the branded Evidrai email directly, configure SMTP on the backend:

- `SMTP_HOST`
- `SMTP_PORT`, default `587`
- `SMTP_USERNAME`, optional if provider does not require auth
- `SMTP_PASSWORD`, optional if provider does not require auth
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`, default `Evidrai`
- `SMTP_STARTTLS`, default `true`
- `SMTP_USE_SSL`, default `false`

Request:

```json
{
  "email": "new-user@example.com",
  "tier": "pro",
  "send_invite": true,
  "send_branded_email": true,
  "redirect_to": "https://evidrai.vercel.app",
  "personal_message": "You are invited to controlled early access for Evidrai."
}
```

Response:

```json
{
  "ok": true,
  "sent_invite": true,
  "branded_email_sent": true,
  "branded_email_error": "",
  "owner_id": "supabase-user-id",
  "email": "new-user@example.com",
  "user": {},
  "invite_email": {
    "subject": "Your Evidrai early access invite",
    "text": "Your Evidrai early access invite...",
    "html": "<!doctype html>...",
    "logo_url": "https://evidrai.vercel.app/brand/evidrai-logo-full.jpg",
    "app_url": "https://evidrai.vercel.app"
  },
  "message": "Invitation sent and profile created."
}
```

If `send_invite` is false, the backend creates a Supabase auth user without sending the invite email. The response still includes `invite_email` so an admin can copy a polished branded message. Supabase controls the actual auth-link delivery unless a separate mail provider is added later.

If `send_branded_email` is true but SMTP is missing or the provider rejects the message, user creation still succeeds and `branded_email_sent` is false with `branded_email_error` explaining the mail failure.

### 7.4 Send branded invite email

```http
POST /admin/users/send-invite-email
Authorization: Bearer <admin-token>
```

Sends the branded Evidrai early-access email without creating or changing the user. Requires SMTP configuration.

Request:

```json
{
  "email": "new-user@example.com",
  "tier": "pro",
  "redirect_to": "https://evidrai.vercel.app",
  "personal_message": "You are invited to controlled early access for Evidrai."
}
```

Response:

```json
{
  "ok": true,
  "email": "new-user@example.com",
  "branded_email_sent": true,
  "invite_email": {},
  "message": "Branded invite email sent."
}
```

### 7.5 Delete user profile

```http
DELETE /admin/users/{owner_id}
Authorization: Bearer <admin-token>
```

Deletes the Evidrai profile record only. It does not delete the Supabase auth account.

Response:

```json
{
  "ok": true,
  "owner_id": "...",
  "deleted": true,
  "message": "User profile deleted. Supabase auth account was not deleted."
}
```

## 8. Assessment endpoints

### 8.1 Legacy claim check

```http
POST /claims/check
```

Request:

```json
{
  "claim": "France is a member of the EU.",
  "source_url": "",
  "category": "auto-detect",
  "mode": "deep",
  "include_debug": false
}
```

Response envelope:

```json
{
  "ok": true,
  "build": "phase-1-api-059fba3",
  "result": {
    "verdict": "Supported",
    "confidence": "High",
    "sources": [],
    "settings": {
      "result_mode": "deep",
      "claim_category": "auto-detect",
      "source_url": "",
      "build": "phase-1-api-059fba3"
    },
    "assessment": {
      "schema_version": "assessment_response.v1",
      "assessment_id": "uuid"
    }
  }
}
```

Notes:

- This endpoint is retained for compatibility.
- It does not save the embedded `assessment` as a report.
- New product flows should use `/assessments/fast` or `/assessments/deep`.

### 8.2 Fast assessment

```http
POST /assessments/fast
Authorization: Bearer <token>
```

Requires: `fast_claims` feature.

Request:

```json
{
  "claim": "France is a member of the EU.",
  "source_url": "",
  "category": "auto-detect",
  "include_debug": false
}
```

Response: `AssessmentResponse`.

Fast mode requires `OPENAI_API_KEY`, but does not require `TAVILY_API_KEY`.

### 8.3 Deep assessment

```http
POST /assessments/deep
Authorization: Bearer <token>
```

Requires: `deep_claims` feature.

Request:

```json
{
  "claim": "France is a member of the EU.",
  "source_url": "",
  "category": "auto-detect",
  "include_debug": false
}
```

Response: `AssessmentResponse`.

Deep mode requires both:

```text
OPENAI_API_KEY
TAVILY_API_KEY
```

### 8.4 URL-only assessment behaviour

For `/assessments/fast`, `/assessments/deep`, and `/claims/check`, a request may provide an empty `claim` and a valid `source_url`.

The backend will:

1. fetch the URL
2. extract candidate claims
3. choose a primary candidate or fallback to source title/excerpt
4. run the normal assessment flow

Invalid request:

```json
{
  "claim": "",
  "source_url": ""
}
```

Returns HTTP 400.

## 9. AssessmentResponse schema

Representative shape:

```json
{
  "schema_version": "assessment_response.v1",
  "assessment_id": "uuid",
  "created_at": "2026-05-19T05:00:00.000000+00:00",
  "build": "phase-1-api-059fba3",
  "mode": "deep",
  "owner_id": "supabase-user-id-or-anon-id",
  "request": {
    "claim": "France is a member of the EU.",
    "source_url": null,
    "category": "auto-detect",
    "settings": {
      "retrieval_provider": "tavily",
      "legacy_endpoint": "/claims/check"
    }
  },
  "verdict": {
    "label": "Supported",
    "confidence": "High",
    "summary": "Short product-ready summary.",
    "key_caveat": "Important limitation or caveat.",
    "evidence_strength_score": 7.5
  },
  "claim_breakdown": [
    {
      "id": "sc_1",
      "text": "France is a member of the EU.",
      "dimension": "factual_core",
      "assessment": "Supported",
      "confidence": "High",
      "rationale": "Rule-engine rationale.",
      "supporting_source_ids": ["src_1"],
      "contradicting_source_ids": []
    }
  ],
  "evidence_map": {
    "supports_factual_core": ["src_1"],
    "contradicts_factual_core": [],
    "supports_interpretation": [],
    "disputes_interpretation": [],
    "context_only": [],
    "weak_or_irrelevant": []
  },
  "sources": [
    {
      "id": "src_1",
      "title": "Official source",
      "url": "https://example.com",
      "domain": "example.com",
      "source_type": "primary",
      "stance": "supports",
      "evidence_category": "evidence",
      "source_role": "primary_evidence",
      "narrative_cluster": "official-record",
      "score": 4.5,
      "scoring_factors": {
        "authority": 5,
        "relevance": 5,
        "directness": 5,
        "recency": 4,
        "bias_risk": 1,
        "weighted": 4.5
      },
      "summary": "Why this source matters.",
      "classification_reason": "Primary source directly supports the claim."
    }
  ],
  "reasoning": {
    "consensus_strength": "Strong",
    "consensus_summary": "...",
    "reasoning_summary": {},
    "evidence_assessment": {},
    "rule_engine": {},
    "amplification_warning": null
  },
  "debug": null
}
```

## 10. Reports endpoints

### 10.1 List reports

```http
GET /reports?limit=50
Authorization: Bearer <token>
```

Response:

```json
{
  "ok": true,
  "owner_id": "supabase-user-id",
  "reports": [
    {
      "assessment_id": "uuid",
      "created_at": "2026-05-19T05:00:00+00:00",
      "mode": "deep",
      "claim": "France is a member of the EU.",
      "verdict": "Supported",
      "owner_id": "supabase-user-id"
    }
  ]
}
```

If authenticated, the list is scoped to the authenticated user. Anonymous mode scopes to `X-Evidrai-User-Id` where supplied.

### 10.2 Get report

```http
GET /reports/{report_id}
Authorization: Bearer <token>
```

Response: full `AssessmentResponse`.

Access rule:

- if the report has an `owner_id`, only the owner or a master admin can load it
- ownerless/legacy reports are loadable

## 11. Feedback endpoints

### 11.1 Submit assessment feedback

```http
POST /assessments/{assessment_id}/feedback
```

Request:

```json
{
  "rating": "Useful",
  "reasons": ["Verdict clarity", "Source quality"],
  "trust_signals": ["needs_primary_sourcing", "balanced_explanation"],
  "accepted_verdict": "unsure",
  "challenge_text": "The answer needs a primary regulatory source.",
  "counter_evidence": [
    {"url": "https://example.com/primary-source", "text": "Relevant excerpt"}
  ],
  "persuasive_source_ids": ["src_1"],
  "distrusted_source_ids": ["src_3"],
  "comment": "Useful result, but caveat could be clearer."
}
```

`rating` must be one of:

```text
Useful
Partly useful
Not useful
```

Response:

```json
{
  "ok": true,
  "feedback_id": "uuid",
  "assessment_id": "uuid",
  "destination": "postgres",
  "message": "Feedback saved."
}
```

The backend loads the original report and stores feedback with assessment context. The extended fields are also captured by the Trust Intelligence Feedback Layer as structured training-quality trust signals. `accepted_verdict` may be `accepted`, `rejected`, `unsure`, or empty.

### 11.2 List feedback for assessment

```http
GET /assessments/{assessment_id}/feedback?limit=100
```

Response:

```json
{
  "ok": true,
  "assessment_id": "uuid",
  "feedback_count": 1,
  "feedback": [
    {
      "feedback_id": "uuid",
      "assessment_id": "uuid",
      "rating": "Useful",
      "comment": "..."
    }
  ]
}
```

### 11.3 Get feedback by ID

```http
GET /feedback/{feedback_id}
```

Response:

```json
{
  "ok": true,
  "feedback_id": "uuid",
  "assessment_id": "uuid",
  "feedback": {}
}
```

Returns HTTP 404 if the feedback ID is unknown.

### 11.4 Admin trust analytics

```http
GET /admin/trust/analytics?limit=20
```

Requires master admin access.

Response:

```json
{
  "ok": true,
  "backend": "postgres",
  "top_signals": [],
  "most_disputed_claims": [],
  "source_reliability_observations": []
}
```

This is the first internal endpoint for the Trust Intelligence Feedback Layer. It exposes structured feedback patterns without coupling the product to any single model provider.

### 11.5 Backfill trust analytics from saved reports

```http
POST /admin/trust/backfill?limit=1000
```

Requires master admin access.

This replays existing saved reports into the Trust Intelligence claim/source tables. It is safe to run more than once because claim snapshots upsert by `assessment_id` and source rows are refreshed per assessment.

Response:

```json
{
  "ok": true,
  "reports_seen": 25,
  "captured": 25,
  "failed": 0,
  "failures": [],
  "analytics": {}
}
```

## 12. Source and transcript endpoints

### 12.1 Extract source URL

```http
POST /sources/extract
```

Request:

```json
{
  "source_url": "https://example.com/article"
}
```

Response shape: `ExtractedSource` from `evidrai/ingestion/url.py`.

Representative response:

```json
{
  "schema_version": "source_extract.v1",
  "url": "https://example.com/article",
  "title": "Article title",
  "description": "Meta description",
  "text_excerpt": "Readable excerpt...",
  "candidate_claims": ["Candidate claim from article"]
}
```

Exact fields should be checked against `evidrai/ingestion/url.py` if extending this endpoint.

### 12.2 Diagnose YouTube transcript extraction

```http
POST /transcripts/diagnose
```

Request:

```json
{
  "source_url": "https://youtu.be/cR5Dmj6GK88?is=byMagKFTQJoUPeOM"
}
```

Rules:

- `source_url` must be HTTP(S)
- currently supports YouTube URLs only

Response includes backend availability/failure detail for YouTube transcript extraction. Use it to debug Render/Vercel/cloud-hosted transcript behaviour.

## 13. Speech/video endpoints

### 13.1 Extract speech claims

```http
POST /speech/extract
Authorization: Bearer <token>
```

Requires: `speech_audit` feature.

Request:

```json
{
  "transcript": "Paste transcript text here...",
  "source_url": "https://youtu.be/cR5Dmj6GK88?is=byMagKFTQJoUPeOM",
  "max_claims": 3,
  "try_youtube_captions": true
}
```

Behaviour:

- If `transcript` is present, pasted transcript is used.
- If no transcript is present and `source_url` is a YouTube URL and `try_youtube_captions` is true, the backend attempts caption extraction.
- YouTube extraction is best-effort and may be blocked by hosting/IP/provider restrictions.

Response envelope:

```json
{
  "ok": true,
  "build": "phase-1-api-059fba3",
  "result": {
    "schema_version": "speech_extraction.v1",
    "title": "Speech / video audit",
    "speaker": "",
    "source_url": "https://youtu.be/...",
    "summary": "Short summary of the material.",
    "claims": [
      {
        "id": "claim_1",
        "quote": "Original quoted line",
        "normalized_claim": "Checkable claim",
        "timestamp": "",
        "speaker": "",
        "topic": "general",
        "claim_type": "factual",
        "checkability": "checkable",
        "priority": "high",
        "why_it_matters": "Why this claim matters",
        "verification_query": "Suggested query"
      }
    ],
    "skipped_rhetoric": [],
    "extraction_notes": [],
    "transcript_truncated": false,
    "transcript_chars_used": 1234,
    "transcript_chars_original": 1234,
    "settings": {
      "result_mode": "speech_extract",
      "source_url": "https://youtu.be/...",
      "max_claims": 3,
      "build": "phase-1-api-059fba3"
    }
  }
}
```

### 13.2 Verify selected speech claims

```http
POST /speech/verify
Authorization: Bearer <token>
```

Requires: `speech_audit` feature.

Request:

```json
{
  "claims": [
    {
      "id": "claim_1",
      "quote": "Original quoted line",
      "normalized_claim": "Checkable claim",
      "timestamp": "",
      "speaker": "",
      "topic": "general",
      "claim_type": "factual",
      "checkability": "checkable",
      "priority": "high",
      "why_it_matters": "Why this claim matters",
      "verification_query": "Suggested query"
    }
  ],
  "source_url": "https://youtu.be/cR5Dmj6GK88?is=byMagKFTQJoUPeOM",
  "verification_mode": "fast"
}
```

`verification_mode` must be:

```text
fast
deep
```

Deep requires `TAVILY_API_KEY`. Fast does not.

Response envelope:

```json
{
  "ok": true,
  "build": "phase-1-api-059fba3",
  "result": {
    "schema_version": "speech_verification.v1",
    "source_url": "https://youtu.be/...",
    "claims_checked": [
      {
        "speech_claim": {},
        "audit_index": 1,
        "verification_mode": "fast",
        "assessment_id": "uuid",
        "assessment": {
          "schema_version": "assessment_response.v1",
          "assessment_id": "uuid",
          "mode": "speech-fast"
        }
      }
    ],
    "claims_checked_count": 1,
    "verification_mode": "fast",
    "settings": {
      "result_mode": "speech_verify",
      "source_url": "https://youtu.be/...",
      "verification_mode": "fast",
      "build": "phase-1-api-059fba3"
    }
  }
}
```

Important: each checked claim is saved as a normal report and can be loaded later through `/reports/{assessment_id}`.

### 13.3 One-shot speech audit

```http
POST /speech/audit
Authorization: Bearer <token>
```

Requires: `speech_audit` feature.

Request:

```json
{
  "transcript": "Paste transcript text here...",
  "source_url": "https://youtu.be/cR5Dmj6GK88?is=byMagKFTQJoUPeOM",
  "max_claims": 3,
  "verification_mode": "fast",
  "try_youtube_captions": true
}
```

Response envelope:

```json
{
  "ok": true,
  "build": "phase-1-api-059fba3",
  "result": {
    "schema_version": "speech_audit.v1",
    "title": "Speech / video audit",
    "speaker": "",
    "source_url": "https://youtu.be/...",
    "summary": "...",
    "claims_extracted": [],
    "claims_checked": [
      {
        "assessment_id": "uuid",
        "assessment": {
          "schema_version": "assessment_response.v1"
        }
      }
    ],
    "claims_checked_count": 1,
    "verification_mode": "fast",
    "transcript_truncated": false,
    "transcript_chars_used": 1234,
    "transcript_chars_original": 1234,
    "claims_needing_attention_count": 0,
    "skipped_rhetoric": [],
    "extraction_notes": [],
    "settings": {
      "result_mode": "speech_audit",
      "source_url": "https://youtu.be/...",
      "max_claims": 3,
      "verification_mode": "fast",
      "build": "phase-1-api-059fba3"
    }
  }
}
```

Product UI should prefer the two-stage `/speech/extract` then `/speech/verify` flow to avoid verifying irrelevant/rhetorical claims and to control token spend.

## 14. Entitlement failures

Examples:

Free user attempting speech audit:

```json
{
  "detail": {
    "code": "feature_not_available",
    "message": "Your Free plan does not include this feature."
  }
}
```

Speech claim limit exceeded:

```json
{
  "detail": {
    "code": "limit_exceeded",
    "message": "Your Pro plan allows up to 5 speech claims per audit."
  }
}
```

Deep mode without Tavily:

```json
{
  "detail": {
    "code": "configuration_error",
    "message": "TAVILY_API_KEY is required for deep mode"
  }
}
```

## 15. Operational examples

### 15.1 Local run

```bash
uvicorn api.main:app --reload
```

### 15.2 Fast assessment curl

```bash
curl -sS http://127.0.0.1:8000/assessments/fast \
  -H 'Content-Type: application/json' \
  -H 'X-Evidrai-User-Id: local-test-user' \
  -d '{"claim":"France is a member of the EU.","category":"auto-detect"}'
```

### 15.3 Deep assessment curl

```bash
curl -sS http://127.0.0.1:8000/assessments/deep \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <supabase-access-token>' \
  -d '{"claim":"France is a member of the EU.","category":"auto-detect"}'
```

### 15.4 Speech extraction curl

```bash
curl -sS http://127.0.0.1:8000/speech/extract \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <supabase-access-token>' \
  -d '{"transcript":"","source_url":"https://youtu.be/cR5Dmj6GK88?is=byMagKFTQJoUPeOM","max_claims":3,"try_youtube_captions":true}'
```

## 16. Current implemented endpoints checklist

```text
GET    /
GET    /version
GET    /health
GET    /runtime
GET    /auth/diagnostics
GET    /tiers
GET    /me
GET    /admin/users
PATCH  /admin/users/tier
POST   /admin/users/invite
DELETE /admin/users/{owner_id}
GET    /admin/trust/analytics
POST   /admin/trust/backfill
POST   /sources/extract
POST   /transcripts/diagnose
POST   /claims/check
POST   /assessments/fast
POST   /assessments/deep
GET    /reports
GET    /reports/{report_id}
POST   /assessments/{assessment_id}/feedback
GET    /assessments/{assessment_id}/feedback
GET    /feedback/{feedback_id}
POST   /speech/extract
POST   /speech/verify
POST   /speech/audit
```

## 17. Known non-endpoints / future API work

These are not implemented as stable endpoints yet:

```text
PATCH /feedback/{feedback_id}/review
POST  /assessment-jobs
GET   /assessment-jobs/{job_id}
GET   /reports/{id}/share
POST  /sources/snapshot
POST  /uploads/audio-transcribe
```

Do not document these as live without adding tests and FastAPI routes first.
