import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app
from evidrai.api_models import AssessmentRequestRecord, AssessmentResponse, AssessmentVerdict
from evidrai.entitlements import UserProfile


client = TestClient(app)


def grant_tier(monkeypatch, tier="pro", owner_id="test-user", email="user@example.com"):
    monkeypatch.setattr(
        api_main,
        "_profile_from_request",
        lambda request: (
            api_main.AuthContext(owner_id=owner_id, auth_method="supabase_jwt", email=email),
            UserProfile(
                owner_id=owner_id,
                email=email,
                tier=tier,
                terms_version=api_main.CURRENT_TERMS_VERSION,
                privacy_version=api_main.CURRENT_PRIVACY_VERSION,
                terms_accepted_at="2026-06-01T00:00:00+00:00",
                privacy_acknowledged_at="2026-06-01T00:00:00+00:00",
            ),
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
    assert payload["tiers"][0]["features"]["deep_claims"] is True
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
    assert payload["consent"]["required"] is False


def test_me_with_anonymous_header_does_not_create_profile(monkeypatch):
    calls = []
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": calls.append((owner_id, email)) or UserProfile(owner_id=owner_id, email=email, tier="free"))

    response = client.get("/me", headers={"X-Evidrai-User-Id": "anon_test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["user"]["owner_id"] == "anon_test"
    assert calls == []


def test_anonymous_assessment_is_blocked_without_creating_profile(monkeypatch):
    calls = []
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": calls.append((owner_id, email)) or UserProfile(owner_id=owner_id, email=email, tier="free"))

    response = client.post("/assessments/fast", json={"claim": "Anonymous claim"}, headers={"X-Evidrai-User-Id": "anon_test"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "auth_required"
    assert calls == []


def test_me_consent_update_records_profile_consent(monkeypatch):
    context = api_main.AuthContext(owner_id="jwt-user", auth_method="supabase_jwt", email="user@example.com")
    monkeypatch.setattr(api_main, "_auth_context_from_request", lambda request: context)
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": UserProfile(owner_id=owner_id, email=email, tier="free"))

    captured = {}

    def fake_update_user_consent(owner_id, **details):
        captured["owner_id"] = owner_id
        captured.update(details)
        return UserProfile(
            owner_id=owner_id,
            email="user@example.com",
            tier="free",
            terms_version=details["terms_version"],
            privacy_version=details["privacy_version"],
            terms_accepted_at=details["terms_accepted_at"],
            privacy_acknowledged_at=details["privacy_acknowledged_at"],
            marketing_opt_in=details["marketing_opt_in"],
            marketing_opt_in_at=details["marketing_opt_in_at"],
            consent_source=details["consent_source"],
        )

    monkeypatch.setattr(api_main, "update_user_consent", fake_update_user_consent)

    response = client.post("/me/consent", json={"terms_accepted": True, "marketing_opt_in": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["consent"]["required"] is False
    assert captured["owner_id"] == "jwt-user"
    assert captured["terms_version"] == api_main.CURRENT_TERMS_VERSION
    assert captured["privacy_version"] == api_main.CURRENT_PRIVACY_VERSION
    assert captured["marketing_opt_in"] is True
    assert captured["terms_accepted_at"]


def test_me_consent_update_allows_marketing_opt_out(monkeypatch):
    context = api_main.AuthContext(owner_id="jwt-user", auth_method="supabase_jwt", email="user@example.com")
    monkeypatch.setattr(api_main, "_auth_context_from_request", lambda request: context)
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": UserProfile(owner_id=owner_id, email=email, tier="free"))

    captured = {}

    def fake_update_user_consent(owner_id, **details):
        captured.update(details)
        return UserProfile(
            owner_id=owner_id,
            email="user@example.com",
            tier="free",
            terms_version=details["terms_version"],
            privacy_version=details["privacy_version"],
            terms_accepted_at=details["terms_accepted_at"],
            privacy_acknowledged_at=details["privacy_acknowledged_at"],
            marketing_opt_in=details["marketing_opt_in"],
            marketing_opt_in_at=details["marketing_opt_in_at"],
        )

    monkeypatch.setattr(api_main, "update_user_consent", fake_update_user_consent)

    response = client.post("/me/consent", json={"terms_accepted": True, "marketing_opt_in": False})

    assert response.status_code == 200
    assert captured["marketing_opt_in"] is False
    assert captured["marketing_opt_in_at"] == ""
    assert response.json()["consent"]["required"] is False


def test_me_consent_update_requires_terms_acceptance(monkeypatch):
    context = api_main.AuthContext(owner_id="jwt-user", auth_method="supabase_jwt", email="user@example.com")
    monkeypatch.setattr(api_main, "_auth_context_from_request", lambda request: context)
    monkeypatch.setattr(api_main, "get_or_create_profile", lambda owner_id, email="": UserProfile(owner_id=owner_id, email=email, tier="free"))

    response = client.post("/me/consent", json={"terms_accepted": False, "marketing_opt_in": False})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "terms_required"


def test_public_contact_form_creates_support_queue_item(monkeypatch):
    captured = {}

    class Saved:
        ok = True
        feedback_id = "contact-1"
        destination = "local"

    def fake_save_feedback(record):
        captured.update(record)
        return Saved()

    monkeypatch.setattr(api_main, "save_feedback", fake_save_feedback)

    response = client.post(
        "/contact/messages",
        json={
            "name": "Alex Tester",
            "email": "alex@example.com",
            "organisation": "Example Org",
            "topic": "research",
            "message": "I need evidence exports for a newsroom workflow.",
            "page_url": "https://evidrai.com/contact",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message_id"] == "contact-1"
    assert captured["result_key"] == "support_issue"
    assert captured["owner_id"] == "contact:alex@example.com"
    assert captured["assessment_output"]["support_issue"]["browser_context"]["email"] == "alex@example.com"


def test_public_contact_form_validates_email():
    response = client.post(
        "/contact/messages",
        json={"name": "Alex", "email": "not-email", "topic": "general", "message": "Please contact me about Evidrai."},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "contact_email_required"


def test_free_tier_can_request_standard_assessment(monkeypatch):
    grant_tier(monkeypatch, "free")

    response = client.post("/assessments/deep", json={"claim": "Test claim"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "configuration_error"


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




def test_admin_users_marks_master_admin_access(monkeypatch):
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(
        api_main,
        "list_user_profiles",
        lambda limit=100: [
            UserProfile(owner_id="master", email="master@example.com", tier="researcher"),
            UserProfile(owner_id="user-1", email="user@example.com", tier="pro"),
        ],
    )

    response = client.get("/admin/users", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    users = response.json()["users"]
    assert users[0]["admin_access"] is True
    assert users[0]["admin_access_source"] == "master_admin_email"
    assert users[1]["admin_access"] is False
    assert users[1]["tier_label"] == "Pro"


def test_admin_user_activity_finds_reports_by_email(monkeypatch):
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "list_user_profiles", lambda limit=1000: [UserProfile(owner_id="user-1", email="alex@example.com", tier="pro")])
    monkeypatch.setattr(api_main, "list_reports", lambda limit=25, owner_id="": [{"assessment_id": "r1", "claim": "Test claim", "verdict": "Supported", "owner_id": owner_id}])

    response = client.get("/admin/users/activity?email=alex@example.com", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["owner_id"] == "user-1"
    assert payload["reports"] == [{"assessment_id": "r1", "claim": "Test claim", "verdict": "Supported", "owner_id": "user-1"}]



def test_admin_scoring_policy_requires_admin(monkeypatch):
    monkeypatch.setattr(api_main, "admin_token", lambda: "secret-token")

    response = client.get("/admin/scoring-policy")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_forbidden"


def test_master_admin_can_view_and_update_scoring_policy(monkeypatch):
    policy = api_main.get_scoring_policy()
    saved = []
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "get_scoring_policy", lambda: policy)
    monkeypatch.setattr(api_main, "list_scoring_policy_history", lambda limit=25: [api_main.policy_to_dict(policy)])
    monkeypatch.setattr(api_main, "update_scoring_policy", lambda update, updated_by="admin", change_note="": saved.append((update, updated_by, change_note)) or policy)

    get_response = client.get("/admin/scoring-policy", headers={"Authorization": "Bearer token"})
    patch_response = client.patch(
        "/admin/scoring-policy",
        json={"source_type_independence": {"scientific": 5.0, "news": 2.4}, "change_note": "Tune source independence."},
        headers={"Authorization": "Bearer token"},
    )

    assert get_response.status_code == 200
    assert get_response.json()["policy"]["source_type_authority"]["scientific"] == 5.0
    assert patch_response.status_code == 200
    assert saved[0][1] == "master@example.com"
    assert saved[0][2] == "Tune source independence."


def test_admin_update_user_profile_details(monkeypatch):
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "update_user_profile_details", lambda owner_id, **details: UserProfile(owner_id=owner_id, email=details.get("email", ""), tier="pro", company_name=details.get("company_name", ""), billing_account_name=details.get("billing_account_name", "")))

    response = client.patch(
        "/admin/users/profile",
        json={"owner_id": "user-1", "email": "user@example.com", "company_name": "Acme", "billing_account_name": "Acme Global"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["company_name"] == "Acme"
    assert response.json()["user"]["billing_account_name"] == "Acme Global"


def test_admin_bulk_set_tier(monkeypatch):
    updated = []
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "set_user_tier", lambda owner_id, tier, email="": updated.append((owner_id, tier)) or UserProfile(owner_id=owner_id, tier=tier))

    response = client.post("/admin/users/bulk", json={"owner_ids": ["u1", "u2"], "action": "set_tier", "tier": "researcher"}, headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert updated == [("u1", "researcher"), ("u2", "researcher")]
    assert [user["tier"] for user in response.json()["users"]] == ["researcher", "researcher"]


def test_admin_password_actions_call_supabase(monkeypatch):
    calls = []
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "_supabase_request", lambda method, path, body=None: calls.append((method, path, body)) or {})

    reset = client.post("/admin/users/password-reset", json={"owner_id": "u1", "email": "user@example.com"}, headers={"Authorization": "Bearer token"})
    resend = client.post("/admin/users/resend-invite", json={"owner_id": "u1", "email": "user@example.com"}, headers={"Authorization": "Bearer token"})
    password = client.patch("/admin/users/password", json={"owner_id": "u1", "password": "temporary123"}, headers={"Authorization": "Bearer token"})

    assert reset.status_code == 200
    assert resend.status_code == 200
    assert password.status_code == 200
    assert calls == [
        ("POST", "recover", {"email": "user@example.com"}),
        ("POST", "resend", {"type": "signup", "email": "user@example.com"}),
        ("PUT", "admin/user/u1", {"password": "temporary123"}),
    ]

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


def test_admin_delete_user_removes_supabase_auth_user_and_profile(monkeypatch):
    deleted = []
    supabase_calls = []
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "_supabase_request", lambda method, path, body=None, params=None: supabase_calls.append((method, path, body, params)) or {})
    monkeypatch.setattr(api_main, "delete_user_profile", lambda owner_id: deleted.append(owner_id) or True)

    response = client.delete("/admin/users/user-1", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["auth_deleted"] is True
    assert payload["profile_deleted"] is True
    assert supabase_calls == [("DELETE", "admin/users/user-1", None, None)]
    assert deleted == ["user-1"]


def test_admin_delete_user_falls_back_to_profile_email_when_owner_id_is_not_auth_id(monkeypatch):
    calls = []
    monkeypatch.setattr(api_main, "master_admin_emails", lambda: {"master@example.com"})
    monkeypatch.setattr(api_main, "context_from_headers", lambda authorization="", owner_header="": api_main.AuthContext(owner_id="master", auth_method="supabase_jwt", email="master@example.com"))
    monkeypatch.setattr(api_main, "list_user_profiles", lambda limit=1000: [UserProfile(owner_id="profile-id", email="user@example.com", tier="free")])
    monkeypatch.setattr(api_main, "delete_user_profile", lambda owner_id: True)

    def fake_supabase_request(method, path, body=None, params=None):
        calls.append((method, path, params))
        if method == "DELETE" and path == "admin/users/profile-id":
            raise api_main.HTTPException(status_code=404, detail={"code": "not_found"})
        if method == "GET" and path == "admin/users":
            return {"users": [{"id": "auth-id", "email": "user@example.com"}]}
        return {}

    monkeypatch.setattr(api_main, "_supabase_request", fake_supabase_request)

    response = client.delete("/admin/users/profile-id", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["auth_deleted"] is True
    assert calls == [
        ("DELETE", "admin/users/profile-id", None),
        ("GET", "admin/users", {"page": 1, "per_page": 100}),
        ("DELETE", "admin/users/auth-id", None),
    ]


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


def test_bot_check_skips_authenticated_users(monkeypatch):
    monkeypatch.setattr(api_main, "turnstile_configured", lambda: True)
    monkeypatch.setattr(api_main.requests, "post", lambda *args, **kwargs: pytest.fail("Turnstile should not run for authenticated users"))

    request = api_main.Request({"type": "http", "headers": [], "client": ("127.0.0.1", 12345)})

    api_main._require_bot_check(request, authenticated=True)


def test_bot_check_still_requires_token_for_unauthenticated_users(monkeypatch):
    monkeypatch.setattr(api_main, "turnstile_configured", lambda: True)
    request = api_main.Request({"type": "http", "headers": [], "client": ("127.0.0.1", 12345)})

    with pytest.raises(api_main.HTTPException) as exc:
        api_main._require_bot_check(request, authenticated=False)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "bot_check_required"


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
    monkeypatch.setattr(api_main, "turnstile_configured", lambda: True)

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

    grant_tier(monkeypatch, "free")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setenv("FEEDBACK_LOG_PATH", str(tmp_path / "feedback.jsonl"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    response = client.post("/assessments/fast", json={"claim": "Paris is the capital of France."})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "assessment_response.v1"
    assert payload["mode"] == "fast"
    assert payload["owner_id"] == "test-user"
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
    payload = public.json()
    assert payload["access_level"] == "full"
    assert payload["assessment"]["request"]["claim"] == "Shareable claim"


def test_free_user_can_create_simple_public_report_share(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    grant_tier(monkeypatch, "free", owner_id="alice")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    assessment = client.post("/assessments/fast", json={"claim": "Free share claim"}, headers={"X-Evidrai-User-Id": "alice"}).json()
    share = client.post(f"/reports/{assessment['assessment_id']}/share", json={"platform": "copy"}, headers={"X-Evidrai-User-Id": "alice"})

    assert share.status_code == 200
    assert share.json()["access_level"] == "simple"
    token = share.json()["token"]
    public = client.get(f"/public/reports/{token}")
    assert public.status_code == 200
    payload = public.json()
    assert payload["access_level"] == "simple"
    assert payload["assessment"]["request"]["claim"] == "Free share claim"
    assert payload["assessment"]["sources"] == []


def test_report_delete_and_protect_metadata(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    grant_tier(monkeypatch, "pro", owner_id="alice")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    assessment = client.post("/assessments/fast", json={"claim": "Managed report"}, headers={"X-Evidrai-User-Id": "alice"}).json()
    report_id = assessment["assessment_id"]

    metadata = client.patch(f"/reports/{report_id}/metadata", json={"protected": True}, headers={"X-Evidrai-User-Id": "alice"})
    assert metadata.status_code == 200
    assert metadata.json()["report"]["protected"] is True
    assert client.get("/reports", headers={"X-Evidrai-User-Id": "alice"}).json()["reports"][0]["protected"] is True

    deleted = client.delete(f"/reports/{report_id}", headers={"X-Evidrai-User-Id": "alice"})
    assert deleted.status_code == 200
    assert deleted.json()["report"]["deleted"] is True
    assert client.get(f"/reports/{report_id}", headers={"X-Evidrai-User-Id": "alice"}).status_code == 404
    assert client.get("/reports", headers={"X-Evidrai-User-Id": "alice"}).json()["reports"] == []


def test_report_retention_cycles_old_unprotected_reports(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    grant_tier(monkeypatch, "free", owner_id="alice")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    protected = client.post("/assessments/fast", json={"claim": "Protected oldest"}, headers={"X-Evidrai-User-Id": "alice"}).json()
    client.patch(f"/reports/{protected['assessment_id']}/metadata", json={"protected": True}, headers={"X-Evidrai-User-Id": "alice"})
    for index in range(6):
        client.post("/assessments/fast", json={"claim": f"Report {index}"}, headers={"X-Evidrai-User-Id": "alice"})

    reports = client.get("/reports", headers={"X-Evidrai-User-Id": "alice"}).json()["reports"]
    assert len(reports) == 5
    assert protected["assessment_id"] in [item["assessment_id"] for item in reports]
    assert reports[-1]["protected"] is True


def test_report_history_can_be_scoped_by_owner_header(monkeypatch, tmp_path):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {"verdict": "Supported", "confidence": "High", "summary": "ok"}

    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    def profile_from_owner_header(request):
        owner_id = request.headers.get("x-evidrai-user-id") or "alice"
        return (
            api_main.AuthContext(owner_id=owner_id, auth_method="supabase_jwt", email=f"{owner_id}@example.com"),
            UserProfile(
                owner_id=owner_id,
                email=f"{owner_id}@example.com",
                tier="free",
                terms_version=api_main.CURRENT_TERMS_VERSION,
                privacy_version=api_main.CURRENT_PRIVACY_VERSION,
                terms_accepted_at="2026-06-01T00:00:00+00:00",
                privacy_acknowledged_at="2026-06-01T00:00:00+00:00",
            ),
        )

    monkeypatch.setattr(api_main, "_profile_from_request", profile_from_owner_header)

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




def test_unowned_legacy_report_is_not_visible_to_signed_in_user(monkeypatch, tmp_path):
    grant_tier(monkeypatch, "pro", owner_id="alice")
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path / "reports"))
    assessment = AssessmentResponse(
        build="test-build",
        mode="fast",
        request=AssessmentRequestRecord(claim="Legacy unowned claim"),
        verdict=AssessmentVerdict(label="Supported", confidence="High"),
    )
    api_main.save_report(assessment)

    assert client.get("/reports", headers={"X-Evidrai-User-Id": "alice"}).json()["reports"] == []
    assert client.get(f"/reports/{assessment.assessment_id}", headers={"X-Evidrai-User-Id": "alice"}).status_code == 403
    assert client.post(f"/reports/{assessment.assessment_id}/share", json={"platform": "copy"}, headers={"X-Evidrai-User-Id": "alice"}).status_code == 403
    assert client.patch(f"/reports/{assessment.assessment_id}/metadata", json={"protected": True}, headers={"X-Evidrai-User-Id": "alice"}).status_code == 403

def test_claim_check_embeds_assessment_contract(monkeypatch):
    def fake_run_claim_assessment(*, claim, source_url, category, mode, output_style="standard"):
        return {
            "verdict": "Unverified",
            "confidence": "Low",
            "summary": "Not enough evidence.",
            "debug_trace": {"schema_version": "pipeline_trace.v1", "normalized_claim": claim},
        }

    grant_tier(monkeypatch, "free")
    monkeypatch.setattr(api_main, "_run_claim_assessment", fake_run_claim_assessment)

    response = client.post("/claims/check", json={"claim": "Test claim", "mode": "fast", "include_debug": True})

    assert response.status_code == 200
    payload = response.json()
    assessment = payload["result"]["assessment"]
    assert assessment["schema_version"] == "assessment_response.v1"
    assert assessment["owner_id"] == "test-user"
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
    assert payload["invite_email"]["subject"] == "Your Evidrai early access invite"
    assert "controlled early access" in payload["invite_email"]["text"].lower()
    assert payload["invite_email"]["logo_url"].endswith("/brand/evidrai-logo-full.jpg")


def test_create_or_invite_supabase_user_includes_invite_message_metadata(monkeypatch):
    monkeypatch.setattr(api_main, "_supabase_auth_user_by_email", lambda email: None)
    captured = {}

    def fake_supabase_request(method, path, *, body=None, params=None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return {"id": "new-user", "email": body["email"]}

    monkeypatch.setattr(api_main, "_supabase_request", fake_supabase_request)

    api_main._create_or_invite_supabase_user(
        api_main.AdminInviteUserRequest(
            email="User@example.com",
            tier="researcher",
            send_invite=True,
            personal_message="Welcome to the private trial.",
        )
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "invite"
    assert captured["body"]["email"] == "user@example.com"
    assert captured["body"]["data"]["evidrai_tier"] == "researcher"
    assert captured["body"]["data"]["evidrai_invite_message"] == "Welcome to the private trial."


def test_create_or_invite_supabase_user_blocks_existing_auth_email(monkeypatch):
    monkeypatch.setattr(api_main, "_supabase_auth_user_by_email", lambda email: {"id": "auth-id", "email": email.lower()})

    with pytest.raises(api_main.HTTPException) as exc:
        api_main._create_or_invite_supabase_user(api_main.AdminInviteUserRequest(email="User@example.com", tier="free", send_invite=True))

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "supabase_auth_user_already_exists"
    assert exc.value.detail["supabase_user_id"] == "auth-id"


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


def test_llm_client_preserves_rate_limit_after_retries(monkeypatch):
    from evidrai.clients.llm import OpenAICompatibleClient
    from evidrai.errors import LLMRequestError

    class Response:
        status_code = 429
        headers = {}
        text = '{"error":{"message":"rate limited"}}'
        def json(self):
            return {"error": {"message": "rate limited"}}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "")
    monkeypatch.setattr("evidrai.clients.llm.time.sleep", lambda _: None)
    monkeypatch.setattr("evidrai.clients.llm.requests.post", lambda *args, **kwargs: Response())

    client = OpenAICompatibleClient()
    try:
        client.complete_json([{"role": "user", "content": "Return JSON"}])
    except LLMRequestError as exc:
        assert str(exc) == "LLM rate limit hit."
        assert exc.status_code == 429
    else:
        raise AssertionError("Expected LLMRequestError")


def test_llm_client_falls_back_to_secondary_model_on_rate_limit(monkeypatch):
    from evidrai.clients.llm import OpenAICompatibleClient

    calls = []

    class RateLimitedResponse:
        status_code = 429
        headers = {}
        text = '{"error":{"message":"rate limited"}}'
        def json(self):
            return {"error": {"message": "rate limited"}}

    class SuccessResponse:
        status_code = 200
        headers = {}
        text = '{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'
        def raise_for_status(self):
            return None
        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    def fake_post(*args, **kwargs):
        model = kwargs["json"]["model"]
        calls.append(model)
        if model == "primary-model":
            return RateLimitedResponse()
        return SuccessResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "primary-model")
    monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "fallback-model")
    monkeypatch.setattr("evidrai.clients.llm.time.sleep", lambda _: None)
    monkeypatch.setattr("evidrai.clients.llm.requests.post", fake_post)

    client = OpenAICompatibleClient()
    assert client.complete_json([{"role": "user", "content": "Return JSON"}]) == {"ok": True}
    assert "primary-model" in calls
    assert calls[-1] == "fallback-model"
