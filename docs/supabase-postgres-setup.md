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

## Migrations

Schema is controlled by explicit SQL migrations in `migrations/`.

Current migrations:

- `001_create_assessments_feedback.sql`

The app applies unapplied migrations on first Postgres store use and records them in:

- `evidrai_schema_migrations`

You can also apply migrations manually from a configured environment:

```bash
python scripts/apply_migrations.py
```

For Supabase SQL Editor/manual setup, copy the SQL from the migration file and run it once. The SQL is idempotent (`IF NOT EXISTS`).

Later production hardening should add backups, row-level security policy decisions, and object storage for large artefacts.

## Supabase notes

Use the pooled connection string for deployed apps if concurrency grows. Keep `sslmode=require` enabled.

Do not store large transcripts, raw source snapshots, or video artefacts directly in Postgres long term. Store metadata and references in Postgres; move large artefacts to object storage.
