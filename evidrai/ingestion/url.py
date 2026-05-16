from __future__ import annotations

import re
from html import unescape
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from evidrai.errors import EvidraiError
from evidrai.utils import domain_from_url, is_probable_url


class SourceExtractionError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: Optional[str] = None, status_code: int = 422) -> None:
        super().__init__(message, code="source_extraction_error", status_code=status_code, developer_detail=developer_detail)


class ExtractedSource(BaseModel):
    schema_version: str = "source_extract.v1"
    ok: bool = True
    url: str
    final_url: str = ""
    domain: str = ""
    title: str = ""
    description: str = ""
    text: str = ""
    excerpt: str = ""
    candidate_claims: List[str] = Field(default_factory=list)
    word_count: int = 0
    extraction_method: str = "html_text"


def _first_match(patterns: List[str], html: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            return clean_text(match.group(1))
    return ""


def clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav|aside)\b.*?</\1>", " ", html or "")
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p\s*>", "\n", html)
    html = re.sub(r"(?is)</(h1|h2|h3|li)\s*>", "\n", html)
    text = clean_text(html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title(html: str) -> str:
    return _first_match(
        [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
            r"<title[^>]*>(.*?)</title>",
            r"<h1[^>]*>(.*?)</h1>",
        ],
        html,
    )


def extract_description(html: str) -> str:
    return _first_match(
        [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        ],
        html,
    )


def candidate_claims_from_text(title: str, description: str, text: str, max_claims: int = 5) -> List[str]:
    candidates: List[str] = []
    for item in (title, description):
        item = clean_text(item)
        if item and len(item) >= 20:
            candidates.append(item)
    sentences = re.split(r"(?<=[.!?])\s+", text or "")
    for sentence in sentences:
        cleaned = clean_text(sentence)
        if 40 <= len(cleaned) <= 260 and re.search(r"\b(is|are|was|were|has|have|will|said|says|found|reported|announced|claims?)\b", cleaned, flags=re.I):
            candidates.append(cleaned)
        if len(candidates) >= max_claims * 2:
            break
    deduped: List[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
        if len(deduped) >= max_claims:
            break
    return deduped


def extract_source_from_html(url: str, html: str, *, final_url: Optional[str] = None) -> ExtractedSource:
    if not is_probable_url(url):
        raise SourceExtractionError("source_url must start with http:// or https://", status_code=400)
    text = html_to_text(html)
    title = extract_title(html)
    description = extract_description(html)
    excerpt = text[:1800]
    return ExtractedSource(
        url=url,
        final_url=final_url or url,
        domain=domain_from_url(final_url or url),
        title=title,
        description=description,
        text=text,
        excerpt=excerpt,
        candidate_claims=candidate_claims_from_text(title, description, text),
        word_count=len(re.findall(r"\w+", text)),
    )


def fetch_source_url(url: str, *, timeout: int = 20) -> ExtractedSource:
    if not is_probable_url(url):
        raise SourceExtractionError("source_url must start with http:// or https://", status_code=400)
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Evidrai/0.1 source extractor (+https://evidrai.local)"},
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise SourceExtractionError(
                "Could not fetch source URL.",
                developer_detail=f"HTTP {response.status_code}: {(response.text or '')[:300]}",
                status_code=502,
            )
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and response.text.lstrip().startswith("<") is False:
            raise SourceExtractionError("Source URL did not return readable HTML.", developer_detail=content_type or "unknown content-type")
        return extract_source_from_html(url, response.text, final_url=response.url)
    except SourceExtractionError:
        raise
    except requests.RequestException as exc:
        raise SourceExtractionError("Could not fetch source URL.", developer_detail=str(exc), status_code=502)
