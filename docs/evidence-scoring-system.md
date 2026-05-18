# Evidrai Evidence Scoring System

Status: Draft v0.1  
Scope: Deep verification flow, source ranking, source weighting, and user-facing confidence display.

## Purpose

Evidrai scores evidence so users can see not just *what* verdict was reached, but *why* the underlying source set deserves more or less trust.

The scoring system has three separate layers:

1. **Source score**: how strong an individual source is for the specific claim.
2. **Evidence strength score**: how strong the total evidence set is after weighting, contradiction checks, and independence checks.
3. **Confidence score**: how confident Evidrai should be in the final verdict.

These are related, but they are not the same thing.

A high-quality source can be irrelevant to the claim. A large number of weak sources can create noise rather than confidence. A confident tone from a speaker or publisher is not evidence.

## Core principles

- **Claim-first, not speaker-first.** Evidrai scores the evidence behind the claim, not the fame, status, or confidence of the person making it.
- **Primary evidence carries the most weight.** Original records, filings, datasets, transcripts, laws, court documents, and direct source material should usually outrank commentary.
- **Independence beats volume.** Ten articles repeating the same wire report or briefing count as one evidence chain, not ten independent confirmations.
- **Support and contradiction are both evidence.** A high-quality contradiction should reduce confidence in a supporting verdict, not be averaged away.
- **Context is not proof.** Background material may explain the claim, but it should not strongly support the claim unless it directly verifies or falsifies it.
- **Recency matters only when the claim is time-sensitive.** Old sources are not automatically weak. Historical claims may require older primary material.
- **Authority is domain-specific.** A government source may be primary for official statistics but weak for claims about its own wrongdoing unless independently corroborated.
- **Explainability is mandatory.** Every score shown to the user must be traceable to simple factors.

## Source score

Each reviewed source receives a `source_score` from **0.0 to 5.0**.

Recommended display bands:

- **4.5-5.0: Very strong**
- **3.75-4.49: Strong**
- **2.75-3.74: Useful / mixed**
- **1.75-2.74: Weak**
- **0.0-1.74: Poor / irrelevant**

### Source score formula

For each source:

```text
source_score =
  authority_score   * 0.30 +
  relevance_score   * 0.25 +
  directness_score  * 0.20 +
  recency_score     * 0.10 +
  independence_score * 0.10 +
  bias_risk_score   * 0.05
```

All component scores are normalised to **0.0-5.0**.

`bias_risk_score` is inverted before scoring: low bias risk produces a higher contribution.

### Component definitions

#### 1. Authority score

How authoritative the source is for this type of claim.

Suggested baseline:

- **5.0**: Primary document or direct record: court filing, statute, transcript, official dataset, regulatory filing, peer-reviewed paper where relevant.
- **4.5**: Authoritative institutional source with direct responsibility: statistical agency, standards body, official company filing.
- **4.0**: High-quality secondary reporting with named sources, linked documents, or original investigation.
- **3.0**: Reputable secondary reporting without transparent sourcing.
- **2.0**: Commentary, opinion, advocacy, campaign material, unsourced aggregation.
- **1.0**: Anonymous social post, forum claim, recycled content, unattributed rumour.

Important: authority is not global. A source can be authoritative for one claim type and weak for another.

#### 2. Relevance score

How closely the source addresses the specific claim.

- **5.0**: Directly addresses the exact claim.
- **4.0**: Addresses the same event, entity, date, and factual question.
- **3.0**: Addresses the topic but requires inference.
- **2.0**: Background context only.
- **1.0**: Barely related.
- **0.0**: Irrelevant.

#### 3. Directness score

How close the source is to the underlying evidence.

- **5.0**: Contains or links the original evidence.
- **4.0**: Quotes or summarises original evidence clearly.
- **3.0**: Reports facts based on described evidence but does not expose it.
- **2.0**: Reports claims made by others.
- **1.0**: Repeats narrative, allegation, or commentary.

#### 4. Recency score

How temporally appropriate the source is.

Use claim type:

- For live/current claims: newer and updated sources score higher.
- For historical claims: contemporaneous primary records may score higher than recent summaries.
- For legal/scientific/regulatory claims: current status matters, but original source material remains important.

Suggested scoring:

- **5.0**: Current or temporally ideal for the claim.
- **4.0**: Recent enough, no obvious staleness risk.
- **3.0**: Possibly dated but still useful.
- **2.0**: Dated for a time-sensitive claim.
- **1.0**: Likely stale or superseded.

#### 5. Independence score

Whether this source adds genuinely independent evidence.

- **5.0**: Independent primary source or original reporting.
- **4.0**: Distinct secondary source with independent evidence.
- **3.0**: Some independent value, but partly follows existing reporting.
- **2.0**: Repeats the same wire story, press release, briefing, or source chain.
- **1.0**: Pure amplification with no independent evidence.

This is critical. Source volume must not create fake confidence.

#### 6. Bias risk score

Risk that the source has a strong incentive to frame the claim selectively.

For calculation, this should be converted so lower risk increases the final score.

Suggested raw risk values:

- **1.0**: Low bias or strong transparency controls.
- **2.0**: Some institutional or editorial position, but clear sourcing.
- **3.0**: Known perspective or partial stake.
- **4.0**: Strong advocacy, campaign, commercial, or political interest.
- **5.0**: Directly self-interested, anonymous, manipulative, or propagandistic.

Converted contribution:

```text
bias_risk_score = 5 - raw_bias_risk
```

## Source categories and default weighting

Some source types should begin with higher or lower priors, then be adjusted by relevance, directness, independence, and bias risk.

### High-weight sources

These can carry substantial weight when relevant:

- Court records and legal filings
- Legislation and official regulations
- Official statistical datasets
- Regulatory filings
- Direct transcripts, recordings, or source documents
- Peer-reviewed papers for scientific claims
- Standards bodies and technical specifications
- Original investigative reporting with transparent evidence

### Medium-weight sources

Useful, but should usually require corroboration:

- Reputable news reporting
- Specialist publications
- Expert analysis with disclosed reasoning
- Institutional reports
- Company announcements for factual claims about the company itself

### Low-weight sources

May be useful context, but weak evidence alone:

- Opinion pieces
- Social media posts
- Aggregators
- Political campaign material
- Advocacy organisations
- Unsourced newsletters or blogs
- AI-generated summaries
- Content farms

## Claim support classification

Each source must also be classified by what it does to the claim:

- **Supports**: directly supports the claim.
- **Contradicts**: directly falsifies or materially challenges the claim.
- **Mixed**: supports part of the claim but weakens or complicates another part.
- **Context**: useful background, but does not verify or falsify.
- **Irrelevant**: does not materially address the claim.

Only `Supports` and `Contradicts` should strongly affect the final verdict. `Context` should help explanation, not inflate confidence.

## Evidence strength score

The overall `evidence_strength_score` is shown from **0 to 10**.

It should reflect the weighted evidence set, not just average source quality.

Recommended formula:

```text
support_weight = sum(source_score * support_multiplier * independence_multiplier)
contradiction_weight = sum(source_score * contradiction_multiplier * independence_multiplier)
context_weight = sum(source_score * 0.15 for context sources)

raw_strength = max(support_weight, contradiction_weight) + context_weight
conflict_penalty = min(support_weight, contradiction_weight) / max(support_weight, contradiction_weight, 1)
cluster_penalty = amplification_penalty_for_duplicate_evidence_chains

evidence_strength_score = clamp((raw_strength / target_strength) * 10 - conflict_penalty - cluster_penalty, 0, 10)
```

Practical MVP version:

```text
weighted_support = sum(score for sources classified Supports)
weighted_contradiction = sum(score for sources classified Contradicts)
weighted_context = sum(score * 0.15 for sources classified Context or Mixed)
conflict = min(weighted_support, weighted_contradiction)
leading_side = max(weighted_support, weighted_contradiction)

evidence_strength_score = clamp(((leading_side + weighted_context) / 12) * 10 - (conflict / 2), 0, 10)
```

## Confidence score

The user-facing confidence score is shown from **0 to 100**.

Confidence should answer:

> How confident should Evidrai be in the verdict, given the quality, independence, relevance, and conflict pattern of the reviewed evidence?

It should not be a simple restatement of source count.

Suggested bands:

- **85-100: High confidence**
- **65-84: Moderate confidence**
- **40-64: Low / cautious confidence**
- **0-39: Very low confidence**

### Confidence inputs

Confidence should rise with:

- direct primary evidence
- multiple independent source chains
- strong source relevance
- clear support or contradiction
- transparent sourcing

Confidence should fall with:

- material contradictions
- same-source amplification
- missing primary evidence where primary evidence should exist
- vague or broad claims
- dated sources for time-sensitive claims
- self-interested sources
- model uncertainty
- incomplete retrieval

### Guard rails

Use hard caps where appropriate:

- No external retrieval: cap at **60** unless the claim is purely analytical or internally checkable.
- No direct evidence: cap at **70**.
- Only one evidence chain: cap at **75**.
- Mostly contextual sources: cap at **55**.
- High contradiction from strong sources: cap supporting verdict at **60**.
- Claim depends on current facts and sources are stale: cap at **65**.
- Source set is mostly amplification: cap at **60** and show amplification warning.

## Weighted source examples

### Example A: Court filing confirms claim

- Court filing: 5.0, Supports, primary, independent
- Reputable article linking the filing: 4.2, Supports, secondary
- Commentary article: 2.0, Context

Likely result:

- High evidence strength
- High confidence
- Explanation should cite the filing first, article second, commentary only as context.

### Example B: Many articles repeat one allegation

- Five news articles all trace to one anonymous briefing: 3.0 each, Supports, same cluster
- No documents or named evidence
- One denial from subject: 2.0, Contradicts, self-interested

Likely result:

- Moderate source visibility but weak independent evidence
- Confidence capped
- Amplification warning shown
- Verdict likely `Unverified` or `Weakly supported`, not `Supported`.

### Example C: Official source contradicts viral claim

- Viral social post: 1.2, Supports, low authority
- Official dataset: 4.8, Contradicts, primary
- Independent expert explainer: 4.0, Contradicts, secondary

Likely result:

- High contradiction weight
- Verdict should reject or correct the claim
- Confidence can be high if the official dataset is directly relevant.

## UI display requirements

The Streamlit result page should expose:

1. **Verdict**
2. **Confidence**: 0-100 or Low/Medium/High mapped to numeric confidence
3. **Evidence strength**: 0-10
4. **Average source quality**: 0-5
5. **Primary source count**
6. **Independent evidence chains**
7. **Amplification warning**, when applicable
8. **Per-source score** with explanation factors

Per-source display should include:

- source title and domain
- source type
- support classification
- source score
- scoring factors
- short reason why this source matters or does not matter

## Implementation notes

Current code already has the following scoring concepts:

- `ScoringConfig` in `evidrai/config.py`
- `score_source()` in `evidrai/pipeline/verification.py`
- `weighted_score` on evidence sources
- `claim_support`, `evidence_category`, `source_role`, and `narrative_cluster`
- UI score display in `evidrai/ui/render.py`

Recommended next implementation changes:

1. Add `independence_score` as a first-class source factor.
2. Reduce `recency_weight` from 0.15 to 0.10 unless the claim is time-sensitive.
3. Reduce `bias_weight` from 0.10 to 0.05 and treat it as a modifier rather than a major determinant.
4. Store `scoring_rationale` per source.
5. Count independent evidence chains using `narrative_cluster`.
6. Add confidence caps based on missing primary evidence, amplification, contradiction, and retrieval quality.
7. Keep source score, evidence strength, and confidence separate in the API contract.

## API field recommendations

Recommended source-level fields:

```json
{
  "title": "...",
  "url": "...",
  "domain": "...",
  "source_type": "primary | secondary | commentary | social | unknown",
  "claim_support": "supports | contradicts | mixed | context | irrelevant",
  "source_score": 4.6,
  "scoring_factors": {
    "authority": 5.0,
    "relevance": 4.5,
    "directness": 5.0,
    "recency": 4.0,
    "independence": 5.0,
    "bias_risk": 1.0,
    "weighted": 4.6
  },
  "narrative_cluster": "official_court_filing",
  "scoring_rationale": "Primary legal filing directly addressing the claim."
}
```

Recommended result-level fields:

```json
{
  "verdict": "Likely supported",
  "confidence": 82,
  "evidence_strength_score": 8.1,
  "source_quality_average": 4.2,
  "primary_source_count": 2,
  "independent_evidence_chains": 3,
  "amplification_warning": false,
  "confidence_rationale": "Verdict is supported by primary documents and two independent secondary sources, with no strong contradiction."
}
```

## Product rule

Never show a naked score without explanation.

A useful score must answer three questions:

1. What was scored?
2. Why did it get that score?
3. What would change the score?
