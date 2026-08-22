from evidrai.models import SubClaim
from evidrai.rules.verdict import assess_amplification_risk, align_reasoning_with_rules, rule_based_verdict_from_evidence


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
    recency=4.0,
    cluster="cluster",
):
    return {
        "title": f"{support} {category}",
        "url": f"https://example.com/{cluster}/{support}/{category}",
        "source_type": source_type,
        "claim_support": support,
        "evidence_category": category,
        "weighted_score": score,
        "recency_score": recency,
        "narrative_cluster": cluster,
    }


def verdict_for(sources, subclaims=None, pendulum_band="Mixed / uncertain", claim_text="Test claim"):
    return rule_based_verdict_from_evidence(
        claim_text,
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


def test_settled_science_false_claim_is_not_timid_when_credibly_contradicted():
    result = verdict_for(
        [
            source(
                support="contradicts",
                category="credible_contradiction",
                source_type="secondary",
                score=4.6,
                cluster="science-reference",
            ),
        ],
        subclaims=[subclaim(claim_type="factual")],
        pendulum_band="Contradicted by evidence",
        claim_text="The Earth is flat.",
    )

    assert result["verdict"] == "False / contradicted"
    assert result["confidence"] == "High"


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


def test_amplification_warning_triggers_for_repeated_single_cluster_without_primary_support():
    warning = assess_amplification_risk(
        [
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="same-briefing"),
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="same-briefing"),
            source(support="supports", category="reported_allegation", source_type="secondary", cluster="same-briefing"),
            source(support="mixed", category="contextual_signal", source_type="secondary", cluster="same-briefing"),
        ]
    )

    assert warning["triggered"] is True
    assert warning["level"] == "high"
    assert warning["details"]["dominant_cluster_count"] == 4
    assert warning["details"]["primary_support_clusters"] == 0


def test_amplification_warning_stays_clear_for_independent_primary_and_reporting_chains():
    warning = assess_amplification_risk(
        [
            source(support="supports", category="direct_evidence", source_type="primary", cluster="court-record"),
            source(support="supports", category="credible_reporting", source_type="secondary", cluster="independent-reporting"),
            source(support="contradicts", category="credible_contradiction", source_type="secondary", cluster="independent-rebuttal"),
        ]
    )

    assert warning["triggered"] is False
    assert warning["level"] == "none"


def test_contradicted_claim_uses_clear_unsupported_framing():
    rule_view = verdict_for(
        [
            source(support="contradicts", category="credible_contradiction", source_type="secondary", cluster="fact-check"),
            source(support="mixed", category="rumor_amplification", source_type="secondary", cluster="rumor"),
        ],
        pendulum_band="Contradicted by evidence",
    )

    aligned = align_reasoning_with_rules(
        {
            "verified_verdict": "Unverified",
            "verified_confidence": "Low",
            "consensus_strength": "Weak agreement",
            "consensus_summary": "Reviewed sources contradict the claim.",
        },
        rule_view,
    )

    assert aligned["verified_verdict"] == "False / contradicted"
    assert aligned["consensus_strength"] == "Claim unsupported; credible contradiction found"
    assert aligned["consensus_summary"].startswith("Claim unsupported; credible contradiction found.")


def test_time_sensitive_claim_does_not_overweight_stale_secondary_contradiction():
    result = verdict_for(
        [
            source(
                support="contradicts",
                category="credible_contradiction",
                source_type="news",
                score=4.5,
                recency=1.0,
                cluster="old-pbs-context",
            ),
        ],
        subclaims=[subclaim(claim_type="factual")],
        pendulum_band="Contradicted by evidence",
        claim_text="A recent software release supports this capability",
    )

    assert result["stats"]["contradictory_evidence"] == 1
    assert result["stats"]["stale_contradictory_evidence"] == 1
    assert result["stats"]["high_quality_contradictory"] == 0
    assert result["verdict"] != "False / contradicted"


def test_acquisition_claim_with_only_partnership_evidence_is_not_plain_unverified():
    result = verdict_for(
        [
            source(support="mixed", category="contextual_signal", source_type="official", score=4.5, cluster="cisco-partnership")
            | {"title": "Cisco and Nutanix announce global strategic partnership"},
            source(support="supports", category="contextual_signal", source_type="secondary", score=3.9, cluster="partner-coverage")
            | {"summary": "The companies have partnered on a joint hybrid multicloud offering."},
            source(support="mixed", category="denial_or_rebuttal", source_type="secondary", score=3.7, cluster="rumor-rebuttal")
            | {"classification_reason": "Reports discuss partnership activity, not acquisition confirmation."},
        ],
        subclaims=[SubClaim(id="sc_1", text="Cisco is buying Nutanix", claim_type="factual", risk_flags=[])],
        claim_text="Cisco is buying Nutanix",
    )

    assert result["acquisition_partnership_rebuttal"]["triggered"] is True
    assert result["verdict"] == "Not supported by credible evidence"
    assert result["confidence"] == "Medium"
