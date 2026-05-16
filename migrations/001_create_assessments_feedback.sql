-- Evidrai ledger migration 001
-- Creates the initial Postgres-backed assessment and feedback tables.

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ,
    mode TEXT,
    claim TEXT,
    source_url TEXT,
    verdict TEXT,
    confidence TEXT,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS assessments_created_at_idx
    ON assessments (created_at DESC);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    assessment_id TEXT,
    captured_at TIMESTAMPTZ,
    rating TEXT,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS feedback_assessment_id_idx
    ON feedback (assessment_id);

CREATE INDEX IF NOT EXISTS feedback_captured_at_idx
    ON feedback (captured_at DESC);
