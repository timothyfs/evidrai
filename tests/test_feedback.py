import json

from evidrai.feedback import LocalFeedbackStore, append_feedback_jsonl, build_feedback_record, build_notion_feedback_children, build_notion_feedback_payload, list_feedback_for_assessment


def test_build_feedback_record_contains_result_context():
    record = build_feedback_record(
        result_key="deep_123",
        rating="Partly useful",
        reasons=["Verdict clarity"],
        comment="Too cautious",
        result={
            "claim": "Test claim",
            "verified_verdict": "Likely supported",
            "verified_confidence": "Medium",
            "result_id": "deep_123",
            "assessment_id": "assess_123",
        },
        source_url="https://example.com/source",
        settings={"verification_depth": "Deep", "output_mode": "Detailed"},
    )

    assert record["feedback_id"]
    assert record["result_key"] == "deep_123"
    assert record["claim"] == "Test claim"
    assert record["verdict"] == "Likely supported"
    assert record["confidence"] == "Medium"
    assert record["reasons"] == ["Verdict clarity"]
    assert record["comment"] == "Too cautious"
    assert record["source_url"] == "https://example.com/source"
    assert record["assessment_id"] == "assess_123"
    assert record["request"]["settings"]["verification_depth"] == "Deep"
    assert record["assessment_output"]["claim"] == "Test claim"


def test_append_feedback_jsonl_writes_one_json_record(tmp_path):
    path = tmp_path / "feedback.jsonl"
    record = build_feedback_record(
        result_key="quick_1",
        rating="Useful",
        reasons=[],
        comment="",
        result={"verdict": "Unverified", "confidence": "Low"},
    )

    written = append_feedback_jsonl(record, path)

    assert written == path
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["feedback_id"] == record["feedback_id"]
    assert payload["rating"] == "Useful"


def test_list_feedback_for_assessment_filters_and_sorts(tmp_path):
    path = tmp_path / "feedback.jsonl"
    older = build_feedback_record(
        result_key="old",
        rating="Useful",
        reasons=[],
        comment="older",
        result={"assessment_id": "assess_1", "claim": "Claim 1"},
    )
    newer = build_feedback_record(
        result_key="new",
        rating="Useful",
        reasons=[],
        comment="newer",
        result={"assessment_id": "assess_1", "claim": "Claim 1"},
    )
    other = build_feedback_record(
        result_key="other",
        rating="Useful",
        reasons=[],
        comment="other",
        result={"assessment_id": "assess_2", "claim": "Claim 2"},
    )
    older["captured_at"] = "2026-01-01T00:00:00+00:00"
    newer["captured_at"] = "2026-01-02T00:00:00+00:00"
    append_feedback_jsonl(older, path)
    append_feedback_jsonl(other, path)
    append_feedback_jsonl(newer, path)
    path.write_text(path.read_text(encoding="utf-8") + "not-json\n", encoding="utf-8")

    results = list_feedback_for_assessment("assess_1", path=path)

    assert [item["comment"] for item in results] == ["newer", "older"]


def test_local_feedback_store_can_be_injected(tmp_path, monkeypatch):
    monkeypatch.setattr("evidrai.feedback.create_notion_feedback_page", lambda record: None)
    store = LocalFeedbackStore(tmp_path / "feedback.jsonl")
    record = build_feedback_record(
        result_key="key",
        rating="Useful",
        reasons=[],
        comment="stored",
        result={"assessment_id": "assess_store", "claim": "Claim"},
    )

    save_result = store.save(record)

    assert save_result.ok is True
    assert store.list_by_assessment("assess_store")[0]["comment"] == "stored"


def test_notion_feedback_payload_initializes_review_workflow_fields():
    record = build_feedback_record(
        result_key="deep_review",
        rating="Partly useful",
        reasons=["Verdict clarity"],
        comment="Needs review",
        result={"claim": "Review claim", "verified_verdict": "Unverified"},
    )

    payload = build_notion_feedback_payload(record, "database-id")
    props = payload["properties"]

    assert props["Error type"] == {"multi_select": []}
    assert props["Accepted as regression case"] == {"checkbox": False}
    assert props["Reviewer notes"] == {"rich_text": []}


def test_notion_feedback_children_include_request_and_full_output():
    record = build_feedback_record(
        result_key="deep_456",
        rating="Not useful",
        reasons=["Verdict clarity"],
        comment="Verdict disagrees with evidence scorecard",
        result={
            "claim": "Example claim",
            "verified_verdict": "Unverified",
            "verified_confidence": "Medium",
            "sources": [{"title": "Source A", "summary": "Evidence summary"}],
            "rule_engine": {"verdict": "Likely supported"},
        },
        settings={"verification_depth": "Deep", "claim_category": "politics"},
    )

    children = build_notion_feedback_children(record)
    text = json.dumps(children)

    assert "Full request and settings" in text
    assert "Full assessment output" in text
    assert "Verdict disagrees with evidence scorecard" in text
    assert "verification_depth" in text
    assert "rule_engine" in text
