from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from pydantic import ValidationError

from prompts import load_json
from evidrai.config import SCORING_CONFIG

class OpenAICompatibleClient:
    def __init__(self) -> None:
        secrets = getattr(st, "secrets", {})
        self.api_key = secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
        self.base_url = secrets.get("OPENAI_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        self.model = secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        if not self.configured:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        last_exc: Optional[Exception] = None
        for attempt in range(SCORING_CONFIG.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "temperature": temperature,
                        "response_format": {"type": "json_object"},
                        "messages": messages,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = load_json(content)
                if not isinstance(parsed, dict):
                    raise ValueError("Model returned non-object JSON.")
                return parsed
            except (requests.RequestException, ValueError, KeyError, ValidationError, TypeError) as exc:
                last_exc = exc
                if attempt == SCORING_CONFIG.max_retries - 1:
                    break
                time.sleep(SCORING_CONFIG.retry_base_sleep * (2 ** attempt))
        raise RuntimeError(f"LLM request failed after retries: {last_exc}")
