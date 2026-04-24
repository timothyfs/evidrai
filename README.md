# Evidrai

Evidrai is a Streamlit-based claim verification prototype for assessing the evidential strength of a claim, headline, quote, post, or article excerpt.

It combines:
- a fast first-pass assessment
- a deeper retrieval-backed verification flow
- structured JSON outputs from an OpenAI-compatible model
- evidence scoring, contradiction checks, and rule-based guard rails to reduce overconfident verdicts

## What it does

Given a claim or a source URL, Evidrai can:
- extract the core claim and subclaims
- retrieve external sources for deeper verification
- rank and summarise sources
- distinguish evidence from rumour, allegation, and contextual noise
- produce a user-facing verdict with confidence and explanation

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
- retrieves sources via Tavily
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
- A Tavily API key if you want Deep mode

## Configuration

The app reads configuration from Streamlit secrets or environment variables.

Required for model calls:
- `OPENAI_API_KEY`

Optional:
- `OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `TAVILY_API_KEY` for Deep mode

## Setup

1. Create and activate a virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure your environment variables or Streamlit secrets
4. Run the app:

```bash
streamlit run app.py
```

## Current architecture

This repo is intentionally still simple, but the current prototype keeps several concerns in one file:
- UI rendering
- model clients
- retrieval logic
- source scoring
- verdict/rule logic

That is workable for now, but it should eventually be split into modules once the behaviour is stable.

## Known limitations

- This is still a prototype, not a production verification system
- Output quality depends heavily on the quality of retrieved sources
- Deep mode depends on external API availability and search quality
- Some claims are inherently interpretive, predictive, or too vague to verify cleanly
- The app uses rule-based downgrades to avoid over-claiming, but that does not make it immune to poor retrieval or bad source material

## Notes

- The app currently talks to an OpenAI-compatible API via HTTP requests
- Deep mode is unavailable unless `TAVILY_API_KEY` is configured
- The repo structure has been intentionally kept unchanged during this cleanup pass to reduce risk
