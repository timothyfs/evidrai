# Admin UI scale roadmap

Status: logged from Tim feedback on 2026-05-26.

The current admin UI is acceptable for roughly the first 10 accounts, but it will not scale cleanly once early access expands. Treat this as a platform/admin workstream, not a cosmetic UI task.

## Problem

The admin surface currently supports basic user listing, invite/create, tier update, and profile deletion. That is enough for initial testing, but not for managing growing customer cohorts, business accounts, billing ownership, or support workflows.

## Required improvements

### 1. Search and filtering

- Search users by email, owner ID, tier, subscription status, company/account, and created/updated date.
- Filter by tier: Free, Pro, Researcher / Journalist.
- Filter by account status: active, invited, email unconfirmed, trial, suspended, deleted/local-only.
- Add pagination/server-side query support rather than loading a flat list.

### 2. Group/bulk administration

- Multi-select users.
- Bulk tier changes.
- Bulk invite/resend invite.
- Bulk suspend/reactivate once account state exists.
- Bulk company/account assignment.
- Clear confirmation step for destructive or billing-impacting actions.

### 3. Account support actions

Admins should be able to do more than delete:

- Update user email/profile metadata where safe.
- Reset password or trigger Supabase password reset email.
- Resend confirmation/invite email.
- Revoke sessions/sign out user if needed.
- Suspend/reactivate access without deleting history.
- View basic support diagnostics: auth provider, email confirmed, last sign-in if available, tier, limits, report count.

### 4. Invite and onboarding workflow

- Invite users with a proper Evidrai welcome email.
- Allow optional message/template per cohort.
- Track invite status: sent, accepted, expired, bounced if available.
- Support resend invite/welcome email.
- Avoid exposing Supabase-default copy as the long-term customer experience.

### 5. Granular customer permissions

Move beyond coarse product tiers where needed:

- Feature flags per user or account.
- Permissions for speech audit, deep checks, exports, sharing, API access, evidence ledger, source snapshots, admin/sub-admin rights.
- Quotas per user/account, not only global tier defaults.
- Audit trail for permission changes.

### 6. Company / business accounts

Introduce the notion of an organisation/business account:

- A company/account can own multiple users.
- Users belong to one or more companies/accounts.
- Company has billing owner/admins/members.
- Company-level plan, limits, feature flags, and usage aggregation.
- Reports and evidence assets may be user-owned, company-owned, or shared within a company.
- Admin UI should support viewing company users, usage, invoices/subscription state, and access controls.

### 7. Billing integration

Wire billing into the account model:

- Payment provider customer ID and subscription ID.
- Plan/subscription status from billing provider.
- Trial start/end dates.
- Invoice/payment status where available.
- Billing owner for company accounts.
- Webhook-driven updates into user/company subscription state.
- Admin override should be explicit and auditable.

## Suggested implementation sequence

1. Add server-side admin user search/filter/pagination.
2. Add resend invite/password reset support actions.
3. Add non-destructive suspend/reactivate account state.
4. Add company/account schema and APIs.
5. Add company assignment and company-level user list in admin UI.
6. Add billing provider integration and webhook state sync.
7. Add granular feature flags/quotas at user and company level.
8. Add bulk actions once the underlying APIs and audit trail are safe.

## Acceptance criteria for v1 scale-up

- Admin can find a user quickly without scanning a flat list.
- Admin can resend invites/password reset emails without manual Supabase work.
- Admin can update access without deleting accounts.
- Business accounts can group multiple users under one billable account.
- Billing state is visible and source-of-truth-driven, not manually guessed.
- Admin actions that affect access or billing are logged.
