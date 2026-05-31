from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from evidrai.config import database_url
from evidrai.db import run_migrations


@dataclass(frozen=True)
class SourceScoreWeights:
    authority: float = 0.30
    relevance: float = 0.25
    directness: float = 0.20
    independence: float = 0.10
    recency: float = 0.10
    bias_risk: float = 0.05


@dataclass(frozen=True)
class ScoringPolicy:
    schema_version: str = "scoring_policy.v1"
    version: int = 1
    updated_at: str = ""
    updated_by: str = "system"
    change_note: str = "Default Evidrai scoring policy."
    source_score_weights: SourceScoreWeights = field(default_factory=SourceScoreWeights)
    source_type_authority: Dict[str, float] = field(default_factory=lambda: {
        "scientific": 5.0,
        "government": 4.7,
        "legal": 4.6,
        "primary": 4.5,
        "secondary": 3.4,
        "news": 2.8,
        "contextual": 2.2,
    })
    source_type_independence: Dict[str, float] = field(default_factory=lambda: {
        "scientific": 5.0,
        "government": 4.5,
        "legal": 4.4,
        "primary": 4.3,
        "secondary": 3.2,
        "news": 2.4,
        "contextual": 2.0,
    })
    source_type_bias_risk: Dict[str, float] = field(default_factory=lambda: {
        "scientific": 1.2,
        "government": 1.6,
        "legal": 1.8,
        "primary": 1.8,
        "secondary": 2.6,
        "news": 3.3,
        "contextual": 3.7,
    })
    notes: list[str] = field(default_factory=lambda: [
        "Scientific sources start highest for independence when directly relevant.",
        "Government and legal sources follow, but still depend on claim fit and directness.",
        "News sources are judged more harshly because political/editorial framing and shared source chains can inflate apparent confidence.",
        "Scores are decision-support signals, not truth labels. Weight changes must remain auditable.",
    ])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_scoring_policy() -> ScoringPolicy:
    return ScoringPolicy(updated_at=_now())


def _policy_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".evidrai_scoring_policy.json"


def _history_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".evidrai_scoring_history.jsonl"


def _coerce_policy(payload: Dict[str, Any]) -> ScoringPolicy:
    weights = payload.get("source_score_weights") or {}
    return ScoringPolicy(
        schema_version=str(payload.get("schema_version") or "scoring_policy.v1"),
        version=int(payload.get("version") or 1),
        updated_at=str(payload.get("updated_at") or _now()),
        updated_by=str(payload.get("updated_by") or "system"),
        change_note=str(payload.get("change_note") or ""),
        source_score_weights=SourceScoreWeights(**{**asdict(SourceScoreWeights()), **weights}),
        source_type_authority={**default_scoring_policy().source_type_authority, **dict(payload.get("source_type_authority") or {})},
        source_type_independence={**default_scoring_policy().source_type_independence, **dict(payload.get("source_type_independence") or {})},
        source_type_bias_risk={**default_scoring_policy().source_type_bias_risk, **dict(payload.get("source_type_bias_risk") or {})},
        notes=list(payload.get("notes") or default_scoring_policy().notes),
    )


def policy_to_dict(policy: ScoringPolicy) -> Dict[str, Any]:
    return asdict(policy)


def _psycopg():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg, dict_row


def _connect():
    psycopg, dict_row = _psycopg()
    return psycopg.connect(database_url(), row_factory=dict_row)


def _load_from_db() -> ScoringPolicy | None:
    if not database_url():
        return None
    try:
        run_migrations(_connect)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM scoring_policy_versions ORDER BY version DESC LIMIT 1")
                row = cur.fetchone()
                if not row:
                    return None
                return _coerce_policy(dict(row["payload"] or {}))
    except Exception:
        return None


def _save_to_db(policy: ScoringPolicy) -> None:
    if not database_url():
        return
    run_migrations(_connect)
    payload = policy_to_dict(policy)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scoring_policy_versions (version, updated_at, updated_by, change_note, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (version) DO UPDATE SET
                    updated_at = EXCLUDED.updated_at,
                    updated_by = EXCLUDED.updated_by,
                    change_note = EXCLUDED.change_note,
                    payload = EXCLUDED.payload
                """,
                (policy.version, policy.updated_at, policy.updated_by, policy.change_note, json.dumps(payload)),
            )
        conn.commit()


def get_scoring_policy() -> ScoringPolicy:
    db_policy = _load_from_db()
    if db_policy:
        return db_policy
    path = _policy_path()
    if path.exists():
        try:
            return _coerce_policy(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return default_scoring_policy()


def list_scoring_policy_history(limit: int = 25) -> list[Dict[str, Any]]:
    if database_url():
        try:
            run_migrations(_connect)
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT payload FROM scoring_policy_versions ORDER BY version DESC LIMIT %s", (limit,))
                    return [dict(row["payload"] or {}) for row in cur.fetchall()]
        except Exception:
            pass
    path = _history_path()
    if not path.exists():
        return [policy_to_dict(get_scoring_policy())]
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(rows[-limit:])) or [policy_to_dict(get_scoring_policy())]


def update_scoring_policy(update: Dict[str, Any], *, updated_by: str = "admin", change_note: str = "") -> ScoringPolicy:
    current = get_scoring_policy()
    merged = policy_to_dict(current)
    for key in ("source_score_weights", "source_type_authority", "source_type_independence", "source_type_bias_risk"):
        if isinstance(update.get(key), dict):
            merged[key] = {**dict(merged.get(key) or {}), **dict(update[key])}
    if isinstance(update.get("notes"), list):
        merged["notes"] = update["notes"]
    merged["version"] = int(current.version) + 1
    merged["updated_at"] = _now()
    merged["updated_by"] = updated_by or "admin"
    merged["change_note"] = change_note or str(update.get("change_note") or "Admin scoring policy update.")
    policy = _coerce_policy(merged)
    payload = policy_to_dict(policy)
    _policy_path().write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with _history_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
    _save_to_db(policy)
    return policy


def weight_sum(policy: ScoringPolicy | None = None) -> float:
    w = (policy or get_scoring_policy()).source_score_weights
    return round(w.authority + w.relevance + w.directness + w.independence + w.recency + w.bias_risk, 6)
