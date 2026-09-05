from evidrai.telemetry import TelemetryCollector, estimate_cost_usd
from evidrai.api_models import serialize_assessment_response
from evidrai.pipeline.verification import merge_supplied_sources, score_source


def test_collector_accumulates_llm_and_search():
    c = TelemetryCollector()
    c.record_llm("gpt-4o-mini", {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140})
    c.record_llm("gpt-4o-mini", {"prompt_tokens": 50, "completion_tokens": 10})
    c.record_search(1)
    c.record_search(3)
    snap = c.snapshot(elapsed_ms=1234)

    assert snap["model"] == "gpt-4o-mini"
    assert snap["llm_calls"] == 2
    assert snap["prompt_tokens"] == 150
    assert snap["completion_tokens"] == 50
    assert snap["total_tokens"] == 200
    assert snap["search_calls"] == 4
    assert snap["elapsed_ms"] == 1234
    assert snap["estimated_cost_usd"] > 0


def test_collector_handles_missing_usage():
    c = TelemetryCollector()
    c.record_llm("gpt-4o-mini", None)
    snap = c.snapshot()
    assert snap["llm_calls"] == 1
    assert snap["prompt_tokens"] == 0
    assert snap["elapsed_ms"] is None


def test_estimate_cost_is_deterministic():
    cost = estimate_cost_usd(1000, 1000, 0)
    # 1k input @ 0.00015 + 1k output @ 0.0006 = 0.00075
    assert abs(cost - 0.00075) < 1e-9


def _minimal_result(**extra):
    result = {
        "verdict": "Supported",
        "confidence": "High",
        "confidence_score": 82,
        "summary": "ok",
        "sources": [],
        "claim_analysis": {"subclaims": [{"id": "sc_1", "text": "A claim"}]},
    }
    result.update(extra)
    return result


def test_serializer_maps_telemetry():
    telemetry = {
        "model": "gpt-4o-mini",
        "llm_calls": 3,
        "prompt_tokens": 900,
        "completion_tokens": 120,
        "total_tokens": 1020,
        "search_calls": 5,
        "elapsed_ms": 4200,
        "estimated_cost_usd": 0.0002,
    }
    response = serialize_assessment_response(
        _minimal_result(telemetry=telemetry),
        claim="A claim",
        mode="deep",
        build="test-build",
    )
    assert response.telemetry is not None
    assert response.telemetry.total_tokens == 1020
    assert response.telemetry.search_calls == 5
    assert response.telemetry.elapsed_ms == 4200


def test_serializer_telemetry_optional():
    response = serialize_assessment_response(
        _minimal_result(),
        claim="A claim",
        mode="deep",
        build="test-build",
    )
    assert response.telemetry is None


def test_merge_supplied_sources_adds_and_dedupes():
    retrieved = [score_source({"title": "Web", "url": "https://web.example/a", "snippet": "x", "content": "x"}, "A claim")]
    supplied = [
        {"title": "Customer doc", "url": "https://intranet.example/doc", "content": "Internal evidence text."},
        {"url": "https://web.example/a", "content": "dupe should be dropped"},
    ]
    merged = merge_supplied_sources(retrieved, supplied, "A claim")
    urls = [s.url for s in merged]
    assert "https://intranet.example/doc" in urls
    # dedupe: the retrieved web URL appears exactly once
    assert urls.count("https://web.example/a") == 1
    assert len(merged) == 2


def test_merge_supplied_sources_noop_when_empty():
    retrieved = [score_source({"title": "Web", "url": "https://web.example/a", "snippet": "x", "content": "x"}, "A claim")]
    assert merge_supplied_sources(retrieved, None, "A claim") == retrieved
    assert merge_supplied_sources(retrieved, [], "A claim") == retrieved
