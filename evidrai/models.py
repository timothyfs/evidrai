from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class SubClaim:
    id: str
    text: str
    claim_type: str
    entities: List[str] = field(default_factory=list)
    jurisdiction: Optional[str] = None
    time_sensitivity: str = "medium"
    verification_requirements: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)


@dataclass
class EvidenceSource:
    title: str
    url: str
    domain: str
    source_type: str
    snippet: str = ""
    content: str = ""
    published_date: Optional[str] = None
    authority_score: float = 0.0
    relevance_score: float = 0.0
    directness_score: float = 0.0
    recency_score: float = 0.0
    bias_risk_score: float = 2.5
    weighted_score: float = 0.0
    claim_support: str = "irrelevant"
    evidence_category: str = "irrelevant"
    source_role: str = "context"
    narrative_cluster: str = ""

    def to_packet(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "source_type": self.source_type,
            "published_date": self.published_date,
            "summary": self.snippet,
            "claim_support": self.claim_support,
            "evidence_category": self.evidence_category,
            "source_role": self.source_role,
            "narrative_cluster": self.narrative_cluster,
            "weighted_score": self.weighted_score,
        }


@dataclass
class ClaimAnalysisResult:
    normalized_claim: str
    subclaims: List[SubClaim] = field(default_factory=list)
    overall_notes: List[str] = field(default_factory=list)

    @property
    def subclaim_texts(self) -> List[str]:
        return [sub.text for sub in self.subclaims]

    def to_packet(self) -> Dict[str, Any]:
        return {
            "normalized_claim": self.normalized_claim,
            "subclaims": [asdict(sub) for sub in self.subclaims],
            "overall_notes": list(self.overall_notes),
        }


@dataclass
class RetrievalResult:
    queries: List[str] = field(default_factory=list)
    sources: List[EvidenceSource] = field(default_factory=list)

    def to_packet(self) -> Dict[str, Any]:
        return {
            "queries": list(self.queries),
            "sources": [source.to_packet() for source in self.sources],
        }


@dataclass
class EvidencePacket:
    claim: str
    subclaims: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "subclaims": list(self.subclaims),
            "sources": [dict(source) for source in self.sources],
        }


@dataclass
class PendulumResult:
    band: str
    score: float = 0.0
    explanation: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PendulumResult":
        return cls(
            band=payload.get("band", "Mixed / uncertain"),
            score=float(payload.get("score") or 0.0),
            explanation=payload.get("explanation", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"band": self.band, "score": self.score, "explanation": self.explanation}


@dataclass
class RuleEngineResult:
    verdict: str
    confidence: str
    rationale: str
    stats: Dict[str, Any] = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)
    soft_claim: bool = False
    serious_allegation: bool = False

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuleEngineResult":
        return cls(
            verdict=payload.get("verdict", "Unverified"),
            confidence=payload.get("confidence", "Low"),
            rationale=payload.get("rationale", ""),
            stats=dict(payload.get("stats", {}) or {}),
            risk_flags=list(payload.get("risk_flags", []) or []),
            soft_claim=bool(payload.get("soft_claim", False)),
            serious_allegation=bool(payload.get("serious_allegation", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "stats": self.stats,
            "risk_flags": list(self.risk_flags),
            "soft_claim": self.soft_claim,
            "serious_allegation": self.serious_allegation,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "stats": self.stats,
            "risk_flags": list(self.risk_flags),
        }


@dataclass
class VerificationResult:
    claim: str
    claim_analysis: ClaimAnalysisResult
    retrieval: RetrievalResult
    evidence_packet: EvidencePacket
    pendulum: PendulumResult
    rule_engine: RuleEngineResult
    reasoning: Dict[str, Any] = field(default_factory=dict)
    provisional_verdict: str = "unverifiable"
    provisional_confidence: int = 0
    schema_version: str = "pipeline_result.v1"

    def to_dict(self) -> Dict[str, Any]:
        payload = dict(self.reasoning)
        payload.update(
            {
                "schema_version": self.schema_version,
                "claim": self.claim,
                "claim_analysis": self.claim_analysis.to_packet(),
                "subclaims": self.evidence_packet.subclaims,
                "retrieval": self.retrieval.to_packet(),
                "sources": self.evidence_packet.sources,
                "queries": self.retrieval.queries,
                "evidence_packet": self.evidence_packet.to_dict(),
                "pendulum": self.pendulum.to_dict(),
                "risk_flags": sorted(self.rule_engine.risk_flags),
                "rule_engine": self.rule_engine.to_public_dict(),
                "provisional_verdict": self.provisional_verdict,
                "provisional_confidence": self.provisional_confidence,
            }
        )
        return payload


class EvidenceTypeModel(BaseModel):
    type: str = "Unknown"
    weight: str = "Low"
    impact: str = "neutral"
    note: str = ""


class LegacyAssessmentModel(BaseModel):
    verdict: str = "Unverified"
    confidence: str = "Low"
    tldr: str = ""
    summary: str = ""
    why_convincing: str = ""
    interpretation_note: str = ""
    interpretation_confidence: str = "Low"
    explicit_vs_inferred: Dict[str, str] = Field(default_factory=dict)
    evidence_access_note: str = ""
    evidence_types: List[EvidenceTypeModel] = Field(default_factory=list)
    what_would_change_verdict: str = ""
    user_takeaway: str = ""
    caution_flags: List[str] = Field(default_factory=list)


class ClaimAnalysisItemModel(BaseModel):
    id: str = "sc_1"
    text: str
    claim_type: str = "other"
    entities: List[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    time_sensitivity: str = "medium"
    verification_requirements: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)


class ClaimAnalysisModel(BaseModel):
    normalized_claim: str = ""
    subclaims: List[ClaimAnalysisItemModel] = Field(default_factory=list)
    overall_notes: List[str] = Field(default_factory=list)


class SourceSummaryModel(BaseModel):
    summary: str = ""
    claim_support: str = "irrelevant"
    evidence_category: str = "irrelevant"
    source_role: str = "context"
    narrative_cluster: str = ""
    key_points: List[str] = Field(default_factory=list)
    quoted_or_precise_points: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)


class ReasoningSummaryModel(BaseModel):
    supported_points: List[str] = Field(default_factory=list)
    contradicted_points: List[str] = Field(default_factory=list)
    uncertain_points: List[str] = Field(default_factory=list)


class EvidenceAssessmentModel(BaseModel):
    primary_sources_used: List[str] = Field(default_factory=list)
    secondary_sources_used: List[str] = Field(default_factory=list)
    source_conflicts: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    rumor_drivers: List[str] = Field(default_factory=list)
    actual_evidence: List[str] = Field(default_factory=list)


class VerifiedAssessmentModel(BaseModel):
    verified_verdict: str = "Unverified"
    verified_confidence: str = "Low"
    consensus_strength: str = "No clear consensus"
    consensus_summary: str = ""
    pendulum_band: str = ""
    pendulum_explanation: str = ""
    tldr: str = ""
    one_line_correction: str = ""
    reasoning_summary: ReasoningSummaryModel = Field(default_factory=ReasoningSummaryModel)
    evidence_assessment: EvidenceAssessmentModel = Field(default_factory=EvidenceAssessmentModel)
    misinformation_patterns: List[str] = Field(default_factory=list)
    why_this_claim_spreads: List[str] = Field(default_factory=list)
    final_explanation: str = ""
