from __future__ import annotations

import json
from typing import Any, Dict

from evidrai.api_models import serialize_assessment_response
from evidrai.config import get_app_build


def assessment_export_payload(
    result: Dict[str, Any],
    *,
    claim: str = "",
    source_url: str = "",
    category: str = "auto-detect",
    mode: str = "deep",
    include_debug: bool = True,
) -> Dict[str, Any]:
    """Build a stable JSON-safe assessment export packet.

    Exports intentionally use public packets/debug traces and do not include raw
    fetched source content, API keys, or provider credentials.
    """
    assessment = serialize_assessment_response(
        result,
        claim=claim or result.get("claim") or "",
        source_url=source_url or result.get("source_url") or "",
        category=category,
        mode=mode,
        build=get_app_build(),
        include_debug=include_debug,
    )
    payload = assessment.model_dump(mode="json")
    payload["export_version"] = "assessment_export.v1"
    return payload


def assessment_export_json(
    result: Dict[str, Any],
    *,
    claim: str = "",
    source_url: str = "",
    category: str = "auto-detect",
    mode: str = "deep",
    include_debug: bool = True,
) -> str:
    return json.dumps(
        assessment_export_payload(
            result,
            claim=claim,
            source_url=source_url,
            category=category,
            mode=mode,
            include_debug=include_debug,
        ),
        indent=2,
        sort_keys=True,
    )
