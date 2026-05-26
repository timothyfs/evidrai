#!/usr/bin/env python3
"""Production smoke checks for the deployed Evidrai web + API surfaces.

Default mode is safe for frequent UI work: it checks public frontend assets,
public API health/config endpoints, the anonymous account profile, the async
Fast assessment job path used by the web UI, and report listing for the same
anonymous smoke user.

Optional authenticated checks are enabled with environment variables:

  EVIDRAI_ACCESS_TOKEN=<supabase access token> EVIDRAI_RUN_DEEP=1 python scripts/smoke_production.py
  EVIDRAI_ACCESS_TOKEN=<supabase access token> EVIDRAI_RUN_SPEECH=1 python scripts/smoke_production.py

Exit code is non-zero on failed checks. Skips are reported but do not fail
unless EVIDRAI_REQUIRE_AUTH_FEATURES=1 is set.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_API_BASE_URL = "https://evidrai.onrender.com"
DEFAULT_WEB_URL = "https://evidrai.vercel.app"


@dataclass
class SmokeResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def pass_(self, name: str, detail: str = "") -> None:
        self.passed.append(f"{name}{': ' + detail if detail else ''}")

    def fail(self, name: str, detail: str) -> None:
        self.failed.append(f"{name}: {detail}")

    def skip(self, name: str, detail: str) -> None:
        self.skipped.append(f"{name}: {detail}")

    def note(self, detail: str) -> None:
        self.notes.append(detail)


class SmokeClient:
    def __init__(self, api_base_url: str, user_id: str, access_token: str = "", timeout: float = 30.0):
        self.api_base_url = api_base_url.rstrip("/")
        self.user_id = user_id
        self.access_token = access_token
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, *, absolute: bool = False) -> tuple[int, Any, dict[str, str]]:
        url = path if absolute else f"{self.api_base_url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "evidrai-production-smoke/1.0",
            "X-Evidrai-User-Id": self.user_id,
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                text = raw.decode("utf-8", errors="replace")
                parsed: Any
                try:
                    parsed = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    parsed = text
                return response.status, parsed, dict(response.headers)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = raw
            return exc.code, parsed, dict(exc.headers)


def expect(condition: bool, result: SmokeResult, name: str, detail: str = "") -> bool:
    if condition:
        result.pass_(name, detail)
        return True
    result.fail(name, detail or "expectation failed")
    return False


def payload_detail(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload.get("message")
        if detail:
            return json.dumps(detail, ensure_ascii=False)[:500] if isinstance(detail, (dict, list)) else str(detail)[:500]
        return json.dumps(payload, ensure_ascii=False)[:500]
    return str(payload)[:500]


def check_frontend(web_url: str, result: SmokeResult, timeout: float) -> None:
    req = urllib.request.Request(web_url, headers={"User-Agent": "evidrai-production-smoke/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    expect(response.status == 200, result, "frontend homepage", f"HTTP {response.status}")
    chunks = re.findall(r'/_next/static/chunks/app/page-[^"<>]+\.js', html)
    if not chunks:
        result.fail("frontend bundle discovery", "could not find app/page chunk")
        return
    chunk_url = web_url.rstrip("/") + chunks[0]
    req = urllib.request.Request(chunk_url, headers={"User-Agent": "evidrai-production-smoke/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        js = response.read().decode("utf-8", errors="replace")
    markers = {
        "detail missing-score diagnostic": "Evidence score not calculated",
        "source card article-title metadata": "sourceArticleTitle",
        "clean source display helper": "Unknown source",
    }
    for label, marker in markers.items():
        expect(marker in js, result, f"frontend marker: {label}", marker)
    result.note(f"Frontend chunk: {chunks[0]}")


def check_get(client: SmokeClient, path: str, name: str, result: SmokeResult) -> Any:
    status, payload, _headers = client.request("GET", path)
    if expect(status == 200, result, name, f"HTTP {status}"):
        return payload
    result.note(f"{name} payload: {payload_detail(payload)}")
    return payload


def create_fast_job(client: SmokeClient, result: SmokeResult, poll_seconds: int) -> str:
    claim = "The Eiffel Tower is in Paris."
    status, payload, _headers = client.request(
        "POST",
        "/assessment-jobs/fast",
        {"claim": claim, "source_url": "", "category": "general", "output_style": "standard"},
    )
    if not expect(status == 200, result, "fast assessment job create", f"HTTP {status}"):
        result.note(f"fast job create payload: {payload_detail(payload)}")
        return ""
    job_id = str(payload.get("job_id") or "") if isinstance(payload, dict) else ""
    if not expect(bool(job_id), result, "fast assessment job id", job_id):
        return ""

    deadline = time.monotonic() + poll_seconds
    last_payload: Any = payload
    while time.monotonic() < deadline:
        time.sleep(2)
        status, last_payload, _headers = client.request("GET", f"/assessment-jobs/{job_id}")
        if status != 200:
            result.fail("fast assessment job poll", f"HTTP {status}: {payload_detail(last_payload)}")
            return ""
        state = last_payload.get("status") if isinstance(last_payload, dict) else ""
        if state == "completed":
            assessment = last_payload.get("assessment") or {}
            assessment_id = assessment.get("assessment_id") or last_payload.get("assessment_id") or ""
            expect(bool(assessment_id), result, "fast assessment produced report", str(assessment_id))
            expect((assessment.get("mode") == "fast"), result, "fast assessment mode", str(assessment.get("mode")))
            expect(bool((assessment.get("verdict") or {}).get("label")), result, "fast assessment verdict", str((assessment.get("verdict") or {}).get("label")))
            return str(assessment_id)
        if state == "failed":
            result.fail("fast assessment job completed", f"failed: {last_payload.get('error') if isinstance(last_payload, dict) else last_payload}")
            return ""
    result.fail("fast assessment job completed", f"timed out after {poll_seconds}s; last={payload_detail(last_payload)}")
    return ""


def check_deep(client: SmokeClient, result: SmokeResult) -> None:
    status, payload, _headers = client.request(
        "POST",
        "/assessments/deep",
        {"claim": "The Eiffel Tower is in Paris.", "source_url": "", "category": "general"},
    )
    if status == 200 and isinstance(payload, dict):
        expect(payload.get("mode") == "deep", result, "deep assessment mode", str(payload.get("mode")))
        expect(isinstance((payload.get("verdict") or {}).get("evidence_strength_score"), (int, float)), result, "deep evidence score present", str((payload.get("verdict") or {}).get("evidence_strength_score")))
    else:
        result.fail("deep assessment", f"HTTP {status}: {payload_detail(payload)}")


def check_speech(client: SmokeClient, result: SmokeResult) -> None:
    transcript = "Today I said that the Eiffel Tower is in Paris. I also said that Mars is closer to Earth than the Moon, which needs checking."
    status, payload, _headers = client.request(
        "POST",
        "/speech/extract",
        {"transcript": transcript, "source_url": "", "max_claims": 1, "try_youtube_captions": False},
    )
    if status != 200 or not isinstance(payload, dict):
        result.fail("speech extract", f"HTTP {status}: {payload_detail(payload)}")
        return
    result.pass_("speech extract", "HTTP 200")
    extraction = payload.get("result") or {}
    claims = extraction.get("claims") or extraction.get("claims_extracted") or []
    if not claims:
        result.fail("speech extract claims", "no claims returned")
        return
    status, payload, _headers = client.request(
        "POST",
        "/speech/verify",
        {"claims": claims[:1], "source_url": "", "verification_mode": "fast"},
    )
    if status == 200 and isinstance(payload, dict):
        checked = (payload.get("result") or {}).get("claims_checked") or []
        expect(bool(checked), result, "speech verify checked claims", f"{len(checked)} checked")
    else:
        result.fail("speech verify", f"HTTP {status}: {payload_detail(payload)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Evidrai production smoke checks.")
    parser.add_argument("--api-base-url", default=os.getenv("EVIDRAI_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--web-url", default=os.getenv("EVIDRAI_WEB_URL", DEFAULT_WEB_URL))
    parser.add_argument("--user-id", default=os.getenv("EVIDRAI_SMOKE_USER_ID", f"anon_smoke_{int(time.time())}"))
    parser.add_argument("--access-token", default=os.getenv("EVIDRAI_ACCESS_TOKEN", ""))
    parser.add_argument("--run-deep", action="store_true", default=os.getenv("EVIDRAI_RUN_DEEP", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--run-speech", action="store_true", default=os.getenv("EVIDRAI_RUN_SPEECH", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--require-auth-features", action="store_true", default=os.getenv("EVIDRAI_REQUIRE_AUTH_FEATURES", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--timeout", type=float, default=float(os.getenv("EVIDRAI_SMOKE_TIMEOUT", "30")))
    parser.add_argument("--poll-seconds", type=int, default=int(os.getenv("EVIDRAI_SMOKE_POLL_SECONDS", "90")))
    args = parser.parse_args()

    result = SmokeResult()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    client = SmokeClient(args.api_base_url, args.user_id, args.access_token, timeout=args.timeout)

    result.note(f"Started: {started}")
    result.note(f"API: {args.api_base_url}")
    result.note(f"Web: {args.web_url}")
    result.note(f"Smoke user: {args.user_id}")

    try:
        check_frontend(args.web_url, result, args.timeout)
    except Exception as exc:  # noqa: BLE001 - smoke script should keep collecting failures
        result.fail("frontend checks", f"{type(exc).__name__}: {exc}")

    runtime = check_get(client, "/runtime", "api runtime", result)
    if isinstance(runtime, dict):
        result.note(f"API build: {runtime.get('build', 'unknown')}")
    tiers = check_get(client, "/tiers", "api tiers", result)
    if isinstance(tiers, dict):
        expect(bool(tiers.get("tiers")), result, "tier definitions present", f"{len(tiers.get('tiers') or [])} tiers")
    me = check_get(client, "/me", "api me", result)
    if isinstance(me, dict):
        user = me.get("user") or {}
        result.note(f"Profile: authenticated={me.get('authenticated')} tier={user.get('tier')} label={user.get('tier_label')}")
    check_get(client, "/reports", "reports list", result)

    assessment_id = create_fast_job(client, result, args.poll_seconds)
    if assessment_id:
        status, payload, _headers = client.request("GET", f"/reports/{assessment_id}")
        if status == 200 and isinstance(payload, dict):
            expect(payload.get("assessment_id") == assessment_id, result, "saved report reload", assessment_id)
        else:
            result.fail("saved report reload", f"HTTP {status}: {payload_detail(payload)}")

    if args.run_deep:
        if args.access_token:
            check_deep(client, result)
        elif args.require_auth_features:
            result.fail("deep assessment", "EVIDRAI_ACCESS_TOKEN required")
        else:
            result.skip("deep assessment", "set EVIDRAI_ACCESS_TOKEN and EVIDRAI_RUN_DEEP=1")
    else:
        result.skip("deep assessment", "not requested; set EVIDRAI_RUN_DEEP=1")

    if args.run_speech:
        if args.access_token:
            check_speech(client, result)
        elif args.require_auth_features:
            result.fail("speech audit", "EVIDRAI_ACCESS_TOKEN required")
        else:
            result.skip("speech audit", "set EVIDRAI_ACCESS_TOKEN and EVIDRAI_RUN_SPEECH=1")
    else:
        result.skip("speech audit", "not requested; set EVIDRAI_RUN_SPEECH=1")

    print("\nEvidrai production smoke")
    print("=" * 28)
    for note in result.notes:
        print(f"ℹ {note}")
    for item in result.passed:
        print(f"✓ {item}")
    for item in result.skipped:
        print(f"- SKIP {item}")
    for item in result.failed:
        print(f"✗ {item}")
    print(f"\nSummary: {len(result.passed)} passed, {len(result.skipped)} skipped, {len(result.failed)} failed")
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
