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
from evidrai.pipeline.verification import parse_claim_analysis


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
    assert payload["queries"] == ["Typed claim evidence"]
    assert payload["claim_analysis"]["subclaims"][0]["risk_flags"] == ["named_person"]
    assert payload["evidence_packet"]["claim"] == "Typed claim"
    assert payload["retrieval"]["sources"][0]["title"] == "Evidence"
    assert payload["pendulum"]["band"] == "Strongly evidenced"
    assert payload["rule_engine"]["verdict"] == "Supported"
    assert payload["provisional_confidence"] == 77
    assert "content" not in payload["sources"][0]
    assert payload["retrieval"]["sources"][0]["domain"] == "example.com"
