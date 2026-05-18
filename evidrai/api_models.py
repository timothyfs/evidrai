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
            score=float(source.get("weighted_score") or 0.0),
            scoring_factors={
                "authority": float(source.get("authority_score") or 0.0),
                "relevance": float(source.get("relevance_score") or 0.0),
                "directness": float(source.get("directness_score") or 0.0),
                "recency": float(source.get("recency_score") or 0.0),
                "bias_risk": float(source.get("bias_risk_score") or 0.0),
                "weighted": float(source.get("weighted_score") or 0.0),
            },
            narrative_cluster=source.get("narrative_cluster") or "",
            summary=source.get("summary") or source.get("snippet") or "",
            classification_reason=source.get("classification_reason") or source.get("evidence_category") or "",
        )
        for i, source in enumerate(sources)
    ]

    verdict_label = normalize_verdict_label(result.get("verified_verdict") or result.get("verdict") or "Unverified")
    confidence = normalize_confidence_label(result.get("verified_confidence") or result.get("confidence") or "Low")
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
            supporting_source_ids=_source_ids_by_stance(sources, "supports"),
            contradicting_source_ids=_source_ids_by_stance(sources, "contradicts"),
        )
        for i, item in enumerate(raw_subclaims)
    ]

    evidence_map = EvidenceMap(
        supports_factual_core=_source_ids_by_stance(sources, "supports"),
        contradicts_factual_core=_source_ids_by_stance(sources, "contradicts"),
        supports_interpretation=_source_ids_by_role(sources, {"evidence"}),
        disputes_interpretation=_source_ids_by_stance(sources, "mixed"),
        context_only=_source_ids_by_role(sources, {"context"}),
        weak_or_irrelevant=_source_ids_by_stance(sources, "irrelevant"),
    )

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
            },
        ),
        verdict=AssessmentVerdict(
            label=verdict_label,
            confidence=confidence,
            summary=result.get("tldr") or result.get("summary") or result.get("consensus_summary") or "",
            key_caveat=result.get("one_line_correction") or result.get("evidence_access_note") or "",
            evidence_strength_score=evidence_score,
        ),
        claim_breakdown=claim_breakdown,
        evidence_map=evidence_map,
        sources=source_models,
        reasoning={
            "consensus_strength": result.get("consensus_strength"),
            "consensus_summary": result.get("consensus_summary"),
            "reasoning_summary": result.get("reasoning_summary"),
            "evidence_assessment": result.get("evidence_assessment"),
            "rule_engine": result.get("rule_engine"),
            "amplification_warning": result.get("amplification_warning"),
        },
        debug=result.get("debug_trace") if include_debug else None,
    )
