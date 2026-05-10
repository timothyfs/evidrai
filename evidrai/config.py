from __future__ import annotations

from dataclasses import dataclass

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


