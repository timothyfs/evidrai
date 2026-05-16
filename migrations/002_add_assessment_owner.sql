-- Evidrai ledger migration 002
-- Adds auth-ready ownership metadata for user-scoped report history.

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS owner_id TEXT;

CREATE INDEX IF NOT EXISTS assessments_owner_created_at_idx
    ON assessments (owner_id, created_at DESC);
