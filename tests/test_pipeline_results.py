from evidrai.models import (
    ClaimAnalysisResult,
    EvidencePacket,
    EvidenceSource,
    PendulumResult,
    RetrievalResult,
    RuleEngineResult,
    SubClaim,
    VerificationResult,
    PipelineResultModel,
)
from evidrai.pipeline.verification import build_fast_evidence_context, build_fast_search_queries, parse_claim_analysis, run_speech_audit, truncate_speech_transcript


def test_truncate_speech_transcript_limits_extraction_budget():
    text = "x" * 13000

    truncated, was_truncated = truncate_speech_transcript(text, max_chars=12000)

    assert was_truncated is True
    assert len(truncated) == 12000


def test_run_speech_audit_defaults_to_fast_verification(monkeypatch):
    class FakeLLM:
        configured = True

        def complete_json(self, messages, temperature=0.1):
            return {
                "title": "Speech",
                "speaker": "Speaker",
                "summary": "Summary",
                "claims": [
                    {
                        "quote": "A quote",
                        "normalized_claim": "A checkable claim",
                        "priority": "high",
                        "checkability": "checkable",
                    }
                ],
                "skipped_rhetoric": [],
                "extraction_notes": [],
            }

    class FakeSearch:
        configured = False

    calls = []

    def fake_run_quick_pass(user_input, category, llm, search):
        calls.append(user_input)
        return {"verdict": "Unverified", "confidence": "Low", "tldr": "Fast result"}

    monkeypatch.setattr("evidrai.pipeline.verification.run_quick_pass", fake_run_quick_pass)

    result = run_speech_audit("transcript", "", 3, FakeLLM(), FakeSearch())

    assert result["verification_mode"] == "fast"
    assert result["claims_checked_count"] == 1
    assert result["claims_checked"][0]["verification_mode"] == "fast"
    assert calls == ["A checkable claim\n\nOriginal quote: A quote"]


def test_build_fast_evidence_context_scores_search_sources():
    class FakeSearch:
        configured = True

        def search(self, query, max_results=5):
            return [
                {
                    "title": "Official Paris record",
                    "url": "https://example.gov/paris",
                    "snippet": "Paris is the capital city of France according to the official record.",
                    "published_date": "2025-01-01",
                }
            ]

    _context, sources = build_fast_evidence_context("Paris is the capital city of France", FakeSearch())

    assert sources[0]["weighted_score"] > 0
    assert sources[0]["scoring_factors"]["authority"] > 0
    assert sources[0]["scoring_factors"]["relevance"] > 0
    assert sources[0]["scoring_factors"]["directness"] > 0
    assert sources[0]["scoring_factors"]["recency"] > 0
    assert sources[0]["scoring_factors"]["bias_risk"] > 0


def test_fast_search_queries_include_uk_official_domains():
    queries = build_fast_search_queries("The UK spends more on debt interest than on defence")

    assert queries[0] == "The UK spends more on debt interest than on defence"
    assert any(query.startswith("site:gov.uk ") for query in queries)
    assert any(query.startswith("site:commonslibrary.parliament.uk ") for query in queries)
    assert any(query.startswith("site:obr.uk ") for query in queries)


def test_parse_claim_analysis_returns_typed_result_with_fallback_subclaim():
    result = parse_claim_analysis({"normalized_claim": ""}, "Raw claim text")

    assert isinstance(result, ClaimAnalysisResult)
    assert result.normalized_claim == "Raw claim text"
    assert len(result.subclaims) == 1
    assert result.subclaims[0].text == "Raw claim text"
    assert result.subclaim_texts == ["Raw claim text"]


def test_evidence_source_packet_preserves_public_fields_only():
    source = EvidenceSource(
        title="Source title",
        url="https://example.com/story",
        domain="example.com",
        source_type="primary",
        snippet="Public summary",
        content="Raw fetched content should not be exported here",
        weighted_score=4.7,
        claim_support="supports",
        evidence_category="direct_evidence",
        source_role="evidence",
        narrative_cluster="cluster-1",
    )

    packet = source.to_packet()

    assert packet["summary"] == "Public summary"
    assert packet["weighted_score"] == 4.7
    assert "content" not in packet


def test_verification_result_serializes_ui_compatibility_and_trace_boundaries():
    subclaim = SubClaim(id="sc_1", text="Typed claim", claim_type="factual", risk_flags=["named_person"])
    claim_analysis = ClaimAnalysisResult(normalized_claim="Typed claim", subclaims=[subclaim])
    source = EvidenceSource(
        title="Evidence",
        url="https://example.com/evidence",
        domain="example.com",
        source_type="primary",
        snippet="Evidence summary",
        weighted_score=4.5,
        claim_support="supports",
        evidence_category="direct_evidence",
    )
    retrieval = RetrievalResult(queries=["Typed claim evidence"], sources=[source])
    evidence_packet = EvidencePacket(
        claim="Typed claim",
        subclaims=claim_analysis.subclaim_texts,
        sources=[source.to_packet()],
    )
    pendulum = PendulumResult(band="Strongly evidenced", score=8.2, explanation="1 evidentiary source")
    rule_engine = RuleEngineResult(
        verdict="Supported",
        confidence="Medium",
        rationale="Direct evidence found.",
        stats={"supportive_evidence": 1},
        risk_flags=["named_person"],
    )
    result = VerificationResult(
        claim="Typed claim",
        claim_analysis=claim_analysis,
        retrieval=retrieval,
        evidence_packet=evidence_packet,
        pendulum=pendulum,
        rule_engine=rule_engine,
        reasoning={"verified_verdict": "Supported", "verified_confidence": "Medium"},
        provisional_verdict="true",
        provisional_confidence=77,
    )

    model = result.to_model()
    payload = result.to_dict()

    assert isinstance(model, PipelineResultModel)
    assert payload["schema_version"] == "pipeline_result.v1"
    assert payload["claim"] == "Typed claim"
    assert payload["subclaims"] == ["Typed claim"]
    assert payload["sources"][0]["summary"] == "Evidence summary"
    assert payload["sources"][0]["scoring_factors"]["weighted"] == 4.5
    assert payload["queries"] == ["Typed claim evidence"]
    assert payload["claim_analysis"]["subclaims"][0]["risk_flags"] == ["named_person"]
    assert payload["evidence_packet"]["claim"] == "Typed claim"
    assert payload["evidence_packet"]["sources"][0]["scoring_factors"]["weighted"] == 4.5
    assert payload["retrieval"]["sources"][0]["title"] == "Evidence"
    assert payload["retrieval"]["sources"][0]["scoring_factors"]["weighted"] == 4.5
    assert payload["pendulum"]["band"] == "Strongly evidenced"
    assert payload["rule_engine"]["verdict"] == "Supported"
    assert payload["provisional_confidence"] == 77
    assert "content" not in payload["sources"][0]
    assert payload["retrieval"]["sources"][0]["domain"] == "example.com"
    assert payload["debug_trace"]["schema_version"] == "pipeline_trace.v1"
    assert payload["debug_trace"]["normalized_claim"] == "Typed claim"
    assert payload["debug_trace"]["scoring"]["source_scores"][0]["scoring_factors"]["weighted"] == 4.5
    assert payload["debug_trace"]["downgrade_rationale"] == "Direct evidence found."
