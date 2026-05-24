from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app
from evidrai.entitlements import UserProfile


client = TestClient(app)


def grant_tier(monkeypatch, tier="pro", owner_id="test-user", email="user@example.com"):
    monkeypatch.setattr(
        api_main,
        "_profile_from_request",
        lambda request: (
            api_main.AuthContext(owner_id=owner_id, auth_method="supabase_jwt", email=email),
            UserProfile(owner_id=owner_id, email=email, tier=tier),
        ),
    )


def test_root_endpoint_returns_service_metadata():
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "evidrai-api"
    assert payload["api_version"] == "api.v1"
    assert payload["docs"] == "/docs"


def test_version_endpoint_returns_build_metadata():
    response = client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "evidrai-api"
    assert payload["api_version"] == "api.v1"
    assert "build" in payload


def test_health_endpoint_returns_build_and_config_flags():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["api_version"] == "api.v1"
    assert "build" in payload
    assert "openai_configured" in payload
    assert "tavily_configured" in payload
    assert "storage_backend" in payload
    assert "auth_configured" in payload


def test_runtime_endpoint_matches_health_shape():
    response = client.get("/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["api_version"] == "api.v1"
    assert "storage_backend" in payload


def test_tiers_endpoint_returns_feature_matrix():
    response = client.get("/tiers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "feature_matrix.v1"
    assert [tier["tier"] for tier in payload["tiers"]] == ["free", "pro", "researcher"]
    assert payload["tiers"][0]["features"]["deep_claims"] is False
    assert payload["tiers"][1]["features"]["speech_audit"] is True


def test_me_endpoint_returns_current_profile(monkeypatch):
    grant_tier(monkeypatch, "researcher", owner_id="jwt-user", email="user@example.com")

    response = client.get("/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["owner_id"] == "jwt-user"
    assert payload["user"]["tier_label"] == "Researcher / Journalist"
    assert payload["user"]["features"]["evidence_ledger"] is True


def test_free_tier_cannot_run_deep_assessment(monkeypatch):
    grant_tier(monkeypatch, "free")

    response = client.post("/assessments/deep", json={"claim": "Test claim"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "feature_not_available"


def test_admin_user_tier_update_requires_token(monkeypatch):
    monkeypatch.setattr(api_main, "admin_token", lambda: "secret-token")

    response = client.patch("/admin/users/tier", json={"owner_id": "user-1", "tier": "pro"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_forbidden"


def test_master_admin_email_can_update_user_tier(monkeypatch):
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "set_user_tier", lambda owner_id, tier, email="": UserProfile(owner_id=owner_id, email=email, tier=tier))

    response = client.patch(
        "/admin/users/tier",
        json={"owner_id": "user-1", "email": "user@example.com", "tier": "researcher"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["tier_label"] == "Researcher / Journalist"


def test_admin_user_tier_update_sets_profile(monkeypatch):
    monkeypatch.setattr(api_main, "admin_token", lambda: "secret-token")
    monkeypatch.setattr(api_main, "set_user_tier", lambda owner_id, tier, email="": UserProfile(owner_id=owner_id, email=email, tier=tier))

    response = client.patch(
        "/admin/users/tier",
        json={"owner_id": "user-1", "email": "user@example.com", "tier": "pro"},
        headers={"X-Evidrai-Admin-Token": "secret-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["owner_id"] == "user-1"
    assert payload["user"]["tier_label"] == "Pro"


def test_admin_delete_user_profile(monkeypatch):
    deleted = []
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "delete_user_profile", lambda owner_id: deleted.append(owner_id) or True)

    response = client.delete("/admin/users/user-1", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert deleted == ["user-1"]


def test_admin_delete_user_profile_cannot_delete_self(monkeypatch):
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))

    response = client.delete("/admin/users/master", headers={"Authorization": "Bearer token"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "cannot_delete_self"


def test_claim_check_requires_input():
    response = client.post("/claims/check", json={"claim": "", "source_url": ""})

    assert response.status_code == 400
    assert "claim or source_url" in response.json()["detail"]


def test_claim_check_rejects_invalid_source_url():
    response = client.post("/claims/check", json={"claim": "test", "source_url": "youtube.com/example"})

    assert response.status_code == 400
    assert "source_url" in response.json()["detail"]


def test_speech_audit_requires_transcript_or_accessible_url(monkeypatch):
    grant_tier(monkeypatch, "pro")
    response = client.post("/speech/audit", json={"transcript": "", "source_url": ""})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "transcript_required"
    assert "transcript" in detail["message"]


def test_speech_audit_rejects_invalid_source_url(monkeypatch):
    grant_tier(monkeypatch, "pro")
    response = client.post("/speech/audit", json={"transcript": "some speech", "source_url": "not-a-url"})

    assert response.status_code == 400
    assert "source_url" in response.json()["detail"]


def test_speech_extract_returns_selected_claims(monkeypatch):
    grant_tier(monkeypatch, "pro")

    class FakeLLM:
        configured = True

    class FakeSearch:
        configured = False

    monkeypatch.setattr(api_main, "_clients", lambda: (FakeLLM(), FakeSearch()))
    monkeypatch.setattr(
        api_main,
        "extract_speech_audit_claims",
        lambda transcript, source_url, max_claims, llm: {
            "title": "Test speech",
            "speaker": "Speaker",
            "source_url": source_url,
            "summary": "Summary",
            "claims": [{"id": "claim_1", "quote": "Quote", "normalized_claim": "Normalized claim"}],
            "skipped_rhetoric": [],
            "extraction_notes": [],
            "transcript_truncated": False,
            "transcript_chars_used": len(transcript),
            "transcript_chars_original": len(transcript),
        },
    )

    response = client.post("/speech/extract", json={"transcript": "some speech", "max_claims": 3})

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["schema_version"] == "speech_extraction.v1"
    assert payload["claims"][0]["id"] == "claim_1"
    assert payload["settings"]["result_mode"] == "speech_extract"


def test_speech_verify_requires_selected_claims(monkeypatch):
    grant_tier(monkeypatch, "pro")
    response = client.post("/speech/verify", json={"claims": []})

    assert response.status_code == 400
    assert "selected claim" in response.json()["detail"]


def test_speech_verify_defaults_to_fast_without_tavily(monkeypatch):
    grant_tier(monkeypatch, "pro")

    class FakeLLM:
        configured = True

    class FakeSearch:
        configured = False

    monkeypatch.setattr(api_main, "_clients", lambda: (FakeLLM(), FakeSearch()))
    monkeypatch.setattr(
        api_main,
        "verify_speech_claim",
        lambda claim, index, source_url, mode, llm, search: {
            "speech_claim": claim,
            "audit_index": index,
            "verification_mode": mode,
            "verdict": "Unverified",
        },
    )

    response = client.post(
        "/speech/verify",
        json={"claims": [{"id": "claim_1", "quote": "Quote", "normalized_claim": "Normalized claim"}], "verification_mode": "fast"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["schema_version"] == "speech_verification.v1"
    assert payload["claims_checked_count"] == 1
    assert payload["claims_checked"][0]["verification_mode"] == "fast"


def test_speech_audit_defaults_to_fast_without_tavily(monkeypatch):
    grant_tier(monkeypatch, "pro")

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
    observed = {}

    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        observed["output_style"] = output_style
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
            "output_style": output_style,
        }

    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setenv("FEEDBACK_LOG_PATH", str(tmp_path / "feedback.jsonl"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    response = client.post("/assessments/fast", json={"claim": "Paris is the capital of France."})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "assessment_response.v1"
    assert payload["mode"] == "fast"
    assert payload["owner_id"] is None
    assert payload["verdict"]["label"] == "Supported"
    assert payload["claim_breakdown"][0]["id"] == "sc_1"
    assert payload["evidence_map"]["supports_factual_core"] == ["src_1"]
    assert payload["sources"][0]["id"] == "src_1"
    assert payload["debug"] is None
    assert payload["request"]["settings"]["output_style"] == "standard"
    assert observed["output_style"] == "standard"

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

    feedback_lookup_response = client.get(f"/feedback/{feedback_payload['feedback_id']}")
    assert feedback_lookup_response.status_code == 200
    feedback_lookup_payload = feedback_lookup_response.json()
    assert feedback_lookup_payload["assessment_id"] == payload["assessment_id"]
    assert feedback_lookup_payload["feedback"]["comment"] == "Good enough"

    missing_feedback_response = client.get("/feedback/00000000-0000-0000-0000-000000000000")
    assert missing_feedback_response.status_code == 404


def test_fast_absurdity_humour_is_fast_only(monkeypatch, tmp_path):
    observed = []

    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        observed.append((mode, output_style))
        return {
            "verdict": "Unverified",
            "confidence": "Low",
            "tldr": "Evidence is thin.",
            "humour_summary": "The claim arrives wearing a lab coat made entirely of question marks.",
            "humour_safety_note": "Applied to claim quality only.",
            "output_style": output_style,
        }

    grant_tier(monkeypatch, "researcher")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    fast = client.post("/assessments/fast", json={"claim": "A dubious but harmless claim", "output_style": "absurdity_humour"}).json()
    deep = client.post("/assessments/deep", json={"claim": "A dubious but harmless claim", "output_style": "absurdity_humour"}).json()

    assert observed == [("fast", "absurdity_humour"), ("deep", "standard")]
    assert fast["reasoning"]["humour_summary"].startswith("The claim arrives")
    assert fast["request"]["settings"]["output_style"] == "absurdity_humour"
    assert deep["request"]["settings"]["output_style"] == "standard"


def test_bearer_token_owner_overrides_spoofable_owner_header(monkeypatch):
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization, owner_header: api_main.AuthContext(owner_id="jwt-user", auth_method="supabase_jwt", email="user@example.com"))

    request = type("Request", (), {"headers": {"authorization": "Bearer test", "x-evidrai-user-id": "spoof"}})()

    assert api_main._owner_id_from_request(request) == "jwt-user"


def test_pro_user_can_create_public_report_share(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    grant_tier(monkeypatch, "pro", owner_id="alice")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    assessment = client.post("/assessments/fast", json={"claim": "Shareable claim"}, headers={"X-Evidrai-User-Id": "alice"}).json()
    share = client.post(f"/reports/{assessment['assessment_id']}/share", json={"platform": "copy"}, headers={"X-Evidrai-User-Id": "alice"})

    assert share.status_code == 200
    token = share.json()["token"]
    public = client.get(f"/public/reports/{token}")
    assert public.status_code == 200
    assert public.json()["request"]["claim"] == "Shareable claim"


def test_free_user_cannot_create_public_report_share(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    grant_tier(monkeypatch, "free", owner_id="alice")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    assessment = client.post("/assessments/fast", json={"claim": "Free share claim"}, headers={"X-Evidrai-User-Id": "alice"}).json()
    share = client.post(f"/reports/{assessment['assessment_id']}/share", json={"platform": "copy"}, headers={"X-Evidrai-User-Id": "alice"})

    assert share.status_code == 403


def test_report_history_can_be_scoped_by_owner_header(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    alice = client.post("/assessments/fast", json={"claim": "Alice claim"}, headers={"X-Evidrai-User-Id": "alice"}).json()
    client.post("/assessments/fast", json={"claim": "Bob claim"}, headers={"X-Evidrai-User-Id": "bob"})

    response = client.get("/reports", headers={"X-Evidrai-User-Id": "alice"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["owner_id"] == "alice"
    assert [item["assessment_id"] for item in payload["reports"]] == [alice["assessment_id"]]
    assert payload["reports"][0]["owner_id"] == "alice"

    own_report = client.get(f"/reports/{alice['assessment_id']}", headers={"X-Evidrai-User-Id": "alice"})
    assert own_report.status_code == 200

    other_report = client.get(f"/reports/{alice['assessment_id']}", headers={"X-Evidrai-User-Id": "bob"})
    assert other_report.status_code == 403


def test_claim_check_embeds_assessment_contract(monkeypatch):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
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
    assert assessment["owner_id"] is None
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
    grant_tier(monkeypatch, "pro")

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
    grant_tier(monkeypatch, "pro")

    class FakeLLM:
        configured = True

    class FakeSearch:
        configured = False

    monkeypatch.setattr(api_main, "_clients", lambda: (FakeLLM(), FakeSearch()))

    response = client.post("/assessments/deep", json={"claim": "Test claim"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "configuration_error"


def test_admin_invite_user_creates_profile(monkeypatch):
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "_create_or_invite_supabase_user", lambda request: {"id": "new-user", "email": request.email})
    monkeypatch.setattr(api_main, "set_user_tier", lambda owner_id, tier, email="": UserProfile(owner_id=owner_id, email=email, tier=tier))

    response = client.post(
        "/admin/users/invite",
        json={"email": "New.User@example.com", "tier": "pro", "send_invite": True},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent_invite"] is True
    assert payload["owner_id"] == "new-user"
    assert payload["user"]["tier_label"] == "Pro"


def test_speech_extract_youtube_bot_check_returns_safe_fallback(monkeypatch):
    grant_tier(monkeypatch, "pro")
    monkeypatch.setattr(
        api_main,
        "extract_youtube_transcript",
        lambda url: {
            "ok": False,
            "code": "youtube_bot_check",
            "error": "YouTube blocked automatic transcript access for this video. Paste the transcript into the Transcript box and run the speech/video audit again.",
            "developer_detail": "Sign in to confirm you’re not a bot. Use --cookies-from-browser",
        },
    )

    response = client.post("/speech/extract", json={"transcript": "", "source_url": "https://youtube.com/watch?v=WVOvmHUu8Vw"})

    assert response.status_code == 422
    payload = response.json()["detail"]
    assert payload["code"] == "youtube_bot_check"
    assert "Paste the transcript" in payload["message"]
    assert "cookies" not in payload["message"]


def test_speech_extract_requires_transcript_unless_youtube_opt_in(monkeypatch):
    grant_tier(monkeypatch, "pro")
    called = []
    monkeypatch.setattr(api_main, "extract_youtube_transcript", lambda url: called.append(url) or {"ok": False})

    response = client.post(
        "/speech/extract",
        json={"transcript": "", "source_url": "https://youtube.com/watch?v=WVOvmHUu8Vw", "try_youtube_captions": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "transcript_required"
    assert called == []


def test_youtube_video_id_extracts_watch_url():
    from evidrai.transcripts import youtube_video_id

    assert youtube_video_id("https://www.youtube.com/watch?v=cR5Dmj6GK88") == "cR5Dmj6GK88"
    assert youtube_video_id("https://youtu.be/WVOvmHUu8Vw") == "WVOvmHUu8Vw"


def test_transcript_diagnostics_rejects_non_youtube_url():
    response = client.post("/transcripts/diagnose", json={"source_url": "https://example.com/video"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_source"


def test_nato_never_supported_america_has_counterexample_source(monkeypatch):
    from evidrai.pipeline.verification import build_search_queries, known_counterexample_sources
    from evidrai.models import SubClaim

    claim = "NATO never supported America"
    subclaims = [SubClaim(id="sc_1", text=claim, claim_type="political")]

    queries = build_search_queries(subclaims)
    sources = known_counterexample_sources(claim)

    assert any("Article 5" in query and "United States" in query for query in queries)
    assert sources
    assert sources[0].domain == "nato.int"
    assert sources[0].claim_support == "contradicts"
    assert sources[0].evidence_category == "credible_contradiction"


def test_fast_pass_overrides_nato_never_claim_with_known_counterexample():
    from evidrai.pipeline.verification import run_quick_pass

    class FakeLLM:
        configured = True
        def complete_json(self, messages, temperature=0.1):
            return {"verdict": "Unverified", "confidence": "Medium", "summary": "Too vague"}

    class FakeSearch:
        configured = False

    result = run_quick_pass("NATO never supported America", "auto-detect", FakeLLM(), FakeSearch())

    assert result["verdict"] == "Not supported by credible evidence"
    assert result["confidence"] == "High"
    assert result["fast_sources"][0]["domain"] == "nato.int"


def test_absolute_claim_queries_include_generic_counterexample_searches():
    from evidrai.pipeline.verification import build_search_queries
    from evidrai.models import SubClaim

    subclaims = [SubClaim(id="sc_1", text="No electric cars have caught fire", claim_type="factual")]
    queries = build_search_queries(subclaims)

    assert any("counterexample" in query for query in queries)
    assert any("official exception" in query for query in queries)
    assert any("evidence against" in query for query in queries)


def test_rule_engine_single_strong_counterexample_defeats_absolute_claim():
    from evidrai.rules.verdict import rule_based_verdict_from_evidence
    from evidrai.models import SubClaim

    subclaims = [SubClaim(id="sc_1", text="No electric cars have caught fire", claim_type="factual", risk_flags=["absolute_claim"])]
    sources = [{
        "source_type": "primary",
        "claim_support": "contradicts",
        "evidence_category": "credible_contradiction",
        "weighted_score": 4.8,
        "title": "Official fire incident dataset",
        "url": "https://example.gov/fire-data",
    }]

    result = rule_based_verdict_from_evidence("No electric cars have caught fire", subclaims, sources, "Mixed / uncertain")

    assert result["verdict"] == "False / contradicted"
    assert result["confidence"] == "High"
    assert result["absolute_claim"] is True


def test_absolute_claim_detector_ignores_titles_and_dates():
    from evidrai.pipeline.verification import has_absolute_claim_language

    assert has_absolute_claim_language("The First Lady attended the summit") is False
    assert has_absolute_claim_language("The first minister gave a speech") is False
    assert has_absolute_claim_language("Sales improved last week") is False
    assert has_absolute_claim_language("What is her last name?") is False


def test_absolute_claim_detector_keeps_claim_level_absolutes():
    from evidrai.pipeline.verification import has_absolute_claim_language

    assert has_absolute_claim_language("NATO never supported America") is True
    assert has_absolute_claim_language("This was the first time Article 5 was invoked") is True
    assert has_absolute_claim_language("She was the only person to vote against it") is True
    assert has_absolute_claim_language("No credible evidence supports the claim") is True


def test_master_admin_me_gets_researcher_tier(monkeypatch):
    calls = []
    context = api_main.AuthContext(owner_id="admin-user", auth_method="supabase_jwt", email="timfsmithson@gmail.com")
    monkeypatch.setattr(api_main, "_auth_context_from_request", lambda request: context)
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"timfsmithson@gmail.com"})
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": UserProfile(owner_id=owner_id, email=email, tier="free"))

    def fake_set_user_tier(owner_id, tier, email=""):
        calls.append((owner_id, tier, email))
        return UserProfile(owner_id=owner_id, email=email, tier=tier)

    monkeypatch.setattr(api_main, "set_user_tier", fake_set_user_tier)

    response = client.get("/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_admin"] is True
    assert payload["user"]["tier"] == "researcher"
    assert payload["user"]["tier_label"] == "Researcher / Journalist"
    assert calls == [("admin-user", "researcher", "timfsmithson@gmail.com")]


def test_assessment_job_completes_and_returns_assessment(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {
            "verdict": "Supported",
            "confidence": "High",
            "tldr": "The evidence supports it.",
            "claim_analysis": {"subclaims": [{"id": "sc_1", "text": claim}]},
            "sources": [{"title": "Source", "url": "https://example.com", "claim_support": "supports", "source_role": "evidence"}],
        }

    grant_tier(monkeypatch, "researcher")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setenv("EVIDRAI_JOB_STORE", str(tmp_path / "jobs"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    create_response = client.post("/assessment-jobs/deep", json={"claim": "Paris is the capital of France."})
    assert create_response.status_code == 200
    job = create_response.json()
    assert job["job_id"]

    status_response = client.get(f"/assessment-jobs/{job['job_id']}", headers={"X-Evidrai-User-Id": "test-user"})
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "completed"
    assert status["assessment"]["mode"] == "deep"
    assert status["assessment"]["sources"][0]["url"] == "https://example.com"
