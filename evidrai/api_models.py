from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from evidrai.enums import (
    normalize_claim_support_label,
    normalize_confidence_label,
    normalize_evidence_category_label,
    normalize_source_role_label,
    normalize_verdict_label,
)


class AssessmentRequestRecord(BaseModel):
    claim: str = ""
    source_url: Optional[str] = None
    category: str = "auto-detect"
    settings: Dict[str, Any] = Field(default_factory=dict)


class AssessmentVerdict(BaseModel):
    label: str = "Unverified"
    confidence: str = "Low"
    
    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: object) -> str:
        return normalize_verdict_label(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> str:
        return normalize_confidence_label(value)
    summary: str = ""
    key_caveat: str = ""
    evidence_strength_score: Optional[float] = None


class ClaimBreakdownItem(BaseModel):
    id: str
    text: str
    dimension: str = "factual_core"
    assessment: str = "Unverified"
    confidence: str = "Low"

    @field_validator("assessment", mode="before")
    @classmethod
    def normalize_assessment(cls, value: object) -> str:
        return normalize_verdict_label(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> str:
        return normalize_confidence_label(value)
    rationale: str = ""
    supporting_source_ids: List[str] = Field(default_factory=list)
    contradicting_source_ids: List[str] = Field(default_factory=list)


class EvidenceMap(BaseModel):
    supports_factual_core: List[str] = Field(default_factory=list)
    contradicts_factual_core: List[str] = Field(default_factory=list)
    supports_interpretation: List[str] = Field(default_factory=list)
    disputes_interpretation: List[str] = Field(default_factory=list)
    context_only: List[str] = Field(default_factory=list)
    weak_or_irrelevant: List[str] = Field(default_factory=list)


class AssessmentEvidenceSource(BaseModel):
    id: str
    title: str = "Untitled"
    url: str = ""
    domain: str = ""
    source_type: str = "contextual"
    stance: str = "irrelevant"
    evidence_category: str = "irrelevant"
    source_role: str = "context"
    narrative_cluster: str = ""

    @field_validator("stance", mode="before")
    @classmethod
    def normalize_stance(cls, value: object) -> str:
        return normalize_claim_support_label(value)

    @field_validator("evidence_category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> str:
        return normalize_evidence_category_label(value)

    @field_validator("source_role", mode="before")
    @classmethod
    def normalize_role(cls, value: object) -> str:
        return normalize_source_role_label(value)
    score: float = 0.0
    scoring_factors: Dict[str, float] = Field(default_factory=dict)
    summary: str = ""
    classification_reason: str = ""


class AssessmentResponse(BaseModel):
    schema_version: str = "assessment_response.v1"
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    build: str
    mode: str
    owner_id: Optional[str] = None
    request: AssessmentRequestRecord
    verdict: AssessmentVerdict
    claim_breakdown: List[ClaimBreakdownItem] = Field(default_factory=list)
    evidence_map: EvidenceMap = Field(default_factory=EvidenceMap)
    sources: List[AssessmentEvidenceSource] = Field(default_factory=list)
    reasoning: Dict[str, Any] = Field(default_factory=dict)
    debug: Optional[Dict[str, Any]] = None


def _source_id(index: int) -> str:
    return f"src_{index + 1}"


def _source_ids_by_stance(sources: List[Dict[str, Any]], stance: str) -> List[str]:
    normalized_stance = normalize_claim_support_label(stance)
    return [_source_id(i) for i, source in enumerate(sources) if normalize_claim_support_label(source.get("claim_support")) == normalized_stance]


def _source_ids_by_role(sources: List[Dict[str, Any]], roles: set[str]) -> List[str]:
    normalized_roles = {normalize_source_role_label(role) for role in roles}
    return [_source_id(i) for i, source in enumerate(sources) if normalize_source_role_label(source.get("source_role")) in normalized_roles]


def _source_ids_by_contradiction_signal(sources: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    contradiction_categories = {"credible_contradiction", "denial_or_rebuttal"}
    for i, source in enumerate(sources):
        stance = normalize_claim_support_label(source.get("claim_support"))
        role = normalize_source_role_label(source.get("source_role"))
        category = normalize_evidence_category_label(source.get("evidence_category"))
        if stance == "contradicts" or role == "contradiction" or category in contradiction_categories:
            ids.append(_source_id(i))
    return ids


def _source_ids_by_support_signal(sources: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    contradiction_ids = set(_source_ids_by_contradiction_signal(sources))
    for i, source in enumerate(sources):
        source_id = _source_id(i)
        if source_id in contradiction_ids:
            continue
        if normalize_claim_support_label(source.get("claim_support")) == "supports":
            ids.append(source_id)
    return ids


def _verdict_aligned_with_evidence(verdict: str, confidence: str, sources: List[Dict[str, Any]]) -> tuple[str, str, str]:
    """Last-mile guard so the public payload cannot contradict its own evidence map."""
    support_ids = _source_ids_by_support_signal(sources)
    contradiction_ids = _source_ids_by_contradiction_signal(sources)
    if not contradiction_ids:
        return verdict, confidence, ""

    supportive_verdicts = {"Supported", "Likely supported", "Partly supported"}
    if verdict not in supportive_verdicts:
        return verdict, confidence, ""

    if not support_ids:
        return (
            "False / contradicted",
            "Medium" if confidence == "High" else confidence,
            "Verdict adjusted because the reviewed evidence contains contradiction signals and no clear supporting source.",
        )
    if len(contradiction_ids) >= len(support_ids):
        return (
            "Weakly supported / likely incorrect",
            "Medium" if confidence == "High" else confidence,
            "Verdict adjusted because contradiction signals are at least as strong as supporting signals in the reviewed evidence.",
        )
    if verdict in {"Supported", "Likely supported"}:
        return (
            "Partly supported",
            "Medium" if confidence == "High" else confidence,
            "Verdict softened because the reviewed evidence includes material contradiction signals.",
        )
    return verdict, confidence, ""


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_score(source: Dict[str, Any]) -> float:
    factors = source.get("scoring_factors") if isinstance(source.get("scoring_factors"), dict) else {}
    return _float_or_none(source.get("weighted_score")) or _float_or_none(factors.get("weighted")) or 0.0


def _source_scoring_factors(source: Dict[str, Any]) -> Dict[str, float]:
    supplied = source.get("scoring_factors") if isinstance(source.get("scoring_factors"), dict) else {}
    factors: Dict[str, float] = {}
    for key, raw_key in (
        ("authority", "authority_score"),
        ("relevance", "relevance_score"),
        ("directness", "directness_score"),
        ("recency", "recency_score"),
        ("independence", "independence_score"),
        ("bias_risk", "bias_risk_score"),
    ):
        value = _float_or_none(supplied.get(key))
        if value is None:
            value = _float_or_none(source.get(raw_key))
        if value is not None:
            factors[key] = value
    weighted = _source_score(source)
    if weighted:
        factors["weighted"] = weighted
    return factors


def serialize_assessment_response(
    result: Dict[str, Any],
    *,
    claim: str,
    source_url: str = "",
    category: str = "auto-detect",
    mode: str,
    build: str,
    include_debug: bool = False,
    owner_id: str = "",
) -> AssessmentResponse:
    """Map the current pipeline/fast payload into the public API v1 shape."""
    sources = list(result.get("sources") or result.get("fast_sources") or [])
    source_models = [
        AssessmentEvidenceSource(
            id=_source_id(i),
            title=source.get("title") or "Untitled",
            url=source.get("url") or "",
            domain=source.get("domain") or "",
            source_type=source.get("source_type") or "contextual",
            stance=source.get("claim_support") or "irrelevant",
            evidence_category=source.get("evidence_category") or "irrelevant",
            source_role=source.get("source_role") or "context",
            score=_source_score(source),
            scoring_factors=_source_scoring_factors(source),
            narrative_cluster=source.get("narrative_cluster") or "",
            summary=source.get("summary") or source.get("snippet") or "",
            classification_reason=source.get("classification_reason") or source.get("evidence_category") or "",
        )
        for i, source in enumerate(sources)
    ]

    verdict_label = normalize_verdict_label(result.get("verified_verdict") or result.get("verdict") or "Unverified")
    confidence = normalize_confidence_label(result.get("verified_confidence") or result.get("confidence") or "Low")
    verdict_label, confidence, verdict_alignment_note = _verdict_aligned_with_evidence(verdict_label, confidence, sources)
    pendulum = result.get("pendulum") or {}
    evidence_score = pendulum.get("score") if isinstance(pendulum, dict) else None
    if evidence_score is None:
        evidence_score = result.get("pendulum_score")

    claim_analysis = result.get("claim_analysis") or {}
    raw_subclaims = claim_analysis.get("subclaims") or []
    if not raw_subclaims and result.get("subclaims"):
        raw_subclaims = [{"id": f"sc_{i+1}", "text": text} for i, text in enumerate(result.get("subclaims") or [])]
    claim_breakdown = [
        ClaimBreakdownItem(
            id=str(item.get("id") or f"sc_{i+1}"),
            text=item.get("text") or claim,
            dimension=item.get("claim_type") or "factual_core",
            assessment=verdict_label,
            confidence=confidence,
            rationale=(result.get("rule_engine") or {}).get("rationale", ""),
            supporting_source_ids=_source_ids_by_support_signal(sources),
            contradicting_source_ids=_source_ids_by_contradiction_signal(sources),
        )
        for i, item in enumerate(raw_subclaims)
    ]

    evidence_map = EvidenceMap(
        supports_factual_core=_source_ids_by_support_signal(sources),
        contradicts_factual_core=_source_ids_by_contradiction_signal(sources),
        supports_interpretation=_source_ids_by_role(sources, {"evidence"}),
        disputes_interpretation=_source_ids_by_stance(sources, "mixed"),
        context_only=_source_ids_by_role(sources, {"context"}),
        weak_or_irrelevant=_source_ids_by_stance(sources, "irrelevant"),
    )
    consensus_summary = result.get("consensus_summary")
    evidence_assessment = result.get("evidence_assessment")
    if verdict_alignment_note:
        consensus_summary = f"{verdict_alignment_note} {consensus_summary or ''}".strip()
        if not isinstance(evidence_assessment, dict):
            evidence_assessment = {}
        gaps = list(evidence_assessment.get("evidence_gaps") or [])
        if verdict_alignment_note not in gaps:
            gaps.append(verdict_alignment_note)
        evidence_assessment["evidence_gaps"] = gaps

    return AssessmentResponse(
        build=build,
        mode=mode,
        owner_id=owner_id or None,
        request=AssessmentRequestRecord(
            claim=claim,
            source_url=source_url or None,
            category=category,
            settings={
                "retrieval_provider": "tavily" if mode == "deep" else None,
                "legacy_endpoint": "/claims/check",
                "claim_semantics": result.get("claim_semantics") or {},
                "output_style": result.get("output_style") or "standard",
            },
        ),
        verdict=AssessmentVerdict(
            label=verdict_label,
            confidence=confidence,
            summary=consensus_summary or result.get("tldr") or result.get("summary") or "",
            key_caveat=verdict_alignment_note or result.get("one_line_correction") or result.get("evidence_access_note") or "",
            evidence_strength_score=evidence_score,
        ),
        claim_breakdown=claim_breakdown,
        evidence_map=evidence_map,
        sources=source_models,
        reasoning={
            "consensus_strength": result.get("consensus_strength"),
            "consensus_summary": consensus_summary,
            "reasoning_summary": result.get("reasoning_summary"),
            "evidence_assessment": evidence_assessment,
            "rule_engine": result.get("rule_engine"),
            "amplification_warning": result.get("amplification_warning"),
            "claim_semantics": result.get("claim_semantics"),
            "humour_summary": result.get("humour_summary"),
            "humour_safety_note": result.get("humour_safety_note"),
            "output_style": result.get("output_style") or "standard",
        },
        debug=result.get("debug_trace") if include_debug else None,
    )
