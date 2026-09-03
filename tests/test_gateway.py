import json

from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app
from evidrai.api_keys import ApiKeyRecord
from evidrai.api_models import AssessmentRequestRecord, AssessmentResponse, AssessmentVerdict, ClaimBreakdownItem
from evidrai.entitlements import UserProfile
from evidrai.gateway import build_gateway_decision
from evidrai.gateway_models import GatewayVerifyRequest, ProposedAction


client = TestClient(app)


def _assessment(verdict: str, confidence: str = "High", confidence_score: int = 82, evidence_strength_score: float = 8.0) -> AssessmentResponse:
    return AssessmentResponse(
        build="test-build",
        mode="deep",
        request=AssessmentRequestRecord(claim="Paris is the capital of France.", category="general"),
        verdict=AssessmentVerdict(
            label=verdict,
            confidence=confidence,
            confidence_score=confidence_score,
            summary="Test assessment.",
            evidence_strength_score=evidence_strength_score,
        ),
        claim_breakdown=[
            ClaimBreakdownItem(
                id="sc_1",
                text="Paris is the capital of France.",
                assessment=verdict,
                confidence=confidence,
                supporting_source_ids=["src_1"] if verdict in {"Supported", "Likely supported"} else [],
                contradicting_source_ids=["src_2"] if verdict == "False / contradicted" else [],
            )
        ],
    )


def _gateway_request(**overrides) -> GatewayVerifyRequest:
    payload = {
        "workflow_id": "finance-briefing",
        "request_id": "req_1",
        "ai_output": "Paris is the capital of France.",
        "proposed_action": ProposedAction(type="publish_briefing", description="Publish a briefing."),
        "domain": "finance",
        "consequence_level": "high",
        "policy_id": "finance_default_v1",
    }
    payload.update(overrides)
    return GatewayVerifyRequest.model_validate(payload)


def test_gateway_supported_high_confidence_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRAI_GATEWAY_AUDIT_STORE", str(tmp_path / "gateway_audit.jsonl"))

    response = build_gateway_decision(request=_gateway_request(), assessment=_assessment("Supported"), owner_id="owner", build="test")

    assert response.decision == "pass"
    assert response.recommended_next_step == "proceed"
    assert response.allowed_actions == ["publish_briefing"]
    assert response.blocking_claims == []
    assert response.review_claims == []


def test_gateway_unverified_high_consequence_reviews(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRAI_GATEWAY_AUDIT_STORE", str(tmp_path / "gateway_audit.jsonl"))

    response = build_gateway_decision(
        request=_gateway_request(),
        assessment=_assessment("Unverified", confidence="Low", confidence_score=35, evidence_strength_score=0),
        owner_id="owner",
        build="test",
    )

    assert response.decision == "review"
    assert response.review_claims == ["sc_1"]
    assert any(rule.rule_id == "material_claim_unverified" for rule in response.triggered_rules)


def test_gateway_contradicted_material_claim_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRAI_GATEWAY_AUDIT_STORE", str(tmp_path / "gateway_audit.jsonl"))

    response = build_gateway_decision(
        request=_gateway_request(),
        assessment=_assessment("False / contradicted", confidence="High", confidence_score=88, evidence_strength_score=8),
        owner_id="owner",
        build="test",
    )

    assert response.decision == "block"
    assert response.blocking_claims == ["sc_1"]
    assert any(rule.rule_id == "material_claim_contradicted" for rule in response.triggered_rules)


def test_gateway_unknown_policy_falls_back_safely(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRAI_GATEWAY_AUDIT_STORE", str(tmp_path / "gateway_audit.jsonl"))

    response = build_gateway_decision(
        request=_gateway_request(policy_id="missing_policy_v1"),
        assessment=_assessment("Supported"),
        owner_id="owner",
        build="test",
    )

    assert response.decision == "review"
    assert response.policy_id == "finance_default_v1"
    assert any(rule.rule_id == "policy_fallback_applied" for rule in response.triggered_rules)


def test_gateway_persists_audit_record(tmp_path, monkeypatch):
    audit_path = tmp_path / "gateway_audit.jsonl"
    monkeypatch.setenv("EVIDRAI_GATEWAY_AUDIT_STORE", str(audit_path))

    response = build_gateway_decision(request=_gateway_request(), assessment=_assessment("Supported"), owner_id="owner", build="test")

    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["schema_version"] == "gateway_audit.v1"
    assert rows[0]["gateway_id"] == response.gateway_id
    assert rows[0]["assessment_id"] == response.assessment_id
    assert rows[0]["decision"] == "pass"
    assert "bot_token" not in rows[0]["request"]


def _researcher_profile(owner_id: str = "contract-user") -> UserProfile:
    return UserProfile(
        owner_id=owner_id,
        email="contract@example.com",
        tier="researcher",
        terms_version=api_main.CURRENT_TERMS_VERSION,
        privacy_version=api_main.CURRENT_PRIVACY_VERSION,
        terms_accepted_at="2026-06-01T00:00:00+00:00",
        privacy_acknowledged_at="2026-06-01T00:00:00+00:00",
    )


def _fake_assessment(*, claim, source_url, category, mode, output_style="standard"):
    return {
        "verdict": "Supported",
        "confidence": "High",
        "confidence_score": 82,
        "summary": "The reviewed evidence supports the claim.",
        "sources": [
            {
                "title": "Primary record",
                "url": "https://example.com/record",
                "domain": "example.com",
                "source_type": "primary",
                "summary": "Primary evidence summary.",
                "claim_support": "supports",
                "evidence_category": "direct_evidence",
                "source_role": "evidence",
                "weighted_score": 4.8,
            }
        ],
        "claim_analysis": {
            "subclaims": [{"id": "sc_1", "text": claim, "claim_type": "factual_core"}],
        },
        "pendulum": {"score": 8.0},
        "rule_engine": {"rationale": "Direct evidence found."},
    }


def test_gateway_endpoint_contract_with_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRAI_GATEWAY_AUDIT_STORE", str(tmp_path / "gateway_audit.jsonl"))
    monkeypatch.setattr(api_main, "authenticate_api_key", lambda key: ApiKeyRecord(key_id="key_1", owner_id="contract-user", scopes=["gateway:write"]))
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": _researcher_profile(owner_id))
    monkeypatch.setattr(api_main, "_run_claim_assessment", _fake_assessment)
    monkeypatch.setattr(api_main, "save_report", lambda assessment: assessment)

    response = client.post(
        "/v1/gateway/verify",
        json={
            "workflow_id": "finance-briefing",
            "request_id": "req_1",
            "ai_output": "Paris is the capital of France.",
            "proposed_action": {"type": "publish_briefing", "description": "Publish a briefing."},
            "domain": "finance",
            "consequence_level": "high",
            "policy_id": "finance_default_v1",
        },
        headers={"X-Evidrai-Api-Key": "evd_live_contract_secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "gateway_decision.v1"
    assert payload["gateway_id"].startswith("gw_")
    assert payload["decision"] == "pass"
    assert payload["policy_id"] == "finance_default_v1"
    assert payload["assessment_id"]
    assert payload["claims"][0]["claim_id"] == "sc_1"
    assert payload["assessment"] is None

