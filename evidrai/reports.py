from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from evidrai.api_models import AssessmentResponse
from evidrai.errors import EvidraiError


class ReportNotFoundError(EvidraiError):
    def __init__(self, report_id: str) -> None:
        super().__init__("Report not found.", code="report_not_found", status_code=404, developer_detail=report_id)


class ReportStoreError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: str = "") -> None:
        super().__init__(message, code="report_store_error", status_code=500, developer_detail=developer_detail)


def report_store_dir() -> Path:
    configured = os.getenv("EVIDRAI_REPORT_STORE")
    return Path(configured) if configured else Path(".evidrai/reports")


def report_path(report_id: str) -> Path:
    safe = "".join(ch for ch in report_id if ch.isalnum() or ch in {"-", "_"})
    if not safe:
        raise ReportNotFoundError(report_id)
    return report_store_dir() / f"{safe}.json"


def save_report(assessment: AssessmentResponse) -> AssessmentResponse:
    try:
        directory = report_store_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = report_path(assessment.assessment_id)
        path.write_text(json.dumps(assessment.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
        return assessment
    except EvidraiError:
        raise
    except Exception as exc:
        raise ReportStoreError("Could not save report.", developer_detail=str(exc))


def load_report(report_id: str) -> AssessmentResponse:
    path = report_path(report_id)
    if not path.exists():
        raise ReportNotFoundError(report_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AssessmentResponse.model_validate(payload)
    except Exception as exc:
        raise ReportStoreError("Could not load report.", developer_detail=str(exc))


def list_reports(limit: int = 50) -> List[Dict[str, Any]]:
    directory = report_store_dir()
    if not directory.exists():
        return []
    items = []
    for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "assessment_id": payload.get("assessment_id"),
                    "created_at": payload.get("created_at"),
                    "mode": payload.get("mode"),
                    "claim": (payload.get("request") or {}).get("claim"),
                    "verdict": (payload.get("verdict") or {}).get("label"),
                }
            )
        except Exception:
            continue
    return items
