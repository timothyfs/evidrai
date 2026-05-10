from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    build_claim_analysis_messages,
    build_reasoning_messages,
    build_source_summary_messages,
)
from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.config import SCORING_CONFIG
from evidrai.models import (
    ClaimAnalysisModel,
    EvidenceSource,
    LegacyAssessmentModel,
    SourceSummaryModel,
    SubClaim,
    VerifiedAssessmentModel,
)
from evidrai.rules.verdict import (
    align_reasoning_with_rules,
    collect_risk_flags,
    evidence_pendulum,
    map_confidence_label,
    map_pendulum_to_verified_verdict,
    rule_based_verdict_from_evidence,
    split_evidence_vs_rumor,
)
from evidrai.utils import classify_source_type, domain_from_url, recency_score, validate_model

def call_legacy_model(claim: str, category: str, detail_mode: str, llm: OpenAICompatibleClient) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(claim, category, detail_mode)},
    ]
    payload = llm.complete_json(messages, temperature=0.1)
    return validate_model(payload, LegacyAssessmentModel)


# -----------------------------
# Fast provisional pass
# -----------------------------


def run_quick_pass(user_input: str, category: str, llm: OpenAICompatibleClient) -> Dict[str, Any]:
    """Fast first-pass assessment without external retrieval."""
    try:
        data = call_legacy_model(user_input, category or "auto-detect", "Simple", llm)
    except Exception:
        # Fallback minimal payload so the UI can still stage the response cleanly.
        data = {}
    return {
        "verdict": data.get("verdict", "Unverified"),
        "confidence": data.get("confidence", "Low"),
        "tldr": data.get("tldr") or data.get("summary") or "Initial assessment generated.",
        "one_line_correction": data.get("user_takeaway") or data.get("what_would_change_verdict") or "Deep verification may refine this answer.",
        "summary": data.get("summary", ""),
        "why_convincing": data.get("why_convincing", ""),
        "evidence_access_note": data.get("evidence_access_note", ""),
        "what_would_change_verdict": data.get("what_would_change_verdict", ""),
        "user_takeaway": data.get("user_takeaway", ""),
        "evidence_types": data.get("evidence_types", []) or [],
    }


# -----------------------------
# Multi-step pipeline
# -----------------------------


def parse_claim_analysis(payload: Dict[str, Any], user_input: str) -> List[SubClaim]:
    validated = validate_model(payload, ClaimAnalysisModel)
    subclaims = []
    for i, item in enumerate(validated.get("subclaims", []) or []):
        subclaims.append(
            SubClaim(
                id=str(item.get("id", f"sc_{i+1}")),
                text=(item.get("text") or "").strip(),
                claim_type=item.get("claim_type", "other"),
                entities=list(item.get("entities", []) or []),
                jurisdiction=item.get("jurisdiction"),
                time_sensitivity=item.get("time_sensitivity", "medium"),
                verification_requirements=list(item.get("verification_requirements", []) or []),
                risk_flags=[x for x in item.get("risk_flags", []) if x],
            )
        )
    if not subclaims:
        subclaims = [SubClaim(id="sc_1", text=user_input.strip(), claim_type="other")]
    return subclaims


def build_search_queries(subclaims: List[SubClaim]) -> List[str]:
    queries: List[str] = []
    seen = set()
    for sub in subclaims:
        candidates = [
            sub.text,
            f'"{sub.text}"',
            f"{sub.text} official source",
            f"{sub.text} evidence",
            f"{sub.text} debunked OR disputed",
        ]
        if sub.claim_type == "legal":
            candidates.extend([
                f"site:gov.uk {sub.text}",
                f"site:legislation.gov.uk {sub.text}",
                f"site:judiciary.uk {sub.text}",
            ])
        for q in candidates:
            q = re.sub(r"\s+", " ", q).strip()
            if q and q not in seen:
                seen.add(q)
                queries.append(q)
    return queries[:12]


def score_source(item: Dict[str, Any], claim_text: str) -> EvidenceSource:
    url = item.get("url", "")
    domain = domain_from_url(url)
    source_type = classify_source_type(domain)
    title = item.get("title", "Untitled")
    snippet = item.get("snippet", "")
    content = item.get("content", "")
    haystack = f"{title} {snippet} {content}".lower()
    terms = [t for t in re.findall(r"[A-Za-z]{4,}", claim_text.lower())][:8]
    overlap = 0
    for t in terms:
        if re.search(SCORING_CONFIG.term_pattern.format(term=re.escape(t)), haystack):
            overlap += 1
    relevance = min(5.0, 1.0 + overlap)
    authority = 5.0 if source_type == "primary" else 3.8 if source_type == "secondary" else 2.2
    directness = 4.5 if any(re.search(SCORING_CONFIG.term_pattern.format(term=re.escape(t)), haystack) for t in terms[:3]) else 2.5
    recency = recency_score(item.get("published_date"))
    bias_risk = 1.5 if source_type == "primary" else 2.5 if source_type == "secondary" else 3.5
    weighted = authority * SCORING_CONFIG.authority_weight + relevance * SCORING_CONFIG.relevance_weight + directness * SCORING_CONFIG.directness_weight + recency * SCORING_CONFIG.recency_weight + (5 - bias_risk) * SCORING_CONFIG.bias_weight
    return EvidenceSource(
        title=title,
        url=url,
        domain=domain,
        source_type=source_type,
        snippet=snippet,
        content=content,
        published_date=item.get("published_date"),
        authority_score=authority,
        relevance_score=relevance,
        directness_score=directness,
        recency_score=recency,
        bias_risk_score=bias_risk,
        weighted_score=round(weighted, 2),
    )


def retrieve_sources(search: TavilySearchClient, queries: List[str], claim_text: str) -> List[EvidenceSource]:
    dedup: Dict[str, EvidenceSource] = {}
    for query in queries[:6]:
        for item in search.search(query, max_results=4):
            url = item.get("url") or ""
            if not url or url in dedup:
                continue
            dedup[url] = score_source(item, claim_text)
    return sorted(dedup.values(), key=lambda x: x.weighted_score, reverse=True)[:SCORING_CONFIG.max_source_summaries]


def _summarize_one_source(llm: OpenAICompatibleClient, subclaim_text: str, source: EvidenceSource) -> EvidenceSource:
    text = source.content or source.snippet
    if not text:
        return source
    payload = llm.complete_json(build_source_summary_messages(subclaim_text, source.title, source.url, text[:6000]))
    validated = validate_model(payload, SourceSummaryModel)
    source.claim_support = validated.get("claim_support", "irrelevant")
    source.evidence_category = validated.get("evidence_category", "irrelevant")
    source.source_role = validated.get("source_role", "context")
    source.narrative_cluster = validated.get("narrative_cluster", "")
    source.snippet = validated.get("summary", source.snippet)
    return source


def summarize_sources(llm: OpenAICompatibleClient, subclaim: SubClaim, sources: List[EvidenceSource]) -> List[EvidenceSource]:
    if not llm.configured or not sources:
        return sources

    indexed_sources = list(enumerate(sources))
    results: Dict[int, EvidenceSource] = {}
    max_workers = min(SCORING_CONFIG.max_summary_workers, len(indexed_sources))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_summarize_one_source, llm, subclaim.text, source): idx
            for idx, source in indexed_sources
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = sources[idx]

    return [results.get(i, source) for i, source in indexed_sources]


def compute_confidence(sources: List[EvidenceSource]) -> int:
    if not sources:
        return 35
    avg = sum(s.weighted_score for s in sources) / len(sources)
    primary_count = sum(1 for s in sources if s.source_type == "primary")
    contradictory = sum(1 for s in sources if s.claim_support == "contradicts")
    supporting = sum(1 for s in sources if s.claim_support == "supports")
    score = int(avg * 14 + primary_count * 4 - max(0, contradictory - supporting) * 4)
    return max(20, min(score, 96))


def provisional_verdict(sources: List[EvidenceSource]) -> str:
    supports = sum(1 for s in sources if s.claim_support == "supports")
    contradicts = sum(1 for s in sources if s.claim_support == "contradicts")
    mixed = sum(1 for s in sources if s.claim_support == "mixed")
    primary_support = any(s.source_type == "primary" and s.claim_support == "supports" for s in sources)
    primary_contradict = any(s.source_type == "primary" and s.claim_support == "contradicts" for s in sources)
    if primary_contradict and contradicts >= supports + mixed:
        return "false"
    if primary_support and supports >= contradicts + mixed:
        return "true"
    if mixed or (supports and contradicts):
        return "misleading"
    if not sources:
        return "unverifiable"
    return "unverifiable"


def run_claim_pipeline(user_input: str, llm: OpenAICompatibleClient, search: TavilySearchClient) -> Dict[str, Any]:
    claim_analysis = validate_model(llm.complete_json(build_claim_analysis_messages(user_input)), ClaimAnalysisModel)
    subclaims = parse_claim_analysis(claim_analysis, user_input)
    claim_text = claim_analysis.get("normalized_claim") or user_input
    queries = build_search_queries(subclaims)
    sources = retrieve_sources(search, queries, claim_text)
    sources = summarize_sources(llm, subclaims[0], sources)
    confidence = compute_confidence(sources)
    pre = provisional_verdict(sources)

    evidence_packet = {
        "claim": claim_text,
        "subclaims": [s.text for s in subclaims],
        "sources": [
            {
                "title": s.title,
                "url": s.url,
                "domain": s.domain,
                "source_type": s.source_type,
                "published_date": s.published_date,
                "summary": s.snippet,
                "claim_support": s.claim_support,
                "evidence_category": getattr(s, "evidence_category", "irrelevant"),
                "source_role": getattr(s, "source_role", "context"),
                "narrative_cluster": getattr(s, "narrative_cluster", ""),
                "weighted_score": s.weighted_score,
            }
            for s in sources
        ],
    }

    pendulum = evidence_pendulum(
        evidence_packet["sources"],
        subclaims[0].claim_type if subclaims else "other",
    )

    reasoning = validate_model(
        llm.complete_json(
            build_reasoning_messages(
                claim_text,
                evidence_packet,
                pre,
                confidence,
                pendulum["band"],
                pendulum["explanation"],
            )
        ),
        VerifiedAssessmentModel,
    )

    reasoning["claim"] = claim_text
    reasoning["subclaims"] = evidence_packet["subclaims"]
    reasoning["sources"] = evidence_packet["sources"]
    reasoning["queries"] = queries
    reasoning["risk_flags"] = sorted(collect_risk_flags(subclaims))
    reasoning["pendulum_band"] = reasoning.get("pendulum_band") or pendulum["band"]
    reasoning["pendulum_explanation"] = reasoning.get("pendulum_explanation") or pendulum["explanation"]
    reasoning["verified_verdict"] = reasoning.get("verified_verdict") or map_pendulum_to_verified_verdict(reasoning["pendulum_band"])
    reasoning["verified_confidence"] = reasoning.get("verified_confidence") or map_confidence_label(reasoning.get("confidence", confidence))

    rule_view = rule_based_verdict_from_evidence(claim_text, subclaims, evidence_packet["sources"], reasoning["pendulum_band"])
    reasoning = align_reasoning_with_rules(reasoning, rule_view)
    reasoning["rule_engine"] = {
        "verdict": rule_view["verdict"],
        "confidence": rule_view["confidence"],
        "rationale": rule_view["rationale"],
        "stats": rule_view["stats"],
        "risk_flags": rule_view["risk_flags"],
    }

    split_view = split_evidence_vs_rumor(evidence_packet["sources"])
    reasoning.setdefault("evidence_assessment", {})
    reasoning["evidence_assessment"]["actual_evidence"] = reasoning["evidence_assessment"].get("actual_evidence") or split_view["actual_evidence"]
    reasoning["evidence_assessment"]["rumor_drivers"] = reasoning["evidence_assessment"].get("rumor_drivers") or split_view["rumor_drivers"]

    if not reasoning.get("consensus_strength"):
        support_count = sum(1 for s in sources if s.claim_support == "supports")
        contradict_count = sum(1 for s in sources if s.claim_support == "contradicts")
        primary_support = sum(1 for s in sources if s.source_type == "primary" and s.claim_support == "supports")
        if support_count >= 3 and contradict_count == 0 and primary_support >= 1:
            reasoning["consensus_strength"] = "Strong agreement"
        elif support_count >= 2 and contradict_count <= 1:
            reasoning["consensus_strength"] = "Moderate agreement"
        elif support_count and contradict_count:
            reasoning["consensus_strength"] = "Mixed evidence"
        elif support_count:
            reasoning["consensus_strength"] = "Weak agreement"
        else:
            reasoning["consensus_strength"] = "No clear consensus"

    if not reasoning.get("consensus_summary"):
        reasoning["consensus_summary"] = "This assessment reflects the balance of the reviewed sources rather than a single outlet or internal score."

    return reasoning
