from evidrai.api_models import AssessmentRequestRecord, AssessmentResponse, AssessmentVerdict
from evidrai.reports import LocalReportStore, list_reports, load_report, save_report


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
