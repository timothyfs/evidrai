# Evidrai

Evidrai is a Streamlit-based claim verification prototype for assessing the evidential strength of a claim, headline, quote, post, URL, or article excerpt.

It combines:
- a fast first-pass assessment
- a deeper retrieval-backed verification flow
- structured JSON outputs from an OpenAI-compatible model
- evidence scoring, contradiction checks, and rule-based guard rails to reduce overconfident verdicts

## What it does

Given a claim or source URL, Evidrai can:
- extract the core claim and subclaims
- retrieve external sources for deeper verification
- rank and summarise sources
- distinguish evidence from rumour, allegation, and contextual noise
- produce a user-facing verdict with confidence and explanation
- audit a pasted speech or video transcript by extracting checkable claims and verifying them claim by claim

## How Evidrai scores evidence

Evidrai is claim-first, not speaker-first. A claim is assessed against the evidence chain behind it, not against the popularity, status, or confidence of whoever repeated it.

Core principles:

- **Amplification is not corroboration.** Repeated publication, social sharing, political prominence, or syndication does not make a claim more true by itself.
- **Independence beats volume.** Five articles repeating the same allegation, briefing, wire story, or social post may count as one evidentiary chain, not five independent confirmations.
- **Primary evidence carries the most weight.** Court records, official documents, filings, datasets, direct transcripts, and other primary material are preferred over commentary or repetition.
- **Reputable media are weighted signals, not arbiters of truth.** Outlets with rigorous reporting standards can increase confidence when they add transparent, independently sourced evidence. They do not define the answer alone.
- **Authority triggers attention, not automatic credibility.** Politicians, governments, celebrities, institutions, and high-profile media can all make unsupported claims. Evidrai scores the claim, not the title of the person saying it.
- **Context is separated from support.** Background, association, allegation, denial, and narrative momentum are useful for understanding why a claim spreads, but they are not treated as direct substantiation.

When Evidrai detects that many reviewed sources appear to trace back to the same narrative cluster, it may show an **amplification warning**. That warning means the claim may be widely repeated while still lacking independent evidentiary support.

Supported verdicts:
- Supported
- Likely supported
- Unverified
- Misleading framing
- Weakly supported / likely incorrect
- Not supported by credible evidence

## Product modes

### Single Claim Check

Single Claim Check is the default mode. It assesses one claim, headline, quote, post, URL, or article excerpt through the Fast or Deep verification flow.

### Speech / Video Audit

Speech / Video Audit is for longer material such as YouTube transcripts, political speeches, interviews, podcasts, and video captions.

In the MVP version, users paste the transcript manually or provide a YouTube URL with accessible captions. Evidrai then:

- extracts concrete, checkable factual claims
- skips pure rhetoric, slogans, insults, and vague applause lines
- prioritises high-impact claims
- runs the existing Deep evidence pipeline on each selected claim
- produces a report with the original quote, normalized claim, verdict, confidence, evidence links, and explanation

If YouTube shows a transcript in the browser but automated extraction fails, copy the visible transcript into the app. The transcript helper cleans timestamp-only lines, duplicate caption fragments, and common noise before the audit runs.

This mode is designed to audit any speaker or institution, not a specific politician or ideology.

Current limitation: some YouTube videos do not expose captions, and YouTube may block audio download. In those cases, paste a transcript manually or use an external speech-to-text workflow.

Future improvement: audio download plus speech-to-text fallback when captions are missing.

## Verification depths

### Fast

Fast mode runs a quick first-pass assessment without external retrieval.

Use it when:
- you want a rapid credibility read
- the claim is simple
- you do not need external evidence gathering

### Deep

Deep mode adds retrieval-backed verification.

It:
- extracts subclaims
- generates search queries
- retrieves sources via Tavily, when configured
- scores and summarises sources
- applies pendulum and rule-based checks before producing the final verdict

Use it when:
- the claim is contested
- evidence quality matters
- you want stronger justification than a single-pass answer

## Requirements

- Python 3.10+
- A virtual environment is recommended
- An OpenAI-compatible API key for model calls
- A Tavily API key if you want Deep mode retrieval

## Configuration

The app reads configuration from Streamlit secrets or environment variables. Streamlit Cloud should use app secrets, not browser calls to API URLs.

Required for model calls:
- `OPENAI_API_KEY`

Optional:
- `OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`
- `OPENAI_MODEL` defaults to `gpt-4o-mini`
- `TAVILY_API_KEY` enables Deep mode retrieval

For Streamlit Cloud, configure these under app secrets:

```toml
OPENAI_API_KEY = "..."
OPENAI_BASE_URL = "https://api.openai.com/v1" # optional
OPENAI_MODEL = "gpt-4o-mini"                 # optional
TAVILY_API_KEY = "..."                       # optional, required for retrieval-backed Deep mode
```

Do not commit local secrets.

Supported Streamlit secrets formats:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4o-mini"
TAVILY_API_KEY = "tvly-..."
```

or:

```toml
[openai]
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"

[tavily]
api_key = "tvly-..."
```

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the app locally:

```bash
streamlit run app.py
```

Run the Phase 1 API locally:

```bash
uvicorn api.main:app --reload
```

Initial API endpoints:

- `GET /health`
- `POST /claims/check`
- `POST /speech/audit`

API docs are available locally at `http://127.0.0.1:8000/docs` when Uvicorn is running.

Backend runtime endpoints:

- `GET /`
- `GET /version`
- `GET /health`
- `GET /runtime`

See `docs/fastapi-backend-hardening.md` for the first independent-backend hardening slice.

Independent API deployment prep lives in `docs/fastapi-independent-deployment.md`. Deployment entrypoints are available via `Procfile`, `Dockerfile.api`, and `render.yaml`.

## Storage backend

Evidrai uses local JSON persistence by default. If `DATABASE_URL` is configured, it switches to Postgres-backed assessment and feedback stores.

Recommended prototype backend: Supabase Postgres with `sslmode=require`.

See `docs/supabase-postgres-setup.md`. SQL migrations live in `migrations/` and can be applied with `python scripts/apply_migrations.py` when `DATABASE_URL` is configured.

## Validation commands

Run the API-key-free rule-engine tests:

```bash
python -m pytest -q
```

Run a quick compile check:

```bash
python -m compileall app.py evidrai prompts.py tests
```

Both commands should pass before pushing changes.

## Project structure

```text
app.py                         Streamlit entrypoint; delegates to evidrai.ui.render.main
api/main.py                    Phase 1 FastAPI wrapper around the verification engine
prompts.py                     Prompt builders and JSON loading helpers
requirements.txt               Runtime and test dependencies
web/                           Thin Next.js customer frontend for the independent API

evidrai/
  clients/
    llm.py                     OpenAI-compatible JSON client
    search.py                  Tavily search client
  config.py                    Scoring and retry configuration
  models.py                    Dataclasses and Pydantic response models
  pipeline/
    verification.py            Fast pass and retrieval-backed verification pipeline
  rules/
    verdict.py                 Evidence classification, pendulum scoring, and rule guard rails
  ui/
    render.py                  Streamlit UI rendering and interaction flow
  utils.py                     URL handling, source classification, validation helpers

tests/
  test_rule_engine.py          API-key-free rule-engine regression tests
```

## Current limitations

- This is still a prototype, not a production verification system
- Output quality depends heavily on retrieved source quality
- Deep mode depends on external API availability and search quality
- Some claims are inherently interpretive, predictive, or too vague to verify cleanly
- Rule-based downgrades reduce over-claiming, but they do not compensate for bad retrieval or weak source material

## Notes

- Fast mode still requires the model API key because it uses the OpenAI-compatible client.
- Deep mode can run without Tavily configured, but retrieval will return no sources and the result will be correspondingly weak.
- Tests are designed to run without API keys.
