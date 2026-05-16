from evidrai.api_models import AssessmentEvidenceSource, AssessmentVerdict
from evidrai.enums import (
    normalize_claim_support_label,
    normalize_confidence_label,
    normalize_evidence_category_label,
    normalize_source_role_label,
    normalize_verdict_label,
)
from evidrai.export import assessment_export_payload


def test_contract_enums_normalize_common_drift():
    assert normalize_verdict_label("TRUE") == "Supported"
    assert normalize_verdict_label("partially_true") == "Misleading framing"
    assert normalize_verdict_label("nonsense") == "Unverified"
    assert normalize_confidence_label(72) == "High"
    assert normalize_confidence_label("unknown") == "Medium"
    assert normalize_claim_support_label("supporting") == "supports"
    assert normalize_evidence_category_label("credible reporting") == "credible_reporting"
    assert normalize_source_role_label("supports_factual_core") == "evidence"


def test_api_models_apply_enum_normalization():
    verdict = AssessmentVerdict(label="TRUE", confidence=25)
    source = AssessmentEvidenceSource(
        id="src_1",
        stance="supporting",
        evidence_category="credible reporting",
        source_role="supports_factual_core",
    )

    assert verdict.label == "Supported"
    assert verdict.confidence == "Low"
    assert source.stance == "supports"
    assert source.evidence_category == "credible_reporting"
    assert source.source_role == "evidence"


def test_assessment_export_excludes_raw_content_and_includes_trace():
    payload = assessment_export_payload(
        {
            "verified_verdict": "TRUE",
            "verified_confidence": 80,
            "claim": "Typed claim",
            "sources": [
                {
                    "title": "Source",
                    "url": "https://example.com/source",
                    "domain": "example.com",
                    "source_type": "primary",
                    "summary": "Public summary",
                    "content": "raw fetched content should not export",
                    "claim_support": "supporting",
                    "evidence_category": "direct evidence",
                    "source_role": "supports_factual_core",
                    "weighted_score": 4.2,
                }
            ],
            "debug_trace": {"schema_version": "pipeline_trace.v1", "normalized_claim": "Typed claim"},
        },
        claim="Typed claim",
        mode="deep",
        include_debug=True,
    )

    assert payload["export_version"] == "assessment_export.v1"
    assert payload["schema_version"] == "assessment_response.v1"
    assert payload["verdict"]["label"] == "Supported"
    assert payload["sources"][0]["summary"] == "Public summary"
    assert "content" not in payload["sources"][0]
    assert payload["debug"]["schema_version"] == "pipeline_trace.v1"
