import json

from evidrai.api_models import AssessmentResponse, AssessmentRequestRecord, AssessmentVerdict
from evidrai.trust import LocalTrustStore, assessment_trust_snapshot, build_trust_events_from_feedback, pseudonymous_actor_id


def sample_assessment() -> AssessmentResponse:
    return AssessmentResponse(
        assessment_id="assess_trust_1",
        created_at="2026-05-19T12:00:00+00:00",
        build="test-build",
        mode="fast",
        owner_id="user-123",
        request=AssessmentRequestRecord(claim="Test claim", source_url="https://example.com", category="general", settings={}),
        verdict=AssessmentVerdict(label="Unverified", confidence="Low", summary="Summary", key_caveat="Caveat", evidence_strength_score=2.5),
        claim_breakdown=[],
        evidence_map={},
        sources=[
            {
                "id": "src_1",
                "title": "Source",
                "url": "https://example.com/source",
                "domain": "example.com",
                "source_type": "secondary",
                "stance": "context",
                "evidence_category": "context",
                "source_role": "background",
                "narrative_cluster": "cluster-a",
                "score": 2.0,
                "summary": "Source summary",
                "classification_reason": "Reason",
            }
        ],
        reasoning={},
    )


def test_assessment_trust_snapshot_pseudonymizes_actor_and_preserves_sources():
    snapshot = assessment_trust_snapshot(sample_assessment())

    assert snapshot["assessment_id"] == "assess_trust_1"
    assert snapshot["actor_hash"] == pseudonymous_actor_id("user-123")
    assert snapshot["actor_hash"] != "user-123"
    assert snapshot["narrative_clusters"] == ["cluster-a"]
    assert snapshot["sources"][0]["domain"] == "example.com"


def test_build_trust_events_from_feedback_contains_verdict_challenge_and_counter_evidence():
    record = {
        "feedback_id": "fb_1",
        "assessment_id": "assess_trust_1",
        "owner_id": "user-123",
        "captured_at": "2026-05-19T12:01:00+00:00",
        "rating": "Partly useful",
        "comment": "Needs primary source",
        "accepted_verdict": "rejected",
        "trust_signals": ["needs_primary_sourcing"],
        "challenge_text": "Primary evidence was missing",
        "counter_evidence": [{"url": "https://example.com/primary"}],
        "assessment_output": sample_assessment().model_dump(mode="json"),
    }

    events = build_trust_events_from_feedback(record)
    signal_types = {event["signal_type"] for event in events}

    assert "verdict_rejected" in signal_types
    assert "needs_primary_sourcing" in signal_types
    assert "user_challenge" in signal_types
    assert "counter_evidence_submitted" in signal_types


def test_local_trust_store_writes_assessment_and_feedback_events(tmp_path):
    path = tmp_path / "trust.jsonl"
    store = LocalTrustStore(path)
    assessment = sample_assessment()

    store.save_assessment_snapshot(assessment)
    store.save_feedback_events({
        "feedback_id": "fb_1",
        "assessment_id": assessment.assessment_id,
        "owner_id": "user-123",
        "accepted_verdict": "accepted",
        "trust_signals": ["changed_view"],
        "assessment_output": assessment.model_dump(mode="json"),
    })

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["event_kind"] == "assessment_snapshot"
    assert {line.get("signal_type") for line in lines[1:]} == {"verdict_accepted", "changed_view"}
    summary = store.analytics_summary()
    assert summary["top_signals"][0]["count"] >= 1
