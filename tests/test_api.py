from fastapi.testclient import TestClient

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
