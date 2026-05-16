# Independent FastAPI deployment

Status: deployment-prep slice for moving Evidrai beyond Streamlit.

## Goal

Run the Evidrai API as its own backend service. Streamlit remains a lab/admin UI, not the product runtime.

## Entrypoint

```bash
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Required environment variables

```text
OPENAI_API_KEY
DATABASE_URL
```

Recommended/optional:

```text
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY
API_ALLOWED_ORIGINS=https://your-frontend.example,http://localhost:3000
```

Do not commit secrets. Use the hosting provider's encrypted environment settings.

## Deployment files

- `Procfile` — generic Python web process
- `Dockerfile.api` — container deployment
- `render.yaml` — Render blueprint starter
- `scripts/smoke_api.py` — post-deploy smoke test

## Render deployment path

1. Create a new Render Web Service from the GitHub repo.
2. Use Python runtime or Docker.
3. Start command:

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

4. Add env vars:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `TAVILY_API_KEY`
   - `DATABASE_URL`
   - `API_ALLOWED_ORIGINS`
5. Health check path:

```text
/health
```

6. Deploy.

## Smoke test

Basic no-write smoke test:

```bash
API_BASE_URL=https://your-api-host.example python scripts/smoke_api.py
```

Full smoke test, including a Fast assessment and report listing:

```bash
API_BASE_URL=https://your-api-host.example API_SMOKE_FULL=1 python scripts/smoke_api.py
```

The full test uses model credits and writes an assessment to the configured storage backend.

## Success criteria

- `GET /health` returns `ok: true`
- `storage_backend` is `postgres`
- `openai_configured` is `true`
- `/docs` loads
- `POST /assessments/fast` returns an `AssessmentResponse`
- `/reports` lists the saved assessment
