from evidrai.pipeline.verification import select_audit_claims


def test_select_audit_claims_prioritizes_high_checkable_claims():
    claims = [
        {"normalized_claim": "Minor applause line", "checkability": "rhetoric", "priority": "high"},
        {"normalized_claim": "Low priority detail", "checkability": "checkable", "priority": "low"},
        {"normalized_claim": "High impact factual claim", "checkability": "checkable", "priority": "high"},
        {"normalized_claim": "Medium partly checkable claim", "checkability": "partly_checkable", "priority": "medium"},
    ]

    selected = select_audit_claims(claims, 2)

    assert [claim["normalized_claim"] for claim in selected] == [
        "High impact factual claim",
        "Medium partly checkable claim",
    ]


def test_select_audit_claims_filters_empty_and_rhetorical_claims():
    claims = [
        {"normalized_claim": "", "quote": "", "checkability": "checkable", "priority": "high"},
        {"normalized_claim": "We are the greatest", "checkability": "rhetoric", "priority": "high"},
        {"quote": "GDP rose by 3 percent", "checkability": "checkable", "priority": "medium"},
    ]

    selected = select_audit_claims(claims, 5)

    assert len(selected) == 1
    assert selected[0]["quote"] == "GDP rose by 3 percent"
