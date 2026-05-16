# FastAPI backend hardening

Status: Step 1 of moving Evidrai beyond Streamlit.

## Purpose

FastAPI is the product backend. Streamlit remains the lab/admin UI.

This step makes the backend more deployment-ready without changing product behaviour.

## Added runtime endpoints

```http
GET /
GET /version
GET /health
GET /runtime
```

- `/` returns service metadata and links to docs/health.
- `/version` returns API/build metadata.
- `/health` returns runtime configuration flags.
- `/runtime` mirrors health for future admin/status use.

## CORS

The API now uses FastAPI CORS middleware.

Configure allowed origins with:

```toml
API_ALLOWED_ORIGINS = "http://localhost:3000,https://your-frontend.example"
```

or:

```toml
[api]
allowed_origins = "http://localhost:3000,https://your-frontend.example"
```

Default local frontend origins:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

## Current backend-of-record endpoints

```http
POST /assessments/fast
POST /assessments/deep
GET /reports
GET /reports/{report_id}
POST /assessments/{assessment_id}/feedback
GET /assessments/{assessment_id}/feedback
POST /speech/audit
POST /sources/extract
```

## Next step

Deploy the FastAPI service independently from Streamlit, using the same Supabase `DATABASE_URL` and API/search secrets.
