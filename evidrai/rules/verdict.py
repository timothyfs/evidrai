from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from evidrai.models import SubClaim
from evidrai.utils import ensure_list

def normalize_claim_support(value: str) -> str:
    v = (value or "").strip().lower()
    mapping = {
        "supports": "Supports",
        "contradicts": "Contradicts",
        "mixed": "Mixed",
        "neutral": "Context",
        "irrelevant": "Context",
    }
    return mapping.get(v, "Context")


def map_source_quality_label(score: Any) -> str:
    try:
        val = float(score)
    except (TypeError, ValueError):
        return "Unknown"
    if val >= 4.25:
        return "High"
    if val >= 3.2:
        return "Medium"
    return "Low"

def map_pipeline_verdict(verdict: str) -> str:
    value = (verdict or "").strip().lower()
    mapping = {
        "true": "Supported",
        "supported": "Supported",
        "likely supported": "Likely supported",
        "partly supported": "Partly supported",
        "partially supported": "Partly supported",
        "partially_true": "Misleading framing",
        "partially true": "Misleading framing",
        "misleading": "Misleading framing",
        "contested": "Contested",
        "reported but unconfirmed": "Reported but unconfirmed",
        "false": "False / contradicted",
        "false / contradicted": "False / contradicted",
        "contradicted": "False / contradicted",
        "not supported by credible evidence": "Not supported by credible evidence",
        "weakly supported / likely incorrect": "Weakly supported / likely incorrect",
        "unverifiable": "Unverified",
        "unverified": "Unverified",
    }
    return mapping.get(value, "Unverified")


def map_confidence_label(value: Any) -> str:
    if isinstance(value, (int, float)) or str(value).isdigit():
        score = int(float(value))
        if score >= 70:
            return "High"
        if score >= 45:
            return "Medium"
        return "Low"
    text = str(value).strip().title()
    return text if text in {"High", "Medium", "Low"} else "Medium"

SERIOUS_ALLEGATION_TYPES = {"criminal", "corruption", "espionage", "foreign_agent", "misconduct_named_person"}

VERDICT_ORDER = {
    "Supported": 5,
    "Likely supported": 4,
    "Partly supported": 3.5,
    "Misleading framing": 3,
    "Contested": 2.5,
    "Reported but unconfirmed": 2.25,
    "Unverified": 2,
    "Weakly supported / likely incorrect": 1,
    "Not supported by credible evidence": 0,
    "False / contradicted": 0,
}

SOFT_CLAIM_FLAGS = {
    "opinion",
    "prediction",
    "rhetorical",
    "ambiguity",
    "vague",
    "motive_attribution",
    "value_judgment",
    "non_falsifiable",
}


def _normalized_text_set(values: List[str]) -> set[str]:
    out: set[str] = set()
    for v in values or []:
        cleaned = (v or "").strip().lower()
        if cleaned:
            out.add(cleaned)
    return out


def collect_risk_flags(subclaims: List[SubClaim]) -> set[str]:
    flags: set[str] = set()
    for sub in subclaims or []:
        flags.update(_normalized_text_set(sub.risk_flags))
    return flags


def is_soft_or_hard_to_verify_claim(subclaims: List[SubClaim]) -> bool:
    flags = collect_risk_flags(subclaims)
    if flags & SOFT_CLAIM_FLAGS:
        return True
    soft_types = {"opinion", "prediction", "rhetorical", "other"}
    return all((sub.claim_type or "other").lower() in soft_types for sub in (subclaims or []))


def compute_evidence_stats(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    stats = {
        "supportive_evidence": 0,
        "contradictory_evidence": 0,
        "mixed_sources": 0,
        "rumor_or_context": 0,
        "allegation_or_context_support": 0,
        "denial_or_rebuttal": 0,
        "primary_supportive": 0,
        "primary_contradictory": 0,
        "supportive_reporting": 0,
        "contradictory_reporting": 0,
        "high_quality_supportive": 0,
        "high_quality_contradictory": 0,
        "unique_clusters": set(),
    }
    for s in sources or []:
        category = normalize_evidence_category(s.get("evidence_category", "irrelevant"))
        support = (s.get("claim_support") or "").strip().lower()
        cluster = (s.get("narrative_cluster") or s.get("url") or s.get("title") or "").strip().lower()
        if cluster:
            stats["unique_clusters"].add(cluster)

        source_type = (s.get("source_type") or "").lower()
        is_primaryish = source_type in {"primary", "official", "government", "court", "parliament", "document", "record"}
        is_high_quality = is_primaryish or source_type == "secondary" or float(s.get("weighted_score") or 0) >= 4.25

        if category in {"direct_evidence", "credible_reporting", "expert_analysis"}:
            if support == "supports":
                stats["supportive_evidence"] += 1
                if category == "credible_reporting":
                    stats["supportive_reporting"] += 1
                if is_primaryish or category == "direct_evidence":
                    stats["primary_supportive"] += 1
                if is_high_quality:
                    stats["high_quality_supportive"] += 1
            elif support == "contradicts":
                stats["contradictory_evidence"] += 1
                if category == "credible_reporting":
                    stats["contradictory_reporting"] += 1
                if is_primaryish or category == "direct_evidence":
                    stats["primary_contradictory"] += 1
                if is_high_quality:
                    stats["high_quality_contradictory"] += 1
            else:
                stats["mixed_sources"] += 1
        elif category == "credible_contradiction":
            stats["contradictory_evidence"] += 1
            if is_primaryish:
                stats["primary_contradictory"] += 1
            if is_high_quality:
                stats["high_quality_contradictory"] += 1
        elif category in {"reported_allegation", "contextual_signal", "denial_or_rebuttal", "rumor_amplification", "irrelevant"}:
            stats["rumor_or_context"] += 1
            if support == "supports":
                stats["allegation_or_context_support"] += 1
            if category == "denial_or_rebuttal":
                stats["denial_or_rebuttal"] += 1
            if support == "mixed":
                stats["mixed_sources"] += 1

    stats["unique_clusters"] = len(stats["unique_clusters"])
    return stats


def assess_amplification_risk(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Identify when repeated coverage looks like amplification, not corroboration.

    The warning is deliberately separate from source quality. A reputable outlet can
    still be part of the same evidentiary chain as other outlets if they are all
    repeating the same allegation, briefing, wire copy, or narrative cluster.
    """
    total_sources = len(sources or [])
    if not total_sources:
        return {"triggered": False, "level": "none", "message": "", "details": {}}

    clusters: Counter[str] = Counter()
    substantive_support_clusters: set[str] = set()
    primary_support_clusters: set[str] = set()
    rumor_context_count = 0
    supportive_count = 0

    for idx, source in enumerate(sources or []):
        category = normalize_evidence_category(source.get("evidence_category", "irrelevant"))
        support = (source.get("claim_support") or "").strip().lower()
        cluster = (source.get("narrative_cluster") or source.get("url") or source.get("title") or f"source-{idx}").strip().lower()
        if cluster:
            clusters[cluster] += 1
        if support == "supports":
            supportive_count += 1
        if category in {"reported_allegation", "contextual_signal", "rumor_amplification", "denial_or_rebuttal"}:
            rumor_context_count += 1
        if support == "supports" and category in {"direct_evidence", "credible_reporting", "expert_analysis"}:
            substantive_support_clusters.add(cluster)
            source_type = (source.get("source_type") or "").lower()
            if source_type in {"primary", "official", "government", "court", "parliament", "document", "record"}:
                primary_support_clusters.add(cluster)

    dominant_cluster, dominant_count = clusters.most_common(1)[0] if clusters else ("", 0)
    dominant_ratio = dominant_count / total_sources if total_sources else 0.0
    substantive_cluster_count = len(substantive_support_clusters)
    primary_cluster_count = len(primary_support_clusters)

    repeated_single_chain = total_sources >= 3 and dominant_count >= 3 and dominant_ratio >= 0.6
    thin_independence = supportive_count >= 2 and substantive_cluster_count <= 1 and primary_cluster_count == 0
    mostly_contextual = rumor_context_count >= max(2, supportive_count)
    triggered = repeated_single_chain or thin_independence or mostly_contextual

    if repeated_single_chain and thin_independence:
        level = "high"
    elif triggered:
        level = "medium"
    else:
        level = "none"

    message = ""
    if triggered:
        message = (
            "This claim appears to rely on repeated coverage or contextual signals more than independent evidentiary chains. "
            "Evidrai treats amplification as a visibility signal, not corroboration."
        )

    return {
        "triggered": triggered,
        "level": level,
        "message": message,
        "details": {
            "source_count": total_sources,
            "unique_narrative_clusters": len(clusters),
            "dominant_cluster": dominant_cluster,
            "dominant_cluster_count": dominant_count,
            "dominant_cluster_ratio": round(dominant_ratio, 2),
            "supportive_sources": supportive_count,
            "substantive_support_clusters": substantive_cluster_count,
            "primary_support_clusters": primary_cluster_count,
            "rumor_or_context_sources": rumor_context_count,
        },
    }


def rule_based_verdict_from_evidence(
    claim_text: str,
    subclaims: List[SubClaim],
    sources: List[Dict[str, Any]],
    pendulum_band: str,
) -> Dict[str, Any]:
    stats = compute_evidence_stats(sources)
    flags = collect_risk_flags(subclaims)
    soft_claim = is_soft_or_hard_to_verify_claim(subclaims)
    serious_allegation = any((sub.claim_type or "").lower() in SERIOUS_ALLEGATION_TYPES for sub in (subclaims or []))
    concrete_factual_claim = not soft_claim and "motive_attribution" not in flags

    supportive = stats["supportive_evidence"]
    contradictory = stats["contradictory_evidence"]
    primary_supportive = stats["primary_supportive"]
    primary_contradictory = stats["primary_contradictory"]
    high_quality_supportive = stats["high_quality_supportive"]
    high_quality_contradictory = stats["high_quality_contradictory"]
    rumorish = stats["rumor_or_context"]
    contextual_support = stats["allegation_or_context_support"]
    mixed_sources = stats["mixed_sources"]

    has_no_real_support = supportive == 0 and primary_supportive == 0 and high_quality_supportive == 0
    mostly_contextual_packet = rumorish >= max(2, supportive + contradictory)

    verdict = "Unverified"
    confidence = "Low"
    rationale = "Evidence is limited or mixed."

    if has_no_real_support and contextual_support > 0:
        verdict = "Reported but unconfirmed" if serious_allegation and not soft_claim else "Unverified"
        confidence = "Medium" if serious_allegation else "Low"
        rationale = "The reviewed material contains reporting, allegation, context, or association, but no direct confirmation in the reviewed set substantiates the claim as stated."
    elif supportive >= 2 and contradictory == 0 and primary_supportive >= 1:
        verdict = "Supported"
        confidence = "High" if supportive >= 3 else "Medium"
        rationale = "The reviewed evidence includes direct or high-quality support without material contradiction."
    elif supportive >= 2 and contradictory == 0 and high_quality_supportive >= 1:
        verdict = "Likely supported"
        confidence = "Medium"
        rationale = "The balance of credible evidence leans supportive, but it is not fully closed."
    elif contradictory >= 2 and supportive == 0:
        verdict = "False / contradicted" if high_quality_contradictory >= 1 else "Not supported by credible evidence"
        confidence = "High" if primary_contradictory >= 1 or high_quality_contradictory >= 1 else "Medium"
        rationale = "Credible evidence directly contradicts the claim, and no substantive support was identified in the reviewed set."
    elif contradictory >= 1 and supportive >= 1:
        if supportive >= contradictory and high_quality_supportive >= 1:
            verdict = "Partly supported"
            confidence = "Medium"
            rationale = "The factual core has support, but important qualification, framing, or interpretation remains unresolved."
        else:
            verdict = "Weakly supported / likely incorrect"
            confidence = "Medium"
            rationale = "Some support exists, but stronger evidence points the other way."
    elif pendulum_band == "Strongly evidenced" and high_quality_supportive >= 1:
        verdict = "Supported"
        confidence = "Medium"
        rationale = "The evidence pattern is strongly supportive and includes at least some high-quality support."
    elif pendulum_band == "Mostly supported" and high_quality_supportive >= 1 and not has_no_real_support:
        verdict = "Likely supported"
        confidence = "Medium"
        rationale = "The evidence pattern leans supportive, though some uncertainty remains."
    elif pendulum_band == "Contradicted by evidence":
        verdict = "False / contradicted"
        confidence = "Medium"
        rationale = "The evidence packet contains credible material that conflicts with the claim."
    elif pendulum_band == "Weakly supported":
        verdict = "Weakly supported / likely incorrect"
        confidence = "Low"
        rationale = "The available support is weak and does not carry the claim cleanly."
    elif mostly_contextual_packet and has_no_real_support:
        verdict = "Reported but unconfirmed" if contextual_support > 0 else ("Not supported by credible evidence" if serious_allegation and not soft_claim else "Unverified")
        confidence = "Low"
        rationale = "The packet is dominated by allegation, context, adjacency, or rumor signals rather than substantive evidence. Treat this as reported but not confirmed."
    elif mixed_sources > 0:
        if supportive >= 2 and contradictory == 0 and high_quality_supportive >= 1:
            verdict = "Likely supported"
            confidence = "Medium"
            rationale = "The factual core is supported by credible reporting, while the remaining uncertainty is interpretive rather than evidentiary."
        else:
            verdict = "Contested"
            confidence = "Low"
            rationale = "The evidence packet is mixed or partly interpretive rather than cleanly confirmatory."

    if soft_claim and verdict in {"Supported", "Likely supported", "Partly supported", "Not supported by credible evidence", "False / contradicted"}:
        if supportive >= 2 and contradictory == 0:
            verdict = "Likely supported" if verdict == "Supported" else verdict
            confidence = "Medium"
            rationale = "The factual core has credible support, but part of the claim is interpretive or legally contested, so confidence is capped."
        else:
            verdict = "Unverified" if verdict != "Supported" else "Likely supported"
            confidence = "Low" if verdict == "Unverified" else "Medium"
            rationale = "The claim is partly interpretive, predictive, rhetorical, or too vague for a stronger factual verdict."

    if "motive_attribution" in flags and verdict not in {"Supported", "Likely supported"}:
        verdict = "Unverified"
        confidence = "Low"
        rationale = "This claim depends on motive attribution, which usually cannot be verified cleanly from public evidence alone."

    if serious_allegation and has_no_real_support and verdict == "Unverified" and rumorish >= 1:
        verdict = "Reported but unconfirmed" if contextual_support > 0 else "Not supported by credible evidence"
        confidence = "Medium"
        rationale = "This is a serious allegation with reporting or contextual signals, but the reviewed set does not contain direct confirmation."

    return {
        "verdict": verdict,
        "confidence": confidence,
        "rationale": rationale,
        "stats": stats,
        "soft_claim": soft_claim,
        "serious_allegation": serious_allegation,
        "risk_flags": sorted(flags),
    }


def align_reasoning_with_rules(reasoning: Dict[str, Any], rule_view: Dict[str, Any]) -> Dict[str, Any]:
    model_verdict = map_pipeline_verdict(reasoning.get("verified_verdict") or "Unverified")
    model_confidence = map_confidence_label(reasoning.get("verified_confidence") or "Low")
    rule_verdict = rule_view["verdict"]
    rule_confidence = rule_view["confidence"]

    stats = rule_view["stats"]
    factual_core_supported = stats["supportive_evidence"] >= 2 and stats["contradictory_evidence"] == 0
    rule_is_stronger = VERDICT_ORDER.get(rule_verdict, 2) > VERDICT_ORDER.get(model_verdict, 2)
    model_is_stronger = VERDICT_ORDER.get(model_verdict, 2) > VERDICT_ORDER.get(rule_verdict, 2)

    if model_is_stronger:
        reasoning["verified_verdict"] = rule_verdict
        reasoning["verified_confidence"] = rule_confidence
    elif rule_verdict == "Reported but unconfirmed" and model_verdict == "Unverified":
        reasoning["verified_verdict"] = rule_verdict
        reasoning["verified_confidence"] = rule_confidence
    elif rule_verdict == "False / contradicted" and stats["contradictory_evidence"] >= 1:
        reasoning["verified_verdict"] = rule_verdict
        reasoning["verified_confidence"] = rule_confidence
    elif rule_is_stronger and factual_core_supported:
        reasoning["verified_verdict"] = rule_verdict
        reasoning["verified_confidence"] = rule_confidence
    else:
        reasoning["verified_verdict"] = model_verdict
        if VERDICT_ORDER.get(model_verdict, 2) == VERDICT_ORDER.get(rule_verdict, 2):
            confidence_rank = {"Low": 0, "Medium": 1, "High": 2}
            reasoning["verified_confidence"] = rule_confidence if confidence_rank.get(rule_confidence, 0) < confidence_rank.get(model_confidence, 0) else model_confidence
        else:
            reasoning["verified_confidence"] = model_confidence

    if rule_view["soft_claim"] and reasoning.get("verified_confidence") == "High":
        reasoning["verified_confidence"] = "Medium"
    if rule_view["soft_claim"] and reasoning.get("verified_verdict") in {"Supported", "Likely supported", "Partly supported", "Not supported by credible evidence", "False / contradicted"}:
        if factual_core_supported:
            if reasoning.get("verified_verdict") == "Supported":
                reasoning["verified_verdict"] = "Likely supported"
            reasoning["verified_confidence"] = "Medium"
        elif reasoning.get("verified_verdict") != "Supported":
            reasoning["verified_verdict"] = "Unverified"
            reasoning["verified_confidence"] = "Low"

    # Context, allegations, donor adjacency, and repeated commentary should not be presented as substantive support.
    stats = rule_view["stats"]
    if stats["supportive_evidence"] == 0 and stats["allegation_or_context_support"] > 0:
        reasoning["verified_verdict"] = rule_view["verdict"]
        reasoning["verified_confidence"] = rule_view["confidence"]

    evidence_assessment = reasoning.setdefault("evidence_assessment", {})
    stats = rule_view["stats"]
    evidence_assessment["evidence_gaps"] = ensure_list(evidence_assessment.get("evidence_gaps"))
    if stats["supportive_evidence"] == 0:
        evidence_assessment["evidence_gaps"].append("No direct or clearly supportive evidentiary source was identified in the reviewed packet.")
    if stats["allegation_or_context_support"] > 0 and stats["supportive_evidence"] == 0:
        evidence_assessment["evidence_gaps"].append("Several sources provide allegation, adjacency, or contextual association rather than direct substantiation of the claim as stated.")
    if rule_view["soft_claim"]:
        evidence_assessment["evidence_gaps"].append("Part of the claim is interpretive, rhetorical, predictive, or otherwise difficult to verify directly.")

    explanation_note = rule_view["rationale"]
    final_explanation = (reasoning.get("final_explanation") or "").strip()
    if explanation_note and explanation_note not in final_explanation:
        reasoning["final_explanation"] = (final_explanation + "\n\nRule-based check: " + explanation_note).strip()

    summary = (reasoning.get("consensus_summary") or "").strip()
    if explanation_note and explanation_note not in summary:
        reasoning["consensus_summary"] = (summary + " " + explanation_note).strip()

    return reasoning

def normalize_evidence_category(category: str) -> str:
    c = (category or "").strip().lower()
    mapping = {
        "documented_support": "direct_evidence",
        "direct_evidence": "direct_evidence",
        "primary_evidence": "direct_evidence",
        "credible_reporting": "credible_reporting",
        "expert_analysis": "expert_analysis",
        "reported_allegation": "reported_allegation",
        "allegation": "reported_allegation",
        "context_only": "contextual_signal",
        "contextual_signal": "contextual_signal",
        "denial": "denial_or_rebuttal",
        "denial_or_rebuttal": "denial_or_rebuttal",
        "credible_contradiction": "credible_contradiction",
        "contradiction": "credible_contradiction",
        "rumor_amplification": "rumor_amplification",
        "irrelevant": "irrelevant",
    }
    return mapping.get(c, "irrelevant")


def source_bucket_multiplier(source_type: str, domain: str) -> float:
    stype = (source_type or "").lower()
    d = (domain or "").lower()
    if stype in {"official", "government", "court", "parliament"}:
        return 1.5
    if stype in {"primary", "document", "record"}:
        return 1.4
    if any(x in d for x in ["reuters.com", "apnews.com", "bbc.", "ft.com", "nytimes.com", "theguardian.com", "lemonde.fr", "france24.com"]):
        return 1.3
    if stype in {"expert_publication", "journal", "think_tank"}:
        return 1.2
    if stype in {"commentary", "analysis"}:
        return 1.0
    if stype in {"local_news"}:
        return 0.9
    if stype in {"forum", "reddit", "quora"}:
        return 0.3
    if stype in {"social", "social_media", "x", "twitter", "facebook", "instagram", "tiktok"}:
        return 0.4
    return 0.7


def evidence_pendulum(sources: List[Dict[str, Any]], claim_type: str = "other") -> Dict[str, Any]:
    weights = {
        "direct_evidence": 3.0,
        "credible_reporting": 2.0,
        "expert_analysis": 1.0,
        "reported_allegation": 0.5,
        "contextual_signal": 0.25,
        "denial_or_rebuttal": 0.25,
        "credible_contradiction": 3.0,
        "rumor_amplification": 0.0,
        "irrelevant": 0.0,
    }
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for s in sources:
        key = (s.get("narrative_cluster") or f"{s.get('domain','')}|{s.get('evidence_category','')}|{s.get('claim_support','')}").strip().lower()
        grouped.setdefault(key, []).append(s)

    score = 0.0
    support_count = contradiction_count = rumor_count = 0
    decay = [1.0, 0.7, 0.4, 0.2]
    for items in grouped.values():
        items = sorted(items, key=lambda x: source_bucket_multiplier(x.get("source_type",""), x.get("domain","")), reverse=True)
        for idx, s in enumerate(items):
            cat = normalize_evidence_category(s.get("evidence_category", "irrelevant"))
            support = (s.get("claim_support") or "").strip().lower()
            mult = source_bucket_multiplier(s.get("source_type",""), s.get("domain",""))
            base = weights.get(cat, 0.0)
            direction = 0.0
            if cat == "credible_contradiction":
                direction = -1.0
            elif support == "supports":
                direction = 1.0
            elif support == "contradicts":
                direction = -1.0
            elif cat in {"reported_allegation", "contextual_signal", "denial_or_rebuttal", "rumor_amplification"}:
                direction = 0.0
            contribution = base * mult * (decay[idx] if idx < len(decay) else 0.1) * direction
            score += contribution
            if cat in {"direct_evidence", "credible_reporting", "expert_analysis"} and support == "supports":
                support_count += 1
            if cat in {"credible_contradiction"} or (cat in {"direct_evidence", "credible_reporting", "expert_analysis"} and support == "contradicts"):
                contradiction_count += 1
            if cat in {"reported_allegation", "contextual_signal", "rumor_amplification", "denial_or_rebuttal"}:
                rumor_count += 1

    adjusted = score
    if (claim_type or "").lower() in SERIOUS_ALLEGATION_TYPES and adjusted > 0:
        adjusted -= 3.0

    if support_count == 0 and contradiction_count == 0 and rumor_count > 0:
        band = "Unsubstantiated rumor"
    elif contradiction_count >= 2 and adjusted <= -6:
        band = "Contradicted by evidence"
    elif adjusted >= 8:
        band = "Strongly evidenced"
    elif adjusted >= 4:
        band = "Mostly supported"
    elif adjusted >= -3:
        band = "Mixed / uncertain"
    elif adjusted >= -7:
        band = "Weakly supported"
    else:
        band = "Unsubstantiated rumor"

    explanation = f"{support_count} evidentiary source(s), {contradiction_count} contradiction signal(s), {rumor_count} rumor/context signal(s)"
    return {"band": band, "score": round(adjusted, 2), "explanation": explanation}


def map_pendulum_to_verified_verdict(band: str) -> str:
    mapping = {
        "Strongly evidenced": "Supported",
        "Mostly supported": "Likely supported",
        "Mixed / uncertain": "Misleading framing",
        "Weakly supported": "Weakly supported / likely incorrect",
        "Unsubstantiated rumor": "Unverified",
        "Contradicted by evidence": "False / contradicted",
    }
    return mapping.get(band, "Unverified")


def split_evidence_vs_rumor(sources: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    actual_evidence: List[str] = []
    rumor_drivers: List[str] = []
    for s in sources:
        cat = normalize_evidence_category(s.get("evidence_category", ""))
        summary = s.get("summary") or s.get("snippet") or ""
        if not summary:
            continue
        if cat in {"direct_evidence", "credible_reporting", "expert_analysis", "credible_contradiction"}:
            actual_evidence.append(summary)
        elif cat in {"reported_allegation", "contextual_signal", "rumor_amplification", "denial_or_rebuttal"}:
            rumor_drivers.append(summary)
    return {"actual_evidence": actual_evidence[:6], "rumor_drivers": rumor_drivers[:6]}
