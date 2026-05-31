# Evidrai Source Classification and Scoring Architecture

Status: Draft v0.1  
Owner: Evidrai engineering  
Scope: Deep verification source classification, source scoring, admin scoring policy, and audit traceability.

## 1. Purpose

Evidrai classifies and scores sources so that evidence review is explainable, tunable, and auditable. The system is designed to avoid two common failure modes:

1. treating all sources as equally credible; and
2. letting repeated coverage inflate confidence when the sources are not independent.

The score is not a truth label. It is a structured input into the wider verdict process. A high-authority source can still score poorly if it is irrelevant, indirect, stale, or conflicted. A low-prior source can still contribute if it directly addresses the claim and supplies useful evidence.

## 2. Relevant implementation files

| Area | File |
| --- | --- |
| Deterministic source type classification | `evidrai/utils.py` |
| Source score calculation | `evidrai/pipeline/verification.py` |
| Scoring policy defaults and persistence | `evidrai/scoring.py` |
| Admin scoring API | `api/main.py` |
| Admin scoring UI | `web/app/admin/page.tsx` |
| Policy version database migration | `migrations/012_create_scoring_policy_versions.sql` |
| Evidence/verdict weighting | `evidrai/rules/verdict.py` |
| User-facing typed source payloads | `evidrai/models.py`, `evidrai/api_models.py` |

## 3. High-level flow

```text
User claim
  -> claim analysis LLM pass
  -> search query generation
  -> source retrieval
  -> deterministic domain classification
  -> source score calculation
  -> source summary / support classification
  -> evidence pendulum and rule engine
  -> final reasoning response
  -> persisted report and trust ledger rows
```

Source classification happens before LLM source summarisation. This keeps the initial source-type prior deterministic and auditable. LLM passes may classify support relationship, evidence category, narrative cluster, and uncertainty, but the current source-type baseline is domain-driven unless a source is explicitly created by the pipeline as a known primary/counterexample source.

## 4. Source type categories

### 4.1 Scientific

**Definition:** Scientific, medical, research, standards, peer-reviewed, or preprint sources when the domain is recognised by the classifier.

**Current deterministic examples:**

- `nature.com`
- `science.org`
- `sciencedirect.com`
- `springer.com`
- `pubmed.ncbi.nlm.nih.gov`
- `nih.gov`
- `who.int`
- `thelancet.com`
- `nejm.org`
- `arxiv.org`
- `biorxiv.org`
- `medrxiv.org`

**Rationale:** Scientific and technical claims should prioritise original research, medical institutions, standards bodies, and research repositories over commentary. These sources start with the highest authority and independence priors, but they still require relevance and directness. A scientific source that discusses the general topic but not the claim should not dominate the verdict.

**Audit note:** Preprint domains are included because they may be valuable early evidence, but they are not equivalent to peer-reviewed conclusions. The system must continue to account for directness, relevance, uncertainty, and corroboration.

### 4.2 Government

**Definition:** Official government, public agency, official health-service, statistics, or intergovernmental domains.

**Current deterministic examples:**

- `.gov`
- `.gouv.fr`
- `nhs.uk`
- `oecd.org`

**Rationale:** Government sources are often authoritative for laws, official statistics, public records, agency policy, and public-service facts. They are not automatically authoritative for every claim. A government source may be less independent when assessing claims about that same government, agency, or political decision.

**Audit note:** Authority is claim-specific. The default prior is high, but final scoring also considers relevance, directness, independence, and bias risk.

### 4.3 Legal

**Definition:** Official legal, legislative, parliamentary, court, judiciary, or statutory-publication sources.

**Current deterministic examples:**

- `.parliament.uk`
- `.legislation.gov.uk`
- `.judiciary.uk`
- `supremecourt.uk`
- `justice.gov.uk`
- `eur-lex.europa.eu`

**Rationale:** Legal sources are high-priority for claims about statutes, judgements, proceedings, court records, legal obligations, and regulatory status. They can be primary evidence for the existence or wording of a law, judgement, filing, or official proceeding.

**Audit note:** Legal sources can be dense or narrow. They still need claim relevance. A statute can prove what the law says, but may not prove how it is enforced in practice.

### 4.4 Primary

**Definition:** Direct original evidence rather than interpretation of evidence.

Examples include:

- court filings;
- statutes and official records;
- regulatory filings;
- official datasets;
- transcripts;
- recordings;
- original source documents;
- direct counterexample records;
- first-party documentary evidence.

**Current implementation status:** `primary` exists in the scoring policy and verdict rules, but the deterministic domain classifier does not currently assign generic web domains to `primary`. It is mainly used where the pipeline creates or receives an explicitly known primary source, for example a known counterexample source in `known_counterexample_sources()`.

**Rationale:** Primary evidence should generally beat commentary, summaries, or articles describing the same material. It starts with a high authority and independence prior.

**Audit note:** Primary is intentionally conservative. A domain alone is often not enough to prove that a page is primary evidence. For example, a government press release is official but may not be the primary record for an underlying claim. Future improvements should classify page-level evidence type, not just domain.

### 4.5 News

**Definition:** Recognised news publishers and wire/reporting outlets.

**Current deterministic examples:**

- `reuters.com`
- `apnews.com`
- `bbc.com`
- `ft.com`
- `nytimes.com`
- `theguardian.com`
- `lemonde.fr`
- `france24.com`

**Rationale:** News reporting can be useful, especially for current events, but it is judged more cautiously than scientific, government, legal, or primary sources. News organisations may rely on common wires, shared briefings, anonymous sources, political framing, editorial selection, or repetition of the same source chain.

**Audit note:** This is not a judgement that news is invalid. It is an anti-amplification control. Multiple articles repeating the same wire report should not count as multiple independent confirmations.

### 4.6 Secondary

**Definition:** Reputable non-primary synthesis, specialist analysis, institutional reports, expert explainers, or other sources that analyse primary material without being the original record.

Examples include:

- specialist policy analysis;
- expert reports;
- institutional research summaries;
- technical explainers;
- reputable analysis that cites underlying evidence.

**Current implementation status:** `secondary` remains in the scoring policy and typed payloads for compatibility and future classifier development. The current deterministic classifier mostly assigns recognised publishers to `news` and unmatched sources to `contextual`, rather than assigning many sources to `secondary`.

**Rationale:** Secondary sources are useful when they clearly expose their reasoning and cite primary evidence. They should usually require corroboration when used as the main basis for a verdict.

**Audit note:** Secondary is a planned refinement point. A future page/content classifier should distinguish expert secondary analysis from generic contextual material.

### 4.7 Contextual

**Definition:** Default fallback for sources that do not match a recognised scientific, government, legal, or news domain.

**Rationale:** Contextual sources may help explain background, terminology, or narrative history, but they start with lower authority and independence priors. They should not strongly drive a verdict unless they contain direct evidence and the rest of the scoring factors support that.

**Audit note:** Contextual does not mean useless. It means the source did not receive a recognised high-prior classification from the deterministic domain allowlists.

## 5. Classification order

The current deterministic classifier in `evidrai/utils.py` applies checks in this order:

```text
1. scientific domain match -> scientific
2. legal domain match      -> legal
3. government domain match -> government
4. news domain match       -> news
5. no match                -> contextual
```

The order matters. Some domains may plausibly fit more than one category. Legal is checked before government so legal/publication domains can remain legally categorised. Scientific is checked first so major research and medical domains receive scientific treatment even if they are also institutional.

## 6. Source score formula

Each source receives component scores normalised to `0.0-5.0`.

```text
source_score =
  authority_score    * authority_weight +
  relevance_score    * relevance_weight +
  directness_score   * directness_weight +
  independence_score * independence_weight +
  recency_score      * recency_weight +
  (5 - bias_risk)    * bias_risk_weight
```

Default weights:

| Factor | Default weight | Meaning |
| --- | ---: | --- |
| Authority | `0.30` | Baseline credibility of source type for the claim. |
| Relevance | `0.25` | Whether the source addresses the specific claim. |
| Directness | `0.20` | How close the source is to underlying evidence. |
| Independence | `0.10` | Whether it adds a separate evidence chain. |
| Recency | `0.10` | Whether the source is temporally appropriate. |
| Bias risk | `0.05` | Inverted risk. Lower bias risk increases score. |

The weight total should remain approximately `1.00`. The admin UI highlights this because changing one factor without rebalancing the total can distort all source scores.

## 7. Default source-type priors

Current default policy in `evidrai/scoring.py`:

| Source type | Authority | Independence | Bias risk |
| --- | ---: | ---: | ---: |
| Scientific | `5.0` | `5.0` | `1.2` |
| Government | `4.7` | `4.5` | `1.6` |
| Legal | `4.6` | `4.4` | `1.8` |
| Primary | `4.5` | `4.3` | `1.8` |
| Secondary | `3.4` | `3.2` | `2.6` |
| News | `2.8` | `2.4` | `3.3` |
| Contextual | `2.2` | `2.0` | `3.7` |

Bias risk is raw risk. A lower number is better. The score calculation converts it using `5 - bias_risk`.

## 8. Factor explanations

### Authority

Authority is the source-type prior. It answers: “Before looking at the content, how authoritative is this source category for claims of this kind?”

Authority is not global. A government page may be authoritative for an official statistic, but less independent for a claim about government misconduct. A scientific paper may be authoritative for a narrow finding but weak evidence for an exaggerated public claim.

### Relevance

Relevance measures how closely the source matches the claim text. The current implementation uses term overlap against title, snippet, and content. This is deliberately simple and auditable, but it is not semantic proof.

### Directness

Directness measures whether the source appears to contain or directly discuss the underlying evidence. Current implementation uses key-term presence as a proxy. Future versions should strengthen this with content-level evidence-type extraction.

### Independence

Independence measures whether a source adds a distinct evidence chain. Defaults are source-type priors. The verdict layer also groups narrative clusters so repeated coverage is treated as amplification rather than independent proof.

### Recency

Recency uses publication date when available. Current default scoring is:

| Age | Score |
| --- | ---: |
| 0-7 days | `5.0` |
| 8-30 days | `4.0` |
| 31-180 days | `3.0` |
| 181-365 days | `2.0` |
| Older / missing stale source | `1.0` for old, `2.5` for unknown |

Audit caveat: recency should eventually be claim-type aware. Historical claims may require old primary records.

### Bias risk

Bias risk estimates structural incentive risk by source type. The system treats news and contextual sources more cautiously because political, commercial, advocacy, or editorial incentives can influence framing. This does not mean those sources are ignored. It means they require stronger relevance, directness, and corroboration.

## 9. Admin policy versioning

Admins can tune scoring policy in the admin UI. Every saved change requires a change note and creates a new policy version.

Persistent storage:

- table: `scoring_policy_versions`
- migration: `migrations/012_create_scoring_policy_versions.sql`
- fields: version, updated time, editor, change note, full JSON payload

The active policy is the latest version by version number. If database storage is unavailable, the implementation can fall back to local JSON files for development.

## 10. Audit controls

The current design supports auditability through:

- deterministic source-type classification from visible domain lists;
- explicit scoring factors returned in source payloads;
- admin-visible current weights and priors;
- mandatory change notes for policy edits;
- versioned scoring policy persistence;
- source-level `scoring_factors` included in reports and trust ledger rows;
- separation between source quality, evidence support, and final verdict.

## 11. Known limitations and planned hardening

Current limitations:

1. Source type is mostly domain-based, not page-content-based.
2. `primary` is underused by deterministic classification because primary evidence often requires page-level detection.
3. `secondary` is reserved but not strongly populated by the current deterministic classifier.
4. Recency is date-based but not yet fully claim-type aware.
5. Relevance and directness use simple lexical proxies before LLM summarisation.
6. Bias risk is a source-type prior, not a full media-bias database.

Recommended next improvements:

1. Add page-level source-type extraction: direct record, press release, report, article, opinion, social post, dataset, transcript.
2. Split `news` into wire, original reporting, opinion/editorial, and aggregation.
3. Add jurisdiction-aware legal/government classification.
4. Add science maturity labels: peer reviewed, preprint, guideline, meta-analysis, press release.
5. Add per-report scoring policy version to assessment payloads so old reports can be reproduced exactly.
6. Add LLM-call and source-classification audit logs for production diagnostics.

## 12. Governance position

The scoring system is intentionally tunable, but not silently mutable. Policy changes should be treated as methodological changes. Every production adjustment should include:

- reason for change;
- expected behaviour change;
- risk assessment;
- before/after sample checks;
- rollback path.

This ensures Evidrai can explain not only what it concluded, but how the evidence methodology was configured at the time.
