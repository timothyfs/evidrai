from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable

from evidrai.api_models import AssessmentResponse
from evidrai.benchmark.dataset import BenchmarkClaim, load_claims, scorable_claims
from evidrai.benchmark.metrics import ScoredAssessment, score_assessment, summarise_scores

AssessmentCreator = Callable[[BenchmarkClaim], AssessmentResponse]


def _run_id() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_admin_benchmark(
    *,
    create_assessment: AssessmentCreator,
    include_held_out: bool = False,
    limit: int | None = None,
    fail_loud: bool = True,
    methodology_version: str = "benchmark-methodology-v1",
    model_version: str = "live-api-config",
) -> dict[str, Any]:
    claims = load_claims()
    selected = scorable_claims(claims, include_held_out=include_held_out)
    if limit is not None:
        selected = selected[: max(0, limit)]

    scores: list[ScoredAssessment] = []
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for claim in selected:
        try:
            assessment = create_assessment(claim)
            payload = assessment.model_dump(mode="json")
            score = score_assessment(
                claim_id=claim.id,
                label=claim.label,
                domain=claim.domain,
                verdict_type=claim.verdict_type,
                difficulty=claim.difficulty,
                split=claim.split,
                assessment=payload,
            )
            scores.append(score)
            rows.append({"claim": asdict(claim), "assessment": payload, "score": asdict(score)})
        except Exception as exc:
            failures.append({"claim_id": claim.id, "error": str(exc)})

    ok = not failures or not fail_loud
    return {
        "ok": ok,
        "run_id": _run_id(),
        "methodology_version": methodology_version,
        "model_version": model_version,
        "include_held_out": include_held_out,
        "dataset_size": len(claims),
        "selected_size": len(selected),
        "scored_size": len(scores),
        "failure_count": len(failures),
        "failures": failures,
        "metrics": summarise_scores(scores),
        "results": rows,
    }

