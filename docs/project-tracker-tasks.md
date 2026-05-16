# Evidrai Project Tracker Tasks

Date: 2026-05-10

## Ready / next

### Add pytest rule-engine test harness
- Status: Done
- Priority: High
- Area: Validation
- Description: Add pytest and fixture-based tests for the core judgement logic so verdict behaviour is protected before further changes.
- Acceptance criteria:
  - Tests run without API keys.
  - Covers no sources, allegation-only, primary support, credible contradiction, mixed evidence, and soft/opinion claims.

### Update README for new package structure
- Status: Done
- Priority: High
- Area: Documentation
- Description: README still describes the old simple repo shape. Update it to explain `app.py`, `evidrai/`, `prompts.py`, Streamlit deployment, and local validation commands.
- Acceptance criteria:
  - README reflects current structure.
  - Includes compile check command.
  - Notes Streamlit secrets needed: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `OPENAI_MODEL`, `TAVILY_API_KEY`.

### Add Streamlit deployment smoke checklist
- Status: Done
- Priority: High
- Area: Deployment
- Description: Create a short checklist for verifying Streamlit Cloud after each push.
- Acceptance criteria:
  - App imports successfully.
  - Fast mode runs.
  - Deep mode handles missing Tavily key cleanly.
  - Deep mode works when Tavily is configured.

### Commit/push tracker and docs cleanup
- Status: Todo
- Priority: Medium
- Area: Repo hygiene
- Description: Commit the project docs and any tracker-related planning files once reviewed.
- Acceptance criteria:
  - `git status` clean after commit.
  - Streamlit still deploys.

## Next after test harness

### Create typed pipeline result objects
- Status: In progress
- Priority: High
- Area: Architecture
- Description: Replace loose pipeline dictionaries with typed result boundaries for claim analysis, retrieval, scoring, source summaries, verification, and trace output.
- Acceptance criteria:
  - Each stage output has a stable schema.
  - UI can render from typed objects or serialized equivalents.
  - Stage outputs can be saved as fixtures.

### Add debug/trace mode
- Status: Todo
- Priority: High
- Area: Observability
- Description: Add an optional developer/debug view showing normalized claim, subclaims, queries, retrieved URLs, scoring factors, source classifications, rule stats, and downgrade rationale.
- Acceptance criteria:
  - User-facing UI remains simple.
  - Debug view explains why the verdict happened.

### Strengthen Pydantic validation with enums
- Status: Todo
- Priority: Medium
- Area: Validation
- Description: Add enums for verdicts, confidence labels, source support labels, and evidence categories to reduce schema drift.
- Acceptance criteria:
  - Invalid model output is caught or normalized.
  - Verdict/support/category values are constrained.

### Add saved assessment JSON export
- Status: Todo
- Priority: Medium
- Area: Product
- Description: Allow exporting the full assessment packet for debugging, regression fixtures, and later user history.
- Acceptance criteria:
  - Export includes input, normalized claim, sources, rule stats, verdict, confidence, and schema version.
  - Does not expose secrets.

### Improve error handling and diagnostics
- Status: Todo
- Priority: Medium
- Area: Reliability
- Description: Replace broad `except Exception` paths with clearer failure classes/messages where useful, especially for API, JSON, schema, and search failures.
- Acceptance criteria:
  - User sees useful but safe errors.
  - Developer logs retain enough context to debug.

## Expansion backlog

### Add URL/article extraction module
- Status: Backlog
- Priority: Medium
- Area: Ingestion
- Description: Add a separate ingestion layer for article/page URLs instead of relying on pasted claims plus optional URL context.

### Support multiple search providers
- Status: Backlog
- Priority: Medium
- Area: Retrieval
- Description: Abstract search provider logic so Tavily is not the only retrieval option.

### Add source reputation registry
- Status: Backlog
- Priority: Medium
- Area: Evidence quality
- Description: Add configurable source metadata for domains, source types, known authority, and risk labels.

### Persist user feedback
- Status: Backlog
- Priority: Low
- Area: Product
- Description: Store feedback beyond current Streamlit session state so it can guide improvements.

### Add saved assessment history
- Status: Backlog
- Priority: Low
- Area: Product
- Description: Persist previous assessments for review and comparison.

### Explore browser extension/API backend path
- Status: Backlog
- Priority: Low
- Area: Product strategy
- Description: Once the verification core is stable, evaluate packaging Evidrai as an API/backend service or browser extension.
