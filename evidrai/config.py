from __future__ import annotations

import os
from dataclasses import dataclass
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


APP_BUILD = "2026-05-13-typed-pipeline-results"

SCORING_CONFIG = ScoringConfig()


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
