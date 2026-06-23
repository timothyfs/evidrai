from evidrai.entitlements import PostgresUserProfileStore, get_user_profile_store


def test_get_user_profile_store_uses_postgres_when_database_url_is_configured(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")

    store = get_user_profile_store()

    assert isinstance(store, PostgresUserProfileStore)


def test_get_user_profile_store_reuses_postgres_store(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")

    assert get_user_profile_store() is get_user_profile_store()
