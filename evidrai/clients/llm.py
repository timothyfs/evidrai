from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from pydantic import ValidationError

from prompts import load_json
from evidrai.config import SCORING_CONFIG, http_error_detail, normalize_openai_base_url, read_config_value
from evidrai.errors import ConfigurationError, LLMRequestError

class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.api_key = read_config_value(
            secret_paths=(
                ("OPENAI_API_KEY",),
                ("openai", "api_key"),
                ("openai", "OPENAI_API_KEY"),
            ),
            env_names=("OPENAI_API_KEY",),
        )
        self.base_url = normalize_openai_base_url(
            read_config_value(
                secret_paths=(
                    ("OPENAI_BASE_URL",),
                    ("openai", "base_url"),
                    ("openai", "OPENAI_BASE_URL"),
                ),
                env_names=("OPENAI_BASE_URL",),
                default="https://api.openai.com/v1",
            )
        )
        self.model = read_config_value(
            secret_paths=(
                ("OPENAI_MODEL",),
                ("openai", "model"),
                ("openai", "OPENAI_MODEL"),
            ),
            env_names=("OPENAI_MODEL",),
            default="gpt-4o-mini",
        ) or "gpt-4o-mini"
        fallback_models = read_config_value(
            secret_paths=(
                ("OPENAI_FALLBACK_MODELS",),
                ("openai", "fallback_models"),
                ("openai", "OPENAI_FALLBACK_MODELS"),
            ),
            env_names=("OPENAI_FALLBACK_MODELS",),
            default="gpt-4o-mini",
        ) or ""
        self.fallback_models = [model.strip() for model in str(fallback_models).split(",") if model.strip() and model.strip() != self.model]

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        if not self.configured:
            raise ConfigurationError("OPENAI_API_KEY is not configured in app secrets or environment variables.")
        last_exc: Optional[Exception] = None
        model_candidates = [self.model, *self.fallback_models]
        for model in model_candidates:
            for attempt in range(SCORING_CONFIG.max_retries):
                try:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "temperature": temperature,
                            "response_format": {"type": "json_object"},
                            "messages": messages,
                        },
                        timeout=60,
                    )
                    if response.status_code in {401, 403}:
                        raise LLMRequestError("OpenAI authentication failed.", developer_detail=http_error_detail(response), status_code=503)
                    if response.status_code == 429:
                        last_exc = LLMRequestError("OpenAI rate limit hit.", developer_detail=http_error_detail(response), status_code=429)
                        if attempt == SCORING_CONFIG.max_retries - 1:
                            break
                        retry_after = response.headers.get("Retry-After")
                        sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else SCORING_CONFIG.retry_base_sleep * (2 ** attempt)
                        time.sleep(sleep_for)
                        continue
                    if 400 <= response.status_code < 500:
                        raise LLMRequestError("OpenAI request was rejected.", developer_detail=http_error_detail(response), status_code=503)
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = load_json(content)
                    if not isinstance(parsed, dict):
                        raise ValueError("Model returned non-object JSON.")
                    return parsed
                except (ConfigurationError, LLMRequestError):
                    raise
                except (requests.RequestException, ValueError, KeyError, ValidationError, TypeError) as exc:
                    last_exc = exc
                    if attempt == SCORING_CONFIG.max_retries - 1:
                        break
                    time.sleep(SCORING_CONFIG.retry_base_sleep * (2 ** attempt))
        if isinstance(last_exc, LLMRequestError):
            raise last_exc
        raise LLMRequestError("LLM request failed after retries.", developer_detail=str(last_exc))
