from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from evidrai.config import SCORING_CONFIG, read_config_value

class TavilySearchClient:
    def __init__(self) -> None:
        self.api_key = read_config_value(
            secret_paths=(
                ("TAVILY_API_KEY",),
                ("tavily", "api_key"),
                ("tavily", "TAVILY_API_KEY"),
            ),
            env_names=("TAVILY_API_KEY",),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if not self.configured:
            return []
        last_exc: Optional[Exception] = None
        for attempt in range(SCORING_CONFIG.max_retries):
            try:
                response = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_raw_content": True,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                out: List[Dict[str, Any]] = []
                for item in data.get("results", []):
                    out.append(
                        {
                            "title": item.get("title", "Untitled"),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", "")[:500],
                            "content": item.get("raw_content") or item.get("content") or "",
                            "published_date": item.get("published_date"),
                        }
                    )
                return out
            except (requests.RequestException, ValueError, TypeError) as exc:
                last_exc = exc
                if attempt == SCORING_CONFIG.max_retries - 1:
                    break
                time.sleep(SCORING_CONFIG.retry_base_sleep * (2 ** attempt))
        raise RuntimeError(f"Search request failed after retries: {last_exc}")
