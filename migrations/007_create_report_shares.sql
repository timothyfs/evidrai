-- Evidrai migration 007
-- Public share tokens for Pro shareable reports.

CREATE TABLE IF NOT EXISTS report_shares (
    token TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    owner_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS report_shares_active_assessment_idx
    ON report_shares (assessment_id)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS report_shares_owner_created_at_idx
    ON report_shares (owner_id, created_at DESC);
