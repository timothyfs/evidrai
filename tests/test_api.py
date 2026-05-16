from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app


client = TestClient(app)


def test_health_endpoint_returns_build_and_config_flags():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "build" in payload
    assert "openai_configured" in payload
    assert "tavily_configured" in payload


def test_claim_check_requires_input():
    response = client.post("/claims/check", json={"claim": "", "source_url": ""})

    assert response.status_code == 400
    assert "claim or source_url" in response.json()["detail"]


def test_claim_check_rejects_invalid_source_url():
    response = client.post("/claims/check", json={"claim": "test", "source_url": "youtube.com/example"})

    assert response.status_code == 400
    assert "source_url" in response.json()["detail"]


def test_speech_audit_requires_transcript_or_accessible_url():
    response = client.post("/speech/audit", json={"transcript": "", "source_url": ""})

    assert response.status_code == 400
    assert "transcript" in response.json()["detail"]


def test_speech_audit_rejects_invalid_source_url():
    response = client.post("/speech/audit", json={"transcript": "some speech", "source_url": "not-a-url"})

    assert response.status_code == 400
    assert "source_url" in response.json()["detail"]


def test_fast_assessment_endpoint_returns_contract_shape(monkeypatch):
    def fake_run_claim_assessment(*, claim, source_url, category, mode):
        return {
            "verdict": "Supported",
            "confidence": "High",
            "tldr": "Paris is the capital of France.",
            "summary": "A basic geography claim.",
            "sources": [
                {
                    "title": "Official source",
                    "url": "https://example.com/paris",
                    "domain": "example.com",
                    "source_type": "primary",
                    "summary": "Paris is listed as the capital.",
                    "claim_support": "supports",
                    "evidence_category": "direct_evidence",
                    "source_role": "evidence",
                    "weighted_score": 4.5,
                }
            ],
            "claim_analysis": {
                "normalized_claim": "Paris is the capital of France.",
                "subclaims": [{"id": "sc_1", "text": "Paris is the capital of France.", "claim_type": "factual_core"}],
            },
            "rule_engine": {"rationale": "Direct support found."},
        }

    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    response = client.post("/assessments/fast", json={"claim": "Paris is the capital of France."})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "assessment_response.v1"
    assert payload["mode"] == "fast"
    assert payload["verdict"]["label"] == "Supported"
    assert payload["claim_breakdown"][0]["id"] == "sc_1"
    assert payload["evidence_map"]["supports_factual_core"] == ["src_1"]
    assert payload["sources"][0]["id"] == "src_1"
    assert payload["debug"] is None


def test_claim_check_embeds_assessment_contract(monkeypatch):
    def fake_run_claim_assessment(*, claim, source_url, category, mode):
        return {
            "verdict": "Unverified",
            "confidence": "Low",
            "summary": "Not enough evidence.",
            "debug_trace": {"schema_version": "pipeline_trace.v1", "normalized_claim": claim},
        }

    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    response = client.post("/claims/check", json={"claim": "Test claim", "mode": "fast", "include_debug": True})

    assert response.status_code == 200
    payload = response.json()
    assessment = payload["result"]["assessment"]
    assert assessment["schema_version"] == "assessment_response.v1"
    assert assessment["debug"]["schema_version"] == "pipeline_trace.v1"
