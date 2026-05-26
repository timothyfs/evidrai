# Production smoke checklist

Use this after frontend/API changes before handing the app back for UI testing.

## Fast default check

```bash
python scripts/smoke_production.py
```

This checks:

- Vercel homepage loads
- deployed frontend bundle contains current UI markers
- Render `/runtime`, `/tiers`, `/me`, `/reports` respond
- anonymous Fast assessment job creates, completes, and saves a report
- saved report can be reloaded

## Optional authenticated checks

Deep assessment and speech audit require a signed-in user because anonymous users only have Fast claims.

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

Before UI testing, the default script should show zero failures. Skips for Deep/Speech are acceptable unless an access token is provided.
