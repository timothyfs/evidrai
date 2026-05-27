-- Evidrai ledger migration 010
-- Adds Researcher / Journalist report workflow labels.

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS report_labels TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS assessments_report_labels_idx
    ON assessments USING GIN (report_labels)
    WHERE deleted_at IS NULL;
