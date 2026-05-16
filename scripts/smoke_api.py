from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
FULL = os.getenv("API_SMOKE_FULL", "").lower() in {"1", "true", "yes"}


def request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(method, f"{BASE_URL}{path}", timeout=30, **kwargs)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def main() -> int:
    checks: list[tuple[str, dict[str, Any]]] = []
    for path in ["/", "/version", "/health", "/runtime"]:
        checks.append((path, request("GET", path)))

    if FULL:
        checks.append(
            (
                "/assessments/fast",
                request(
                    "POST",
                    "/assessments/fast",
                    json={"claim": "Paris is the capital of France.", "category": "general"},
                ),
            )
        )
        checks.append(("/reports", request("GET", "/reports")))

    for path, payload in checks:
        print(f"{path}: ok")
        print(json.dumps(payload, indent=2, sort_keys=True)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
