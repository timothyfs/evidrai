from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
from urllib.parse import urlparse

from pydantic import BaseModel

from .models import VerifiedAssessmentModel
from .config import SCORING_CONFIG

# -----------------------------

PRIMARY_DOMAINS = (
    ".gov",
    ".gouv.fr",
    ".parliament.uk",
    ".legislation.gov.uk",
    ".judiciary.uk",
    ".edu",
    "who.int",
    "nih.gov",
    "nhs.uk",
    "oecd.org",
)
SECONDARY_DOMAINS = (
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "ft.com",
    "nytimes.com",
    "theguardian.com",
    "lemonde.fr",
    "france24.com",
)


def is_probable_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value or "", flags=re.I))


def build_analysis_input(claim: str, source_url: str) -> str:
    claim = (claim or "").strip()
    source_url = (source_url or "").strip()
    if claim and source_url:
        return f"Claim or content to assess:\n{claim}\n\nOptional source URL:\n{source_url}"
    return claim or source_url


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def classify_source_type(domain: str) -> str:
    if any(d in domain for d in PRIMARY_DOMAINS):
        return "primary"
    if any(d in domain for d in SECONDARY_DOMAINS):
        return "secondary"
    return "contextual"


def parse_iso_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def recency_score(date_str: Optional[str]) -> float:
    dt = parse_iso_date(date_str)
    if not dt:
        return 2.5
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = max(0, (now - dt).days)
    if days <= 7:
        return 5.0
    if days <= 30:
        return 4.0
    if days <= 180:
        return 3.0
    if days <= 365:
        return 2.0
    return 1.0




def stable_request_key(*parts: Any) -> str:
    joined = "||".join(str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        if cleaned.lower() in {
            "none",
            "none identified",
            "none identified.",
            "none noted",
            "none noted.",
            "no conflicts",
            "no conflicts.",
            "no conflict",
            "n/a",
            "na",
            "unknown",
        }:
            return []
        return [cleaned]
    return [str(value).strip()] if str(value).strip() else []


def normalize_verified_assessment_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})

    reasoning_summary = payload.get("reasoning_summary")
    if not isinstance(reasoning_summary, dict):
        reasoning_summary = {}
    for key in ("supported_points", "contradicted_points", "uncertain_points"):
        reasoning_summary[key] = ensure_list(reasoning_summary.get(key))
    payload["reasoning_summary"] = reasoning_summary

    evidence = payload.get("evidence_assessment")
    if not isinstance(evidence, dict):
        evidence = {}
    for key in (
        "primary_sources_used",
        "secondary_sources_used",
        "source_conflicts",
        "evidence_gaps",
        "rumor_drivers",
        "actual_evidence",
    ):
        evidence[key] = ensure_list(evidence.get(key))
    payload["evidence_assessment"] = evidence

    for key in ("misinformation_patterns", "why_this_claim_spreads"):
        payload[key] = ensure_list(payload.get(key))

    return payload


def validate_model(payload: Dict[str, Any], model_cls: Type[BaseModel]) -> Dict[str, Any]:
    normalized_payload = payload
    if model_cls is VerifiedAssessmentModel:
        normalized_payload = normalize_verified_assessment_payload(payload)
    model = model_cls.model_validate(normalized_payload)
    return model.model_dump()
