from evidrai.models import SubClaim
from evidrai.rules.verdict import rule_based_verdict_from_evidence


def subclaim(claim_type="factual", risk_flags=None):
    return SubClaim(
        id="sc_1",
        text="Test claim",
        claim_type=claim_type,
        risk_flags=risk_flags or [],
    )


def source(
    *,
    support="supports",
    category="direct_evidence",
    source_type="primary",
    score=4.6,
    cluster="cluster",
):
    return {
        "title": f"{support} {category}",
        "url": f"https://example.com/{cluster}/{support}/{category}",
        "source_type": source_type,
        "claim_support": support,
        "evidence_category": category,
        "weighted_score": score,
        "narrative_cluster": cluster,
    }


def verdict_for(sources, subclaims=None, pendulum_band="Mixed / uncertain"):
    return rule_based_verdict_from_evidence(
        "Test claim",
        subclaims or [subclaim()],
        sources,
        pendulum_band,
    )


def test_no_sources_returns_low_confidence_unverified():
    result = verdict_for([])

    assert result["verdict"] == "Unverified"
    assert result["confidence"] == "Low"
    assert result["stats"]["supportive_evidence"] == 0
    assert result["stats"]["contradictory_evidence"] == 0


def test_serious_allegation_with_context_only_is_not_supported():
    result = verdict_for(
        [
            source(support="supports", category="reported_allegation", source_type="secondary", cluster="allegation-1"),
            source(support="supports", category="contextual_signal", source_type="secondary", cluster="context-1"),
        ],
        subclaims=[subclaim(claim_type="criminal")],
    )

    assert result["verdict"] == "Not supported by credible evidence"
    assert result["confidence"] == "Medium"
    assert result["serious_allegation"] is True
    assert result["stats"]["allegation_or_context_support"] == 2


def test_primary_support_without_contradiction_is_supported():
    result = verdict_for(
        [
            source(support="supports", category="direct_evidence", source_type="primary", cluster="primary-record"),
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="reporting-1"),
            source(support="supports", category="expert_analysis", source_type="secondary", cluster="expert-1"),
        ]
    )

    assert result["verdict"] == "Supported"
    assert result["confidence"] == "High"
    assert result["stats"]["primary_supportive"] >= 1


def test_credible_contradiction_outweighs_absent_support():
    result = verdict_for(
        [
            source(support="contradicts", category="credible_contradiction", source_type="primary", cluster="court-record"),
            source(support="contradicts", category="credible_reporting", source_type="secondary", cluster="reporting-1"),
        ]
    )

    assert result["verdict"] == "Not supported by credible evidence"
    assert result["confidence"] == "High"
    assert result["stats"]["contradictory_evidence"] == 2


def test_mixed_evidence_becomes_misleading_when_support_has_quality():
    result = verdict_for(
        [
            source(support="supports", category="direct_evidence", source_type="primary", cluster="record-1"),
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="reporting-1"),
            source(support="contradicts", category="credible_contradiction", source_type="secondary", cluster="contradiction-1"),
        ]
    )

    assert result["verdict"] == "Misleading framing"
    assert result["confidence"] == "Medium"
    assert result["stats"]["supportive_evidence"] == 2
    assert result["stats"]["contradictory_evidence"] == 1


def test_soft_opinion_claim_is_not_overstated_as_supported():
    result = verdict_for(
        [
            source(support="supports", category="direct_evidence", source_type="primary", cluster="record-1"),
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="reporting-1"),
            source(support="supports", category="expert_analysis", source_type="secondary", cluster="expert-1"),
        ],
        subclaims=[subclaim(claim_type="opinion", risk_flags=["opinion"])],
    )

    assert result["soft_claim"] is True
    assert result["verdict"] == "Likely supported"
    assert result["confidence"] == "Medium"
