-- Evidrai migration 012
-- Versioned scoring policy registry for auditable source/evidence scoring changes.

CREATE TABLE IF NOT EXISTS scoring_policy_versions (
    version INTEGER PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by TEXT NOT NULL DEFAULT 'admin',
    change_note TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS scoring_policy_versions_updated_at_idx
    ON scoring_policy_versions (updated_at DESC);
