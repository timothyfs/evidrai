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


def test_speech_audit_defaults_to_fast_without_tavily(monkeypatch):
    class FakeLLM:
        configured = True

    class FakeSearch:
        configured = False

    monkeypatch.setattr(api_main, "_clients", lambda: (FakeLLM(), FakeSearch()))
    monkeypatch.setattr(
        api_main,
        "run_speech_audit",
        lambda transcript, source_url, max_claims, llm, search, verification_mode="fast": {
            "schema_version": "speech_audit.v1",
            "claims_checked": [],
            "claims_checked_count": 0,
            "claims_needing_attention_count": 0,
            "verification_mode": verification_mode,
        },
    )

    response = client.post("/speech/audit", json={"transcript": "some speech"})

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["verification_mode"] == "fast"
    assert payload["settings"]["max_claims"] == 3


def test_fast_assessment_endpoint_returns_contract_shape(monkeypatch, tmp_path):
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

    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setenv("FEEDBACK_LOG_PATH", str(tmp_path / "feedback.jsonl"))
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

    report_response = client.get(f"/reports/{payload['assessment_id']}")
    assert report_response.status_code == 200
    assert report_response.json()["assessment_id"] == payload["assessment_id"]

    list_response = client.get("/reports")
    assert list_response.status_code == 200
    assert list_response.json()["reports"][0]["assessment_id"] == payload["assessment_id"]

    feedback_response = client.post(
        f"/assessments/{payload['assessment_id']}/feedback",
        json={"rating": "Useful", "reasons": ["Verdict clarity"], "comment": "Good enough"},
    )
    assert feedback_response.status_code == 200
    feedback_payload = feedback_response.json()
    assert feedback_payload["ok"] is True
    assert feedback_payload["assessment_id"] == payload["assessment_id"]
    assert feedback_payload["feedback_id"]

    feedback_list_response = client.get(f"/assessments/{payload['assessment_id']}/feedback")
    assert feedback_list_response.status_code == 200
    feedback_list_payload = feedback_list_response.json()
    assert feedback_list_payload["assessment_id"] == payload["assessment_id"]
    assert feedback_list_payload["feedback_count"] == 1
    assert feedback_list_payload["feedback"][0]["comment"] == "Good enough"


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


def test_sources_extract_endpoint_uses_ingestion(monkeypatch):
    from evidrai.ingestion.url import ExtractedSource

    monkeypatch.setattr(
        api_main,
        "fetch_source_url",
        lambda url: ExtractedSource(
            url="https://example.com/story",
            final_url="https://example.com/story",
            domain="example.com",
            title="Story title",
            description="Description",
            text="Article text",
            excerpt="Article text",
            candidate_claims=["The article says something happened."],
            word_count=5,
        ),
    )

    response = client.post("/sources/extract", json={"source_url": "https://example.com/story"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "source_extract.v1"
    assert payload["candidate_claims"] == ["The article says something happened."]


def test_url_only_assessment_extracts_candidate_claim(monkeypatch):
    class FakeLLM:
        configured = True

    class FakeSearch:
        configured = True

    class FakeExtracted:
        candidate_claims = ["Extracted claim from article."]
        description = ""
        title = ""
        excerpt = ""

    captured = {}

    def fake_pipeline(analysis_input, llm, search):
        captured["analysis_input"] = analysis_input
        return {"verified_verdict": "Unverified", "verified_confidence": "Low"}

    monkeypatch.setattr(api_main, "_clients", lambda: (FakeLLM(), FakeSearch()))
    monkeypatch.setattr(api_main, "fetch_source_url", lambda url: FakeExtracted())
    monkeypatch.setattr(api_main, "run_claim_pipeline", fake_pipeline)

    response = client.post("/assessments/deep", json={"source_url": "https://example.com/story"})

    assert response.status_code == 200
    assert "Extracted claim from article." in captured["analysis_input"]


def test_deep_assessment_missing_tavily_returns_structured_error(monkeypatch):
    class FakeLLM:
        configured = True

    class FakeSearch:
        configured = False

    monkeypatch.setattr(api_main, "_clients", lambda: (FakeLLM(), FakeSearch()))

    response = client.post("/assessments/deep", json={"claim": "Test claim"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "configuration_error"
