from evidrai.models import SubClaim
from evidrai.rules.verdict import align_reasoning_with_rules, rule_based_verdict_from_evidence


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

    assert result["verdict"] == "Reported but unconfirmed"
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

    assert result["verdict"] == "False / contradicted"
    assert result["confidence"] == "High"
    assert result["stats"]["contradictory_evidence"] == 2


def test_mixed_evidence_becomes_partly_supported_when_support_has_quality():
    result = verdict_for(
        [
            source(support="supports", category="direct_evidence", source_type="primary", cluster="record-1"),
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="reporting-1"),
            source(support="contradicts", category="credible_contradiction", source_type="secondary", cluster="contradiction-1"),
        ]
    )

    assert result["verdict"] == "Partly supported"
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


def test_interpretive_dispute_does_not_downgrade_supported_factual_core_to_unverified():
    sources = [
        source(support="supports", category="credible_reporting", source_type="secondary", score=3.8, cluster="reporting-1"),
        source(support="supports", category="credible_reporting", source_type="secondary", score=3.7, cluster="reporting-2"),
        source(support="mixed", category="credible_reporting", source_type="secondary", score=3.6, cluster="analysis-1"),
        source(support="mixed", category="credible_reporting", source_type="secondary", score=3.5, cluster="analysis-2"),
    ]
    result = verdict_for(
        sources,
        subclaims=[subclaim(claim_type="factual", risk_flags=["ambiguity", "legal_interpretation"])],
    )

    assert result["soft_claim"] is True
    assert result["stats"]["supportive_evidence"] == 2
    assert result["stats"]["contradictory_evidence"] == 0
    assert result["stats"]["mixed_sources"] == 2
    assert result["verdict"] == "Likely supported"
    assert result["confidence"] == "Medium"
    assert "interpretive" in result["rationale"] or "legally contested" in result["rationale"]

    overstated = align_reasoning_with_rules(
        {"verified_verdict": "Supported", "verified_confidence": "High"},
        result,
    )
    assert overstated["verified_verdict"] == "Likely supported"
    assert overstated["verified_confidence"] == "Medium"

    understated = align_reasoning_with_rules(
        {"verified_verdict": "Unverified", "verified_confidence": "Medium"},
        result,
    )
    assert understated["verified_verdict"] == "Likely supported"
    assert understated["verified_confidence"] == "Medium"


def test_nicholas_regression_trump_invades_cuba_is_confidently_false_when_contradicted():
    result = verdict_for(
        [
            source(support="contradicts", category="credible_contradiction", source_type="secondary", cluster="bbc-no-invasion"),
            source(support="contradicts", category="credible_contradiction", source_type="primary", cluster="official-no-invasion"),
        ],
        subclaims=[subclaim(claim_type="factual")],
        pendulum_band="Contradicted by evidence",
    )

    assert result["verdict"] == "False / contradicted"
    assert result["confidence"] == "High"


def test_nicholas_regression_red_roses_success_claim_is_not_plain_unverified():
    result = verdict_for(
        [
            source(support="supports", category="credible_reporting", source_type="secondary", score=3.8, cluster="six-nations-record"),
            source(support="supports", category="expert_analysis", source_type="secondary", score=3.6, cluster="world-cup-record"),
            source(support="supports", category="credible_reporting", source_type="secondary", score=3.7, cluster="win-streak-record"),
        ],
        subclaims=[subclaim(claim_type="opinion", risk_flags=["value_judgment", "ambiguity"])],
    )

    assert result["soft_claim"] is True
    assert result["verdict"] == "Likely supported"
    assert result["confidence"] == "Medium"


def test_nicholas_regression_reported_covert_attack_is_reported_but_unconfirmed():
    result = verdict_for(
        [
            source(support="supports", category="reported_allegation", source_type="secondary", score=3.5, cluster="regional-reporting"),
            source(support="supports", category="contextual_signal", source_type="secondary", score=3.3, cluster="security-analysis"),
            source(support="mixed", category="denial_or_rebuttal", source_type="primary", score=4.2, cluster="official-denial"),
        ],
        subclaims=[subclaim(claim_type="foreign_agent")],
    )

    assert result["verdict"] == "Reported but unconfirmed"
    assert result["confidence"] == "Medium"


def test_nicholas_regression_currently_cancelled_event_with_official_rebuttal_is_false():
    result = verdict_for(
        [
            source(support="contradicts", category="credible_contradiction", source_type="official", score=4.8, cluster="police-statement"),
            source(support="contradicts", category="credible_reporting", source_type="secondary", score=4.0, cluster="bbc-report"),
        ],
        subclaims=[subclaim(claim_type="factual")],
    )

    assert result["verdict"] == "False / contradicted"
    assert result["confidence"] == "High"
