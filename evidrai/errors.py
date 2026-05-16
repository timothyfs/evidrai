from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EvidraiError(Exception):
    """Base application error with safe user-facing detail."""

    message: str
    code: str = "evidrai_error"
    status_code: int = 500
    developer_detail: Optional[str] = None

    def __str__(self) -> str:
        return self.message


class ConfigurationError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: Optional[str] = None) -> None:
        super().__init__(message, code="configuration_error", status_code=503, developer_detail=developer_detail)


class LLMRequestError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: Optional[str] = None, status_code: int = 502) -> None:
        super().__init__(message, code="llm_request_error", status_code=status_code, developer_detail=developer_detail)


class SearchRequestError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: Optional[str] = None, status_code: int = 502) -> None:
        super().__init__(message, code="search_request_error", status_code=status_code, developer_detail=developer_detail)


def safe_error_payload(exc: EvidraiError, *, include_debug: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {"code": exc.code, "message": exc.message}
    if include_debug and exc.developer_detail:
        payload["developer_detail"] = exc.developer_detail
    return payload
