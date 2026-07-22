from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

GroundTruthLabel = Literal["true", "false", "mixed", "unresolved", "excluded"]
Split = Literal["visible", "held_out"]


@dataclass(frozen=True)
class GroundTruthSource:
    title: str
    url: str
    source_type: str
    note: str = ""


@dataclass(frozen=True)
class BenchmarkClaim:
    id: str
    claim: str
    label: GroundTruthLabel
    domain: str
    difficulty: Literal["easy", "hard"]
    verdict_type: str
    split: Split
    rationale: str
    ground_truth_sources: list[GroundTruthSource]
    excluded_reason: str | None = None
    added_at: str = ""
    version: str = "benchmark-v1"
    tags: list[str] = field(default_factory=list)

    @property
    def is_scorable(self) -> bool:
        return self.label != "excluded" and self.excluded_reason is None


def _expect_string(value: Any, field_name: str, claim_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{claim_id}: missing or invalid {field_name}")
    return value.strip()


def parse_claim(row: dict[str, Any]) -> BenchmarkClaim:
    claim_id = _expect_string(row.get("id"), "id", "<unknown>")
    raw_sources = row.get("ground_truth_sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError(f"{claim_id}: every benchmark claim needs at least one ground-truth source")
    sources = [
        GroundTruthSource(
            title=_expect_string(source.get("title"), "source.title", claim_id),
            url=_expect_string(source.get("url"), "source.url", claim_id),
            source_type=_expect_string(source.get("source_type"), "source.source_type", claim_id),
            note=str(source.get("note") or "").strip(),
        )
        for source in raw_sources
        if isinstance(source, dict)
    ]
    if len(sources) != len(raw_sources):
        raise ValueError(f"{claim_id}: every ground-truth source must be an object")

    label = _expect_string(row.get("label"), "label", claim_id)
    if label not in {"true", "false", "mixed", "unresolved", "excluded"}:
        raise ValueError(f"{claim_id}: invalid label {label!r}")
    split = _expect_string(row.get("split"), "split", claim_id)
    if split not in {"visible", "held_out"}:
        raise ValueError(f"{claim_id}: invalid split {split!r}")
    difficulty = _expect_string(row.get("difficulty"), "difficulty", claim_id)
    if difficulty not in {"easy", "hard"}:
        raise ValueError(f"{claim_id}: invalid difficulty {difficulty!r}")
    excluded_reason = row.get("excluded_reason")
    if label == "excluded" and not excluded_reason:
        raise ValueError(f"{claim_id}: excluded claims must publish an excluded_reason")

    return BenchmarkClaim(
        id=claim_id,
        claim=_expect_string(row.get("claim"), "claim", claim_id),
        label=label,  # type: ignore[arg-type]
        domain=_expect_string(row.get("domain"), "domain", claim_id),
        difficulty=difficulty,  # type: ignore[arg-type]
        verdict_type=_expect_string(row.get("verdict_type"), "verdict_type", claim_id),
        split=split,  # type: ignore[arg-type]
        rationale=_expect_string(row.get("rationale"), "rationale", claim_id),
        ground_truth_sources=sources,
        excluded_reason=str(excluded_reason).strip() if excluded_reason else None,
        added_at=str(row.get("added_at") or "").strip(),
        version=str(row.get("version") or "benchmark-v1").strip(),
        tags=[str(tag).strip() for tag in row.get("tags", []) if str(tag).strip()],
    )


def default_dataset_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "benchmark" / "claims_v1.jsonl"


def load_claims(path: str | Path | None = None) -> list[BenchmarkClaim]:
    dataset_path = Path(path) if path else default_dataset_path()
    claims: list[BenchmarkClaim] = []
    seen: set[str] = set()
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset_path}:{line_no}: invalid JSONL row: {exc}") from exc
            claim = parse_claim(row)
            if claim.id in seen:
                raise ValueError(f"{dataset_path}:{line_no}: duplicate claim id {claim.id}")
            seen.add(claim.id)
            claims.append(claim)
    if not claims:
        raise ValueError(f"{dataset_path}: dataset is empty")
    return claims


def scorable_claims(claims: Iterable[BenchmarkClaim], include_held_out: bool) -> list[BenchmarkClaim]:
    return [claim for claim in claims if claim.is_scorable and (include_held_out or claim.split == "visible")]

