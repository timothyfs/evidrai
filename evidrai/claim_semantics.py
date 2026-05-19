from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List

DISCLOSURE_TERMS = {
    "disclose": "disclosure/reporting obligation",
    "disclosed": "disclosure/reporting obligation",
    "disclosing": "disclosure/reporting obligation",
    "declare": "formal declaration/register obligation",
    "declared": "formal declaration/register obligation",
    "declaring": "formal declaration/register obligation",
    "report": "reporting obligation",
    "reported": "reporting obligation",
    "register": "register entry obligation",
    "registered": "register entry obligation",
}

SYNONYM_GROUPS = [
    {"disclose", "disclosed", "disclosing", "declare", "declared", "declaring", "report", "reported", "register", "registered"},
    {"donation", "donations", "funding", "funds", "gift", "gifts", "payment", "payments"},
    {"failed", "fail", "failure", "did", "not", "no"},
]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "has", "have", "in", "is", "it", "of", "on", "or", "the", "to", "was", "were", "with",
}


@dataclass(frozen=True)
class ClaimSemantics:
    canonical_claim_key: str
    canonical_terms: List[str]
    distinction_terms: List[str]
    precision_note: str
    expanded_queries: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_claim_key": self.canonical_claim_key,
            "canonical_terms": list(self.canonical_terms),
            "distinction_terms": list(self.distinction_terms),
            "precision_note": self.precision_note,
            "expanded_queries": list(self.expanded_queries),
        }


def _tokens(text: str) -> List[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z£$€0-9][A-Za-z0-9£$€.,-]*", text or "")]


def _canonical_token(token: str) -> str:
    clean = token.lower().strip(".,;:!?()[]{}\"'")
    for group in SYNONYM_GROUPS:
        if clean in group:
            return sorted(group)[0]
    if clean.endswith("s") and len(clean) > 4:
        return clean[:-1]
    return clean


def _canonical_terms(text: str) -> List[str]:
    terms: List[str] = []
    for token in _tokens(text):
        canonical = _canonical_token(token)
        if canonical and canonical not in STOPWORDS and canonical not in terms:
            terms.append(canonical)
    return terms


def _distinction_terms(text: str) -> List[str]:
    found: List[str] = []
    for token in _tokens(text):
        clean = token.lower().strip(".,;:!?()[]{}\"'")
        label = DISCLOSURE_TERMS.get(clean)
        if label and label not in found:
            found.append(label)
    return found


def _fingerprint(terms: List[str]) -> str:
    material = "|".join(sorted(terms))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"claim_{digest}"


def _expanded_queries(text: str, terms: List[str]) -> List[str]:
    lower = text.lower()
    queries: List[str] = []
    if any(term in lower for term in ["disclose", "declare", "declared", "disclosed", "register", "reported"]):
        subject_terms = [term for term in terms if term not in {"declare", "disclose", "donation", "failed", "not", "report", "register"}]
        subject = " ".join(subject_terms[:4]).strip()
        base = subject or text
        queries.extend([
            f"{base} disclose declare donations",
            f"{base} register declared donations official",
            f"{base} funding donations disclosure rules",
            f"{base} declaration register donations evidence",
        ])
    return [re.sub(r"\s+", " ", query).strip() for query in queries if query.strip()]


def analyze_claim_semantics(text: str) -> ClaimSemantics:
    terms = _canonical_terms(text)
    distinction_terms = _distinction_terms(text)
    precision_note = ""
    if len(distinction_terms) > 1 or distinction_terms:
        precision_note = (
            "This claim appears related to a disclosure/declaration obligation. Evidrai treats near-synonyms as related for retrieval, "
            "but does not collapse them into the same legal conclusion: a professional researcher, journalist, or lawyer may need to distinguish public disclosure, formal declaration, register entry, and reporting duties."
        )
    return ClaimSemantics(
        canonical_claim_key=_fingerprint(terms),
        canonical_terms=terms,
        distinction_terms=distinction_terms,
        precision_note=precision_note,
        expanded_queries=_expanded_queries(text, terms),
    )


def merge_semantic_queries(base_queries: List[str], semantics: ClaimSemantics, limit: int = 16) -> List[str]:
    merged: List[str] = []
    for query in [*base_queries, *semantics.expanded_queries]:
        clean = re.sub(r"\s+", " ", query or "").strip()
        if clean and clean not in merged:
            merged.append(clean)
    return merged[:limit]
