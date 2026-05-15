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

## Verification modes

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
prompts.py                     Prompt builders and JSON loading helpers
requirements.txt               Runtime and test dependencies

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
