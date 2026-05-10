# Evidrai Code Review and Refactor Plan

Date: 2026-05-10

## Current state

The app works, but `app.py` is doing almost everything:

- Streamlit UI
- configuration and secrets loading
- OpenAI-compatible client
- Tavily client
- retry/error handling
- schema definitions
- claim analysis pipeline
- source retrieval
- source scoring
- source summarisation
- evidence/rule logic
- rendering
- cache/session-state handling

`app.py` is 1,556 lines. The largest functions are:

- `main`: 113 lines
- `rule_based_verdict_from_evidence`: 103 lines
- `run_claim_pipeline`: 94 lines
- `render_pipeline_result`: 84 lines
- `evidence_pendulum`: 66 lines
- `compute_evidence_stats`: 63 lines
- `align_reasoning_with_rules`: 50 lines

That is why debugging is painful: UI, external APIs, prompts, schemas, scoring, and product logic are tightly coupled.

## What is good

- Clear product direction: claim → evidence → verdict.
- Pydantic models already exist and provide a useful contract boundary.
- Prompt files are already separated from `app.py`.
- The pipeline has identifiable stages.
- Rule-based downgrades are the right instinct for avoiding overconfident LLM outputs.
- Source scoring and narrative clustering show the right direction for fake-corroboration control.
- Streamlit cache/session-state usage is simple and not over-engineered.

## Main problems

### 1. One file contains too many layers

`app.py` mixes domain logic, API integration, validation, orchestration, and UI. This makes it hard to test anything without running the whole app.

### 2. Pipeline stages are implicit

The deep flow is conceptually staged, but the code does not expose a typed pipeline object or step outputs. Debugging means reading across many functions.

### 3. Domain rules are difficult to validate

The most important product logic lives in large procedural functions:

- `rule_based_verdict_from_evidence`
- `compute_evidence_stats`
- `evidence_pendulum`
- `align_reasoning_with_rules`

These need fixture-based tests. Otherwise small changes can silently alter verdict behaviour.

### 4. External API clients are coupled to Streamlit

`OpenAICompatibleClient` and `TavilySearchClient` read from `st.secrets` directly. That makes them harder to test and reuse outside Streamlit.

### 5. Error handling is broad

Several `except Exception` blocks hide the failure type. That is acceptable for UI resilience, but bad for debugging and validation.

### 6. No test harness yet

There are no tests, fixtures, golden cases, or local validation scripts. For a trust product, this is the biggest gap.

### 7. No typed result boundary

Most pipeline outputs are dictionaries. This is flexible, but it makes accidental schema drift easy.

### 8. Retrieval and scoring are under-instrumented

There is limited traceability for why a source was selected, ranked, summarised, or downgraded.

## Recommended target structure

```text
evidrai/
  __init__.py
  app.py                  # thin Streamlit entrypoint only
  config.py               # settings/secrets/env loading
  models.py               # dataclasses + Pydantic schemas
  clients/
    llm.py                # OpenAI-compatible client
    search.py             # Tavily client
  pipeline/
    claim_analysis.py
    query_generation.py
    retrieval.py
    source_scoring.py
    source_summary.py
    verification.py       # orchestration
  rules/
    evidence_stats.py
    pendulum.py
    verdict_rules.py
    normalization.py
  ui/
    render.py
    controls.py
  prompts.py

tests/
  test_rules.py
  test_scoring.py
  test_models.py
  test_pipeline_fixtures.py
  fixtures/
    simple_supported.json
    rumor_no_evidence.json
    mixed_evidence.json
```

Keep `streamlit run app.py` working by making root `app.py` a thin wrapper around the package UI.

## Refactor plan

### Phase 1 — Safe extraction, no behaviour change

Goal: make the code navigable without changing outputs.

1. Create package directory `evidrai/`.
2. Move models into `evidrai/models.py`.
3. Move utility/normalisation functions into `evidrai/rules/normalization.py`.
4. Move API clients into `evidrai/clients/`.
5. Move rendering functions into `evidrai/ui/render.py`.
6. Keep `app.py` as the Streamlit entrypoint.
7. Run `python -m py_compile` after every step.

Acceptance criteria:

- Streamlit command still works.
- No product behaviour intentionally changes.
- Imports are clean.
- `app.py` becomes mostly UI orchestration.

### Phase 2 — Add tests around rules

Goal: protect the judgement logic before improving it.

Add `pytest` and fixtures for:

- no sources → Unverified / Low
- repeated allegations only → Not supported or Unverified depending seriousness
- primary source support → Supported / Medium or High
- credible contradiction → Not supported by credible evidence
- mixed evidence → Misleading framing or Weakly supported
- soft/opinion claim → cap confidence and avoid hard factual verdict

Acceptance criteria:

- Rule tests run without API keys.
- Verdict changes become deliberate, not accidental.

### Phase 3 — Create typed pipeline results

Goal: make the deep verification flow inspectable.

Introduce typed result objects:

- `ClaimAnalysisResult`
- `RetrievalResult`
- `SourceScoringResult`
- `SourceSummaryResult`
- `VerificationResult`
- `PipelineTrace`

The UI should render from these objects, not loose dictionaries.

Acceptance criteria:

- Each pipeline stage can be called independently.
- Debug view can show stage outputs.
- Saved fixtures can replay without hitting APIs.

### Phase 4 — Improve observability

Goal: make debugging obvious.

Add a debug/trace mode showing:

- normalized claim
- subclaims
- generated queries
- raw retrieved URLs
- scoring factors per source
- source summary classification
- rule engine stats
- final downgrade rationale

Acceptance criteria:

- User-facing UI remains simple.
- Developer/debug view explains why the result happened.

### Phase 5 — Strengthen validation

Goal: make Evidrai safer as a trust product.

Add:

- enum fields for verdicts, confidence, support labels, evidence categories
- stricter Pydantic validation
- schema version on outputs
- fixture-based regression tests for known tricky claims
- optional saved assessment JSON export

Acceptance criteria:

- Invalid model output is caught early and repaired or downgraded safely.
- Output schema drift is visible.

### Phase 6 — Expand product cleanly

Once modular, expansion is much easier:

- URL/article extraction as a separate ingestion module
- multiple search providers
- model/provider routing
- source reputation registry
- user feedback persistence
- saved assessment history
- batch claim analysis
- browser extension/API backend later

## Immediate next steps

Recommended first PR:

1. Add `pytest` to dev dependencies.
2. Extract models and rules without changing behaviour.
3. Add tests for `compute_evidence_stats`, `evidence_pendulum`, and `rule_based_verdict_from_evidence`.
4. Keep UI unchanged.

This gives immediate maintainability without risking the Streamlit deployment.

## Phase 1 extraction completed — 2026-05-10

The responsibility split has been applied without intentional behaviour changes.

New structure:

```text
app.py                         # thin Streamlit entrypoint
prompts.py                     # prompt builders and JSON loader
evidrai/models.py              # dataclasses and Pydantic schemas
evidrai/config.py              # scoring configuration
evidrai/utils.py               # URL/date/list/schema utility functions
evidrai/clients/llm.py         # OpenAI-compatible client
evidrai/clients/search.py      # Tavily search client
evidrai/pipeline/verification.py # fast/deep verification pipeline
evidrai/rules/verdict.py       # evidence stats, pendulum, verdict alignment
evidrai/ui/render.py           # Streamlit UI rendering and main app flow
```

Validation run:

```bash
python3 -m py_compile app.py prompts.py $(find evidrai -name '*.py' | sort)
```

Result: compile OK.

Note: full import/runtime smoke testing was not run in this local OpenClaw environment because the project dependencies are not installed here (`pydantic`, `requests`, `streamlit`). Streamlit Cloud should already provide these via `requirements.txt`.
