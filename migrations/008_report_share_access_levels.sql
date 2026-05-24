-- Evidrai migration 008
-- Supports simple free shares and full Pro report shares.

ALTER TABLE report_shares
    ADD COLUMN IF NOT EXISTS access_level TEXT NOT NULL DEFAULT 'full';

DROP INDEX IF EXISTS report_shares_active_assessment_idx;

CREATE UNIQUE INDEX IF NOT EXISTS report_shares_active_assessment_access_idx
    ON report_shares (assessment_id, access_level)
    WHERE revoked_at IS NULL;
