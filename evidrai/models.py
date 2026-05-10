from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

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
