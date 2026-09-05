"""Per-assessment cost and usage telemetry.

Additive instrumentation so we can understand cost-per-verification before
designing enterprise usage pricing. Nothing here changes verification behaviour;
it only observes LLM token usage, retrieval-call counts, timing, and a rough
cost estimate. A single TelemetryCollector is attached to the shared LLM and
search clients for one assessment and safely accumulates across the pipeline's
worker threads.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Default per-1K-token prices (USD). Chosen for the default gpt-4o-mini model.
# Override per deployment with env vars; keep these conservative and clearly
# labelled as estimates rather than billed amounts.
_DEFAULT_INPUT_COST_PER_1K = 0.00015
_DEFAULT_OUTPUT_COST_PER_1K = 0.00060
_DEFAULT_SEARCH_COST_PER_CALL = 0.0


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int, search_calls: int) -> float:
    """Rough cost estimate. Not a billed figure — a planning signal."""
    input_cost = (prompt_tokens / 1000.0) * _env_float("EVIDRAI_LLM_INPUT_COST_PER_1K", _DEFAULT_INPUT_COST_PER_1K)
    output_cost = (completion_tokens / 1000.0) * _env_float("EVIDRAI_LLM_OUTPUT_COST_PER_1K", _DEFAULT_OUTPUT_COST_PER_1K)
    search_cost = search_calls * _env_float("EVIDRAI_SEARCH_COST_PER_CALL", _DEFAULT_SEARCH_COST_PER_CALL)
    return round(input_cost + output_cost + search_cost, 6)


@dataclass
class TelemetryCollector:
    """Thread-safe accumulator for a single assessment run."""

    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    search_calls: int = 0
    models: List[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_llm(self, model: str, usage: Optional[Dict[str, Any]]) -> None:
        usage = usage or {}

        def _as_int(value: Any) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

        prompt = _as_int(usage.get("prompt_tokens"))
        completion = _as_int(usage.get("completion_tokens"))
        total = _as_int(usage.get("total_tokens")) or (prompt + completion)
        with self._lock:
            self.llm_calls += 1
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_tokens += total
            if model and model not in self.models:
                self.models.append(model)

    def record_search(self, count: int = 1) -> None:
        with self._lock:
            self.search_calls += max(0, int(count))

    def snapshot(self, *, elapsed_ms: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            model = self.models[0] if len(self.models) == 1 else (",".join(self.models) if self.models else "")
            return {
                "model": model,
                "llm_calls": self.llm_calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "search_calls": self.search_calls,
                "elapsed_ms": elapsed_ms,
                "estimated_cost_usd": estimate_cost_usd(self.prompt_tokens, self.completion_tokens, self.search_calls),
            }
