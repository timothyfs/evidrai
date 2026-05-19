from evidrai.claim_semantics import analyze_claim_semantics, merge_semantic_queries


def test_claim_semantics_groups_disclose_and_declare_but_preserves_precision_note():
    disclosed = analyze_claim_semantics("Nigel Farage failed to disclose £5m donations")
    declared = analyze_claim_semantics("Nigel Farage did not declare £5m donations")

    assert disclosed.canonical_claim_key == declared.canonical_claim_key
    assert "disclosure/reporting obligation" in disclosed.distinction_terms
    assert "formal declaration/register obligation" in declared.distinction_terms
    assert "does not collapse them into the same legal conclusion" in declared.precision_note


def test_claim_semantics_expands_retrieval_queries_for_professional_language_distinctions():
    semantics = analyze_claim_semantics("Nigel Farage did not declare £5m donations")
    queries = merge_semantic_queries(["Nigel Farage did not declare £5m donations"], semantics)
    joined = "\n".join(queries).lower()

    assert "disclose" in joined
    assert "declare" in joined
    assert "register" in joined
    assert "donations" in joined
