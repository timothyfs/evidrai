from datetime import datetime, timezone

from evidrai.api_models import AssessmentRequestRecord, AssessmentResponse, AssessmentVerdict
from evidrai.reports import LocalReportStore, PostgresReportStore, get_report_store, list_reports, load_report, save_report


def test_save_load_and_list_report(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRAI_REPORT_STORE", str(tmp_path))
    assessment = AssessmentResponse(
        build="test-build",
        mode="fast",
        request=AssessmentRequestRecord(claim="A test claim"),
        verdict=AssessmentVerdict(label="Supported", confidence="High"),
    )

    save_report(assessment)
    loaded = load_report(assessment.assessment_id)
    reports = list_reports()

    assert loaded.assessment_id == assessment.assessment_id
    assert loaded.request.claim == "A test claim"
    assert reports[0]["assessment_id"] == assessment.assessment_id
    assert reports[0]["verdict"] == "Supported"


def test_postgres_report_store_load_returns_assessment(monkeypatch):
    store = PostgresReportStore("postgresql://example")
    store._schema_ready = True
    assessment = AssessmentResponse(
        build="test-build",
        mode="fast",
        request=AssessmentRequestRecord(claim="Postgres load claim"),
        verdict=AssessmentVerdict(label="Supported", confidence="High"),
    )

    class FakeCursor:
        def execute(self, *_args):
            pass

        def fetchone(self):
            return {"payload": assessment.model_dump(mode="json")}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(store, "_connect", lambda: FakeConnection())

    loaded = store.load(assessment.assessment_id)

    assert isinstance(loaded, AssessmentResponse)
    assert loaded.request.claim == "Postgres load claim"


def test_postgres_report_store_list_serializes_datetime(monkeypatch):
    store = PostgresReportStore("postgresql://example")
    store._schema_ready = True

    class FakeCursor:
        def execute(self, *_args):
            pass

        def fetchall(self):
            return [
                {
                    "assessment_id": "assess_1",
                    "created_at": datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
                    "mode": "fast",
                    "claim": "Claim",
                    "verdict": "Supported",
                }
            ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(store, "_connect", lambda: FakeConnection())

    reports = store.list()

    assert reports[0]["created_at"] == "2026-05-16T12:00:00+00:00"


def test_get_report_store_uses_postgres_when_database_url_is_configured(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")

    store = get_report_store()

    assert isinstance(store, PostgresReportStore)


def test_get_report_store_reuses_postgres_store(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com/db")

    assert get_report_store() is get_report_store()


def test_local_report_store_can_be_injected(tmp_path):
    store = LocalReportStore(tmp_path)
    assessment = AssessmentResponse(
        build="test-build",
        mode="deep",
        request=AssessmentRequestRecord(claim="Injected store claim"),
        verdict=AssessmentVerdict(label="Unverified", confidence="Low"),
    )

    save_report(assessment, store=store)

    assert load_report(assessment.assessment_id, store=store).request.claim == "Injected store claim"
    assert list_reports(store=store)[0]["mode"] == "deep"


def test_local_report_share_token_loads_public_report(tmp_path):
    store = LocalReportStore(tmp_path / "reports")
    assessment = AssessmentResponse(
        build="test-build",
        mode="fast",
        owner_id="alice",
        request=AssessmentRequestRecord(claim="Shareable claim"),
        verdict=AssessmentVerdict(label="Supported", confidence="High"),
    )
    save_report(assessment, store=store)

    share = store.create_share(assessment.assessment_id, owner_id="alice")
    loaded = store.load_shared(share["token"])

    assert share["assessment_id"] == assessment.assessment_id
    assert share["access_level"] == "full"
    assert loaded["assessment"].request.claim == "Shareable claim"
