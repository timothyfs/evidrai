from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from evidrai.api_models import AssessmentResponse


GatewayDecision = Literal["pass", "review", "block"]
GatewayConsequenceLevel = Literal["low", "medium", "high"]


class ProposedAction(BaseModel):
    type: str = Field(default="unspecified", max_length=120)
    description: str = Field(default="", max_length=1000)


class GatewayVerifyRequest(BaseModel):
    workflow_id: str = Field(default="", max_length=160)
    request_id: str = Field(default="", max_length=160)
    ai_output: str = Field(default="", max_length=20000)
    proposed_action: ProposedAction = Field(default_factory=ProposedAction)
    domain: str = Field(default="general", max_length=80)
    consequence_level: GatewayConsequenceLevel = "medium"
    policy_id: str = Field(default="default_v1", max_length=120)
    cited_sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    include_assessment: bool = False
    include_debug: bool = False
    bot_token: str = ""

    @field_validator("ai_output")
    @classmethod
    def require_ai_output(cls, value: str) -> str:
        clean = (value or "").strip()
        if not clean:
            raise ValueError("ai_output is required")
        return clean


class TriggeredGatewayRule(BaseModel):
    rule_id: str
    severity: GatewayDecision
    message: str
    claim_id: str = ""


class GatewayClaimDecision(BaseModel):
    claim_id: str
    text: str
    assessment: str
    confidence: str
    confidence_score: int = 0
    evidence_strength_score: Optional[float] = None
    materiality: str = "material"
    action_relevance: str = "review_relevant"
    decision: GatewayDecision
    reason: str = ""
    supporting_source_ids: list[str] = Field(default_factory=list)
    contradicting_source_ids: list[str] = Field(default_factory=list)


class GatewayDecisionResponse(BaseModel):
    schema_version: str = "gateway_decision.v1"
    gateway_id: str = Field(default_factory=lambda: f"gw_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision: GatewayDecision
    decision_reason: str
    recommended_next_step: str
    policy_id: str
    policy_version: int
    workflow_id: str = ""
    request_id: str = ""
    assessment_id: str
    triggered_rules: list[TriggeredGatewayRule] = Field(default_factory=list)
    claims: list[GatewayClaimDecision] = Field(default_factory=list)
    blocking_claims: list[str] = Field(default_factory=list)
    review_claims: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    assessment: Optional[AssessmentResponse] = None

