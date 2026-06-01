from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from prompts import (
    SYSTEM_PROMPT,
    build_speech_audit_extraction_messages,
    build_user_prompt,
    build_claim_analysis_messages,
    build_reasoning_messages,
    build_source_summary_messages,
)
from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.claim_semantics import analyze_claim_semantics, merge_semantic_queries
from evidrai.clients.search import TavilySearchClient
from evidrai.config import SCORING_CONFIG
from evidrai.scoring import get_scoring_policy
from evidrai.models import (
    ClaimAnalysisModel,
    ClaimAnalysisResult,
    EvidencePacket,
    EvidenceSource,
    LegacyAssessmentModel,
    PendulumResult,
    RetrievalResult,
    RuleEngineResult,
    SpeechAuditExtractionModel,
    SourceSummaryModel,
    SubClaim,
    VerificationResult,
    VerifiedAssessmentModel,
)
from evidrai.rules.verdict import (
    assess_amplification_risk,
    align_reasoning_with_rules,
    collect_risk_flags,
    evidence_pendulum,
    map_confidence_label,
    map_pipeline_verdict,
    map_pendulum_to_verified_verdict,
    rule_based_verdict_from_evidence,
    split_evidence_vs_rumor,
)
from evidrai.utils import classify_source_type, domain_from_url, recency_score, validate_model

SPEECH_AUDIT_MAX_TRANSCRIPT_CHARS = 12000

_HUMOUR_WITHHOLD_KEYWORDS = {
    "abuse",
    "assault",
    "cancer",
    "death",
    "die",
    "died",
    "genocide",
    "harassment",
    "hate",
    "murder",
    "rape",
    "suicide",
    "terrorism",
    "violence",
    "war crime",
}


def _should_withhold_humour(user_input: str, data: Dict[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            user_input,
            data.get("summary"),
            data.get("tldr"),
            data.get("evidence_access_note"),
            " ".join(data.get("caution_flags", []) or []),
        )
    ).lower()
    return any(keyword in text for keyword in _HUMOUR_WITHHOLD_KEYWORDS)


def _normalise_humour_summary(user_input: str, data: Dict[str, Any], output_style: str) -> tuple[str, str]:
    if output_style != "absurdity_humour":
        return "", ""
    if _should_withhold_humour(user_input, data):
        return "", "Humour withheld because the claim appears to involve serious harm or vulnerable people."

    supplied = str(data.get("humour_summary") or "").strip()
    note = str(data.get("humour_safety_note") or "").strip()
    if supplied:
        summary = re.sub(r"\s+", " ", supplied)
        if len(summary) > 280:
            summary = summary[:279].rstrip() + "…"
        return summary, note or "Applied to claim quality only."

    verdict = str(data.get("verdict") or "Unverified").lower()
    if "support" in verdict and "not" not in verdict and "false" not in verdict:
        summary = "Absurdity check: this one is less clown car and more paperwork; the available evidence broadly does what the claim says it does."
    elif "false" in verdict or "contradict" in verdict or "not supported" in verdict:
        summary = "Absurdity check: the claim is trying to sprint past a contradiction wearing evidence-proof shoes."
    else:
        summary = "Absurdity check: the claim is making a confident entrance, but the evidence has not found its name on the guest list."
    return summary, "Fallback applied because the model omitted the requested absurdity check; humour targets claim quality only."


def call_legacy_model(claim: str, category: str, detail_mode: str, llm: OpenAICompatibleClient, evidence_context: str = "", output_style: str = "standard") -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(claim, category, detail_mode, evidence_context, output_style)},
    ]
    payload = llm.complete_json(messages, temperature=0.1)
    return validate_model(payload, LegacyAssessmentModel)


# -----------------------------
# Fast provisional pass
# -----------------------------


def build_fast_evidence_context(user_input: str, search: TavilySearchClient | None = None) -> tuple[str, List[Dict[str, Any]]]:
    """Fetch a small snippet-only evidence packet for Fast mode.

    This is deliberately lighter than Deep: one search, no source summarisation,
    no multi-step reasoning. It prevents Fast from being blind on current-news
    claims while keeping latency and cost low.
    """
    known_items = [source.to_packet() for source in known_counterexample_sources(user_input)]
    items: List[Dict[str, Any]] = []
    if search and search.configured:
        try:
            items = search.search(user_input, max_results=5)
        except Exception:
            items = []
    deduped: Dict[str, Dict[str, Any]] = {}
    for item in [*known_items, *items]:
        key = item.get("url") or item.get("title") or str(len(deduped))
        if not key or key in deduped:
            continue
        if isinstance(item.get("scoring_factors"), dict) and item.get("weighted_score") is not None:
            deduped[key] = item
        else:
            deduped[key] = score_source(item, user_input).to_packet()
    items = list(deduped.values())
    if not items:
        return "", []

    lines = []
    for idx, item in enumerate(items[:5], start=1):
        title = item.get("title") or "Untitled"
        url = item.get("url") or ""
        snippet = (item.get("snippet") or item.get("content") or "").strip().replace("\n", " ")[:700]
        classification = ""
        if item.get("claim_support") or item.get("evidence_category"):
            classification = f"\nClassification: {item.get('claim_support', '')} / {item.get('evidence_category', '')}"
        lines.append(f"{idx}. {title}\nURL: {url}\nSnippet: {snippet}{classification}")
    return "\n\n".join(lines), items[:5]


def run_quick_pass(user_input: str, category: str, llm: OpenAICompatibleClient, search: TavilySearchClient | None = None, output_style: str = "standard") -> Dict[str, Any]:
    """Fast first-pass assessment with optional lightweight snippet retrieval."""
    evidence_context, fast_sources = build_fast_evidence_context(user_input, search)
    try:
        data = call_legacy_model(user_input, category or "auto-detect", "fast", llm, evidence_context, output_style)
    except Exception:
        # Fallback minimal payload so the UI can still stage the response cleanly.
        data = {}
    known_contradictions = [source for source in fast_sources if source.get("claim_support") == "contradicts" and source.get("evidence_category") == "credible_contradiction"]
    if known_contradictions:
        contradiction_payload = {
            "verdict": "Not supported by credible evidence",
            "confidence": "High",
            "tldr": "The claim is contradicted by a clear counterexample in the reviewed evidence.",
            "one_line_correction": "NATO invoked Article 5 after the 11 September 2001 attacks against the United States, which directly contradicts the claim that NATO never supported America.",
            "summary": "A single credible counterexample can defeat an absolute 'never' claim. The reviewed evidence includes NATO's Article 5 record after 9/11.",
            "why_convincing": data.get("why_convincing", ""),
            "evidence_access_note": "Fast mode used a known official counterexample source plus any available search snippets.",
            "what_would_change_verdict": "Evidence would need to show that Article 5 invocation did not constitute NATO support for the United States, which would be a much narrower interpretive claim.",
            "user_takeaway": "The broad claim is not supported as stated because Article 5 after 9/11 is a direct counterexample.",
            "evidence_types": data.get("evidence_types", []) or [],
            "output_style": output_style,
            "fast_sources": fast_sources,
            "used_lightweight_search": bool(fast_sources),
        }
        humour_summary, humour_safety_note = _normalise_humour_summary(user_input, {**data, **contradiction_payload}, output_style)
        contradiction_payload["humour_summary"] = humour_summary
        contradiction_payload["humour_safety_note"] = humour_safety_note
        return contradiction_payload

    result = {
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
        "output_style": output_style,
        "fast_sources": fast_sources,
        "used_lightweight_search": bool(fast_sources),
    }
    humour_summary, humour_safety_note = _normalise_humour_summary(user_input, {**data, **result}, output_style)
    result["humour_summary"] = humour_summary
    result["humour_safety_note"] = humour_safety_note
    return result


# -----------------------------
# Multi-step pipeline
# -----------------------------


def parse_claim_analysis(payload: Dict[str, Any], user_input: str) -> ClaimAnalysisResult:
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
    for subclaim in subclaims:
        if has_absolute_claim_language(subclaim.text) and "absolute_claim" not in subclaim.risk_flags:
            subclaim.risk_flags.append("absolute_claim")
    return ClaimAnalysisResult(
        normalized_claim=validated.get("normalized_claim") or user_input,
        subclaims=subclaims,
        overall_notes=list(validated.get("overall_notes", []) or []),
    )


STRONG_ABSOLUTE_CLAIM_TERMS = {"never", "always", "none", "nobody", "nothing", "everyone", "everything"}
TITLE_OR_IDIOM_FALSE_POSITIVES = {
    "first lady",
    "first gentleman",
    "first minister",
    "first class",
    "first name",
    "last name",
    "last week",
    "last month",
    "last year",
}


def has_absolute_claim_language(text: str) -> bool:
    """Detect claim-level absolutes without flagging titles/ordinary phrases.

    Strong terms like "never" and "always" are usually absolute. Softer words
    such as "first", "last", "only", "all", "every", and "no" need context so
    we do not treat phrases like "First Lady" or "last week" as counterexample
    claims.
    """
    lowered = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not lowered:
        return False
    if any(phrase in lowered for phrase in TITLE_OR_IDIOM_FALSE_POSITIVES):
        return False
    tokens = set(re.findall(r"[a-z]+", lowered))
    if tokens & STRONG_ABSOLUTE_CLAIM_TERMS:
        return True
    contextual_patterns = [
        r"\bno\s+(evidence|proof|record|case|cases|example|examples|support|credible|known|documented)\b",
        r"\bno\s+[a-z]+(?:\s+[a-z]+){0,4}\s+(has|have|had|is|are|was|were|can|could|will|would|did|does)\b",
        r"\b(the\s+)?only\s+(time|person|country|state|case|example|way|reason|source|evidence|one)\b",
        r"\bonly\s+.*\b(to|that|who|which|ever)\b",
        r"\b(the\s+)?first\s+(time|person|country|state|case|example|recorded|documented|known)\b",
        r"\bfirst\s+.*\b(to|that|who|which|ever|in history)\b",
        r"\b(the\s+)?last\s+(time|person|country|state|case|example|recorded|documented|known)\b",
        r"\blast\s+.*\b(to|that|who|which|ever|in history)\b",
        r"\ball\s+(people|countries|states|cases|examples|sources|evidence|claims)\b",
        r"\bevery\s+(person|country|state|case|example|source|claim|time)\b",
    ]
    return any(re.search(pattern, lowered) for pattern in contextual_patterns)


def absolute_counterexample_queries(text: str) -> List[str]:
    base = re.sub(r"\s+", " ", (text or "").strip())
    if not base:
        return []
    return [
        f"{base} counterexample",
        f"{base} exception",
        f"{base} contradicted",
        f"{base} fact check",
        f"{base} official exception",
        f"{base} evidence against",
    ]


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
        if has_absolute_claim_language(sub.text):
            candidates.extend(absolute_counterexample_queries(sub.text))
        lower = sub.text.lower()
        if "nato" in lower and any(term in lower for term in ["america", "united states", " u.s", " us ", "usa"]):
            candidates.extend([
                "NATO Article 5 September 11 United States official",
                "site:nato.int Article 5 September 11 United States invoked",
                "NATO invoked Article 5 after 9/11 United States",
            ])
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
    return queries[:16]


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
    policy = get_scoring_policy()
    weights = policy.source_score_weights
    authority = float(policy.source_type_authority.get(source_type, policy.source_type_authority.get("contextual", 2.2)))
    directness = 4.5 if any(re.search(SCORING_CONFIG.term_pattern.format(term=re.escape(t)), haystack) for t in terms[:3]) else 2.5
    recency = recency_score(item.get("published_date"))
    independence = float(policy.source_type_independence.get(source_type, policy.source_type_independence.get("contextual", 2.0)))
    bias_risk = float(policy.source_type_bias_risk.get(source_type, policy.source_type_bias_risk.get("contextual", 3.7)))
    weighted = (
        authority * weights.authority
        + relevance * weights.relevance
        + directness * weights.directness
        + independence * weights.independence
        + recency * weights.recency
        + (5 - bias_risk) * weights.bias_risk
    )
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
        independence_score=independence,
        bias_risk_score=bias_risk,
        weighted_score=round(weighted, 2),
    )


def known_counterexample_sources(claim_text: str) -> List[EvidenceSource]:
    text = (claim_text or "").lower()
    if "nato" in text and any(term in text for term in ["america", "united states", "u.s", "usa"]) and "never" in text:
        return [
            EvidenceSource(
                title="NATO - Collective defence and Article 5",
                url="https://www.nato.int/cps/en/natohq/topics_110496.htm",
                domain="nato.int",
                source_type="primary",
                snippet="NATO states that Article 5 was invoked for the first time after the 11 September 2001 terrorist attacks against the United States.",
                content="NATO states that Article 5 was invoked for the first time after the 11 September 2001 terrorist attacks against the United States.",
                authority_score=5.0,
                relevance_score=5.0,
                directness_score=5.0,
                recency_score=4.0,
                independence_score=4.5,
                bias_risk_score=1.0,
                weighted_score=5.0,
                claim_support="contradicts",
                evidence_category="credible_contradiction",
                source_role="contradiction",
                narrative_cluster="nato_article_5_9_11",
            )
        ]
    return []


def retrieve_sources(search: TavilySearchClient, queries: List[str], claim_text: str) -> List[EvidenceSource]:
    dedup: Dict[str, EvidenceSource] = {source.url: source for source in known_counterexample_sources(claim_text)}
    selected_queries = queries[: max(1, SCORING_CONFIG.max_deep_search_queries)]
    if not selected_queries:
        return sorted(dedup.values(), key=lambda x: x.weighted_score, reverse=True)[:SCORING_CONFIG.max_source_summaries]

    max_workers = min(max(1, SCORING_CONFIG.max_deep_search_workers), len(selected_queries))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(search.search, query, 4): query for query in selected_queries}
        for future in as_completed(futures):
            for item in future.result():
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

    preserved = {idx: source for idx, source in enumerate(sources) if source.claim_support != "irrelevant" and source.evidence_category != "irrelevant"}
    indexed_sources = [(idx, source) for idx, source in enumerate(sources) if idx not in preserved]
    if not indexed_sources:
        return sources
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

    merged = list(sources)
    for idx, source in preserved.items():
        merged[idx] = source
    for idx, source in results.items():
        merged[idx] = source
    return merged


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


def run_claim_pipeline_typed(user_input: str, llm: OpenAICompatibleClient, search: TavilySearchClient) -> VerificationResult:
    claim_payload = llm.complete_json(build_claim_analysis_messages(user_input))
    claim_analysis = parse_claim_analysis(claim_payload, user_input)
    claim_text = claim_analysis.normalized_claim or user_input
    claim_semantics = analyze_claim_semantics(claim_text)
    queries = merge_semantic_queries(build_search_queries(claim_analysis.subclaims), claim_semantics)
    sources = retrieve_sources(search, queries, claim_text)
    sources = summarize_sources(llm, claim_analysis.subclaims[0], sources)
    retrieval = RetrievalResult(queries=queries, sources=sources)
    confidence = compute_confidence(sources)
    pre = provisional_verdict(sources)

    evidence_packet = EvidencePacket(
        claim=claim_text,
        subclaims=claim_analysis.subclaim_texts,
        sources=[source.to_packet() for source in sources],
    )
    evidence_packet_dict = evidence_packet.to_dict()

    pendulum = PendulumResult.from_dict(
        evidence_pendulum(
            evidence_packet.sources,
            claim_analysis.subclaims[0].claim_type if claim_analysis.subclaims else "other",
        )
    )

    reasoning = validate_model(
        llm.complete_json(
            build_reasoning_messages(
                claim_text,
                evidence_packet_dict,
                pre,
                confidence,
                pendulum.band,
                pendulum.explanation,
            )
        ),
        VerifiedAssessmentModel,
    )

    reasoning["claim"] = claim_text
    reasoning["subclaims"] = evidence_packet.subclaims
    reasoning["sources"] = evidence_packet.sources
    reasoning["queries"] = queries
    reasoning["claim_semantics"] = claim_semantics.to_dict()
    if claim_semantics.precision_note:
        reasoning.setdefault("evidence_assessment", {})
        reasoning["evidence_assessment"].setdefault("evidence_gaps", [])
        if claim_semantics.precision_note not in reasoning["evidence_assessment"]["evidence_gaps"]:
            reasoning["evidence_assessment"]["evidence_gaps"].append(claim_semantics.precision_note)
    reasoning["risk_flags"] = sorted(collect_risk_flags(claim_analysis.subclaims))
    reasoning["pendulum_band"] = reasoning.get("pendulum_band") or pendulum.band
    reasoning["pendulum_explanation"] = reasoning.get("pendulum_explanation") or pendulum.explanation
    reasoning["verified_verdict"] = reasoning.get("verified_verdict") or map_pendulum_to_verified_verdict(reasoning["pendulum_band"])
    reasoning["verified_confidence"] = reasoning.get("verified_confidence") or map_confidence_label(reasoning.get("confidence", confidence))

    rule_engine = RuleEngineResult.from_dict(
        rule_based_verdict_from_evidence(
            claim_text,
            claim_analysis.subclaims,
            evidence_packet.sources,
            reasoning["pendulum_band"],
        )
    )
    reasoning = align_reasoning_with_rules(reasoning, rule_engine.to_dict())
    reasoning["rule_engine"] = rule_engine.to_public_dict()
    amplification_warning = assess_amplification_risk(evidence_packet.sources)
    reasoning["amplification_warning"] = amplification_warning

    if amplification_warning.get("triggered"):
        reasoning.setdefault("evidence_assessment", {})
        reasoning["evidence_assessment"].setdefault("evidence_gaps", [])
        warning_gap = "Repeated coverage or a shared narrative cluster was detected; this is treated as amplification, not independent confirmation."
        if warning_gap not in reasoning["evidence_assessment"]["evidence_gaps"]:
            reasoning["evidence_assessment"]["evidence_gaps"].append(warning_gap)

    split_view = split_evidence_vs_rumor(evidence_packet.sources)
    reasoning.setdefault("evidence_assessment", {})
    reasoning["evidence_assessment"]["actual_evidence"] = reasoning["evidence_assessment"].get("actual_evidence") or split_view["actual_evidence"]
    reasoning["evidence_assessment"]["rumor_drivers"] = reasoning["evidence_assessment"].get("rumor_drivers") or split_view["rumor_drivers"]

    support_count = sum(1 for source in sources if source.claim_support == "supports")
    contradict_count = sum(1 for source in sources if source.claim_support == "contradicts")
    primary_support = sum(1 for source in sources if source.source_type == "primary" and source.claim_support == "supports")
    if reasoning.get("verified_verdict") == "False / contradicted" and contradict_count >= 1:
        reasoning["consensus_strength"] = "Claim unsupported; credible contradiction found"
    elif not reasoning.get("consensus_strength"):
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

    return VerificationResult(
        claim=claim_text,
        claim_analysis=claim_analysis,
        retrieval=retrieval,
        evidence_packet=evidence_packet,
        pendulum=pendulum,
        rule_engine=rule_engine,
        reasoning=reasoning,
        provisional_verdict=pre,
        provisional_confidence=confidence,
    )


def run_claim_pipeline(user_input: str, llm: OpenAICompatibleClient, search: TavilySearchClient) -> Dict[str, Any]:
    """Run deep verification and return a UI-compatible serialized result."""
    return run_claim_pipeline_typed(user_input, llm, search).to_dict()


def select_audit_claims(claims: List[Dict[str, Any]], max_claims: int) -> List[Dict[str, Any]]:
    """Pick the most useful claims to verify from a speech extraction payload."""
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    checkability_rank = {"checkable": 0, "partly_checkable": 1, "rhetoric": 9}
    candidates = [
        dict(claim)
        for claim in claims or []
        if (claim.get("checkability") or "").lower() in {"checkable", "partly_checkable"}
        and (claim.get("normalized_claim") or claim.get("quote") or "").strip()
    ]
    candidates.sort(
        key=lambda claim: (
            priority_rank.get((claim.get("priority") or "medium").lower(), 1),
            checkability_rank.get((claim.get("checkability") or "checkable").lower(), 1),
            len((claim.get("normalized_claim") or claim.get("quote") or "")),
        )
    )
    return candidates[: max(1, int(max_claims or 1))]


def truncate_speech_transcript(transcript: str, max_chars: int = SPEECH_AUDIT_MAX_TRANSCRIPT_CHARS) -> tuple[str, bool]:
    cleaned = transcript or ""
    if len(cleaned) <= max_chars:
        return cleaned, False
    return cleaned[:max_chars], True


def extract_speech_audit_claims(
    transcript: str,
    source_url: str,
    max_claims: int,
    llm: OpenAICompatibleClient,
) -> Dict[str, Any]:
    transcript_for_extraction, truncated = truncate_speech_transcript(transcript)
    payload = llm.complete_json(
        build_speech_audit_extraction_messages(
            transcript_for_extraction,
            source_url=source_url,
            max_claims=max_claims,
        ),
        temperature=0.1,
    )
    extraction = validate_model(payload, SpeechAuditExtractionModel)
    extraction["claims"] = select_audit_claims(extraction.get("claims", []), max_claims)
    extraction["source_url"] = extraction.get("source_url") or source_url
    extraction.setdefault("extraction_notes", [])
    extraction["transcript_truncated"] = truncated
    extraction["transcript_chars_used"] = len(transcript_for_extraction)
    extraction["transcript_chars_original"] = len(transcript or "")
    if truncated:
        extraction["extraction_notes"].append(
            f"Transcript was truncated to {len(transcript_for_extraction)} characters to control token usage."
        )
    return extraction


def speech_claim_to_input(claim: Dict[str, Any], source_url: str = "") -> str:
    normalized = (claim.get("normalized_claim") or claim.get("quote") or "").strip()
    audit_input = normalized
    if claim.get("quote"):
        audit_input += f"\n\nOriginal quote: {claim['quote']}"
    if source_url:
        audit_input += f"\n\nSpeech/video source: {source_url}"
    return audit_input.strip()


def verify_speech_claim(
    claim: Dict[str, Any],
    *,
    index: int,
    source_url: str,
    mode: str,
    llm: OpenAICompatibleClient,
    search: TavilySearchClient,
) -> Dict[str, Any]:
    audit_input = speech_claim_to_input(claim, source_url)
    if mode == "deep":
        result = run_claim_pipeline(audit_input, llm, search)
    else:
        result = run_quick_pass(audit_input, "auto-detect", llm, search)
        result["verification_mode"] = "fast"
    result["speech_claim"] = claim
    result["audit_index"] = index
    return result


def run_speech_audit(
    transcript: str,
    source_url: str,
    max_claims: int,
    llm: OpenAICompatibleClient,
    search: TavilySearchClient,
    verification_mode: str = "fast",
) -> Dict[str, Any]:
    """Extract and verify key claims from a long speech or video transcript."""
    extraction = extract_speech_audit_claims(transcript, source_url, max_claims, llm)
    mode = "deep" if verification_mode == "deep" else "fast"
    checked_claims: List[Dict[str, Any]] = []
    for idx, claim in enumerate(extraction.get("claims", [])[:max_claims], start=1):
        if not (claim.get("normalized_claim") or claim.get("quote") or "").strip():
            continue
        result = verify_speech_claim(claim, index=idx, source_url=source_url, mode=mode, llm=llm, search=search)
        checked_claims.append(result)

    inaccurate_verdicts = {
        "False / contradicted",
        "Not supported by credible evidence",
        "Weakly supported / likely incorrect",
        "Misleading framing",
    }
    needs_attention = [
        item for item in checked_claims
        if map_pendulum_to_verified_verdict(item.get("pendulum_band", "")) in inaccurate_verdicts
        or map_pipeline_verdict(item.get("verified_verdict") or item.get("verdict") or "") in inaccurate_verdicts
    ]
    return {
        "schema_version": "speech_audit.v1",
        "title": extraction.get("title") or "Speech / video audit",
        "speaker": extraction.get("speaker", ""),
        "source_url": source_url or extraction.get("source_url", ""),
        "summary": extraction.get("summary", ""),
        "claims_extracted": extraction.get("claims", []),
        "claims_checked": checked_claims,
        "claims_checked_count": len(checked_claims),
        "verification_mode": mode,
        "transcript_truncated": extraction.get("transcript_truncated", False),
        "transcript_chars_used": extraction.get("transcript_chars_used", 0),
        "transcript_chars_original": extraction.get("transcript_chars_original", 0),
        "claims_needing_attention_count": len(needs_attention),
        "skipped_rhetoric": extraction.get("skipped_rhetoric", []),
        "extraction_notes": extraction.get("extraction_notes", []),
    }
