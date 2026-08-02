from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Protocol

from evidrai.config import database_url
from evidrai.db import run_migrations
from evidrai.errors import EvidraiError


DEFAULT_API_SCOPES = ("assessments:write", "reports:read", "speech:write")


class ApiKeyError(EvidraiError):
    def __init__(self, message: str, *, code: str = "api_key_error", status_code: int = 401, developer_detail: str = "") -> None:
        super().__init__(message, code=code, status_code=status_code, developer_detail=developer_detail)


@dataclass
class ApiKeyRecord:
    key_id: str
    owner_id: str
    name: str = ""
    key_prefix: str = ""
    scopes: list[str] = field(default_factory=list)
    created_at: str = ""
    last_used_at: str = ""
    revoked_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CreatedApiKey:
    record: ApiKeyRecord
    plaintext_key: str


class ApiKeyStore(Protocol):
    def create(self, owner_id: str, name: str = "", scopes: list[str] | None = None) -> CreatedApiKey:
        ...

    def authenticate(self, plaintext_key: str) -> ApiKeyRecord:
        ...

    def list(self, owner_id: str, include_revoked: bool = False) -> list[ApiKeyRecord]:
        ...

    def revoke(self, key_id: str, owner_id: str = "") -> bool:
        ...


def _new_plaintext_key() -> str:
    return f"evd_live_{secrets.token_urlsafe(32)}"


def _key_hash(plaintext_key: str) -> str:
    return hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()


def _key_prefix(plaintext_key: str) -> str:
    return plaintext_key[:14]


def _dt_value(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _normalise_scopes(scopes: list[str] | None) -> list[str]:
    requested = [str(scope or "").strip() for scope in (scopes or list(DEFAULT_API_SCOPES))]
    allowed = set(DEFAULT_API_SCOPES)
    return sorted({scope for scope in requested if scope in allowed})


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise ApiKeyError("Postgres support requires psycopg.", code="api_key_store_error", status_code=500, developer_detail=str(exc))
    return psycopg, dict_row


class LocalApiKeyStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("EVIDRAI_API_KEY_STORE", ".evidrai/api_keys.json"))

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def create(self, owner_id: str, name: str = "", scopes: list[str] | None = None) -> CreatedApiKey:
        if not owner_id.strip():
            raise ApiKeyError("owner_id is required", code="owner_required", status_code=400)
        plaintext = _new_plaintext_key()
        key_id = f"key_{uuid.uuid4().hex}"
        record = {
            "key_id": key_id,
            "owner_id": owner_id.strip(),
            "name": name.strip()[:120],
            "key_prefix": _key_prefix(plaintext),
            "key_hash": _key_hash(plaintext),
            "scopes": _normalise_scopes(scopes),
            "created_at": "",
            "last_used_at": "",
            "revoked_at": "",
        }
        data = self._read()
        data[key_id] = record
        self._write(data)
        return CreatedApiKey(record=_record_from_mapping(record), plaintext_key=plaintext)

    def authenticate(self, plaintext_key: str) -> ApiKeyRecord:
        supplied_hash = _key_hash((plaintext_key or "").strip())
        for record in self._read().values():
            if record.get("revoked_at"):
                continue
            if hmac.compare_digest(str(record.get("key_hash") or ""), supplied_hash):
                return _record_from_mapping(record)
        raise ApiKeyError("Invalid API key.", code="invalid_api_key", status_code=401)

    def list(self, owner_id: str, include_revoked: bool = False) -> list[ApiKeyRecord]:
        clean_owner = owner_id.strip()
        records = []
        for record in self._read().values():
            if record.get("owner_id") != clean_owner:
                continue
            if record.get("revoked_at") and not include_revoked:
                continue
            records.append(_record_from_mapping(record))
        return records

    def revoke(self, key_id: str, owner_id: str = "") -> bool:
        data = self._read()
        record = data.get(key_id)
        if not record or (owner_id and record.get("owner_id") != owner_id):
            return False
        record["revoked_at"] = record.get("revoked_at") or "revoked"
        data[key_id] = record
        self._write(data)
        return True


class PostgresApiKeyStore:
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

    def create(self, owner_id: str, name: str = "", scopes: list[str] | None = None) -> CreatedApiKey:
        clean_owner = owner_id.strip()
        if not clean_owner:
            raise ApiKeyError("owner_id is required", code="owner_required", status_code=400)
        self._ensure_schema()
        plaintext = _new_plaintext_key()
        key_id = f"key_{uuid.uuid4().hex}"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO api_keys (key_id, owner_id, name, key_prefix, key_hash, scopes)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING key_id, owner_id, name, key_prefix, scopes, created_at, last_used_at, revoked_at
                    """,
                    (key_id, clean_owner, name.strip()[:120], _key_prefix(plaintext), _key_hash(plaintext), json.dumps(_normalise_scopes(scopes))),
                )
                row = cur.fetchone()
            conn.commit()
        return CreatedApiKey(record=_record_from_mapping(row), plaintext_key=plaintext)

    def authenticate(self, plaintext_key: str) -> ApiKeyRecord:
        self._ensure_schema()
        supplied_hash = _key_hash((plaintext_key or "").strip())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE api_keys
                    SET last_used_at = now()
                    WHERE key_hash = %s AND revoked_at IS NULL
                    RETURNING key_id, owner_id, name, key_prefix, scopes, created_at, last_used_at, revoked_at
                    """,
                    (supplied_hash,),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            raise ApiKeyError("Invalid API key.", code="invalid_api_key", status_code=401)
        return _record_from_mapping(row)

    def list(self, owner_id: str, include_revoked: bool = False) -> list[ApiKeyRecord]:
        self._ensure_schema()
        clean_owner = owner_id.strip()
        where = "owner_id = %s" if include_revoked else "owner_id = %s AND revoked_at IS NULL"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT key_id, owner_id, name, key_prefix, scopes, created_at, last_used_at, revoked_at
                    FROM api_keys
                    WHERE {where}
                    ORDER BY created_at DESC
                    """,
                    (clean_owner,),
                )
                rows = cur.fetchall()
        return [_record_from_mapping(row) for row in rows]

    def revoke(self, key_id: str, owner_id: str = "") -> bool:
        self._ensure_schema()
        params: list[Any] = [key_id.strip()]
        owner_clause = ""
        if owner_id.strip():
            owner_clause = " AND owner_id = %s"
            params.append(owner_id.strip())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE api_keys SET revoked_at = COALESCE(revoked_at, now()) WHERE key_id = %s{owner_clause}",
                    tuple(params),
                )
                updated = cur.rowcount > 0
            conn.commit()
        return updated


def _record_from_mapping(row: Dict[str, Any]) -> ApiKeyRecord:
    scopes = row.get("scopes") or []
    if isinstance(scopes, str):
        try:
            scopes = json.loads(scopes)
        except Exception:
            scopes = []
    return ApiKeyRecord(
        key_id=str(row.get("key_id") or ""),
        owner_id=str(row.get("owner_id") or ""),
        name=str(row.get("name") or ""),
        key_prefix=str(row.get("key_prefix") or ""),
        scopes=[str(scope) for scope in scopes if str(scope)],
        created_at=_dt_value(row.get("created_at")),
        last_used_at=_dt_value(row.get("last_used_at")),
        revoked_at=_dt_value(row.get("revoked_at")),
    )


@lru_cache(maxsize=4)
def _cached_api_key_store(url: str) -> PostgresApiKeyStore:
    return PostgresApiKeyStore(url)


def get_api_key_store() -> ApiKeyStore:
    url = database_url()
    if url:
        return _cached_api_key_store(url)
    return LocalApiKeyStore()


def create_api_key(owner_id: str, name: str = "", scopes: list[str] | None = None, store: ApiKeyStore | None = None) -> CreatedApiKey:
    return (store or get_api_key_store()).create(owner_id, name=name, scopes=scopes)


def authenticate_api_key(plaintext_key: str, store: ApiKeyStore | None = None) -> ApiKeyRecord:
    return (store or get_api_key_store()).authenticate(plaintext_key)


def list_api_keys(owner_id: str, include_revoked: bool = False, store: ApiKeyStore | None = None) -> list[ApiKeyRecord]:
    return (store or get_api_key_store()).list(owner_id, include_revoked=include_revoked)


def revoke_api_key(key_id: str, owner_id: str = "", store: ApiKeyStore | None = None) -> bool:
    return (store or get_api_key_store()).revoke(key_id, owner_id=owner_id)
