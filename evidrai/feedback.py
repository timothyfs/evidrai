from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4

import requests

from evidrai.config import database_url, get_app_build, read_config_value, http_error_detail
from evidrai.db import run_migrations


NOTION_VERSION = "2025-09-03"
DEFAULT_FEEDBACK_LOG_PATH = ".evidrai_feedback/feedback.jsonl"


@dataclass(frozen=True)
class FeedbackResult:
    ok: bool
    destination: str
    message: str
    feedback_id: str


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise RuntimeError(f"Postgres support requires psycopg: {exc}")
    return psycopg, dict_row


class FeedbackStore(Protocol):
    """Persistence boundary for assessment feedback."""

    def save(self, record: Dict[str, Any]) -> FeedbackResult:
        ...

    def get_by_feedback_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_by_assessment(self, assessment_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        ...

    def list_recent(self, limit: int = 50, result_key: str = "") -> List[Dict[str, Any]]:
        ...


class PostgresFeedbackStore:
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

    def save(self, record: Dict[str, Any]) -> FeedbackResult:
        self._ensure_schema()
        feedback_id = record.get("feedback_id") or str(uuid4())
        record["feedback_id"] = feedback_id
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feedback (feedback_id, assessment_id, captured_at, rating, payload)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (feedback_id) DO UPDATE SET
                        assessment_id = EXCLUDED.assessment_id,
                        captured_at = EXCLUDED.captured_at,
                        rating = EXCLUDED.rating,
                        payload = EXCLUDED.payload
                    """,
                    (
                        feedback_id,
                        record.get("assessment_id"),
                        record.get("captured_at"),
                        record.get("rating"),
                        json.dumps(record),
                    ),
                )
            conn.commit()

        notion_url = None
        try:
            notion_url = create_notion_feedback_page(record)
        except Exception as exc:
            return FeedbackResult(ok=True, destination="postgres", message=f"Saved to Postgres. Notion logging failed: {exc}", feedback_id=feedback_id)

        if notion_url:
            return FeedbackResult(ok=True, destination="postgres+notion", message="Saved to Postgres and Notion.", feedback_id=feedback_id)
        return FeedbackResult(ok=True, destination="postgres", message="Saved to Postgres feedback store.", feedback_id=feedback_id)

    def get_by_feedback_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM feedback WHERE feedback_id = %s", (feedback_id,))
                row = cur.fetchone()
        if not row:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload

    def _payload_rows(self, rows: list[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            results.append(payload)
        return results

    def list_by_assessment(self, assessment_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload
                    FROM feedback
                    WHERE assessment_id = %s
                    ORDER BY captured_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (assessment_id, limit),
                )
                rows = cur.fetchall()
        return self._payload_rows(rows)

    def list_recent(self, limit: int = 50, result_key: str = "") -> List[Dict[str, Any]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                if result_key:
                    cur.execute(
                        """
                        SELECT payload
                        FROM feedback
                        WHERE payload->>'result_key' = %s
                        ORDER BY captured_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (result_key, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT payload
                        FROM feedback
                        ORDER BY captured_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()
        return self._payload_rows(rows)


class LocalFeedbackStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or feedback_log_path()

    def save(self, record: Dict[str, Any]) -> FeedbackResult:
        return _save_feedback_record(record, path=self.path)

    def get_by_feedback_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        return get_feedback_by_id(feedback_id, path=self.path)

    def list_by_assessment(self, assessment_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return list_feedback_by_assessment_id(assessment_id, limit=limit, path=self.path)

    def list_recent(self, limit: int = 50, result_key: str = "") -> List[Dict[str, Any]]:
        return list_recent_feedback(limit=limit, result_key=result_key, path=self.path)


def feedback_log_path() -> Path:
    configured = read_config_value(
        secret_paths=(("feedback", "log_path"), ("FEEDBACK_LOG_PATH",)),
        env_names=("FEEDBACK_LOG_PATH",),
        default=DEFAULT_FEEDBACK_LOG_PATH,
    )
    return Path(configured or DEFAULT_FEEDBACK_LOG_PATH)


def notion_feedback_database_id() -> Optional[str]:
    return read_config_value(
        secret_paths=(("notion", "feedback_database_id"), ("NOTION_FEEDBACK_DATABASE_ID",)),
        env_names=("NOTION_FEEDBACK_DATABASE_ID",),
    )


def notion_api_key() -> Optional[str]:
    return read_config_value(
        secret_paths=(("notion", "api_key"), ("NOTION_API_KEY",)),
        env_names=("NOTION_API_KEY",),
    )


def feedback_backend_status() -> Dict[str, Any]:
    return {
        "store": "postgres" if database_url() else "local_jsonl",
        "local_jsonl_log": str(feedback_log_path()),
        "postgres_configured": bool(database_url()),
        "notion_configured": bool(notion_api_key() and notion_feedback_database_id()),
        "notion_database_configured": bool(notion_feedback_database_id()),
    }


def build_feedback_record(
    *,
    result_key: str,
    rating: str,
    reasons: list[str],
    comment: str,
    result: Optional[Dict[str, Any]] = None,
    source_url: str = "",
    settings: Optional[Dict[str, Any]] = None,
    trust_signals: Optional[list[str]] = None,
    accepted_verdict: str = "",
    challenge_text: str = "",
    counter_evidence: Optional[list[Dict[str, Any]]] = None,
    persuasive_source_ids: Optional[list[str]] = None,
    distrusted_source_ids: Optional[list[str]] = None,
    owner_id: str = "",
) -> Dict[str, Any]:
    result = result or {}
    settings = settings or {}
    request = result.get("request") if isinstance(result.get("request"), dict) else {}
    claim = result.get("claim") or result.get("normalized_claim") or request.get("claim") or settings.get("claim") or settings.get("analysis_input") or ""
    return {
        "feedback_id": str(uuid4()),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "build": get_app_build(),
        "result_key": result_key,
        "rating": rating,
        "reasons": list(reasons or []),
        "trust_signals": list(trust_signals or []),
        "accepted_verdict": accepted_verdict,
        "challenge_text": (challenge_text or "").strip(),
        "counter_evidence": list(counter_evidence or []),
        "persuasive_source_ids": list(persuasive_source_ids or []),
        "distrusted_source_ids": list(distrusted_source_ids or []),
        "owner_id": owner_id or result.get("owner_id") or "",
        "comment": (comment or "").strip(),
        "claim": claim,
        "verdict": result.get("verified_verdict") or result.get("verdict") or "",
        "confidence": result.get("verified_confidence") or result.get("confidence") or "",
        "source_url": source_url or settings.get("source_url", ""),
        "result_id": result.get("result_id") or result_key,
        "assessment_id": result.get("assessment_id") or (result.get("assessment") or {}).get("assessment_id") or result.get("report_id") or "",
        "request": {
            "claim": claim,
            "source_url": source_url or settings.get("source_url", ""),
            "settings": dict(settings),
        },
        "assessment_output": result,
    }


def _plain_text(text: Any, limit: int = 1900) -> Dict[str, Any]:
    return {"type": "text", "text": {"content": str(text or "")[:limit]}}


def _paragraph(text: Any) -> Dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [_plain_text(text)]}}


def _heading(text: str) -> Dict[str, Any]:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [_plain_text(text, 200)]}}


def _code_block(text: str, language: str = "json") -> Dict[str, Any]:
    return {"object": "block", "type": "code", "code": {"language": language, "rich_text": [_plain_text(text)]}}


def _json_blocks(title: str, payload: Any, max_chars: int = 45000) -> list[Dict[str, Any]]:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if len(serialized) > max_chars:
        serialized = serialized[:max_chars] + "\n... [truncated to fit Notion API payload limits]"
    blocks = [_heading(title)]
    chunk_size = 1800
    for idx in range(0, len(serialized), chunk_size):
        blocks.append(_code_block(serialized[idx : idx + chunk_size]))
    return blocks


def build_notion_feedback_children(record: Dict[str, Any]) -> list[Dict[str, Any]]:
    summary = {
        "feedback_id": record.get("feedback_id"),
        "captured_at": record.get("captured_at"),
        "build": record.get("build"),
        "rating": record.get("rating"),
        "reasons": record.get("reasons", []),
        "comment": record.get("comment", ""),
        "claim": record.get("claim", ""),
        "verdict": record.get("verdict", ""),
        "confidence": record.get("confidence", ""),
    }
    children = [_heading("Feedback summary"), _paragraph(record.get("comment") or "No free-text comment supplied.")]
    children.extend(_json_blocks("Structured feedback", summary, max_chars=8000))
    children.extend(_json_blocks("Full request and settings", record.get("request", {}), max_chars=12000))
    children.extend(_json_blocks("Full assessment output", record.get("assessment_output", {}), max_chars=45000))
    return children[:95]


def append_feedback_jsonl(record: Dict[str, Any], path: Optional[Path] = None) -> Path:
    target = path or feedback_log_path()
    if not target.is_absolute():
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return target


def build_notion_feedback_payload(record: Dict[str, Any], database_id: str) -> Dict[str, Any]:
    title = f"{record.get('rating', 'Feedback')} — {record.get('claim') or record.get('result_key')}"
    notes = "\n".join(
        part
        for part in [
            f"Claim: {record.get('claim', '')}",
            f"Verdict: {record.get('verdict', '')}",
            f"Confidence: {record.get('confidence', '')}",
            f"Reasons: {', '.join(record.get('reasons', []) or [])}",
            f"Comment: {record.get('comment', '')}",
            f"Build: {record.get('build', '')}",
            f"Feedback ID: {record.get('feedback_id', '')}",
        ]
        if part and not part.endswith(": ")
    )
    return {
        "parent": {"database_id": database_id},
        "properties": {
            "Task": {"title": [{"text": {"content": title[:180]}}]},
            "Status": {"select": {"name": "To Do"}},
            "Priority": {"select": {"name": "Medium"}},
            "Task Type": {"select": {"name": "User feedback"}},
            "Workstream": {"rich_text": [{"text": {"content": "User feedback"}}]},
            "Notes": {"rich_text": [{"text": {"content": notes[:1900]}}]},
            "Error type": {"multi_select": []},
            "Accepted as regression case": {"checkbox": False},
            "Reviewer notes": {"rich_text": []},
        },
        "children": build_notion_feedback_children(record),
    }


def create_notion_feedback_page(record: Dict[str, Any]) -> Optional[str]:
    api_key = notion_api_key()
    database_id = notion_feedback_database_id()
    if not api_key or not database_id:
        return None

    payload = build_notion_feedback_payload(record, database_id)
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(http_error_detail(response))
    return response.json().get("url")


def _iter_local_feedback_records(path: Optional[Path] = None):
    target = path or feedback_log_path()
    if not target.is_absolute():
        target = Path.cwd() / target
    if not target.exists():
        return
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def get_feedback_by_id(feedback_id: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    for record in _iter_local_feedback_records(path):
        if record.get("feedback_id") == feedback_id:
            return record
    return None


def list_feedback_by_assessment_id(assessment_id: str, limit: int = 100, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    matches = [record for record in _iter_local_feedback_records(path) if record.get("assessment_id") == assessment_id]
    matches.sort(key=lambda item: item.get("captured_at", ""), reverse=True)
    return matches[:limit]


def list_recent_feedback(limit: int = 50, result_key: str = "", path: Optional[Path] = None) -> List[Dict[str, Any]]:
    records = list(_iter_local_feedback_records(path) or [])
    if result_key:
        records = [record for record in records if record.get("result_key") == result_key]
    records.sort(key=lambda item: item.get("captured_at", ""), reverse=True)
    return records[:limit]


def get_feedback_store() -> FeedbackStore:
    url = database_url()
    if url:
        return PostgresFeedbackStore(url)
    return LocalFeedbackStore()


def _save_feedback_record(record: Dict[str, Any], path: Optional[Path] = None) -> FeedbackResult:
    feedback_id = record.get("feedback_id") or str(uuid4())
    record["feedback_id"] = feedback_id
    log_path = append_feedback_jsonl(record, path=path)

    notion_url = None
    try:
        notion_url = create_notion_feedback_page(record)
    except Exception as exc:
        return FeedbackResult(
            ok=True,
            destination="local_jsonl",
            message=f"Saved locally. Notion logging failed: {exc}",
            feedback_id=feedback_id,
        )

    if notion_url:
        return FeedbackResult(
            ok=True,
            destination="local_jsonl+notion",
            message="Saved to feedback log and Notion.",
            feedback_id=feedback_id,
        )
    return FeedbackResult(
        ok=True,
        destination="local_jsonl",
        message=f"Saved to feedback log: {log_path}",
        feedback_id=feedback_id,
    )


def list_recent_feedback_records(limit: int = 50, result_key: str = "", store: Optional[FeedbackStore] = None) -> List[Dict[str, Any]]:
    return (store or get_feedback_store()).list_recent(limit=limit, result_key=result_key)


def save_feedback(record: Dict[str, Any], store: Optional[FeedbackStore] = None) -> FeedbackResult:
    saved = (store or get_feedback_store()).save(record)
    try:
        from evidrai.trust import capture_feedback_trust_events

        capture_feedback_trust_events(record)
    except Exception:
        # Trust-intelligence capture should not block explicit feedback saving.
        pass
    return saved


def load_feedback_by_id(
    feedback_id: str,
    store: Optional[FeedbackStore] = None,
    path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    if path is not None:
        return LocalFeedbackStore(path).get_by_feedback_id(feedback_id)
    return (store or get_feedback_store()).get_by_feedback_id(feedback_id)


def list_feedback_for_assessment(
    assessment_id: str,
    limit: int = 100,
    store: Optional[FeedbackStore] = None,
    path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    if path is not None:
        return LocalFeedbackStore(path).list_by_assessment(assessment_id, limit=limit)
    return (store or get_feedback_store()).list_by_assessment(assessment_id, limit=limit)
