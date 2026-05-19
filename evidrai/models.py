from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

    def to_trace_packet(self) -> Dict[str, Any]:
        return {
            **self.to_packet(),
            "scoring_factors": {
                "authority": self.authority_score,
                "relevance": self.relevance_score,
                "directness": self.directness_score,
                "recency": self.recency_score,
                "bias_risk": self.bias_risk_score,
                "weighted": self.weighted_score,
            },
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

    def to_trace_packet(self) -> Dict[str, Any]:
        return {
            "queries": list(self.queries),
            "sources": [source.to_trace_packet() for source in self.sources],
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

    def to_trace_packet(self) -> Dict[str, Any]:
        return {
            "schema_version": "pipeline_trace.v1",
            "normalized_claim": self.claim,
            "claim_analysis": self.claim_analysis.to_packet(),
            "queries": list(self.retrieval.queries),
            "retrieval": self.retrieval.to_trace_packet(),
            "source_classifications": [
                {
                    "title": source.title,
                    "url": source.url,
                    "domain": source.domain,
                    "source_type": source.source_type,
                    "claim_support": source.claim_support,
                    "evidence_category": source.evidence_category,
                    "source_role": source.source_role,
                    "narrative_cluster": source.narrative_cluster,
                }
                for source in self.retrieval.sources
            ],
            "scoring": {
                "provisional_verdict": self.provisional_verdict,
                "provisional_confidence": self.provisional_confidence,
                "pendulum": self.pendulum.to_dict(),
                "source_scores": [source.to_trace_packet() for source in self.retrieval.sources],
            },
            "rule_engine": self.rule_engine.to_dict(),
            "downgrade_rationale": self.rule_engine.rationale,
        }

    def to_payload(self) -> Dict[str, Any]:
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
                "debug_trace": self.to_trace_packet(),
            }
        )
        return payload

    def to_model(self) -> "PipelineResultModel":
        return PipelineResultModel.model_validate(self.to_payload())

    def to_dict(self) -> Dict[str, Any]:
        return self.to_model().model_dump(mode="json")


class SubClaimPacketModel(BaseModel):
    """Stable serialized boundary for a parsed subclaim."""

    id: str = "sc_1"
    text: str
    claim_type: str = "other"
    entities: List[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    time_sensitivity: str = "medium"
    verification_requirements: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)


class ClaimAnalysisPacketModel(BaseModel):
    """Stable serialized boundary for claim extraction output."""

    normalized_claim: str = ""
    subclaims: List[SubClaimPacketModel] = Field(default_factory=list)
    overall_notes: List[str] = Field(default_factory=list)


class SourcePacketModel(BaseModel):
    """Public source packet used by UI/API/debug exports.

    Raw fetched page content is intentionally excluded from this boundary.
    """

    title: str = "Untitled"
    url: str = ""
    domain: str = ""
    source_type: str = "contextual"
    published_date: Optional[str] = None
    summary: str = ""
    claim_support: str = "irrelevant"
    evidence_category: str = "irrelevant"
    source_role: str = "context"
    narrative_cluster: str = ""
    weighted_score: float = 0.0


class RetrievalPacketModel(BaseModel):
    """Stable serialized boundary for retrieval output."""

    queries: List[str] = Field(default_factory=list)
    sources: List[SourcePacketModel] = Field(default_factory=list)


class EvidencePacketModel(BaseModel):
    claim: str
    subclaims: List[str] = Field(default_factory=list)
    sources: List[SourcePacketModel] = Field(default_factory=list)


class PendulumPacketModel(BaseModel):
    band: str = "Mixed / uncertain"
    score: float = 0.0
    explanation: str = ""


class RuleEnginePacketModel(BaseModel):
    verdict: str = "Unverified"
    confidence: str = "Low"
    rationale: str = ""
    stats: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: List[str] = Field(default_factory=list)


class SourceTracePacketModel(SourcePacketModel):
    scoring_factors: Dict[str, float] = Field(default_factory=dict)


class RetrievalTracePacketModel(BaseModel):
    queries: List[str] = Field(default_factory=list)
    sources: List[SourceTracePacketModel] = Field(default_factory=list)


class PipelineTraceModel(BaseModel):
    schema_version: str = "pipeline_trace.v1"
    normalized_claim: str = ""
    claim_analysis: ClaimAnalysisPacketModel
    queries: List[str] = Field(default_factory=list)
    retrieval: RetrievalTracePacketModel
    source_classifications: List[Dict[str, Any]] = Field(default_factory=list)
    scoring: Dict[str, Any] = Field(default_factory=dict)
    rule_engine: Dict[str, Any] = Field(default_factory=dict)
    downgrade_rationale: str = ""


class PipelineResultModel(BaseModel):
    """Versioned deep-pipeline result boundary.

    `extra="allow"` keeps the current UI-compatible fields while the project
    migrates from loose dictionaries to fully typed response contracts.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: str = "pipeline_result.v1"
    claim: str
    claim_analysis: ClaimAnalysisPacketModel
    subclaims: List[str] = Field(default_factory=list)
    retrieval: RetrievalPacketModel
    sources: List[SourcePacketModel] = Field(default_factory=list)
    queries: List[str] = Field(default_factory=list)
    evidence_packet: EvidencePacketModel
    pendulum: PendulumPacketModel
    risk_flags: List[str] = Field(default_factory=list)
    rule_engine: RuleEnginePacketModel
    provisional_verdict: str = "unverifiable"
    provisional_confidence: int = 0
    debug_trace: PipelineTraceModel


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
    humour_summary: str = ""
    humour_safety_note: str = ""


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


class SpeechAuditClaimModel(BaseModel):
    id: str = "claim_1"
    quote: str
    normalized_claim: str
    timestamp: str = ""
    speaker: str = ""
    topic: str = "general"
    claim_type: str = "factual"
    checkability: str = "checkable"
    priority: str = "medium"
    why_it_matters: str = ""
    verification_query: str = ""


class SpeechAuditExtractionModel(BaseModel):
    title: str = "Speech / video audit"
    speaker: str = ""
    source_url: str = ""
    summary: str = ""
    claims: List[SpeechAuditClaimModel] = Field(default_factory=list)
    skipped_rhetoric: List[str] = Field(default_factory=list)
    extraction_notes: List[str] = Field(default_factory=list)


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
