-- Evidrai migration 013
-- Stores signup and policy consent state on user profiles for audit and re-consent gating.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS terms_version TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS privacy_version TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS privacy_acknowledged_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS marketing_opt_in BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS marketing_opt_in_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS consent_source TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS consent_user_agent TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS consent_ip_hash TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS user_profiles_consent_versions_idx
    ON user_profiles (terms_version, privacy_version);
