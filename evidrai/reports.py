from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Protocol

from evidrai.api_models import AssessmentResponse
from evidrai.config import admin_token, database_url
from evidrai.db import run_migrations
from evidrai.errors import EvidraiError


class ReportNotFoundError(EvidraiError):
    def __init__(self, report_id: str) -> None:
        super().__init__("Report not found.", code="report_not_found", status_code=404, developer_detail=report_id)


class ReportStoreError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: str = "") -> None:
        super().__init__(message, code="report_store_error", status_code=500, developer_detail=developer_detail)


def _assessment_field(assessment: AssessmentResponse | Dict[str, Any], field: str, default: Any = "") -> Any:
    if isinstance(assessment, dict):
        return assessment.get(field, default)
    return getattr(assessment, field, default)


def _share_secret() -> bytes:
    secret = os.getenv("EVIDRAI_SHARE_SECRET") or admin_token() or os.getenv("EVIDRAI_ADMIN_TOKEN") or "evidrai-dev-share-secret"
    return secret.encode("utf-8")


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _signed_share_token(report_id: str, access_level: str) -> str:
    payload = json.dumps({"rid": report_id, "lvl": access_level}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = _b64_encode(payload)
    signature = _b64_encode(hmac.new(_share_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"s1.{encoded}.{signature}"


def _decode_signed_share_token(token: str) -> Dict[str, str]:
    try:
        version, encoded, signature = token.split(".", 2)
    except ValueError:
        raise ReportNotFoundError(token)
    if version != "s1":
        raise ReportNotFoundError(token)
    expected = _b64_encode(hmac.new(_share_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ReportNotFoundError(token)
    try:
        payload = json.loads(_b64_decode(encoded).decode("utf-8"))
    except Exception:
        raise ReportNotFoundError(token)
    report_id = str(payload.get("rid") or "")
    access_level = "full" if payload.get("lvl") == "full" else "simple"
    if not report_id:
        raise ReportNotFoundError(token)
    return {"assessment_id": report_id, "access_level": access_level}


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

    def iter_assessments(self, limit: int = 1000) -> List[AssessmentResponse]:
        ...

    def create_share(self, report_id: str, owner_id: str = "", access_level: str = "full", assessment: AssessmentResponse | None = None) -> Dict[str, Any]:
        ...

    def load_shared(self, token: str) -> Dict[str, Any]:
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

    def iter_assessments(self, limit: int = 1000) -> List[AssessmentResponse]:
        if not self.directory.exists():
            return []
        assessments: List[AssessmentResponse] = []
        for path in sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                assessments.append(AssessmentResponse.model_validate(json.loads(path.read_text(encoding="utf-8"))))
                if len(assessments) >= limit:
                    break
            except Exception:
                continue
        return assessments

    def _shares_path(self) -> Path:
        return self.directory.parent / "report_shares.json"

    def _read_shares(self) -> Dict[str, Dict[str, Any]]:
        path = self._shares_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_shares(self, data: Dict[str, Dict[str, Any]]) -> None:
        path = self._shares_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def create_share(self, report_id: str, owner_id: str = "", access_level: str = "full", assessment: AssessmentResponse | None = None) -> Dict[str, Any]:
        assessment = assessment or self.load(report_id)
        access_level = "full" if access_level == "full" else "simple"
        assessment_owner = _assessment_field(assessment, "owner_id") or ""
        assessment_created_at = _assessment_field(assessment, "created_at") or ""
        if owner_id and assessment_owner and assessment_owner != owner_id:
            raise ReportNotFoundError(report_id)
        token = _signed_share_token(report_id, access_level)
        return {"token": token, "assessment_id": report_id, "owner_id": assessment_owner or owner_id, "access_level": access_level, "created_at": assessment_created_at, "revoked_at": ""}

    def load_shared(self, token: str) -> Dict[str, Any]:
        if token.startswith("s1."):
            record = _decode_signed_share_token(token)
            assessment = self.load(record["assessment_id"])
            assessment_owner = _assessment_field(assessment, "owner_id") or ""
            assessment_created_at = _assessment_field(assessment, "created_at") or ""
            return {"share": {"token": token, **record, "owner_id": assessment_owner, "created_at": assessment_created_at, "revoked_at": ""}, "assessment": assessment}
        safe = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_"})
        if not safe or safe != token:
            raise ReportNotFoundError(token)
        record = self._read_shares().get(token)
        if not record or record.get("revoked_at"):
            raise ReportNotFoundError(token)
        assessment = self.load(record.get("assessment_id") or "")
        return {"share": {"token": token, **record}, "assessment": assessment}


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

    def iter_assessments(self, limit: int = 1000) -> List[AssessmentResponse]:
        self._ensure_schema()
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT payload
                        FROM assessments
                        ORDER BY created_at DESC NULLS LAST, updated_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = cur.fetchall()
            assessments: List[AssessmentResponse] = []
            for row in rows:
                payload = row["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                assessments.append(AssessmentResponse.model_validate(payload))
            return assessments
        except Exception as exc:
            raise ReportStoreError("Could not iterate reports.", developer_detail=str(exc))

    def create_share(self, report_id: str, owner_id: str = "", access_level: str = "full", assessment: AssessmentResponse | None = None) -> Dict[str, Any]:
        access_level = "full" if access_level == "full" else "simple"
        if assessment is not None:
            assessment_owner = _assessment_field(assessment, "owner_id") or ""
            assessment_created_at = _assessment_field(assessment, "created_at") or ""
            if owner_id and assessment_owner and assessment_owner != owner_id:
                raise ReportNotFoundError(report_id)
            token = _signed_share_token(report_id, access_level)
            return {"token": token, "assessment_id": report_id, "owner_id": assessment_owner or owner_id, "access_level": access_level, "created_at": assessment_created_at, "revoked_at": ""}
        self._ensure_schema()
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT assessment_id, owner_id, created_at FROM assessments WHERE assessment_id = %s", (report_id,))
                    row = cur.fetchone()
            if not row:
                raise ReportNotFoundError(report_id)
            if owner_id and row.get("owner_id") and row.get("owner_id") != owner_id:
                raise ReportNotFoundError(report_id)
            created_at = row.get("created_at")
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            token = _signed_share_token(report_id, access_level)
            return {"token": token, "assessment_id": report_id, "owner_id": row.get("owner_id") or owner_id, "access_level": access_level, "created_at": created_at, "revoked_at": ""}
        except EvidraiError:
            raise
        except Exception as exc:
            raise ReportStoreError("Could not create report share.", developer_detail=str(exc))

    def load_shared(self, token: str) -> Dict[str, Any]:
        self._ensure_schema()
        if token.startswith("s1."):
            record = _decode_signed_share_token(token)
            assessment = self.load(record["assessment_id"])
            assessment_owner = _assessment_field(assessment, "owner_id") or ""
            assessment_created_at = _assessment_field(assessment, "created_at") or ""
            return {"share": {"token": token, **record, "owner_id": assessment_owner, "created_at": assessment_created_at, "revoked_at": ""}, "assessment": assessment}
        safe = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_"})
        if not safe or safe != token:
            raise ReportNotFoundError(token)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT s.token, s.assessment_id, s.owner_id, s.access_level, s.created_at, s.revoked_at, a.payload
                        FROM report_shares s
                        JOIN assessments a ON a.assessment_id = s.assessment_id
                        WHERE s.token = %s AND s.revoked_at IS NULL
                        """,
                        (token,),
                    )
                    row = cur.fetchone()
            if not row:
                raise ReportNotFoundError(token)
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            share = {key: row.get(key) for key in ("token", "assessment_id", "owner_id", "access_level", "created_at", "revoked_at")}
            for key in ("created_at", "revoked_at"):
                if hasattr(share.get(key), "isoformat"):
                    share[key] = share[key].isoformat()
            return {"share": share, "assessment": AssessmentResponse.model_validate(payload)}
        except EvidraiError:
            raise
        except Exception as exc:
            raise ReportStoreError("Could not load shared report.", developer_detail=str(exc))


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


def iter_assessments(limit: int = 1000, store: ReportStore | None = None) -> List[AssessmentResponse]:
    return (store or get_report_store()).iter_assessments(limit=limit)


def create_report_share(report_id: str, owner_id: str = "", access_level: str = "full", assessment: AssessmentResponse | None = None, store: ReportStore | None = None) -> Dict[str, Any]:
    return (store or get_report_store()).create_share(report_id, owner_id=owner_id, access_level=access_level, assessment=assessment)


def load_shared_report(token: str, store: ReportStore | None = None) -> Dict[str, Any]:
    return (store or get_report_store()).load_shared(token)
