from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app
from evidrai.api_keys import ApiKeyRecord
from evidrai.entitlements import UserProfile


client = TestClient(app)


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
        "rule_engine": {"rationale": "Direct evidence found."},
    }


def test_v1_assessment_response_contract_with_api_key(monkeypatch):
    monkeypatch.setattr(api_main, "authenticate_api_key", lambda key: ApiKeyRecord(key_id="key_1", owner_id="contract-user", scopes=["assessments:write"]))
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": _researcher_profile(owner_id))
    monkeypatch.setattr(api_main, "_run_claim_assessment", _fake_assessment)
    monkeypatch.setattr(api_main, "save_report", lambda assessment: assessment)

    response = client.post(
        "/assessments/fast",
        json={"claim": "Paris is the capital of France.", "source_url": "https://example.com/record"},
        headers={"X-Evidrai-Api-Key": "evd_live_contract_secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "assessment_response.v1"
    assert payload["build"]
    assert payload["mode"] == "fast"
    assert payload["owner_id"] == "contract-user"
    assert payload["request"]["claim"] == "Paris is the capital of France."
    assert payload["verdict"]["label"] == "Supported"
    assert payload["verdict"]["confidence"] == "High"
    assert payload["verdict"]["confidence_score"] == 82
    assert payload["claim_breakdown"][0]["id"] == "sc_1"
    assert payload["evidence_map"]["supports_factual_core"] == ["src_1"]
    assert payload["sources"][0]["id"] == "src_1"
    assert payload["sources"][0]["stance"] == "supports"
    assert "content" not in payload["sources"][0]


def test_v1_feature_not_available_error_contract(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "_profile_from_request",
        lambda request: (
            api_main.AuthContext(owner_id="contract-user", auth_method="supabase_jwt", email="contract@example.com"),
            UserProfile(
                owner_id="contract-user",
                email="contract@example.com",
                tier="free",
                terms_version=api_main.CURRENT_TERMS_VERSION,
                privacy_version=api_main.CURRENT_PRIVACY_VERSION,
                terms_accepted_at="2026-06-01T00:00:00+00:00",
                privacy_acknowledged_at="2026-06-01T00:00:00+00:00",
            ),
        ),
    )

    response = client.post("/speech/extract", json={"transcript": "hello world", "max_claims": 1})

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "feature_not_available"
    assert detail["message"]


def test_v1_insufficient_api_scope_error_contract(monkeypatch):
    monkeypatch.setattr(api_main, "authenticate_api_key", lambda key: ApiKeyRecord(key_id="key_1", owner_id="contract-user", scopes=["reports:read"]))
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": _researcher_profile(owner_id))

    response = client.post(
        "/assessments/fast",
        json={"claim": "Paris is the capital of France."},
        headers={"X-Evidrai-Api-Key": "evd_live_contract_secret"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "insufficient_api_scope"
    assert detail["required_scope"] == "assessments:write"


def test_v1_consent_required_error_contract(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "_profile_from_request",
        lambda request: (
            api_main.AuthContext(owner_id="contract-user", auth_method="supabase_jwt", email="contract@example.com"),
            UserProfile(owner_id="contract-user", email="contract@example.com", tier="researcher"),
        ),
    )

    response = client.post("/assessments/fast", json={"claim": "Contract claim"})

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "consent_required"
    assert detail["consent"]["required"] is True


def test_openapi_contains_public_integration_routes():
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    for route in [
        "/assessments/fast",
        "/assessments/deep",
        "/assessment-jobs/{mode}",
        "/assessment-jobs/{job_id}",
        "/speech/extract",
        "/speech/verify",
        "/reports",
        "/reports/{report_id}",
        "/admin/api-keys",
        "/admin/api-keys/{key_id}",
    ]:
        assert route in paths
