import json

from evidrai.feedback import append_feedback_jsonl, build_feedback_record, build_notion_feedback_children


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
