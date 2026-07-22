-- Evidrai ledger migration 014
-- Adds admin-configurable per-user product limit overrides.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS custom_limits JSONB NOT NULL DEFAULT '{}'::jsonb;
