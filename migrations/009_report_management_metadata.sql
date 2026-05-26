-- Evidrai ledger migration 009
-- Adds report management metadata for retention, protection, and soft delete.

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS report_protected BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS assessments_owner_active_created_at_idx
    ON assessments (owner_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS assessments_report_protected_idx
    ON assessments (owner_id, report_protected)
    WHERE deleted_at IS NULL;
