# Streamlit Deployment Smoke Checklist

Use this after each push to Streamlit Cloud.

## 1. Deployment starts cleanly

- Open the Streamlit Cloud app.
- Confirm the app imports and renders without a red exception banner.
- Confirm the page title and input controls load.

## 2. Secrets are present

In Streamlit Cloud app settings, confirm secrets are configured as needed:

- `OPENAI_API_KEY` required for model calls
- `OPENAI_BASE_URL` optional
- `OPENAI_MODEL` optional
- `TAVILY_API_KEY` optional, required for retrieval-backed Deep mode

Do not paste secrets into logs, issues, commits, or chat.

## 3. Fast mode smoke test

- Enter a simple claim.
- Run Fast mode.
- Confirm the app returns:
  - a verdict
  - confidence
  - a short summary or takeaway
- Confirm no external search key is required for this path.

## 4. Deep mode without Tavily

If `TAVILY_API_KEY` is not configured:

- Run Deep mode with a simple claim.
- Confirm the app handles missing retrieval cleanly.
- Expected behaviour: no crash; weak/no-source assessment is acceptable.

## 5. Deep mode with Tavily

If `TAVILY_API_KEY` is configured:

- Run Deep mode with a recent, checkable claim.
- Confirm sources are retrieved and rendered.
- Confirm the evidence snapshot shows supporting, contradicting, or contextual buckets.
- Confirm the final verdict includes rule-engine alignment details where applicable.

## 6. Regression guard

Before treating the deployment as good, run locally:

```bash
python -m pytest -q
python -m compileall app.py evidrai prompts.py tests
```

Expected result:

- rule-engine tests pass
- compile check passes

## 7. Rollback trigger

Rollback or pause promotion if any of these occur:

- app import failure
- Fast mode crashes with valid `OPENAI_API_KEY`
- Deep mode crashes when Tavily is missing
- source rendering breaks the page
- rule-engine tests fail locally
