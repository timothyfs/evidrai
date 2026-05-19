from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Protocol

from evidrai.api_models import AssessmentResponse
from evidrai.config import database_url
from evidrai.db import run_migrations
from evidrai.errors import EvidraiError


class ReportNotFoundError(EvidraiError):
    def __init__(self, report_id: str) -> None:
        super().__init__("Report not found.", code="report_not_found", status_code=404, developer_detail=report_id)


class ReportStoreError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: str = "") -> None:
        super().__init__(message, code="report_store_error", status_code=500, developer_detail=developer_detail)


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise ReportStoreError("Postgres support requires psycopg.", developer_detail=str(exc))
    return psycopg, dict_row


class ReportStore(Protocol):
    """Persistence boundary for assessment reports.

    Local JSON is the current implementation. Postgres/object storage should
    implement this protocol without changing API or UI call sites.
    """

    def save(self, assessment: AssessmentResponse) -> AssessmentResponse:
        ...

    def load(self, report_id: str) -> AssessmentResponse:
        ...

    def list(self, limit: int = 50, owner_id: str = "") -> List[Dict[str, Any]]:
        ...


class LocalReportStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or report_store_dir()

    def path_for(self, report_id: str) -> Path:
        safe = "".join(ch for ch in report_id if ch.isalnum() or ch in {"-", "_"})
        if not safe:
            raise ReportNotFoundError(report_id)
        return self.directory / f"{safe}.json"

    def save(self, assessment: AssessmentResponse) -> AssessmentResponse:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.path_for(assessment.assessment_id)
            path.write_text(json.dumps(assessment.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
            return assessment
        except EvidraiError:
            raise
        except Exception as exc:
            raise ReportStoreError("Could not save report.", developer_detail=str(exc))

    def load(self, report_id: str) -> AssessmentResponse:
        path = self.path_for(report_id)
        if not path.exists():
            raise ReportNotFoundError(report_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return AssessmentResponse.model_validate(payload)
        except Exception as exc:
            raise ReportStoreError("Could not load report.", developer_detail=str(exc))

    def list(self, limit: int = 50, owner_id: str = "") -> List[Dict[str, Any]]:
        if not self.directory.exists():
            return []
        items = []
        for path in sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if owner_id and payload.get("owner_id") != owner_id:
                    continue
                items.append(
                    {
                        "assessment_id": payload.get("assessment_id"),
                        "created_at": payload.get("created_at"),
                        "mode": payload.get("mode"),
                        "claim": (payload.get("request") or {}).get("claim"),
                        "verdict": (payload.get("verdict") or {}).get("label"),
                        "owner_id": payload.get("owner_id"),
                    }
                )
                if len(items) >= limit:
                    break
            except Exception:
                continue
        return items


class PostgresReportStore:
    def __init__(self, url: str) -> None:
        self.url = url
        self._schema_ready = False

    def _connect(self):
        psycopg, dict_row = _psycopg()
        return psycopg.connect(self.url, row_factory=dict_row)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            run_migrations(self._connect)
            self._schema_ready = True
        except Exception as exc:
            raise ReportStoreError("Could not initialise report store.", developer_detail=str(exc))

    def save(self, assessment: AssessmentResponse) -> AssessmentResponse:
        self._ensure_schema()
        payload = assessment.model_dump(mode="json")
        request = payload.get("request") or {}
        verdict = payload.get("verdict") or {}
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO assessments (
                            assessment_id, created_at, mode, claim, source_url, verdict, confidence, owner_id, payload, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                        ON CONFLICT (assessment_id) DO UPDATE SET
                            created_at = EXCLUDED.created_at,
                            mode = EXCLUDED.mode,
                            claim = EXCLUDED.claim,
                            source_url = EXCLUDED.source_url,
                            verdict = EXCLUDED.verdict,
                            confidence = EXCLUDED.confidence,
                            owner_id = EXCLUDED.owner_id,
                            payload = EXCLUDED.payload,
                            updated_at = now()
                        """,
                        (
                            assessment.assessment_id,
                            payload.get("created_at"),
                            payload.get("mode"),
                            request.get("claim"),
                            request.get("source_url"),
                            verdict.get("label"),
                            verdict.get("confidence"),
                            payload.get("owner_id"),
                            json.dumps(payload),
                        ),
                    )
                conn.commit()
            return assessment
        except Exception as exc:
            raise ReportStoreError("Could not save report.", developer_detail=str(exc))

    def load(self, report_id: str) -> AssessmentResponse:
        self._ensure_schema()
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT payload FROM assessments WHERE assessment_id = %s", (report_id,))
                    row = cur.fetchone()
            if not row:
                raise ReportNotFoundError(report_id)
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            return AssessmentResponse.model_validate(payload)
        except EvidraiError:
            raise
        except Exception as exc:
            raise ReportStoreError("Could not load report.", developer_detail=str(exc))

    def list(self, limit: int = 50, owner_id: str = "") -> List[Dict[str, Any]]:
        self._ensure_schema()
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    if owner_id:
                        cur.execute(
                            """
                            SELECT assessment_id, created_at, mode, claim, verdict, owner_id
                            FROM assessments
                            WHERE owner_id = %s
                            ORDER BY created_at DESC NULLS LAST, updated_at DESC
                            LIMIT %s
                            """,
                            (owner_id, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT assessment_id, created_at, mode, claim, verdict, owner_id
                            FROM assessments
                            ORDER BY created_at DESC NULLS LAST, updated_at DESC
                            LIMIT %s
                            """,
                            (limit,),
                        )
                    rows = cur.fetchall()
            items: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                created_at = item.get("created_at")
                if hasattr(created_at, "isoformat"):
                    item["created_at"] = created_at.isoformat()
                items.append(item)
            return items
        except Exception as exc:
            raise ReportStoreError("Could not list reports.", developer_detail=str(exc))


def report_store_dir() -> Path:
    configured = os.getenv("EVIDRAI_REPORT_STORE")
    return Path(configured) if configured else Path(".evidrai/reports")


def report_path(report_id: str) -> Path:
    return LocalReportStore().path_for(report_id)


def get_report_store() -> ReportStore:
    url = database_url()
    if url:
        return PostgresReportStore(url)
    return LocalReportStore()


def save_report(assessment: AssessmentResponse, store: ReportStore | None = None) -> AssessmentResponse:
    saved = (store or get_report_store()).save(assessment)
    try:
        from evidrai.trust import capture_assessment_snapshot

        capture_assessment_snapshot(saved)
    except Exception:
        # Trust-intelligence capture should never block the user-facing report path.
        pass
    return saved


def load_report(report_id: str, store: ReportStore | None = None) -> AssessmentResponse:
    return (store or get_report_store()).load(report_id)


def list_reports(limit: int = 50, owner_id: str = "", store: ReportStore | None = None) -> List[Dict[str, Any]]:
    return (store or get_report_store()).list(limit=limit, owner_id=owner_id)
