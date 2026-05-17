-- Evidrai ledger migration 004
-- Adds admin/user billing scaffolding for password auth, trials, and future payments.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS subscription_status TEXT NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS payment_provider_customer_id TEXT;

CREATE INDEX IF NOT EXISTS user_profiles_subscription_status_idx
    ON user_profiles (subscription_status);
