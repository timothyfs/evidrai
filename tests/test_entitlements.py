import pytest

from evidrai.entitlements import EntitlementError, PostgresUserProfileStore, UserProfile, enforce_speech_claim_limit, get_user_profile_store


def test_get_user_profile_store_uses_postgres_when_database_url_is_configured(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")

    store = get_user_profile_store()

    assert isinstance(store, PostgresUserProfileStore)


def test_get_user_profile_store_reuses_postgres_store(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")

    assert get_user_profile_store() is get_user_profile_store()


def test_custom_speech_claim_limit_overrides_tier_default():
    profile = UserProfile(owner_id="user-1", tier="pro", custom_limits={"max_speech_claims": 10})

    assert profile.to_dict()["limits"]["max_speech_claims"] == 10
    enforce_speech_claim_limit(profile, 10)


def test_speech_claim_limit_uses_effective_profile_limit():
    profile = UserProfile(owner_id="user-1", tier="pro")

    with pytest.raises(EntitlementError) as exc:
        enforce_speech_claim_limit(profile, 6)

    assert exc.value.code == "limit_exceeded"
