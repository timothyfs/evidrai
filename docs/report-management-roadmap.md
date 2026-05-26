# Report management roadmap

Status: logged from Tim feedback on 2026-05-26.

The saved reports area should stay useful without cluttering the main evidence UI. Reports should be managed as a clean library with retention rules, shareable report views, and future marketing/customer-intelligence hooks.

## Product goals

- Keep the main evidence UI focused on the current assessment.
- Collapse the report/history section by default.
- Let users open reports in a dedicated report view/new tab, similar to public shared links.
- Keep storage/report history bounded by tier.
- Allow users to protect important reports from automatic cycling/deletion.
- Capture optional share-recipient email addresses for future marketing/customer follow-up if consent/compliance permits.

## Report history defaults

### UI behaviour

- Saved reports/history section should be collapsed by default.
- Opening a saved report from the main UI should open a dedicated report page in a new tab.
- The dedicated report view should be shareable and visually cleaner than embedding the full report in the main evidence UI.
- Main UI should show concise report rows/cards only: title/claim, date, mode, verdict, source count, protected state, and quick actions.

### Tier limits

Report retention limits by product tier:

- Free: 5 reports
- Pro: 10 reports
- Researcher / Journalist: 100 reports

When a user exceeds the limit, Evidrai should automatically cycle/delete older reports unless they are marked as protected/do-not-delete.

## Report actions

Each saved report should support:

- View in dedicated report page/new tab.
- Copy/share link.
- Delete report.
- Mark as `do not delete` / protected.
- Remove `do not delete` / protected flag.

## Retention behaviour

When saving a new report:

1. Count the user/account's saved reports for the applicable tier.
2. If count is within the tier limit, save normally.
3. If count exceeds the limit:
   - delete or archive the oldest non-protected reports first;
   - never auto-delete reports marked `do not delete`;
   - if all reports are protected and the limit is exceeded, block saving or show a clear user/admin warning.

Open decision: choose whether over-limit non-protected reports are hard-deleted, soft-deleted, or archived. Recommendation: start with soft-delete/archive where practical so accidental loss can be recovered during early access.

## Dedicated report view

- Reports should be viewable through a dedicated route, similar to existing share-link behaviour.
- Owner/private report view should require authentication and ownership/admin access.
- Public shared report view should remain accessible by share token.
- Opening from the reports list should default to a new tab to keep the active assessment workspace clean.

## Sharing and recipient capture

For shared reports:

- Allow the sharer to enter an optional recipient email address.
- Store recipient email with the share event/report share record for future marketing/customer follow-up if Evidrai decides to use it.
- Store capture timestamp, report ID, owner ID, share token, and consent/source context where relevant.
- Make sure privacy/consent copy is explicit before using these emails for marketing.
- Do not expose recipient emails on public report pages.

## Report labels/status markers

Tim's note ended at “allow reports to be marked like…”. This needs clarification.

Possible intended markings:

- favourite / important
- keep / do not delete
- shared / private
- reviewed / needs review
- useful / not useful
- customer-facing / internal-only
- evidence-quality tags

Decision needed before implementation.

## Suggested implementation sequence

1. Collapse report/history UI by default.
2. Add dedicated owner report route/new-tab view using existing report loading path.
3. Add report delete action.
4. Add protected/do-not-delete flag to report metadata/storage.
5. Enforce tier retention limits with protected-report exception.
6. Add share-recipient email capture to share flow.
7. Add report labels/status markers once the intended taxonomy is confirmed.
8. Add tests for retention, protected reports, delete, owner access, and public share access.

## Acceptance criteria

- Reports section is collapsed by default.
- Free users retain up to 5 reports, Pro up to 10, Researcher / Journalist up to 100.
- Users can delete saved reports.
- Users can mark reports as protected/do-not-delete.
- Auto-cycling never deletes protected reports.
- Saved reports open in a dedicated report page/new tab.
- Public share links still work.
- Optional share-recipient email can be captured and stored safely.
- Report ownership and public/private access rules remain enforced.
