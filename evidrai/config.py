from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import subprocess
from typing import Any, Optional, Sequence

import requests
import streamlit as st


@dataclass(frozen=True)
class ScoringConfig:
    authority_weight: float = 0.30
    relevance_weight: float = 0.25
    directness_weight: float = 0.20
    recency_weight: float = 0.15
    bias_weight: float = 0.10
    max_source_summaries: int = 8
    max_summary_workers: int = 4
    max_retries: int = 3
    retry_base_sleep: float = 1.0
    term_pattern: str = r"\b{term}\b"


APP_BUILD_LABEL = "phase-1-api"


@lru_cache(maxsize=1)
def get_app_build() -> str:
    """Return a visible build identifier that changes automatically on deploy.

    Streamlit Cloud exposes commit metadata in some environments; local runs fall
    back to the current Git commit. The label is intentionally human-readable,
    while the commit hash confirms the exact deployed version.
    """
    commit = (
        os.getenv("STREAMLIT_GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or os.getenv("VERCEL_GIT_COMMIT_SHA")
        or _local_git_commit()
    )
    short_commit = commit[:7] if commit else "unknown"
    return f"{APP_BUILD_LABEL}-{short_commit}"


def _local_git_commit() -> Optional[str]:
    try:
        repo_root = Path(__file__).resolve().parents[1]
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except Exception:
        return None

SCORING_CONFIG = ScoringConfig()


DATABASE_URL_SECRET_PATHS = (
    ("database", "url"),
    ("postgres", "url"),
    ("supabase", "database_url"),
    ("supabase", "db_url"),
    ("DATABASE_URL",),
    ("database_url",),
    ("POSTGRES_URL",),
    ("SUPABASE_DATABASE_URL",),
)
DATABASE_URL_ENV_NAMES = ("DATABASE_URL", "POSTGRES_URL", "SUPABASE_DATABASE_URL")


def database_url() -> Optional[str]:
    value = read_config_value(
        secret_paths=DATABASE_URL_SECRET_PATHS,
        env_names=DATABASE_URL_ENV_NAMES,
    )
    if value and value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    return value


def config_presence_diagnostics() -> dict[str, Any]:
    """Return non-secret config diagnostics for UI troubleshooting."""
    secret_keys: list[str] = []
    try:
        secrets = getattr(st, "secrets", {})
        if hasattr(secrets, "keys"):
            secret_keys = sorted(str(key) for key in secrets.keys())
    except Exception:
        secret_keys = []

    configured_paths = []
    for path in DATABASE_URL_SECRET_PATHS:
        if _clean_secret(_lookup_secret(path)):
            configured_paths.append(".".join(path))

    configured_env = [name for name in DATABASE_URL_ENV_NAMES if _clean_secret(os.getenv(name))]
    return {
        "database_url_configured": bool(database_url()),
        "database_secret_paths_configured": configured_paths,
        "database_env_names_configured": configured_env,
        "streamlit_secret_keys": secret_keys,
    }


def _lookup_secret(path: Sequence[str]) -> Optional[Any]:
    """Read from Streamlit secrets without assuming a specific secrets.toml shape."""
    try:
        current: Any = getattr(st, "secrets", {})
    except Exception:
        return None
    for part in path:
        try:
            if hasattr(current, "get"):
                current = current.get(part)
            else:
                current = current[part]
        except Exception:
            return None
        if current is None:
            return None
    return current


def _clean_secret(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    if not text or text.lower() in {"test", "todo", "changeme", "your_key_here", "paste_token_here"}:
        return None
    return text


def read_config_value(
    secret_paths: Sequence[Sequence[str]],
    env_names: Sequence[str],
    default: Optional[str] = None,
) -> Optional[str]:
    for path in secret_paths:
        cleaned = _clean_secret(_lookup_secret(path))
        if cleaned:
            return cleaned
    for env_name in env_names:
        cleaned = _clean_secret(os.getenv(env_name))
        if cleaned:
            return cleaned
    return default


def normalize_openai_base_url(value: Optional[str]) -> str:
    base_url = (value or "https://api.openai.com/v1").strip().rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
    return base_url or "https://api.openai.com/v1"


def http_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message") or payload.get("message")
        if message:
            return str(message)
    except Exception:
        pass
    return (response.text or response.reason or "HTTP error")[:500]
