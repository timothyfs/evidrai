from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Protocol
from uuid import uuid4

from evidrai.config import database_url
from evidrai.db import run_migrations
from evidrai.errors import EvidraiError


TERMINAL_STATUSES = {"completed", "failed"}


class AssessmentJobNotFoundError(EvidraiError):
    def __init__(self, job_id: str) -> None:
        super().__init__("Assessment job not found.", code="assessment_job_not_found", status_code=404, developer_detail=job_id)


class AssessmentJobStoreError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: str = "") -> None:
        super().__init__(message, code="assessment_job_store_error", status_code=500, developer_detail=developer_detail)


@dataclass(frozen=True)
class AssessmentJob:
    job_id: str
    owner_id: str
    status: str
    mode: str
    created_at: str
    updated_at: str
    request: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "owner_id": self.owner_id,
            "status": self.status,
            "mode": self.mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "request": self.request,
            "result": self.result,
            "error": self.error,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise AssessmentJobStoreError("Postgres support requires psycopg.", developer_detail=str(exc))
    return psycopg, dict_row


class AssessmentJobStore(Protocol):
    def create(self, *, owner_id: str, mode: str, request: Dict[str, Any]) -> AssessmentJob:
        ...

    def load(self, job_id: str) -> AssessmentJob:
        ...

    def mark_running(self, job_id: str) -> AssessmentJob:
        ...

    def mark_completed(self, job_id: str, result: Dict[str, Any]) -> AssessmentJob:
        ...

    def mark_failed(self, job_id: str, error: str) -> AssessmentJob:
        ...


class LocalAssessmentJobStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or Path(os.getenv("EVIDRAI_JOB_STORE") or ".evidrai/jobs")

    def path_for(self, job_id: str) -> Path:
        safe = "".join(ch for ch in job_id if ch.isalnum() or ch in {"-", "_"})
        if not safe:
            raise AssessmentJobNotFoundError(job_id)
        return self.directory / f"{safe}.json"

    def _write(self, payload: Dict[str, Any]) -> AssessmentJob:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload["updated_at"] = _now()
        self.path_for(payload["job_id"]).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return AssessmentJob(**payload)

    def create(self, *, owner_id: str, mode: str, request: Dict[str, Any]) -> AssessmentJob:
        now = _now()
        return self._write({
            "job_id": str(uuid4()),
            "owner_id": owner_id,
            "status": "queued",
            "mode": mode,
            "created_at": now,
            "updated_at": now,
            "completed_at": "",
            "request": request,
            "result": None,
            "error": "",
        })

    def load(self, job_id: str) -> AssessmentJob:
        path = self.path_for(job_id)
        if not path.exists():
            raise AssessmentJobNotFoundError(job_id)
        try:
            return AssessmentJob(**json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            raise AssessmentJobStoreError("Could not load assessment job.", developer_detail=str(exc))

    def mark_running(self, job_id: str) -> AssessmentJob:
        payload = self.load(job_id).to_dict()
        if payload["status"] not in TERMINAL_STATUSES:
            payload["status"] = "running"
        return self._write(payload)

    def mark_completed(self, job_id: str, result: Dict[str, Any]) -> AssessmentJob:
        payload = self.load(job_id).to_dict()
        payload.update({"status": "completed", "result": result, "error": "", "completed_at": _now()})
        return self._write(payload)

    def mark_failed(self, job_id: str, error: str) -> AssessmentJob:
        payload = self.load(job_id).to_dict()
        payload.update({"status": "failed", "error": error[:2000], "completed_at": _now()})
        return self._write(payload)


class PostgresAssessmentJobStore:
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

    @staticmethod
    def _job_from_row(row: Dict[str, Any]) -> AssessmentJob:
        if not row:
            raise AssessmentJobNotFoundError("")
        request = row.get("request") or {}
        result = row.get("result")
        if isinstance(request, str):
            request = json.loads(request)
        if isinstance(result, str):
            result = json.loads(result)
        def iso(value: Any) -> str:
            return value.isoformat() if hasattr(value, "isoformat") else str(value or "")
        return AssessmentJob(
            job_id=str(row.get("job_id")),
            owner_id=str(row.get("owner_id") or ""),
            status=str(row.get("status") or "queued"),
            mode=str(row.get("mode") or "fast"),
            created_at=iso(row.get("created_at")),
            updated_at=iso(row.get("updated_at")),
            completed_at=iso(row.get("completed_at")),
            request=request,
            result=result,
            error=str(row.get("error") or ""),
        )

    def create(self, *, owner_id: str, mode: str, request: Dict[str, Any]) -> AssessmentJob:
        self._ensure_schema()
        job_id = str(uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assessment_jobs (job_id, owner_id, status, mode, request, updated_at)
                    VALUES (%s, %s, 'queued', %s, %s::jsonb, now())
                    RETURNING *
                    """,
                    (job_id, owner_id, mode, json.dumps(request)),
                )
                row = cur.fetchone()
            conn.commit()
        return self._job_from_row(row)

    def load(self, job_id: str) -> AssessmentJob:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM assessment_jobs WHERE job_id = %s", (job_id,))
                row = cur.fetchone()
        if not row:
            raise AssessmentJobNotFoundError(job_id)
        return self._job_from_row(row)

    def _update(self, job_id: str, *, status: str, result: Optional[Dict[str, Any]] = None, error: str = "", complete: bool = False) -> AssessmentJob:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE assessment_jobs
                    SET status = %s,
                        result = COALESCE(%s::jsonb, result),
                        error = %s,
                        completed_at = CASE WHEN %s THEN now() ELSE completed_at END,
                        updated_at = now()
                    WHERE job_id = %s
                    RETURNING *
                    """,
                    (status, json.dumps(result) if result is not None else None, error[:2000], complete, job_id),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            raise AssessmentJobNotFoundError(job_id)
        return self._job_from_row(row)

    def mark_running(self, job_id: str) -> AssessmentJob:
        current = self.load(job_id)
        if current.status in TERMINAL_STATUSES:
            return current
        return self._update(job_id, status="running")

    def mark_completed(self, job_id: str, result: Dict[str, Any]) -> AssessmentJob:
        return self._update(job_id, status="completed", result=result, error="", complete=True)

    def mark_failed(self, job_id: str, error: str) -> AssessmentJob:
        return self._update(job_id, status="failed", error=error, complete=True)


def get_assessment_job_store() -> AssessmentJobStore:
    url = database_url()
    if url:
        return PostgresAssessmentJobStore(url)
    return LocalAssessmentJobStore()
