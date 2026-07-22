from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


VERDICT_TO_LABEL = {
    "supported": "true",
    "likely supported": "true",
    "true": "true",
    "not supported by credible evidence": "false",
    "false / contradicted": "false",
    "weakly supported / likely incorrect": "false",
    "false": "false",
    "partly supported": "mixed",
    "misleading framing": "mixed",
    "contested": "mixed",
    "mixed": "mixed",
    "reported but unconfirmed": "unresolved",
    "unverified": "unresolved",
    "unverifiable": "unresolved",
    "unresolved": "unresolved",
}


@dataclass(frozen=True)
class ScoredAssessment:
    claim_id: str
    label: str
    predicted_label: str
    predicted_verdict: str
    confidence: int
    correct: bool
    domain: str
    verdict_type: str
    difficulty: str
    split: str
    assessment_id: str = ""


def normalise_label(value: str) -> str:
    key = (value or "").strip().lower()
    return VERDICT_TO_LABEL.get(key, key)


def extract_confidence(assessment: dict[str, Any]) -> int:
    verdict = assessment.get("verdict") if isinstance(assessment.get("verdict"), dict) else {}
    candidates = (
        verdict.get("confidence_score"),
        assessment.get("confidence_score"),
        assessment.get("verified_confidence_score"),
        assessment.get("reasoning", {}).get("confidence_score") if isinstance(assessment.get("reasoning"), dict) else None,
    )
    for candidate in candidates:
        try:
            if candidate is not None and candidate != "":
                return max(0, min(100, int(round(float(candidate)))))
        except (TypeError, ValueError):
            continue
    label = str(verdict.get("confidence") or assessment.get("verified_confidence") or "").strip()
    return {"High": 85, "Medium": 58, "Low": 35}.get(label, 50)


def score_assessment(
    *,
    claim_id: str,
    label: str,
    domain: str,
    verdict_type: str,
    difficulty: str,
    split: str,
    assessment: dict[str, Any],
) -> ScoredAssessment:
    verdict_payload = assessment.get("verdict") if isinstance(assessment.get("verdict"), dict) else {}
    predicted_verdict = str(verdict_payload.get("label") or assessment.get("verified_verdict") or "Unverified")
    predicted_label = normalise_label(predicted_verdict)
    return ScoredAssessment(
        claim_id=claim_id,
        label=label,
        predicted_label=predicted_label,
        predicted_verdict=predicted_verdict,
        confidence=extract_confidence(assessment),
        correct=predicted_label == label,
        domain=domain,
        verdict_type=verdict_type,
        difficulty=difficulty,
        split=split,
        assessment_id=str(assessment.get("assessment_id") or ""),
    )


def reliability_bins(scores: list[ScoredAssessment]) -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    for lower in range(0, 100, 10):
        upper = lower + 10
        bucket = [score for score in scores if (lower <= score.confidence <= upper if upper == 100 else lower <= score.confidence < upper)]
        if not bucket:
            bins.append({"bucket": f"{lower}-{upper}", "count": 0, "avg_confidence": None, "accuracy": None, "gap": None})
            continue
        avg_confidence = sum(score.confidence for score in bucket) / len(bucket) / 100
        accuracy = sum(1 for score in bucket if score.correct) / len(bucket)
        bins.append({"bucket": f"{lower}-{upper}", "count": len(bucket), "avg_confidence": round(avg_confidence, 4), "accuracy": round(accuracy, 4), "gap": round(avg_confidence - accuracy, 4)})
    return bins


def expected_calibration_error(scores: list[ScoredAssessment]) -> float:
    if not scores:
        return 0.0
    total = 0.0
    for bucket in reliability_bins(scores):
        if bucket["count"]:
            total += (bucket["count"] / len(scores)) * abs(bucket["avg_confidence"] - bucket["accuracy"])
    return round(total, 4)


def brier_score(scores: list[ScoredAssessment]) -> float:
    if not scores:
        return 0.0
    return round(sum(((score.confidence / 100) - (1.0 if score.correct else 0.0)) ** 2 for score in scores) / len(scores), 4)


def grouped_accuracy(scores: list[ScoredAssessment], field: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[ScoredAssessment]] = defaultdict(list)
    for score in scores:
        grouped[str(getattr(score, field))].append(score)
    return {
        key: {
            "count": len(values),
            "accuracy": round(sum(1 for score in values if score.correct) / len(values), 4),
            "avg_confidence": round(sum(score.confidence for score in values) / len(values) / 100, 4),
        }
        for key, values in sorted(grouped.items())
    }


def summarise_scores(scores: list[ScoredAssessment]) -> dict[str, Any]:
    accuracy = sum(1 for score in scores if score.correct) / len(scores) if scores else 0.0
    return {
        "claim_count": len(scores),
        "accuracy": round(accuracy, 4),
        "ece": expected_calibration_error(scores),
        "brier_score": brier_score(scores),
        "reliability_bins": reliability_bins(scores),
        "accuracy_by_verdict_type": grouped_accuracy(scores, "verdict_type"),
        "accuracy_by_domain": grouped_accuracy(scores, "domain"),
        "accuracy_by_difficulty": grouped_accuracy(scores, "difficulty"),
        "overconfident_wrong_claim_ids": [score.claim_id for score in scores if not score.correct and score.confidence >= 70],
        "underconfident_correct_claim_ids": [score.claim_id for score in scores if score.correct and score.confidence < 50],
    }

