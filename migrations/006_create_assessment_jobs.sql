CREATE TABLE IF NOT EXISTS assessment_jobs (
    job_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    mode TEXT NOT NULL DEFAULT 'fast',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    request JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    error TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_assessment_jobs_owner_created
    ON assessment_jobs (owner_id, created_at DESC);
