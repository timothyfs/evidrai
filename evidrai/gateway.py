from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidrai.api_models import AssessmentResponse, ClaimBreakdownItem
from evidrai.gateway_models import (
    GatewayClaimDecision,
    GatewayDecision,
    GatewayDecisionResponse,
    GatewayVerifyRequest,
    TriggeredGatewayRule,
)


DECISION_ORDER: dict[GatewayDecision, int] = {"pass": 0, "review": 1, "block": 2}

VERDICT_ORDER = {
    "False / contradicted": 0,
    "Not supported by credible evidence": 1,
    "Weakly supported / likely incorrect": 1,
    "Unverified": 2,
    "Reported but unconfirmed": 2,
    "Contested": 2,
    "Misleading framing": 3,
    "Partly supported": 3,
    "Likely supported": 4,
    "Supported": 5,
}

MATERIALITY_TERMS = {
    "finance",
    "financial",
    "investment",
    "market",
    "valuation",
    "payment",
    "approve",
    "regulatory",
    "legal",
    "compliance",
    "risk",
    "breach",
    "cyber",
    "crash",
    "fraud",
}


@dataclass(frozen=True)
class GatewayLevelPolicy:
    min_verdict: str = "Unverified"
    min_confidence_score: int = 35
    min_evidence_strength_score: float = 0.0
    unverified_material_claim: GatewayDecision = "pass"
    unsupported_material_claim: GatewayDecision = "review"
    contradicted_material_claim: GatewayDecision = "block"
    misleading_material_claim: GatewayDecision = "review"


@dataclass(frozen=True)
class GatewayPolicy:
    policy_id: str
    version: int = 1
    description: str = ""
    rules: dict[str, GatewayLevelPolicy] = field(default_factory=dict)

    def level(self, consequence_level: str) -> GatewayLevelPolicy:
        return self.rules.get(consequence_level) or self.rules.get("medium") or GatewayLevelPolicy()


def default_gateway_policy() -> GatewayPolicy:
    return GatewayPolicy(
        policy_id="default_v1",
        version=1,
        description="Default gateway policy for general AI-output checks.",
        rules={
            "low": GatewayLevelPolicy(
                min_verdict="Unverified",
                min_confidence_score=35,
                min_evidence_strength_score=0,
                unverified_material_claim="pass",
                unsupported_material_claim="review",
            ),
            "medium": GatewayLevelPolicy(
                min_verdict="Partly supported",
                min_confidence_score=50,
                min_evidence_strength_score=4,
                unverified_material_claim="review",
                unsupported_material_claim="review",
            ),
            "high": GatewayLevelPolicy(
                min_verdict="Likely supported",
                min_confidence_score=70,
                min_evidence_strength_score=7,
                unverified_material_claim="review",
                unsupported_material_claim="block",
            ),
        },
    )


def finance_gateway_policy() -> GatewayPolicy:
    base = default_gateway_policy()
    return GatewayPolicy(
        policy_id="finance_default_v1",
        version=1,
        description="Default gateway policy for finance and market-sensitive workflows.",
        rules={
            **base.rules,
            "high": GatewayLevelPolicy(
                min_verdict="Likely supported",
                min_confidence_score=72,
                min_evidence_strength_score=7,
                unverified_material_claim="review",
                unsupported_material_claim="block",
                contradicted_material_claim="block",
                misleading_material_claim="review",
            ),
        },
    )


def get_gateway_policy(policy_id: str, domain: str = "") -> tuple[GatewayPolicy, bool]:
    requested = (policy_id or "").strip()
    policies = {
        "default_v1": default_gateway_policy(),
        "finance_default_v1": finance_gateway_policy(),
    }
    if requested in policies:
        return policies[requested], False
    if (domain or "").strip().lower() == "finance":
        return policies["finance_default_v1"], True
    return policies["default_v1"], True


def gateway_audit_path() -> Path:
    return Path(os.getenv("EVIDRAI_GATEWAY_AUDIT_STORE", ".evidrai_gateway/gateway_audit.jsonl"))


def save_gateway_audit_record(record: dict[str, Any], path: Path | None = None) -> None:
    target = path or gateway_audit_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worst(decisions: list[GatewayDecision]) -> GatewayDecision:
    if not decisions:
        return "pass"
    return max(decisions, key=lambda item: DECISION_ORDER[item])


def _verdict_rank(verdict: str) -> int:
    return VERDICT_ORDER.get(verdict or "Unverified", 2)


def _confidence_score(assessment: AssessmentResponse) -> int:
    try:
        return int(assessment.verdict.confidence_score)
    except Exception:
        return {"Low": 35, "Medium": 58, "High": 82}.get(assessment.verdict.confidence, 35)


def _evidence_strength(assessment: AssessmentResponse) -> float:
    try:
        return float(assessment.verdict.evidence_strength_score or 0)
    except Exception:
        return 0.0


def _is_material_claim(text: str, domain: str, action_type: str) -> bool:
    haystack = f"{text} {domain} {action_type}".lower()
    if re.search(r"[£$€]\s?\d|\b\d+(?:\.\d+)?\s?(%|percent|million|billion|trillion|m|bn)\b", haystack):
        return True
    if re.search(r"\b[A-Z][A-Za-z0-9&.-]{2,}\b", text or ""):
        return True
    if any(term in haystack for term in MATERIALITY_TERMS):
        return True
    if any(term in haystack for term in ("caused", "causes", "because", "led to", "resulted in", "warned", "said")):
        return True
    return True


def _claim_items(assessment: AssessmentResponse) -> list[ClaimBreakdownItem]:
    if assessment.claim_breakdown:
        return assessment.claim_breakdown
    return [
        ClaimBreakdownItem(
            id="sc_1",
            text=assessment.request.claim,
            assessment=assessment.verdict.label,
            confidence=assessment.verdict.confidence,
            rationale=assessment.verdict.summary,
        )
    ]


def _rule(rule_id: str, severity: GatewayDecision, message: str, claim_id: str = "") -> TriggeredGatewayRule:
    return TriggeredGatewayRule(rule_id=rule_id, severity=severity, message=message, claim_id=claim_id)


def _decision_for_claim(
    claim: ClaimBreakdownItem,
    *,
    assessment: AssessmentResponse,
    request: GatewayVerifyRequest,
    policy: GatewayPolicy,
) -> tuple[GatewayClaimDecision, list[TriggeredGatewayRule]]:
    level_policy = policy.level(request.consequence_level)
    verdict = claim.assessment or assessment.verdict.label
    confidence = claim.confidence or assessment.verdict.confidence
    confidence_score = _confidence_score(assessment)
    evidence_strength = _evidence_strength(assessment)
    materiality = "material" if _is_material_claim(claim.text, request.domain, request.proposed_action.type) else "background"
    action_relevance = "review_relevant" if materiality == "material" else "low"
    rules: list[TriggeredGatewayRule] = []
    decision: GatewayDecision = "pass"
    reason = "Claim satisfies the configured gateway policy."

    if verdict == "False / contradicted":
        decision = level_policy.contradicted_material_claim
        reason = "Material claim is contradicted by the reviewed evidence."
        rules.append(_rule("material_claim_contradicted", decision, reason, claim.id))
    elif verdict in {"Not supported by credible evidence", "Weakly supported / likely incorrect"}:
        decision = level_policy.unsupported_material_claim
        reason = "Material claim is not sufficiently supported by credible evidence."
        rules.append(_rule("material_claim_unsupported", decision, reason, claim.id))
    elif verdict in {"Unverified", "Reported but unconfirmed", "Contested"}:
        decision = level_policy.unverified_material_claim
        reason = "Material claim is not verified enough for the configured consequence level."
        if decision != "pass":
            rules.append(_rule("material_claim_unverified", decision, reason, claim.id))
    elif verdict in {"Misleading framing", "Partly supported"}:
        decision = level_policy.misleading_material_claim
        reason = "Material claim is only partially supported or appears overstated."
        rules.append(_rule("material_claim_overstated", decision, reason, claim.id))

    if materiality == "material" and _verdict_rank(verdict) < _verdict_rank(level_policy.min_verdict):
        decision = _worst([decision, "review"])
        message = f"Verdict {verdict} is below the required threshold {level_policy.min_verdict}."
        reason = message
        rules.append(_rule("minimum_verdict_not_met", "review", message, claim.id))

    if materiality == "material" and confidence_score < level_policy.min_confidence_score:
        decision = _worst([decision, "review"])
        message = f"Confidence score {confidence_score} is below the required threshold {level_policy.min_confidence_score}."
        reason = message
        rules.append(_rule("minimum_confidence_not_met", "review", message, claim.id))

    if materiality == "material" and evidence_strength < level_policy.min_evidence_strength_score:
        decision = _worst([decision, "review"])
        message = f"Evidence strength {evidence_strength:g} is below the required threshold {level_policy.min_evidence_strength_score:g}."
        reason = message
        rules.append(_rule("minimum_evidence_strength_not_met", "review", message, claim.id))

    return (
        GatewayClaimDecision(
            claim_id=claim.id,
            text=claim.text,
            assessment=verdict,
            confidence=confidence,
            confidence_score=confidence_score,
            evidence_strength_score=evidence_strength,
            materiality=materiality,
            action_relevance=action_relevance,
            decision=decision,
            reason=reason,
            supporting_source_ids=claim.supporting_source_ids,
            contradicting_source_ids=claim.contradicting_source_ids,
        ),
        rules,
    )


def build_gateway_decision(
    *,
    request: GatewayVerifyRequest,
    assessment: AssessmentResponse,
    owner_id: str = "",
    build: str = "",
) -> GatewayDecisionResponse:
    policy, used_fallback_policy = get_gateway_policy(request.policy_id, request.domain)
    claim_decisions: list[GatewayClaimDecision] = []
    triggered_rules: list[TriggeredGatewayRule] = []

    if used_fallback_policy:
        triggered_rules.append(
            _rule(
                "policy_fallback_applied",
                "review",
                f"Requested policy {request.policy_id or '(empty)'} was not found; applied {policy.policy_id}.",
            )
        )

    for claim in _claim_items(assessment):
        claim_decision, claim_rules = _decision_for_claim(claim, assessment=assessment, request=request, policy=policy)
        claim_decisions.append(claim_decision)
        triggered_rules.extend(claim_rules)

    decision = _worst([claim.decision for claim in claim_decisions] + [rule.severity for rule in triggered_rules])
    if decision == "block":
        next_step = "stop_downstream_action"
        reason = "One or more material claims failed a blocking gateway policy rule."
    elif decision == "review":
        next_step = "route_to_human_review"
        reason = "One or more material claims require review before the proposed action proceeds."
    else:
        next_step = "proceed"
        reason = "All material claims satisfy the configured gateway policy."

    response = GatewayDecisionResponse(
        decision=decision,
        decision_reason=reason,
        recommended_next_step=next_step,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        workflow_id=request.workflow_id,
        request_id=request.request_id,
        assessment_id=assessment.assessment_id,
        triggered_rules=triggered_rules,
        claims=claim_decisions,
        blocking_claims=[claim.claim_id for claim in claim_decisions if claim.decision == "block"],
        review_claims=[claim.claim_id for claim in claim_decisions if claim.decision == "review"],
        allowed_actions=[request.proposed_action.type] if decision == "pass" and request.proposed_action.type else [],
        assessment=assessment if request.include_assessment else None,
    )

    try:
        save_gateway_audit_record(
            {
                "schema_version": "gateway_audit.v1",
                "created_at": _utc_now_iso(),
                "gateway_id": response.gateway_id,
                "owner_id": owner_id,
                "build": build,
                "request": request.model_dump(mode="json", exclude={"bot_token"}),
                "response": response.model_dump(mode="json", exclude={"assessment"}),
                "assessment_id": assessment.assessment_id,
                "policy_id": response.policy_id,
                "policy_version": response.policy_version,
                "decision": response.decision,
                "triggered_rules": [rule.model_dump(mode="json") for rule in triggered_rules],
            }
        )
    except Exception:
        pass
    return response
