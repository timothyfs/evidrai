# Supabase Postgres setup

Status: optional backend, enabled only when `DATABASE_URL` is configured.

## Recommended use

Use Supabase Postgres as the prototype cloud ledger backend for:

- persisted assessments
- saved report history
- assessment-linked feedback

Keep local JSON fallback for development and emergency recovery.

## Configuration

Set one of these values in the runtime environment or Streamlit secrets:

```toml
DATABASE_URL = "postgresql://postgres:<password>@<host>:5432/postgres?sslmode=require"
```

or:

```toml
[database]
url = "postgresql://postgres:<password>@<host>:5432/postgres?sslmode=require"
```

Do not commit credentials. `.streamlit/secrets.toml` must stay local/private.

## Runtime behaviour

- If `DATABASE_URL` is present, Evidrai uses Postgres stores.
- If `DATABASE_URL` is missing, Evidrai falls back to local JSON:
  - `.evidrai/reports/`
  - `.evidrai_feedback/feedback.jsonl`

The API health endpoint reports the selected backend as `storage_backend`.

## Tables created automatically

The app creates minimal tables on first use:

- `assessments`
- `feedback`

This is intentionally simple for the prototype. Later production hardening should add explicit migrations, backups, row-level security policy decisions, and object storage for large artefacts.

## Supabase notes

Use the pooled connection string for deployed apps if concurrency grows. Keep `sslmode=require` enabled.

Do not store large transcripts, raw source snapshots, or video artefacts directly in Postgres long term. Store metadata and references in Postgres; move large artefacts to object storage.
