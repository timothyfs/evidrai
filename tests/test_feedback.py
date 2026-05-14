import json

from evidrai.feedback import append_feedback_jsonl, build_feedback_record


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
    )

    assert record["feedback_id"]
    assert record["result_key"] == "deep_123"
    assert record["claim"] == "Test claim"
    assert record["verdict"] == "Likely supported"
    assert record["confidence"] == "Medium"
    assert record["reasons"] == ["Verdict clarity"]
    assert record["comment"] == "Too cautious"
    assert record["source_url"] == "https://example.com/source"


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
