from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Python 3.9-compatible StrEnum shim."""

    pass


class VerdictLabel(StrEnum):
    SUPPORTED = "Supported"
    LIKELY_SUPPORTED = "Likely supported"
    PARTLY_SUPPORTED = "Partly supported"
    MISLEADING_FRAMING = "Misleading framing"
    CONTESTED = "Contested"
    REPORTED_UNCONFIRMED = "Reported but unconfirmed"
    UNVERIFIED = "Unverified"
    WEAKLY_SUPPORTED = "Weakly supported / likely incorrect"
    NOT_SUPPORTED = "Not supported by credible evidence"
    FALSE_CONTRADICTED = "False / contradicted"


class ConfidenceLabel(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ClaimSupportLabel(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"
    IRRELEVANT = "irrelevant"


class EvidenceCategory(StrEnum):
    DIRECT_EVIDENCE = "direct_evidence"
    CREDIBLE_REPORTING = "credible_reporting"
    EXPERT_ANALYSIS = "expert_analysis"
    CREDIBLE_CONTRADICTION = "credible_contradiction"
    REPORTED_ALLEGATION = "reported_allegation"
    CONTEXTUAL_SIGNAL = "contextual_signal"
    DENIAL_OR_REBUTTAL = "denial_or_rebuttal"
    RUMOR_AMPLIFICATION = "rumor_amplification"
    IRRELEVANT = "irrelevant"


class SourceRole(StrEnum):
    EVIDENCE = "evidence"
    CONTEXT = "context"
    RUMOR = "rumor"
    CONTRADICTION = "contradiction"


_VERDICT_ALIASES = {
    "true": VerdictLabel.SUPPORTED,
    "supported": VerdictLabel.SUPPORTED,
    "supports": VerdictLabel.SUPPORTED,
    "likely supported": VerdictLabel.LIKELY_SUPPORTED,
    "partly supported": VerdictLabel.PARTLY_SUPPORTED,
    "partially supported": VerdictLabel.PARTLY_SUPPORTED,
    "partially_true": VerdictLabel.MISLEADING_FRAMING,
    "partially true": VerdictLabel.MISLEADING_FRAMING,
    "misleading": VerdictLabel.MISLEADING_FRAMING,
    "misleading framing": VerdictLabel.MISLEADING_FRAMING,
    "contested": VerdictLabel.CONTESTED,
    "reported but unconfirmed": VerdictLabel.REPORTED_UNCONFIRMED,
    "unconfirmed": VerdictLabel.REPORTED_UNCONFIRMED,
    "false": VerdictLabel.FALSE_CONTRADICTED,
    "false / contradicted": VerdictLabel.FALSE_CONTRADICTED,
    "contradicted": VerdictLabel.FALSE_CONTRADICTED,
    "not supported": VerdictLabel.NOT_SUPPORTED,
    "not supported by credible evidence": VerdictLabel.NOT_SUPPORTED,
    "weakly supported": VerdictLabel.WEAKLY_SUPPORTED,
    "weakly supported / likely incorrect": VerdictLabel.WEAKLY_SUPPORTED,
    "unverifiable": VerdictLabel.UNVERIFIED,
    "unverified": VerdictLabel.UNVERIFIED,
}


_SUPPORT_ALIASES = {
    "supports": ClaimSupportLabel.SUPPORTS,
    "support": ClaimSupportLabel.SUPPORTS,
    "supporting": ClaimSupportLabel.SUPPORTS,
    "contradicts": ClaimSupportLabel.CONTRADICTS,
    "contradict": ClaimSupportLabel.CONTRADICTS,
    "contradicting": ClaimSupportLabel.CONTRADICTS,
    "mixed": ClaimSupportLabel.MIXED,
    "partly": ClaimSupportLabel.MIXED,
    "neutral": ClaimSupportLabel.IRRELEVANT,
    "context": ClaimSupportLabel.IRRELEVANT,
    "irrelevant": ClaimSupportLabel.IRRELEVANT,
}


_EVIDENCE_CATEGORY_ALIASES = {
    "direct evidence": EvidenceCategory.DIRECT_EVIDENCE,
    "direct_evidence": EvidenceCategory.DIRECT_EVIDENCE,
    "credible reporting": EvidenceCategory.CREDIBLE_REPORTING,
    "credible_reporting": EvidenceCategory.CREDIBLE_REPORTING,
    "expert analysis": EvidenceCategory.EXPERT_ANALYSIS,
    "expert_analysis": EvidenceCategory.EXPERT_ANALYSIS,
    "credible contradiction": EvidenceCategory.CREDIBLE_CONTRADICTION,
    "credible_contradiction": EvidenceCategory.CREDIBLE_CONTRADICTION,
    "reported allegation": EvidenceCategory.REPORTED_ALLEGATION,
    "reported_allegation": EvidenceCategory.REPORTED_ALLEGATION,
    "contextual signal": EvidenceCategory.CONTEXTUAL_SIGNAL,
    "contextual_signal": EvidenceCategory.CONTEXTUAL_SIGNAL,
    "denial or rebuttal": EvidenceCategory.DENIAL_OR_REBUTTAL,
    "denial_or_rebuttal": EvidenceCategory.DENIAL_OR_REBUTTAL,
    "rumor amplification": EvidenceCategory.RUMOR_AMPLIFICATION,
    "rumour amplification": EvidenceCategory.RUMOR_AMPLIFICATION,
    "rumor_amplification": EvidenceCategory.RUMOR_AMPLIFICATION,
    "irrelevant": EvidenceCategory.IRRELEVANT,
    "context": EvidenceCategory.CONTEXTUAL_SIGNAL,
}


_SOURCE_ROLE_ALIASES = {
    "evidence": SourceRole.EVIDENCE,
    "support": SourceRole.EVIDENCE,
    "supports_factual_core": SourceRole.EVIDENCE,
    "context": SourceRole.CONTEXT,
    "context_only": SourceRole.CONTEXT,
    "rumor": SourceRole.RUMOR,
    "rumour": SourceRole.RUMOR,
    "amplification": SourceRole.RUMOR,
    "contradiction": SourceRole.CONTRADICTION,
    "contradicts": SourceRole.CONTRADICTION,
}


def _normalise_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def normalize_verdict_label(value: object) -> str:
    key = _normalise_key(value).replace("_", " ")
    return _VERDICT_ALIASES.get(key, VerdictLabel.UNVERIFIED).value


def normalize_confidence_label(value: object) -> str:
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        score = int(float(value))
        if score >= 70:
            return ConfidenceLabel.HIGH.value
        if score >= 45:
            return ConfidenceLabel.MEDIUM.value
        return ConfidenceLabel.LOW.value
    text = str(value or "").strip().title()
    if text in {item.value for item in ConfidenceLabel}:
        return text
    return ConfidenceLabel.MEDIUM.value


def normalize_claim_support_label(value: object) -> str:
    key = _normalise_key(value).replace("_", " ")
    return _SUPPORT_ALIASES.get(key, ClaimSupportLabel.IRRELEVANT).value


def normalize_evidence_category_label(value: object) -> str:
    key = _normalise_key(value)
    readable = key.replace("_", " ")
    return _EVIDENCE_CATEGORY_ALIASES.get(key, _EVIDENCE_CATEGORY_ALIASES.get(readable, EvidenceCategory.IRRELEVANT)).value


def normalize_source_role_label(value: object) -> str:
    key = _normalise_key(value)
    readable = key.replace("_", " ")
    return _SOURCE_ROLE_ALIASES.get(key, _SOURCE_ROLE_ALIASES.get(readable, SourceRole.CONTEXT)).value
