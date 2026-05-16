-- Evidrai ledger migration 003
-- Adds user profiles for auth-backed tier and entitlement management.

CREATE TABLE IF NOT EXISTS user_profiles (
    owner_id TEXT PRIMARY KEY,
    email TEXT,
    tier TEXT NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_profiles_tier_idx
    ON user_profiles (tier);
