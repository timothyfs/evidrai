-- Evidrai migration 011
-- Captures optional recipient context for report share events.

ALTER TABLE report_shares
    ADD COLUMN IF NOT EXISTS recipient_email TEXT;

ALTER TABLE report_shares
    ADD COLUMN IF NOT EXISTS recipient_source TEXT;

ALTER TABLE report_shares
    ADD COLUMN IF NOT EXISTS recipient_captured_at TIMESTAMPTZ;

DROP INDEX IF EXISTS report_shares_active_assessment_access_idx;

CREATE INDEX IF NOT EXISTS report_shares_active_assessment_access_lookup_idx
    ON report_shares (assessment_id, access_level)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS report_shares_recipient_email_idx
    ON report_shares (recipient_email)
    WHERE recipient_email IS NOT NULL AND revoked_at IS NULL;
