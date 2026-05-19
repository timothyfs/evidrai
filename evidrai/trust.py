from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4

from evidrai.api_models import AssessmentResponse
from evidrai.config import database_url
from evidrai.db import run_migrations

DEFAULT_TRUST_LOG_PATH = ".evidrai_trust/trust_events.jsonl"

TRUST_SIGNAL_LABELS: Dict[str, str] = {
    "evidence_weak": "This evidence was weak",
    "source_biased": "This source felt biased",
    "changed_view": "This changed my view",
    "needs_primary_sourcing": "This needs stronger primary sourcing",
    "balanced_explanation": "This explanation felt balanced",
    "manipulative_wording": "This wording felt emotionally manipulative",
    "overconfident": "This feels overconfident",
    "too_uncertain": "This feels too uncertain",
    "missed_context": "This missed important context",
    "has_counter_evidence": "I have counter-evidence",
    "source_unreliable": "This source seems unreliable",
    "persuasive_explanation": "This explanation was persuasive",
}

SOURCE_RELIABILITY_DELTAS: Dict[str, float] = {
    "source_biased": -0.2,
    "source_unreliable": -0.3,
    "needs_primary_sourcing": -0.1,
    "changed_view": 0.15,
    "persuasive_explanation": 0.1,
    "balanced_explanation": 0.05,
}


@dataclass(frozen=True)
class TrustSaveResult:
    ok: bool
    destination: str
    event_count: int = 0


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise RuntimeError(f"Postgres support requires psycopg: {exc}")
    return psycopg, dict_row


def trust_log_path() -> Path:
    return Path(os.getenv("EVIDRAI_TRUST_LOG_PATH") or DEFAULT_TRUST_LOG_PATH)


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def pseudonymous_actor_id(owner_id: str | None) -> str:
    if not owner_id:
        return ""
    salt = os.getenv("EVIDRAI_TRUST_HASH_SALT") or "evidrai-local-trust-salt"
    return hashlib.sha256(f"{salt}:{owner_id}".encode("utf-8")).hexdigest()


def _source_payload(source: Any) -> Dict[str, Any]:
    if hasattr(source, "model_dump"):
        return source.model_dump(mode="json")
    if isinstance(source, dict):
        return dict(source)
    return {}


def _cluster_values(sources: List[Dict[str, Any]]) -> List[str]:
    values = []
    for source in sources:
        value = str(source.get("narrative_cluster") or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def assessment_trust_snapshot(assessment: AssessmentResponse) -> Dict[str, Any]:
    payload = assessment.model_dump(mode="json")
    request = payload.get("request") or {}
    verdict = payload.get("verdict") or {}
    sources = [_source_payload(source) for source in (assessment.sources or [])]
    settings = request.get("settings") if isinstance(request.get("settings"), dict) else {}
    return {
        "schema_version": "trust_claim_check.v1",
        "assessment_id": assessment.assessment_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "created_at": payload.get("created_at"),
        "actor_hash": pseudonymous_actor_id(payload.get("owner_id") or ""),
        "claim": request.get("claim") or "",
        "source_url": request.get("source_url") or "",
        "category": request.get("category") or settings.get("category") or "",
        "mode": payload.get("mode") or "",
        "verdict": verdict.get("label") or "",
        "confidence": verdict.get("confidence") or "",
        "evidence_strength_score": verdict.get("evidence_strength_score"),
        "topic": settings.get("topic") or request.get("category") or "",
        "sensitivity_tags": settings.get("sensitivity_tags") or [],
        "narrative_clusters": _cluster_values(sources),
        "evidence_map": payload.get("evidence_map") or {},
        "claim_breakdown": payload.get("claim_breakdown") or [],
        "sources": sources,
        "payload": payload,
    }


def build_trust_events_from_feedback(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    assessment = record.get("assessment_output") if isinstance(record.get("assessment_output"), dict) else {}
    request = assessment.get("request") if isinstance(assessment.get("request"), dict) else {}
    sources = assessment.get("sources") if isinstance(assessment.get("sources"), list) else []
    source_by_id = {str(source.get("id") or ""): source for source in sources if isinstance(source, dict)}
    actor_hash = pseudonymous_actor_id(record.get("owner_id") or (assessment.get("owner_id") if isinstance(assessment, dict) else "") or "")
    base = {
        "assessment_id": record.get("assessment_id") or assessment.get("assessment_id") or "",
        "feedback_id": record.get("feedback_id") or "",
        "actor_hash": actor_hash,
        "created_at": record.get("captured_at") or datetime.now(timezone.utc).isoformat(),
        "claim_pattern": record.get("claim") or request.get("claim") or "",
    }
    events: List[Dict[str, Any]] = []
    accepted = record.get("accepted_verdict")
    if accepted in {"accepted", "rejected", "unsure"}:
        events.append({**base, "event_id": str(uuid4()), "signal_type": f"verdict_{accepted}", "sentiment": accepted, "target_type": "verdict", "details": {"rating": record.get("rating"), "comment": record.get("comment", "")}})

    for signal in record.get("trust_signals") or []:
        if not signal:
            continue
        signal_type = str(signal)
        events.append({**base, "event_id": str(uuid4()), "signal_type": signal_type, "sentiment": _signal_sentiment(signal_type), "target_type": "assessment", "details": {"label": TRUST_SIGNAL_LABELS.get(signal_type, signal_type), "rating": record.get("rating"), "comment": record.get("comment", "")}})

    for source_id in record.get("persuasive_source_ids") or []:
        source = source_by_id.get(str(source_id), {})
        events.append({**base, "event_id": str(uuid4()), "signal_type": "source_persuasive", "sentiment": "positive", "target_type": "source", "target_id": str(source_id), "source_id": str(source_id), "narrative_cluster": source.get("narrative_cluster", ""), "details": {"source": source}})

    for source_id in record.get("distrusted_source_ids") or []:
        source = source_by_id.get(str(source_id), {})
        events.append({**base, "event_id": str(uuid4()), "signal_type": "source_distrusted", "sentiment": "negative", "target_type": "source", "target_id": str(source_id), "source_id": str(source_id), "narrative_cluster": source.get("narrative_cluster", ""), "details": {"source": source}})

    if record.get("challenge_text"):
        events.append({**base, "event_id": str(uuid4()), "signal_type": "user_challenge", "sentiment": "challenge", "target_type": "assessment", "details": {"challenge_text": record.get("challenge_text", "")}})

    for item in record.get("counter_evidence") or []:
        events.append({**base, "event_id": str(uuid4()), "signal_type": "counter_evidence_submitted", "sentiment": "challenge", "target_type": "evidence", "details": item if isinstance(item, dict) else {"value": item}})

    return events


def _signal_sentiment(signal_type: str) -> str:
    if signal_type in {"changed_view", "balanced_explanation", "persuasive_explanation"}:
        return "positive"
    if signal_type in {"evidence_weak", "source_biased", "needs_primary_sourcing", "manipulative_wording", "overconfident", "too_uncertain", "missed_context", "has_counter_evidence", "source_unreliable"}:
        return "negative"
    return "neutral"


class TrustStore(Protocol):
    def save_assessment_snapshot(self, assessment: AssessmentResponse) -> TrustSaveResult:
        ...

    def save_feedback_events(self, record: Dict[str, Any]) -> TrustSaveResult:
        ...

    def analytics_summary(self, limit: int = 20) -> Dict[str, Any]:
        ...


class LocalTrustStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or trust_log_path()

    def _append(self, payload: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n")

    def save_assessment_snapshot(self, assessment: AssessmentResponse) -> TrustSaveResult:
        self._append({"event_kind": "assessment_snapshot", **assessment_trust_snapshot(assessment)})
        return TrustSaveResult(ok=True, destination="local_jsonl", event_count=1)

    def save_feedback_events(self, record: Dict[str, Any]) -> TrustSaveResult:
        events = build_trust_events_from_feedback(record)
        for event in events:
            self._append({"event_kind": "trust_signal", **event})
        return TrustSaveResult(ok=True, destination="local_jsonl", event_count=len(events))

    def analytics_summary(self, limit: int = 20) -> Dict[str, Any]:
        signals: Dict[str, int] = {}
        disputed: Dict[str, int] = {}
        verdicts: Dict[str, int] = {}
        domains: Dict[str, int] = {}
        recent: Dict[str, Dict[str, Any]] = {}
        source_count = 0
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if item.get("event_kind") == "assessment_snapshot":
                    assessment_id = item.get("assessment_id") or ""
                    if assessment_id:
                        recent[assessment_id] = {"assessment_id": assessment_id, "claim": item.get("claim") or "", "verdict": item.get("verdict") or "", "created_at": item.get("created_at") or item.get("captured_at")}
                    verdict = item.get("verdict") or "Unknown"
                    verdicts[verdict] = verdicts.get(verdict, 0) + 1
                    for source in item.get("sources") or []:
                        if isinstance(source, dict):
                            source_count += 1
                            domain = source.get("domain") or "unknown"
                            domains[domain] = domains.get(domain, 0) + 1
                if item.get("event_kind") == "trust_signal":
                    signal = item.get("signal_type") or "unknown"
                    signals[signal] = signals.get(signal, 0) + 1
                    if signal in {"verdict_rejected", "user_challenge", "counter_evidence_submitted"}:
                        claim = item.get("claim_pattern") or item.get("assessment_id") or "unknown"
                        disputed[claim] = disputed.get(claim, 0) + 1
        return {
            "ok": True,
            "backend": "local_jsonl",
            "summary": {"claim_checks": len(recent), "evidence_sources": source_count, "trust_signals": sum(signals.values()), "disputed_claims": sum(disputed.values())},
            "recent_claim_checks": sorted(recent.values(), key=lambda item: item.get("created_at") or "", reverse=True)[:limit],
            "verdict_distribution": _top_counts(verdicts, limit),
            "top_source_domains": _top_counts(domains, limit),
            "top_signals": _top_counts(signals, limit),
            "most_disputed_claims": _top_counts(disputed, limit),
            "source_reliability_observations": [],
        }


class PostgresTrustStore:
    def __init__(self, url: str) -> None:
        self.url = url
        self._schema_ready = False

    def _connect(self):
        psycopg, dict_row = _psycopg()
        return psycopg.connect(self.url, row_factory=dict_row)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        run_migrations(self._connect)
        self._schema_ready = True

    def save_assessment_snapshot(self, assessment: AssessmentResponse) -> TrustSaveResult:
        self._ensure_schema()
        snapshot = assessment_trust_snapshot(assessment)
        sources = snapshot.get("sources") or []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trust_claim_checks (
                        assessment_id, captured_at, created_at, actor_hash, claim, source_url, category, mode,
                        verdict, confidence, evidence_strength_score, topic, sensitivity_tags, narrative_clusters, payload, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (assessment_id) DO UPDATE SET
                        captured_at = EXCLUDED.captured_at,
                        created_at = EXCLUDED.created_at,
                        actor_hash = EXCLUDED.actor_hash,
                        claim = EXCLUDED.claim,
                        source_url = EXCLUDED.source_url,
                        category = EXCLUDED.category,
                        mode = EXCLUDED.mode,
                        verdict = EXCLUDED.verdict,
                        confidence = EXCLUDED.confidence,
                        evidence_strength_score = EXCLUDED.evidence_strength_score,
                        topic = EXCLUDED.topic,
                        sensitivity_tags = EXCLUDED.sensitivity_tags,
                        narrative_clusters = EXCLUDED.narrative_clusters,
                        payload = EXCLUDED.payload,
                        updated_at = now()
                    """,
                    (
                        snapshot["assessment_id"], snapshot["captured_at"], snapshot.get("created_at"), snapshot.get("actor_hash"),
                        snapshot.get("claim"), snapshot.get("source_url"), snapshot.get("category"), snapshot.get("mode"),
                        snapshot.get("verdict"), snapshot.get("confidence"), snapshot.get("evidence_strength_score"), snapshot.get("topic"),
                        snapshot.get("sensitivity_tags") or [], snapshot.get("narrative_clusters") or [], json.dumps(snapshot, default=_json_default),
                    ),
                )
                cur.execute("DELETE FROM trust_evidence_sources WHERE assessment_id = %s", (snapshot["assessment_id"],))
                for source in sources:
                    cur.execute(
                        """
                        INSERT INTO trust_evidence_sources (
                            assessment_id, source_id, url, domain, title, source_type, stance, evidence_category,
                            source_role, narrative_cluster, source_score, scoring_factors, payload
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                        """,
                        (
                            snapshot["assessment_id"], source.get("id"), source.get("url"), source.get("domain"), source.get("title"),
                            source.get("source_type"), source.get("stance"), source.get("evidence_category"), source.get("source_role"),
                            source.get("narrative_cluster"), source.get("score"), json.dumps(source.get("scoring_factors") or {}), json.dumps(source, default=_json_default),
                        ),
                    )
            conn.commit()
        return TrustSaveResult(ok=True, destination="postgres", event_count=1 + len(sources))

    def save_feedback_events(self, record: Dict[str, Any]) -> TrustSaveResult:
        self._ensure_schema()
        events = build_trust_events_from_feedback(record)
        counter_items = record.get("counter_evidence") or []
        with self._connect() as conn:
            with conn.cursor() as cur:
                for event in events:
                    cur.execute(
                        """
                        INSERT INTO trust_signal_events (
                            event_id, assessment_id, feedback_id, actor_hash, created_at, signal_type, sentiment,
                            target_type, target_id, source_id, claim_pattern, narrative_cluster, details
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (event_id) DO NOTHING
                        """,
                        (
                            event.get("event_id"), event.get("assessment_id") or None, event.get("feedback_id") or None, event.get("actor_hash") or None,
                            event.get("created_at"), event.get("signal_type"), event.get("sentiment"), event.get("target_type"), event.get("target_id"),
                            event.get("source_id"), event.get("claim_pattern"), event.get("narrative_cluster"), json.dumps(event.get("details") or {}, default=_json_default),
                        ),
                    )
                    if event.get("signal_type") in SOURCE_RELIABILITY_DELTAS or event.get("signal_type") == "source_distrusted":
                        details = event.get("details") or {}
                        source = details.get("source") if isinstance(details.get("source"), dict) else {}
                        delta = SOURCE_RELIABILITY_DELTAS.get(event.get("signal_type"), -0.25 if event.get("signal_type") == "source_distrusted" else 0)
                        cur.execute(
                            """
                            INSERT INTO source_reliability_observations (
                                observation_id, domain, source_url, source_id, assessment_id, feedback_id, actor_hash,
                                signal_type, reliability_delta, details
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                            """,
                            (str(uuid4()), source.get("domain"), source.get("url"), event.get("source_id"), event.get("assessment_id") or None, event.get("feedback_id") or None, event.get("actor_hash") or None, event.get("signal_type"), delta, json.dumps(details, default=_json_default)),
                        )
                for item in counter_items:
                    payload = item if isinstance(item, dict) else {"value": item}
                    cur.execute(
                        """
                        INSERT INTO trust_counter_evidence (
                            counter_evidence_id, assessment_id, feedback_id, actor_hash, url, text_excerpt, relationship, payload
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (str(uuid4()), record.get("assessment_id") or None, record.get("feedback_id") or None, pseudonymous_actor_id(record.get("owner_id") or "") or None, payload.get("url"), payload.get("text") or payload.get("text_excerpt"), payload.get("relationship") or "counter_evidence", json.dumps(payload, default=_json_default)),
                    )
            conn.commit()
        return TrustSaveResult(ok=True, destination="postgres", event_count=len(events))

    def analytics_summary(self, limit: int = 20) -> Dict[str, Any]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) AS count FROM trust_claim_checks")
                claim_count = int((cur.fetchone() or {}).get("count") or 0)
                cur.execute("SELECT count(*) AS count FROM trust_evidence_sources")
                source_count = int((cur.fetchone() or {}).get("count") or 0)
                cur.execute("SELECT count(*) AS count FROM trust_signal_events")
                signal_count = int((cur.fetchone() or {}).get("count") or 0)
                cur.execute("SELECT count(*) AS count FROM trust_counter_evidence")
                counter_count = int((cur.fetchone() or {}).get("count") or 0)
                cur.execute("SELECT assessment_id, claim, verdict, confidence, created_at FROM trust_claim_checks ORDER BY created_at DESC NULLS LAST, captured_at DESC LIMIT %s", (limit,))
                recent_claims = [dict(row) for row in cur.fetchall()]
                for row in recent_claims:
                    if hasattr(row.get("created_at"), "isoformat"):
                        row["created_at"] = row["created_at"].isoformat()
                cur.execute("SELECT verdict AS value, count(*) AS count FROM trust_claim_checks GROUP BY verdict ORDER BY count DESC LIMIT %s", (limit,))
                verdict_distribution = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT domain AS value, count(*) AS count FROM trust_evidence_sources WHERE domain IS NOT NULL AND domain <> '' GROUP BY domain ORDER BY count DESC LIMIT %s", (limit,))
                top_domains = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT signal_type, count(*) AS count FROM trust_signal_events GROUP BY signal_type ORDER BY count DESC LIMIT %s", (limit,))
                top_signals = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT coalesce(c.claim, e.claim_pattern, e.assessment_id) AS claim, count(*) AS count
                    FROM trust_signal_events e
                    LEFT JOIN trust_claim_checks c ON c.assessment_id = e.assessment_id
                    WHERE e.signal_type IN ('verdict_rejected', 'user_challenge', 'counter_evidence_submitted')
                    GROUP BY coalesce(c.claim, e.claim_pattern, e.assessment_id)
                    ORDER BY count DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                disputed = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT domain, sum(reliability_delta) AS reliability_delta, count(*) AS observations FROM source_reliability_observations WHERE domain IS NOT NULL GROUP BY domain ORDER BY observations DESC LIMIT %s", (limit,))
                source_reliability = [dict(row) for row in cur.fetchall()]
        return {"ok": True, "backend": "postgres", "summary": {"claim_checks": claim_count, "evidence_sources": source_count, "trust_signals": signal_count, "counter_evidence": counter_count, "disputed_claims": sum(int(row.get("count") or 0) for row in disputed)}, "recent_claim_checks": recent_claims, "verdict_distribution": verdict_distribution, "top_source_domains": top_domains, "top_signals": top_signals, "most_disputed_claims": disputed, "source_reliability_observations": source_reliability}


def _top_counts(values: Dict[str, int], limit: int) -> List[Dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]]


def get_trust_store() -> TrustStore:
    url = database_url()
    if url:
        return PostgresTrustStore(url)
    return LocalTrustStore()


def capture_assessment_snapshot(assessment: AssessmentResponse, store: Optional[TrustStore] = None) -> TrustSaveResult:
    return (store or get_trust_store()).save_assessment_snapshot(assessment)


def capture_feedback_trust_events(record: Dict[str, Any], store: Optional[TrustStore] = None) -> TrustSaveResult:
    return (store or get_trust_store()).save_feedback_events(record)




def backfill_trust_from_reports(limit: int = 1000, store: Optional[TrustStore] = None) -> Dict[str, Any]:
    from evidrai.reports import iter_assessments

    trust_store = store or get_trust_store()
    reports = iter_assessments(limit=limit)
    captured = 0
    failed = 0
    failures: List[Dict[str, str]] = []
    for assessment in reports:
        try:
            trust_store.save_assessment_snapshot(assessment)
            captured += 1
        except Exception as exc:
            failed += 1
            if len(failures) < 10:
                failures.append({"assessment_id": assessment.assessment_id, "error": str(exc)})
    return {
        "ok": failed == 0,
        "reports_seen": len(reports),
        "captured": captured,
        "failed": failed,
        "failures": failures,
    }


def trust_analytics_summary(limit: int = 20, store: Optional[TrustStore] = None) -> Dict[str, Any]:
    return (store or get_trust_store()).analytics_summary(limit=limit)
