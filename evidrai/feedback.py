from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from evidrai.config import get_app_build, read_config_value, http_error_detail


NOTION_VERSION = "2025-09-03"
DEFAULT_FEEDBACK_LOG_PATH = ".evidrai_feedback/feedback.jsonl"


@dataclass(frozen=True)
class FeedbackResult:
    ok: bool
    destination: str
    message: str
    feedback_id: str


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
        "local_jsonl_log": str(feedback_log_path()),
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
) -> Dict[str, Any]:
    result = result or {}
    settings = settings or {}
    claim = result.get("claim") or result.get("normalized_claim") or settings.get("claim") or settings.get("analysis_input") or ""
    return {
        "feedback_id": str(uuid4()),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "build": get_app_build(),
        "result_key": result_key,
        "rating": rating,
        "reasons": list(reasons or []),
        "comment": (comment or "").strip(),
        "claim": claim,
        "verdict": result.get("verified_verdict") or result.get("verdict") or "",
        "confidence": result.get("verified_confidence") or result.get("confidence") or "",
        "source_url": source_url or settings.get("source_url", ""),
        "result_id": result.get("result_id") or result_key,
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


def create_notion_feedback_page(record: Dict[str, Any]) -> Optional[str]:
    api_key = notion_api_key()
    database_id = notion_feedback_database_id()
    if not api_key or not database_id:
        return None

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
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Task": {"title": [{"text": {"content": title[:180]}}]},
            "Status": {"select": {"name": "To Do"}},
            "Priority": {"select": {"name": "Medium"}},
            "Task Type": {"select": {"name": "User feedback"}},
            "Workstream": {"rich_text": [{"text": {"content": "User feedback"}}]},
            "Notes": {"rich_text": [{"text": {"content": notes[:1900]}}]},
        },
        "children": build_notion_feedback_children(record),
    }
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


def save_feedback(record: Dict[str, Any]) -> FeedbackResult:
    feedback_id = record.get("feedback_id") or str(uuid4())
    record["feedback_id"] = feedback_id
    log_path = append_feedback_jsonl(record)

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
