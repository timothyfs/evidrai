from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Protocol

from evidrai.config import database_url
from evidrai.db import run_migrations
from evidrai.errors import EvidraiError


TIERS = ("free", "pro", "researcher")


class EntitlementError(EvidraiError):
    def __init__(self, message: str, *, code: str = "entitlement_error", status_code: int = 403, developer_detail: str = "") -> None:
        super().__init__(message, code=code, status_code=status_code, developer_detail=developer_detail)


@dataclass(frozen=True)
class TierDefinition:
    tier: str
    label: str
    description: str
    features: Dict[str, bool]
    limits: Dict[str, int]


@dataclass
class UserProfile:
    owner_id: str
    email: str = ""
    tier: str = "free"
    subscription_status: str = "none"
    trial_started_at: str = ""
    trial_ends_at: str = ""
    payment_provider_customer_id: str = ""
    company_name: str = ""
    organisation_name: str = ""
    billing_account_name: str = ""
    billing_account_id: str = ""
    admin_notes: str = ""
    terms_version: str = ""
    privacy_version: str = ""
    terms_accepted_at: str = ""
    privacy_acknowledged_at: str = ""
    marketing_opt_in: bool = False
    marketing_opt_in_at: str = ""
    consent_source: str = ""
    consent_user_agent: str = ""
    consent_ip_hash: str = ""
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        definition = tier_definition(self.tier)
        payload["tier_label"] = definition.label
        payload["features"] = dict(definition.features)
        payload["limits"] = dict(definition.limits)
        return payload


TIER_DEFINITIONS: Dict[str, TierDefinition] = {
    "free": TierDefinition(
        tier="free",
        label="Free",
        description="Fast individual claim checks with limited saved report history.",
        features={
            "fast_claims": True,
            "deep_claims": False,
            "speech_audit": False,
            "feedback": True,
            "simple_share_reports": True,
            "share_reports": False,
            "exports": False,
            "evidence_ledger": False,
            "source_snapshots": False,
            "api_access": False,
        },
        limits={"saved_reports": 5, "max_speech_claims": 0, "monthly_fast_checks": 25, "monthly_deep_checks": 0, "monthly_speech_audits": 0},
    ),
    "pro": TierDefinition(
        tier="pro",
        label="Pro",
        description="Deep verification and speech/video audits for serious individual use.",
        features={
            "fast_claims": True,
            "deep_claims": True,
            "speech_audit": True,
            "feedback": True,
            "simple_share_reports": True,
            "share_reports": True,
            "exports": True,
            "evidence_ledger": False,
            "source_snapshots": False,
            "api_access": False,
        },
        limits={"saved_reports": 10, "max_speech_claims": 5, "monthly_fast_checks": 500, "monthly_deep_checks": 100, "monthly_speech_audits": 25},
    ),
    "researcher": TierDefinition(
        tier="researcher",
        label="Researcher / Journalist",
        description="Higher limits and investigation-grade provenance, ledger, and export capabilities.",
        features={
            "fast_claims": True,
            "deep_claims": True,
            "speech_audit": True,
            "feedback": True,
            "simple_share_reports": True,
            "share_reports": True,
            "exports": True,
            "evidence_ledger": True,
            "source_snapshots": True,
            "api_access": True,
        },
        limits={"saved_reports": 100, "max_speech_claims": 20, "monthly_fast_checks": 5000, "monthly_deep_checks": 1000, "monthly_speech_audits": 250},
    ),
}


def normalize_tier(tier: str) -> str:
    normalized = (tier or "free").strip().lower()
    if normalized == "admin":
        normalized = "researcher"
    if normalized not in TIERS:
        raise EntitlementError("Unknown user tier.", code="unknown_tier", status_code=400, developer_detail=tier)
    return normalized


def tier_definition(tier: str) -> TierDefinition:
    return TIER_DEFINITIONS[normalize_tier(tier)]


def feature_matrix() -> Dict[str, Any]:
    return {
        "schema_version": "feature_matrix.v1",
        "tiers": [
            {
                "tier": definition.tier,
                "label": definition.label,
                "description": definition.description,
                "features": definition.features,
                "limits": definition.limits,
            }
            for definition in TIER_DEFINITIONS.values()
        ],
    }


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise EntitlementError("Postgres support requires psycopg.", code="profile_store_error", status_code=500, developer_detail=str(exc))
    return psycopg, dict_row


class UserProfileStore(Protocol):
    def get_or_create(self, owner_id: str, email: str = "") -> UserProfile:
        ...

    def set_tier(self, owner_id: str, tier: str, email: str = "") -> UserProfile:
        ...

    def update_details(self, owner_id: str, **details: str) -> UserProfile:
        ...

    def update_consent(self, owner_id: str, **details: Any) -> UserProfile:
        ...

    def list(self, limit: int = 100) -> List[UserProfile]:
        ...

    def delete(self, owner_id: str) -> bool:
        ...


class LocalUserProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("EVIDRAI_USER_PROFILE_STORE", ".evidrai/user_profiles.json"))

    def _read(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def get_or_create(self, owner_id: str, email: str = "") -> UserProfile:
        if not owner_id:
            return UserProfile(owner_id="", email=email, tier="free")
        data = self._read()
        record = data.get(owner_id) or {"owner_id": owner_id, "email": email, "tier": "free"}
        if email and not record.get("email"):
            record["email"] = email
            data[owner_id] = record
            self._write(data)
        elif owner_id not in data:
            data[owner_id] = record
            self._write(data)
        return _profile_from_mapping(record, owner_id=owner_id)

    def set_tier(self, owner_id: str, tier: str, email: str = "") -> UserProfile:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        data = self._read()
        record = data.get(owner_id) or {"owner_id": owner_id, "email": email, "tier": "free"}
        record["tier"] = normalize_tier(tier)
        if email:
            record["email"] = email
        data[owner_id] = record
        self._write(data)
        return self.get_or_create(owner_id, email=record.get("email") or "")

    def update_details(self, owner_id: str, **details: str) -> UserProfile:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        allowed = {"email", "company_name", "organisation_name", "billing_account_name", "billing_account_id", "admin_notes"}
        data = self._read()
        record = data.get(owner_id) or {"owner_id": owner_id, "email": details.get("email", ""), "tier": "free"}
        for key, value in details.items():
            if key in allowed:
                record[key] = str(value or "").strip()
        data[owner_id] = record
        self._write(data)
        return self.get_or_create(owner_id, email=record.get("email") or "")

    def update_consent(self, owner_id: str, **details: Any) -> UserProfile:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        allowed = {
            "terms_version",
            "privacy_version",
            "terms_accepted_at",
            "privacy_acknowledged_at",
            "marketing_opt_in",
            "marketing_opt_in_at",
            "consent_source",
            "consent_user_agent",
            "consent_ip_hash",
        }
        data = self._read()
        record = data.get(owner_id) or {"owner_id": owner_id, "email": details.get("email", ""), "tier": "free"}
        for key, value in details.items():
            if key in allowed:
                record[key] = bool(value) if key == "marketing_opt_in" else str(value or "").strip()
        data[owner_id] = record
        self._write(data)
        return self.get_or_create(owner_id, email=record.get("email") or "")

    def list(self, limit: int = 100) -> List[UserProfile]:
        return [_profile_from_mapping(record, owner_id=owner_id) for owner_id, record in list(self._read().items())[:limit]]

    def delete(self, owner_id: str) -> bool:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        data = self._read()
        existed = owner_id in data
        if existed:
            data.pop(owner_id, None)
            self._write(data)
        return existed


class PostgresUserProfileStore:
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

    def get_or_create(self, owner_id: str, email: str = "") -> UserProfile:
        if not owner_id:
            return UserProfile(owner_id="", email=email, tier="free")
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_profiles (owner_id, email, tier, updated_at)
                    VALUES (%s, %s, 'free', now())
                    ON CONFLICT (owner_id) DO UPDATE SET
                        email = COALESCE(NULLIF(EXCLUDED.email, ''), user_profiles.email),
                        updated_at = now()
                    RETURNING owner_id, email, tier, subscription_status, trial_started_at, trial_ends_at, payment_provider_customer_id, company_name, organisation_name, billing_account_name, billing_account_id, admin_notes, terms_version, privacy_version, terms_accepted_at, privacy_acknowledged_at, marketing_opt_in, marketing_opt_in_at, consent_source, consent_user_agent, consent_ip_hash
                    """,
                    (owner_id, email),
                )
                row = cur.fetchone()
            conn.commit()
        return _profile_from_row(row)

    def set_tier(self, owner_id: str, tier: str, email: str = "") -> UserProfile:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        normalized = normalize_tier(tier)
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_profiles (owner_id, email, tier, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (owner_id) DO UPDATE SET
                        email = COALESCE(NULLIF(EXCLUDED.email, ''), user_profiles.email),
                        tier = EXCLUDED.tier,
                        updated_at = now()
                    RETURNING owner_id, email, tier, subscription_status, trial_started_at, trial_ends_at, payment_provider_customer_id, company_name, organisation_name, billing_account_name, billing_account_id, admin_notes, terms_version, privacy_version, terms_accepted_at, privacy_acknowledged_at, marketing_opt_in, marketing_opt_in_at, consent_source, consent_user_agent, consent_ip_hash
                    """,
                    (owner_id, email, normalized),
                )
                row = cur.fetchone()
            conn.commit()
        return _profile_from_row(row)

    def update_details(self, owner_id: str, **details: str) -> UserProfile:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        allowed = {"email", "company_name", "organisation_name", "billing_account_name", "billing_account_id", "admin_notes"}
        updates = {key: str(value or "").strip() for key, value in details.items() if key in allowed}
        if not updates:
            return self.get_or_create(owner_id)
        self._ensure_schema()
        columns = ", ".join(f"{key} = %s" for key in updates)
        params = list(updates.values()) + [owner_id]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE user_profiles
                    SET {columns}, updated_at = now()
                    WHERE owner_id = %s
                    RETURNING owner_id, email, tier, subscription_status, trial_started_at, trial_ends_at, payment_provider_customer_id, company_name, organisation_name, billing_account_name, billing_account_id, admin_notes, terms_version, privacy_version, terms_accepted_at, privacy_acknowledged_at, marketing_opt_in, marketing_opt_in_at, consent_source, consent_user_agent, consent_ip_hash
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            return self.get_or_create(owner_id, email=updates.get("email", ""))
        return _profile_from_row(row)

    def update_consent(self, owner_id: str, **details: Any) -> UserProfile:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        allowed = {
            "terms_version",
            "privacy_version",
            "terms_accepted_at",
            "privacy_acknowledged_at",
            "marketing_opt_in",
            "marketing_opt_in_at",
            "consent_source",
            "consent_user_agent",
            "consent_ip_hash",
        }
        updates = {key: value for key, value in details.items() if key in allowed}
        if not updates:
            return self.get_or_create(owner_id)
        self._ensure_schema()
        columns = ", ".join(f"{key} = %s" for key in updates)
        params = list(updates.values()) + [owner_id]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE user_profiles
                    SET {columns}, updated_at = now()
                    WHERE owner_id = %s
                    RETURNING owner_id, email, tier, subscription_status, trial_started_at, trial_ends_at, payment_provider_customer_id, company_name, organisation_name, billing_account_name, billing_account_id, admin_notes, terms_version, privacy_version, terms_accepted_at, privacy_acknowledged_at, marketing_opt_in, marketing_opt_in_at, consent_source, consent_user_agent, consent_ip_hash
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            self.get_or_create(owner_id)
            return self.update_consent(owner_id, **details)
        return _profile_from_row(row)

    def list(self, limit: int = 100) -> List[UserProfile]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT owner_id, email, tier, subscription_status, trial_started_at, trial_ends_at, payment_provider_customer_id, company_name, organisation_name, billing_account_name, billing_account_id, admin_notes, terms_version, privacy_version, terms_accepted_at, privacy_acknowledged_at, marketing_opt_in, marketing_opt_in_at, consent_source, consent_user_agent, consent_ip_hash FROM user_profiles ORDER BY updated_at DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
        return [_profile_from_row(row) for row in rows]

    def delete(self, owner_id: str) -> bool:
        if not owner_id:
            raise EntitlementError("owner_id is required", code="owner_required", status_code=400)
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_profiles WHERE owner_id = %s", (owner_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted


def _dt_value(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _profile_from_mapping(row: Dict[str, Any], *, owner_id: str = "") -> UserProfile:
    return UserProfile(
        owner_id=row.get("owner_id") or owner_id,
        email=row.get("email") or "",
        tier=normalize_tier(row.get("tier") or "free"),
        subscription_status=row.get("subscription_status") or "none",
        trial_started_at=_dt_value(row.get("trial_started_at")),
        trial_ends_at=_dt_value(row.get("trial_ends_at")),
        payment_provider_customer_id=row.get("payment_provider_customer_id") or "",
        company_name=row.get("company_name") or "",
        organisation_name=row.get("organisation_name") or "",
        billing_account_name=row.get("billing_account_name") or "",
        billing_account_id=row.get("billing_account_id") or "",
        admin_notes=row.get("admin_notes") or "",
        terms_version=row.get("terms_version") or "",
        privacy_version=row.get("privacy_version") or "",
        terms_accepted_at=_dt_value(row.get("terms_accepted_at")),
        privacy_acknowledged_at=_dt_value(row.get("privacy_acknowledged_at")),
        marketing_opt_in=bool(row.get("marketing_opt_in")),
        marketing_opt_in_at=_dt_value(row.get("marketing_opt_in_at")),
        consent_source=row.get("consent_source") or "",
        consent_user_agent=row.get("consent_user_agent") or "",
        consent_ip_hash=row.get("consent_ip_hash") or "",
    )


def _profile_from_row(row: Dict[str, Any]) -> UserProfile:
    return _profile_from_mapping(row)


def get_user_profile_store() -> UserProfileStore:
    url = database_url()
    if url:
        return PostgresUserProfileStore(url)
    return LocalUserProfileStore()


def get_or_create_profile(owner_id: str, email: str = "", store: UserProfileStore | None = None) -> UserProfile:
    return (store or get_user_profile_store()).get_or_create(owner_id, email=email)


def set_user_tier(owner_id: str, tier: str, email: str = "", store: UserProfileStore | None = None) -> UserProfile:
    return (store or get_user_profile_store()).set_tier(owner_id, tier=tier, email=email)


def update_user_profile_details(owner_id: str, store: UserProfileStore | None = None, **details: str) -> UserProfile:
    return (store or get_user_profile_store()).update_details(owner_id, **details)


def update_user_consent(owner_id: str, store: UserProfileStore | None = None, **details: Any) -> UserProfile:
    return (store or get_user_profile_store()).update_consent(owner_id, **details)


def list_user_profiles(limit: int = 100, store: UserProfileStore | None = None) -> List[UserProfile]:
    return (store or get_user_profile_store()).list(limit=limit)


def delete_user_profile(owner_id: str, store: UserProfileStore | None = None) -> bool:
    return (store or get_user_profile_store()).delete(owner_id)


def require_feature(profile: UserProfile, feature: str, *, authenticated: bool = True) -> None:
    definition = tier_definition(profile.tier)
    if not authenticated:
        raise EntitlementError("Sign in is required for this feature.", code="auth_required", status_code=401)
    if not definition.features.get(feature, False):
        raise EntitlementError(
            f"Your {definition.label} plan does not include this feature.",
            code="feature_not_available",
            status_code=403,
            developer_detail=feature,
        )


def enforce_speech_claim_limit(profile: UserProfile, requested_claims: int) -> None:
    definition = tier_definition(profile.tier)
    max_claims = int(definition.limits.get("max_speech_claims") or 0)
    if requested_claims > max_claims:
        raise EntitlementError(
            f"Your {definition.label} plan allows up to {max_claims} speech claims per audit.",
            code="limit_exceeded",
            status_code=403,
            developer_detail=f"requested={requested_claims}; max={max_claims}",
        )
