-- Evidrai ledger migration 011
-- Adds scalable admin user-management profile details for organisations and billing grouping.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS company_name TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS organisation_name TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS billing_account_name TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS billing_account_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS admin_notes TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS user_profiles_company_name_idx
    ON user_profiles (lower(company_name));

CREATE INDEX IF NOT EXISTS user_profiles_billing_account_id_idx
    ON user_profiles (billing_account_id);
