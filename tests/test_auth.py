import pytest

from evidrai import auth
from evidrai.auth import AuthError, AuthContext, context_from_headers


def test_context_from_headers_uses_anonymous_owner_without_bearer():
    context = context_from_headers(authorization="", owner_header="anon_123")

    assert context == AuthContext(owner_id="anon_123", auth_method="anonymous_header", email="")


def test_context_from_headers_requires_auth_config_for_bearer(monkeypatch):
    monkeypatch.setattr(auth, "supabase_jwt_secret", lambda: None)
    monkeypatch.setattr(auth, "supabase_url", lambda: None)
    auth._jwks_client.cache_clear()

    with pytest.raises(AuthError):
        context_from_headers(authorization="Bearer token", owner_header="spoof")


def test_context_from_headers_prefers_verified_bearer_claims(monkeypatch):
    monkeypatch.setattr(auth, "decode_supabase_access_token", lambda token: {"sub": "user-123", "email": "user@example.com"})

    context = context_from_headers(authorization="Bearer token", owner_header="spoof")

    assert context.owner_id == "user-123"
    assert context.auth_method == "supabase_jwt"
    assert context.email == "user@example.com"
