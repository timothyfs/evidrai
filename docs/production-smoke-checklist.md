# Production smoke checklist

Use this after frontend/API changes before handing the app back for UI testing.

## Fast default check

```bash
python scripts/smoke_production.py
```

This checks:

- Vercel homepage loads
- deployed frontend bundle contains current UI markers
- Render `/runtime`, `/tiers`, `/me` respond
- anonymous `/reports` and Fast assessment jobs are blocked
- signed-in-only access is enforced before users can run assessments

## Optional authenticated checks

Assessment, reports, Deep assessment, and speech audit require a signed-in user because Evidrai captures an email identity before any checks run.

```bash
EVIDRAI_ACCESS_TOKEN='<supabase-access-token>' \
EVIDRAI_RUN_DEEP=1 \
EVIDRAI_RUN_SPEECH=1 \
python scripts/smoke_production.py
```

Set `EVIDRAI_REQUIRE_AUTH_FEATURES=1` if skipped authenticated checks should fail the run.

## Useful overrides

```bash
EVIDRAI_API_BASE_URL=https://evidrai.onrender.com \
EVIDRAI_WEB_URL=https://evidrai.vercel.app \
EVIDRAI_SMOKE_USER_ID=anon_smoke_manual \
python scripts/smoke_production.py
```

## UI handoff gate

Before UI testing, the default script should show zero failures and confirm anonymous users are blocked. For a full user-path smoke test, provide a Supabase access token for a test user.
