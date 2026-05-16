from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.config import get_app_build
from evidrai.errors import EvidraiError
from evidrai.export import assessment_export_json
from evidrai.feedback import build_feedback_record, feedback_backend_status, save_feedback
from evidrai.pipeline.verification import run_claim_pipeline, run_quick_pass, run_speech_audit
from evidrai.rules.verdict import (
    map_confidence_label,
    map_pipeline_verdict,
    map_source_quality_label,
    normalize_claim_support,
)
from evidrai.transcripts import clean_pasted_youtube_transcript, extract_youtube_transcript
from evidrai.utils import build_analysis_input, is_probable_url, stable_request_key


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def numeric_score(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_score_bar(label: str, score: Any, max_score: float, help_text: str = "") -> None:
    value = numeric_score(score)
    pct = clamp(value / max_score if max_score else 0.0)
    st.progress(pct, text=f"{label}: {value:.1f}/{max_score:g}" + (f" · {help_text}" if help_text else ""))


def render_claim_under_review(result: Dict[str, Any]) -> None:
    claim = (result.get("claim") or "").strip()
    subclaims = result.get("subclaims", []) or []
    if not claim and not subclaims:
        return
    st.markdown("### Claim under review")
    if claim:
        st.write(claim)
    if subclaims:
        with st.expander("Subclaims extracted", expanded=False):
            for item in subclaims:
                st.write(f"- {item}")


def claim_dimension_for(subclaim: Dict[str, Any]) -> str:
    claim_type = (subclaim.get("claim_type") or "").lower()
    flags = {str(flag).lower() for flag in subclaim.get("risk_flags", []) or []}
    requirements = " ".join(subclaim.get("verification_requirements", []) or []).lower()
    text = (subclaim.get("text") or "").lower()
    if claim_type in {"legal"} or "legal" in flags or "rule" in requirements or "required" in text or "obligation" in text:
        return "Obligation / rule"
    if claim_type in {"criminal", "corruption", "misconduct_named_person"} or "wrongdoing" in flags:
        return "Wrongdoing / allegation"
    if flags & {"opinion", "value_judgment", "motive_attribution", "ambiguity"}:
        return "Interpretation"
    if claim_type in {"factual", "finance", "health", "science"}:
        return "Factual core"
    return "Context"


def render_claim_breakdown(result: Dict[str, Any]) -> None:
    analysis = result.get("claim_analysis", {}) or {}
    subclaims = analysis.get("subclaims", []) or []
    if not subclaims:
        return
    verdict = map_pipeline_verdict(result.get("verified_verdict") or result.get("verdict") or "Unverified")
    confidence = map_confidence_label(result.get("verified_confidence") or result.get("confidence", "Medium"))
    st.markdown("### Claim breakdown")
    st.caption("Separates factual core from interpretation, obligation, and allegation so one label does not flatten the whole claim.")
    for idx, sub in enumerate(subclaims, start=1):
        if not isinstance(sub, dict):
            st.write(f"- {sub}")
            continue
        dimension = claim_dimension_for(sub)
        status = verdict
        if dimension in {"Interpretation", "Obligation / rule", "Wrongdoing / allegation"} and verdict in {"Supported", "Likely supported", "Partly supported"}:
            status = "Contested / needs qualification"
        flags = sub.get("risk_flags", []) or []
        st.markdown(f"**{idx}. {sub.get('text', 'Subclaim')}**")
        st.caption(f"{dimension} · {status} · Confidence: {confidence}" + (f" · Flags: {', '.join(flags[:4])}" if flags else ""))


def evidence_role_for_source(src: Dict[str, Any]) -> str:
    role = (src.get("source_role") or "").strip().lower()
    category = (src.get("evidence_category") or "").strip().lower()
    support = normalize_claim_support(src.get("claim_support"))
    if support == "Contradicts" or category == "credible_contradiction":
        return "Contradicts factual core"
    if support == "Supports" and category in {"direct_evidence", "credible_reporting", "expert_analysis"}:
        return "Supports factual core"
    if role in {"interpretation", "analysis"} or support == "Mixed":
        return "Disputes or qualifies interpretation"
    if category in {"reported_allegation", "contextual_signal", "denial_or_rebuttal"}:
        return "Reported but unconfirmed / context"
    return "Weak, contextual, or unclear"


def render_evidence_snapshot(sources: List[Dict[str, Any]]) -> None:
    if not sources:
        return
    supporting = [s for s in sources if normalize_claim_support(s.get("claim_support")) == "Supports"]
    contradicting = [s for s in sources if normalize_claim_support(s.get("claim_support")) == "Contradicts"]
    contextual = [s for s in sources if normalize_claim_support(s.get("claim_support")) in {"Mixed", "Context"}]
    total = max(len(sources), 1)

    st.markdown("### Evidence map")
    c1, c2, c3 = st.columns(3)
    c1.metric("Supporting", len(supporting))
    c2.metric("Contradicting", len(contradicting))
    c3.metric("Contextual / mixed", len(contextual))

    st.caption("Evidence mix across the reviewed source set. Grouped by what each source actually does for the claim.")
    render_score_bar("Supporting", len(supporting), total)
    render_score_bar("Contradicting", len(contradicting), total)
    render_score_bar("Contextual / mixed", len(contextual), total)

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for src in sources:
        grouped.setdefault(evidence_role_for_source(src), []).append(src)
    buckets = [
        ("Supports factual core", grouped.get("Supports factual core", [])),
        ("Contradicts factual core", grouped.get("Contradicts factual core", [])),
        ("Disputes or qualifies interpretation", grouped.get("Disputes or qualifies interpretation", [])),
        ("Reported but unconfirmed / context", grouped.get("Reported but unconfirmed / context", [])),
        ("Weak, contextual, or unclear", grouped.get("Weak, contextual, or unclear", [])),
    ]
    for title, bucket in buckets:
        st.markdown(f"**{title}**")
        if not bucket:
            st.caption("None surfaced in the reviewed set.")
            continue
        for src in bucket[:3]:
            summary = src.get("summary") or src.get("snippet") or src.get("title") or "Untitled"
            st.write(f"- {summary}")


def source_quality_stats(result: Dict[str, Any]) -> Dict[str, Any]:
    sources = result.get("sources", []) or []
    primary = sum(1 for s in sources if (s.get("source_type") or "").lower() == "primary")
    high_quality = sum(1 for s in sources if map_source_quality_label(s.get("weighted_score")) == "High")
    contradictions = sum(1 for s in sources if normalize_claim_support(s.get("claim_support")) == "Contradicts")
    supporting = sum(1 for s in sources if normalize_claim_support(s.get("claim_support")) == "Supports")
    contextual = sum(1 for s in sources if normalize_claim_support(s.get("claim_support")) in {"Mixed", "Context"})
    avg_score = sum(numeric_score(s.get("weighted_score")) for s in sources) / len(sources) if sources else 0.0
    return {
        "sources": sources,
        "source_count": len(sources),
        "primary": primary,
        "high_quality": high_quality,
        "contradictions": contradictions,
        "supporting": supporting,
        "contextual": contextual,
        "avg_score": avg_score,
        "primary_ratio": primary / len(sources) if sources else 0.0,
        "high_quality_ratio": high_quality / len(sources) if sources else 0.0,
    }


def render_evidence_scorecard(result: Dict[str, Any]) -> None:
    stats = source_quality_stats(result)
    pendulum = result.get("pendulum", {}) or {}
    band = result.get("pendulum_band", "") or pendulum.get("band", "Mixed / uncertain")
    score = result.get("pendulum_score", None) if result.get("pendulum_score", None) is not None else pendulum.get("score")

    st.markdown("### Evidence scorecard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evidence strength", band)
    c2.metric("Avg source quality", f"{stats['avg_score']:.1f}/5")
    c3.metric("Primary sources", f"{stats['primary']}/{stats['source_count']}")
    c4.metric("Contradictions", stats["contradictions"])

    if score is not None:
        render_score_bar("Overall evidence strength", score, 10, band)
    render_score_bar("Average source quality", stats["avg_score"], 5)
    render_score_bar("Primary-source share", stats["primary_ratio"] * 100, 100)
    render_score_bar("High-quality share", stats["high_quality_ratio"] * 100, 100)


def render_amplification_warning(result: Dict[str, Any]) -> None:
    warning = result.get("amplification_warning") or {}
    if not warning.get("triggered"):
        return

    details = warning.get("details") or {}
    level = str(warning.get("level") or "medium").title()
    st.warning(warning.get("message") or "Repeated coverage detected. Evidrai treats amplification as visibility, not corroboration.")
    st.caption(
        f"Amplification risk: {level} · "
        f"{details.get('unique_narrative_clusters', 0)} narrative cluster(s) across "
        f"{details.get('source_count', 0)} source(s) · "
        f"{details.get('substantive_support_clusters', 0)} substantive support chain(s) · "
        f"{details.get('primary_support_clusters', 0)} primary support chain(s)."
    )


def render_assessment_metrics(result: Dict[str, Any]) -> None:
    stats = source_quality_stats(result)
    elapsed = result.get("elapsed_seconds")

    st.markdown("### Assessment quality details")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sources reviewed", stats["source_count"])
    c2.metric("Supporting", stats["supporting"])
    c3.metric("Contextual / mixed", stats["contextual"])
    c4.metric("High-quality", stats["high_quality"])

    if elapsed is not None:
        st.caption(f"Completed in {elapsed:.1f}s")


def render_feedback_controls(
    result_key: str,
    result: Optional[Dict[str, Any]] = None,
    source_url: str = "",
    settings: Optional[Dict[str, Any]] = None,
) -> None:
    feedback_store = st.session_state.setdefault("feedback_log", {})
    st.markdown("### Feedback")
    backend = feedback_backend_status()
    if backend.get("notion_configured"):
        st.caption("Feedback is saved to the server log and Notion.")
    else:
        st.caption("Feedback is saved to the server log. Notion logging is not configured yet.")

    rating = st.radio(
        "Was this useful?",
        ["Useful", "Partly useful", "Not useful"],
        horizontal=True,
        key=f"fb_rating_{result_key}",
    )
    reasons = st.multiselect(
        "What should improve?",
        [
            "Verdict clarity",
            "Confidence explanation",
            "Source quality",
            "Missing source",
            "Too much detail",
            "Not enough detail",
            "Visual presentation",
            "Other",
        ],
        key=f"fb_reasons_{result_key}",
    )
    comment = st.text_area(
        "Optional comment",
        placeholder="What confused you, what helped, or what source should Evidrai have considered?",
        height=90,
        key=f"fb_comment_{result_key}",
    )

    if st.button("Submit feedback", key=f"fb_submit_{result_key}", use_container_width=True):
        record = build_feedback_record(
            result_key=result_key,
            rating=rating,
            reasons=reasons,
            comment=comment,
            result=result,
            source_url=source_url,
            settings=settings,
        )
        save_result = save_feedback(record)
        feedback_store[result_key] = record | {
            "saved": save_result.ok,
            "destination": save_result.destination,
            "save_message": save_result.message,
        }
        if save_result.ok:
            st.success(f"Feedback captured. {save_result.message}")
        else:
            st.error(save_result.message)

    if result_key in feedback_store:
        latest = feedback_store[result_key]
        st.caption(f"Latest feedback: {latest.get('rating', 'captured')} · {latest.get('destination', 'session')}")


def render_methodology_note() -> None:
    with st.expander("How Evidrai reached this assessment", expanded=False):
        st.write("Claim extraction → query generation → source retrieval → source ranking → contradiction check → verdict and confidence.")
        st.write("A rule engine then checks whether the final verdict is too strong for the evidence packet and can downgrade it to stay aligned with Evidrai's verification policy.")
        st.write("Confidence reflects the quantity, quality, directness, recency, and agreement level of the reviewed evidence. It is not a claim of certainty.")


def render_public_methodology_explainer() -> None:
    with st.expander("How Evidrai works", expanded=False):
        st.markdown(
            """
Evidrai is **claim-first, not speaker-first**. It assesses the evidence behind a claim rather than trusting popularity, status, or repetition.

Core principles:

- **Amplification is not corroboration.** Repeated publication, social sharing, political prominence, or syndication does not make a claim more true by itself.
- **Independence beats volume.** Five articles repeating the same allegation, briefing, wire story, or social post may count as one evidentiary chain, not five independent confirmations.
- **Primary evidence carries the most weight.** Court records, official documents, filings, datasets, direct transcripts, and other primary material are preferred over commentary or repetition.
- **Reputable media are weighted signals, not arbiters of truth.** Strong outlets can improve confidence when they add transparent, independently sourced evidence. They do not define the answer alone.
- **Authority triggers attention, not automatic credibility.** Politicians, governments, celebrities, institutions, and high-profile media can all make unsupported claims. Evidrai scores the claim, not the title of the person saying it.
- **Context is separated from support.** Background, association, allegation, denial, and narrative momentum help explain why a claim spreads, but they are not treated as direct proof.

When many reviewed sources appear to trace back to the same narrative cluster, Evidrai may show an **amplification warning**. That means the claim may be widely repeated while still lacking independent evidentiary support.
            """.strip()
        )


def render_sources(sources: List[Dict[str, Any]]) -> None:
    if not sources:
        return
    st.markdown("### Sources reviewed")
    for src in sources:
        title = src.get("title", "Untitled")
        url = src.get("url", "")
        quality = map_source_quality_label(src.get("weighted_score"))
        stance = normalize_claim_support(src.get("claim_support", "context"))
        score = numeric_score(src.get("weighted_score"))
        meta = f"{src.get('source_type', 'unknown').title()} • quality {quality} • stance {stance}"
        if src.get("published_date"):
            meta += f" • {src['published_date']}"
        st.markdown(f"**[{title}]({url})**")
        st.caption(meta)
        render_score_bar("Source score", score, 5)
        if src.get("summary"):
            st.write(src["summary"])
        st.markdown("---")


def render_topline_block(title: str, verdict: str, confidence: Any, tldr: str, correction: str, badge: Optional[str] = None) -> None:
    st.markdown(f"## {title}")
    if badge:
        st.caption(badge)
    c1, c2 = st.columns(2)
    c1.metric("Verdict", str(verdict).replace("_", " ").title())
    c2.metric("Confidence", str(confidence))
    st.write(tldr or "No summary returned.")
    if correction:
        st.info(correction)

def render_pendulum(band: str, score: Any = None) -> None:
    labels = ["Unsubstantiated rumor", "Weakly supported", "Mixed / uncertain", "Mostly supported", "Strongly evidenced"]
    pos_map = {label: idx for idx, label in enumerate(labels)}
    pos = pos_map.get(band, 2)
    if score is not None:
        render_score_bar("Evidence strength", score, 10, band)
    cols = st.columns(5)
    for i, label in enumerate(labels):
        cols[i].markdown(f"**⬤ {label}**" if i == pos else f"◯ {label}")


def render_consensus_block(result: Dict[str, Any]) -> None:
    strength = (result.get("consensus_strength") or "").strip()
    summary = (result.get("consensus_summary") or "").strip()
    if not strength and not summary:
        return
    st.markdown("### Consensus across evidence")
    if strength:
        st.write(f"**{strength}**")
    if summary:
        st.write(summary)


def render_pipeline_result(result: Dict[str, Any]) -> None:
    verified_verdict = map_pipeline_verdict(result.get("verified_verdict") or result.get("verdict") or "unverifiable")
    verified_confidence = map_confidence_label(result.get("verified_confidence") or result.get("confidence", 0))
    render_topline_block(
        "Verified assessment",
        verified_verdict,
        verified_confidence,
        result.get("tldr", "No summary returned."),
        result.get("one_line_correction", ""),
        badge="Deep cross-evidence review completed.",
    )

    render_evidence_scorecard(result)
    render_amplification_warning(result)
    render_claim_breakdown(result)
    render_claim_under_review(result)
    render_assessment_metrics(result)
    rule_engine = result.get("rule_engine") or {}
    if rule_engine.get("rationale"):
        st.markdown("### Rule engine check")
        st.write(rule_engine.get("rationale"))
        if rule_engine.get("risk_flags"):
            st.caption("Risk flags: " + ", ".join(rule_engine.get("risk_flags")[:8]))
    render_evidence_snapshot(result.get("sources", []) or [])

    pendulum = result.get("pendulum", {}) or {}
    band = result.get("pendulum_band", "") or pendulum.get("band", "")
    score = result.get("pendulum_score", None) if result.get("pendulum_score", None) is not None else pendulum.get("score")
    explanation = result.get("pendulum_explanation", "") or pendulum.get("explanation", "")
    if band:
        st.markdown("### Evidence position")
        render_pendulum(band, score)
        if explanation:
            st.caption(explanation)

    render_consensus_block(result)

    rs = result.get("reasoning_summary", {}) or {}
    ea = result.get("evidence_assessment", {}) or {}
    with st.expander("Evidence summary", expanded=False):
        for label, key in [("Supported", "supported_points"), ("Contradicted", "contradicted_points"), ("Uncertain", "uncertain_points")]:
            vals = rs.get(key, []) or []
            if vals:
                st.markdown(f"**{label}**")
                for v in vals:
                    st.write(f"- {v}")
        actual_evidence = ea.get("actual_evidence", []) or []
        if actual_evidence:
            st.markdown("**What actual evidence exists**")
            for v in actual_evidence:
                st.write(f"- {v}")
        rumor_drivers = ea.get("rumor_drivers", []) or []
        if rumor_drivers:
            st.markdown("**Why some people may think this is true**")
            for v in rumor_drivers:
                st.write(f"- {v}")
        evidence_gaps = ea.get("evidence_gaps", []) or []
        if evidence_gaps:
            st.markdown("**Remaining evidence gaps**")
            for v in evidence_gaps:
                st.write(f"- {v}")

    tab1, tab2, tab3 = st.tabs(["Sources", "Reasoning", "Why it spreads"])
    with tab1:
        with st.expander("Sources and weighting", expanded=True):
            render_sources(result.get("sources", []))
        queries = result.get("queries", []) or []
        if queries:
            with st.expander("Search queries used", expanded=False):
                for q in queries:
                    st.write(f"- {q}")
    with tab2:
        if result.get("final_explanation"):
            st.markdown("### Assessment")
            st.write(result["final_explanation"])
        patterns = result.get("misinformation_patterns", []) or []
        if patterns:
            with st.expander("Misinformation patterns", expanded=False):
                st.write(" • ".join(patterns))
    with tab3:
        spreads = result.get("why_this_claim_spreads", []) or []
        if spreads:
            for item in spreads:
                st.write(f"- {item}")
        else:
            st.caption("No additional spread analysis returned.")

    render_feedback_controls(result.get("result_id", "latest"), result=result, source_url=result.get("source_url", ""), settings=result.get("settings", {}))
    render_methodology_note()


def render_speech_audit_result(result: Dict[str, Any]) -> None:
    st.markdown("## Speech / Video Audit")
    title = result.get("title") or "Speech / video audit"
    speaker = result.get("speaker") or "Unknown speaker"
    st.write(f"**{title}**")
    st.caption(f"Speaker: {speaker}")
    if result.get("source_url"):
        st.caption(f"Source: {result['source_url']}")
    if result.get("summary"):
        st.write(result["summary"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Claims extracted", len(result.get("claims_extracted", []) or []))
    c2.metric("Claims checked", result.get("claims_checked_count", 0))
    c3.metric("Needs attention", result.get("claims_needing_attention_count", 0))

    checked = result.get("claims_checked", []) or []
    if not checked:
        st.info("No checkable claims were extracted from the supplied transcript.")
    for item in checked:
        speech_claim = item.get("speech_claim", {}) or {}
        verdict = map_pipeline_verdict(item.get("verified_verdict") or item.get("verdict") or "Unverified")
        confidence = map_confidence_label(item.get("verified_confidence") or item.get("confidence") or "Low")
        label = f"{item.get('audit_index', '')}. {verdict} · {confidence}"
        quote = speech_claim.get("quote") or speech_claim.get("normalized_claim") or "Claim"
        if speech_claim.get("timestamp"):
            label += f" · {speech_claim['timestamp']}"
        with st.expander(label, expanded=verdict in {"False / contradicted", "Not supported by credible evidence", "Weakly supported / likely incorrect", "Misleading framing"}):
            st.markdown("**Original quote**")
            st.write(quote)
            st.markdown("**Claim checked**")
            st.write(speech_claim.get("normalized_claim") or quote)
            if speech_claim.get("why_it_matters"):
                st.markdown("**Why it matters**")
                st.write(speech_claim["why_it_matters"])
            if item.get("tldr"):
                st.markdown("**Evidrai assessment**")
                st.write(item["tldr"])
            if item.get("one_line_correction"):
                st.info(item["one_line_correction"])
            rule_engine = item.get("rule_engine") or {}
            if rule_engine.get("rationale"):
                st.caption("Rule check: " + rule_engine["rationale"])
            render_amplification_warning(item)
            render_sources((item.get("sources") or [])[:4])

    skipped = result.get("skipped_rhetoric", []) or []
    notes = result.get("extraction_notes", []) or []
    if skipped or notes:
        with st.expander("Extraction notes", expanded=False):
            if notes:
                st.markdown("**Notes**")
                for note in notes:
                    st.write(f"- {note}")
            if skipped:
                st.markdown("**Skipped rhetoric / low-checkability lines**")
                for item in skipped[:8]:
                    st.write(f"- {item}")

    render_feedback_controls(result.get("result_id", "speech_latest"), result=result, source_url=result.get("source_url", ""), settings=result.get("settings", {}))


def render_provisional_result(data: Dict[str, Any], source_url: str) -> None:
    badge = "Fast assessment with lightweight search snippets." if data.get("used_lightweight_search") else "Fast first-pass assessment. Deep verification may update the verdict."
    render_topline_block(
        "Fast provisional assessment",
        data.get("verdict", "Unverified"),
        data.get("confidence", "Low"),
        data.get("tldr") or data.get("summary") or "No summary returned.",
        data.get("one_line_correction") or data.get("user_takeaway") or "Deep verification may refine this answer.",
        badge=badge,
    )

    if source_url:
        st.caption(f"Source link provided: {source_url}")

    with st.expander("Fast-pass notes", expanded=False):
        for heading, key in [
            ("Assessment", "summary"),
            ("Why this may seem convincing", "why_convincing"),
            ("Evidence access note", "evidence_access_note"),
            ("What would change the verdict", "what_would_change_verdict"),
        ]:
            if data.get(key):
                st.markdown(f"**{heading}**")
                st.write(data[key])

        evidence_types = data.get("evidence_types", []) or []
        if evidence_types:
            st.markdown("**Evidence breakdown**")
            for item in evidence_types:
                st.markdown(f"- **{item.get('type', 'Unknown')}** — {item.get('impact', '')}")
                if item.get("note"):
                    st.caption(item["note"])

        fast_sources = data.get("fast_sources", []) or []
        if fast_sources:
            st.markdown("**Lightweight sources checked**")
            for src in fast_sources[:5]:
                title = src.get("title") or "Untitled"
                url = src.get("url") or ""
                if url:
                    st.markdown(f"- [{title}]({url})")
                else:
                    st.write(f"- {title}")

    render_feedback_controls(data.get("result_id", "quick_latest"), result=data, source_url=source_url, settings=data.get("settings", {}))


def render_legacy_result(data: Dict[str, Any], source_url: str) -> None:
    render_provisional_result(data, source_url)


def render_speech_audit_page(
    llm: OpenAICompatibleClient,
    search: TavilySearchClient,
    developer_debug_enabled: bool,
) -> None:
    st.markdown("### Speech / Video Audit")
    st.caption("Paste a transcript or long speech excerpt. Evidrai extracts checkable factual claims, verifies the selected claims, and highlights inaccurate or unsupported statements.")

    transcript = st.text_area(
        "Paste transcript or speech text",
        placeholder="Paste YouTube transcript, rally speech, interview excerpt, podcast transcript, or captions here...",
        height=260,
        key="speech_transcript_input",
    )
    source_url = st.text_input(
        "Optional video/source URL",
        placeholder="https://www.youtube.com/watch?v=...",
        key="speech_source_url_input",
    )
    max_claims = st.slider(
        "Maximum claims to verify",
        min_value=1,
        max_value=10,
        value=5,
        help="Start small: each claim runs through the Deep evidence pipeline.",
    )
    with st.expander("Paste YouTube transcript helper", expanded=False):
        st.write("Copy the transcript from YouTube's transcript panel and paste it above. Evidrai will clean timestamp-only lines, duplicate caption fragments, and common noise before extracting claims.")
        if st.button("Clean pasted transcript", use_container_width=True):
            cleaned_preview = clean_pasted_youtube_transcript(st.session_state.get("speech_transcript_input", ""))
            st.session_state["speech_transcript_input"] = cleaned_preview
            st.success("Transcript cleaned. Review it above, then run the audit.")
    st.info("MVP note: if a YouTube URL has accessible captions, Evidrai will try to fetch them. If YouTube blocks access, paste the visible transcript manually.")

    if st.button("Audit speech / video", type="primary", use_container_width=True):
        cleaned_transcript = (transcript or "").strip()
        cleaned_source_url = (source_url or "").strip()
        if cleaned_source_url and not is_probable_url(cleaned_source_url):
            st.error("The source link does not look like a valid URL. Please include http:// or https://")
            return
        if not cleaned_transcript and cleaned_source_url:
            with st.spinner("Trying to extract YouTube captions..."):
                transcript_result = extract_youtube_transcript(cleaned_source_url)
            if transcript_result.get("ok"):
                cleaned_transcript = transcript_result.get("transcript", "").strip()
                title = transcript_result.get("title")
                language = transcript_result.get("language")
                st.success(f"Transcript extracted" + (f" from {title}" if title else "") + (f" ({language})" if language else ""))
            else:
                st.error(transcript_result.get("error") or "Could not extract a transcript from this URL. Please paste the transcript manually.")
                return
        if not cleaned_transcript:
            st.error("Please paste a transcript or provide a YouTube URL with accessible captions.")
            return
        cleaned_transcript = clean_pasted_youtube_transcript(cleaned_transcript)
        if not llm.configured:
            st.error("OPENAI_API_KEY is not configured in your app secrets or environment.")
            return
        if not search.configured:
            st.error("Speech / Video Audit requires TAVILY_API_KEY because each extracted claim is evidence-checked.")
            return

        cache_key = stable_request_key("speech_audit", cleaned_transcript, cleaned_source_url, max_claims)
        cache = st.session_state["evidrai_cache"]
        if cache_key in cache:
            st.session_state["last_results"] = cache[cache_key]
        else:
            try:
                started_at = time.time()
                status = st.status("Starting speech audit...", expanded=True)
                with status:
                    st.write("Extracting checkable factual claims...")
                    st.write("Running Evidrai evidence checks claim by claim...")
                audit_result = run_speech_audit(cleaned_transcript, cleaned_source_url, max_claims, llm, search)
                audit_result["elapsed_seconds"] = time.time() - started_at
                audit_result["result_id"] = f"speech_{cache_key}"
                audit_result["settings"] = {
                    "result_mode": "speech_audit",
                    "source_url": cleaned_source_url,
                    "max_claims": max_claims,
                    "build": get_app_build(),
                }
                saved = {"speech_result": audit_result, "source_url": cleaned_source_url, "settings": audit_result["settings"]}
                cache[cache_key] = saved
                st.session_state["last_results"] = saved
                status.update(label="Speech audit complete", state="complete", expanded=False)
            except EvidraiError as exc:
                st.error(exc.message)
                if developer_debug_enabled and exc.developer_detail:
                    st.caption(exc.developer_detail)
            except requests.HTTPError as exc:
                try:
                    detail = exc.response.text[:500]
                except Exception:
                    detail = str(exc)
                st.error(f"API error: {detail}")
            except Exception as exc:
                st.error("Speech audit failed. Enable Developer debug panel for details.")
                if developer_debug_enabled:
                    st.exception(exc)

    saved = st.session_state.get("last_results")
    if saved and saved.get("speech_result"):
        try:
            render_speech_audit_result(saved["speech_result"])
        except Exception as exc:
            st.error("The speech audit completed, but Evidrai could not render the result. Enable Developer debug panel for details.")
            if developer_debug_enabled:
                st.exception(exc)

    if developer_debug_enabled:
        render_developer_debug_panel(saved, {"app_mode": "speech_audit"}, llm, search)



def render_pipeline_trace(trace: Dict[str, Any]) -> None:
    """Render the structured trace packet without exposing secrets or raw fetched content."""
    if not trace:
        st.caption("No structured trace packet is available for this result.")
        return

    st.write("**Normalized claim**")
    st.write(trace.get("normalized_claim") or "")

    claim_analysis = trace.get("claim_analysis") or {}
    subclaims = claim_analysis.get("subclaims") or []
    if subclaims:
        st.write("**Subclaims**")
        for item in subclaims:
            st.write(f"- {item.get('id', 'sc')}: {item.get('text', '')} · {item.get('claim_type', 'other')}")

    queries = trace.get("queries") or []
    if queries:
        st.write("**Queries**")
        for query in queries:
            st.write(f"- {query}")

    scoring = trace.get("scoring") or {}
    source_scores = scoring.get("source_scores") or []
    if source_scores:
        st.write("**Source scoring factors**")
        for source in source_scores:
            factors = source.get("scoring_factors") or {}
            label = source.get("title") or source.get("domain") or "Source"
            with st.expander(label, expanded=False):
                st.caption(source.get("url") or "")
                st.json(
                    {
                        "classification": {
                            "source_type": source.get("source_type"),
                            "claim_support": source.get("claim_support"),
                            "evidence_category": source.get("evidence_category"),
                            "source_role": source.get("source_role"),
                            "narrative_cluster": source.get("narrative_cluster"),
                        },
                        "scoring_factors": factors,
                    }
                )

    rule_engine = trace.get("rule_engine") or {}
    if rule_engine:
        st.write("**Rule engine**")
        st.json(rule_engine)

    if trace.get("downgrade_rationale"):
        st.write("**Downgrade / arbitration rationale**")
        st.write(trace["downgrade_rationale"])


def render_developer_debug_panel(
    saved: Optional[Dict[str, Any]],
    settings: Dict[str, Any],
    llm: OpenAICompatibleClient,
    search: TavilySearchClient,
) -> None:
    """Render opt-in diagnostics without exposing secrets."""
    st.markdown("---")
    st.markdown("## Developer debug")
    st.caption("Visible only when the sidebar toggle is enabled for this browser session.")

    with st.expander("Runtime configuration", expanded=False):
        st.json(
            {
                "build": get_app_build(),
                "settings": settings,
                "openai": {
                    "configured": llm.configured,
                    "model": llm.model,
                    "base_url": llm.base_url,
                },
                "tavily": {"configured": search.configured},
            }
        )

    cache = st.session_state.get("evidrai_cache", {})
    feedback_log = st.session_state.get("feedback_log", {})
    with st.expander("Session state summary", expanded=False):
        st.json(
            {
                "cache_entries": len(cache),
                "has_last_results": saved is not None,
                "feedback_count": len(feedback_log),
                "feedback_backend": feedback_backend_status(),
            }
        )
    if feedback_log:
        st.download_button(
            "Download feedback JSON",
            data=json.dumps(feedback_log, indent=2),
            file_name="evidrai-feedback.json",
            mime="application/json",
            use_container_width=True,
        )

    if saved:
        latest_result = saved.get("full_result") or saved.get("quick_result") or saved.get("speech_result") or {}
        trace = latest_result.get("debug_trace") if isinstance(latest_result, dict) else None
        with st.expander("Structured pipeline trace", expanded=False):
            render_pipeline_trace(trace or {})
        if isinstance(latest_result, dict) and latest_result:
            export_settings = latest_result.get("settings") or saved.get("settings") or {}
            st.download_button(
                "Download assessment JSON",
                data=assessment_export_json(
                    latest_result,
                    claim=export_settings.get("claim_input", "") or latest_result.get("claim", ""),
                    source_url=latest_result.get("source_url", "") or saved.get("source_url", ""),
                    category=export_settings.get("claim_category", "auto-detect"),
                    mode=export_settings.get("result_mode", "deep"),
                    include_debug=True,
                ),
                file_name=f"evidrai-assessment-{latest_result.get('result_id', 'latest')}.json",
                mime="application/json",
                use_container_width=True,
            )
        with st.expander("Raw latest result payload", expanded=False):
            st.json(saved)



def main() -> None:
    st.set_page_config(page_title="Evidrai", layout="wide")
    st.title("🔎 Evidrai — Claim Check")
    st.caption("Assess the evidence behind a claim, story, or post — not just how confidently it is repeated.")
    render_public_methodology_explainer()

    llm = OpenAICompatibleClient()
    search = TavilySearchClient()

    if "evidrai_cache" not in st.session_state:
        st.session_state["evidrai_cache"] = {}
    if "last_results" not in st.session_state:
        st.session_state["last_results"] = None
    if "feedback_log" not in st.session_state:
        st.session_state["feedback_log"] = {}

    with st.sidebar:
        st.header("Settings")
        app_mode = st.radio("Mode", ["Single Claim Check", "Speech / Video Audit"], index=0)
        detail_mode = st.radio("Output mode", ["Simple", "Detailed"], index=0)
        category = st.selectbox(
            "Claim category",
            ["auto-detect", "politics", "celebrity", "health", "science", "finance", "history", "general"],
            index=0,
        )
        verification_mode = st.selectbox("Verification depth", ["Auto", "Fast", "Deep"], index=0)
        developer_debug_enabled = st.toggle(
            "Developer debug panel",
            value=False,
            help="Show raw result payloads and non-secret runtime diagnostics for this browser session only.",
        )
        st.markdown("---")
        st.caption("Auto runs Fast for Simple output and Deep for Detailed output. Select Fast or Deep explicitly to override.")
        st.markdown("---")
        st.caption("The product is optimized around claim → evidence → verdict. Fast mode gives a quick first pass. Deep mode shows the evidence pipeline.")
        st.markdown("---")
        st.caption(f"Build: {get_app_build()}")
        st.caption(f"OpenAI: {'configured' if llm.configured else 'missing'} • Model: {llm.model} • Base URL: {llm.base_url}")
        st.caption(f"Tavily: {'configured' if search.configured else 'missing'}")

    if app_mode == "Speech / Video Audit":
        render_speech_audit_page(llm, search, developer_debug_enabled)
        return

    claim = st.text_area(
        "Paste a claim, link description, quote, or content to assess",
        placeholder="Paste a claim, rumor, headline, quote, or a short description of a video/post here...",
        height=140,
        key="claim_input",
    )
    source_url = st.text_input(
        "Optional source link",
        placeholder="Paste a YouTube, article, podcast, Facebook, or Instagram URL if helpful...",
        key="source_url_input",
    )
    st.caption("Tip: if you add a link, also paste the key quote or claim above. The app reasons better when the central claim is explicit.")
    with st.expander("Verdict scale", expanded=False):
        st.write("Supported, Likely supported, Partly supported, Misleading framing, Contested, Reported but unconfirmed, Weakly supported / likely incorrect, Not supported by credible evidence, False / contradicted, or Unverified.")

    if st.button("Check claim", type="primary", use_container_width=True):
        cleaned_claim = (claim or "").strip()
        cleaned_source_url = (source_url or "").strip()
        if not cleaned_claim and not cleaned_source_url:
            st.error("Please enter a claim, some content, or a source link first.")
            return
        if cleaned_source_url and not is_probable_url(cleaned_source_url):
            st.error("The source link does not look like a valid URL. Please include http:// or https://")
            return
        if not llm.configured:
            st.error("OPENAI_API_KEY is not configured in your app secrets or environment.")
            return

        analysis_input = build_analysis_input(cleaned_claim, cleaned_source_url)
        effective_verification_mode = "Deep" if verification_mode == "Auto" and detail_mode == "Detailed" else verification_mode
        use_search = effective_verification_mode == "Deep"
        request_settings = {
            "claim_input": cleaned_claim,
            "source_url": cleaned_source_url,
            "analysis_input": analysis_input,
            "output_mode": detail_mode,
            "claim_category": category,
            "verification_depth": verification_mode,
            "effective_verification_depth": effective_verification_mode,
            "lightweight_fast_search_enabled": search.configured,
            "deep_search_enabled": use_search,
            "build": get_app_build(),
        }
        if effective_verification_mode == "Deep" and not search.configured:
            st.error("Deep mode requires TAVILY_API_KEY to be configured.")
            return

        cache_key = stable_request_key(analysis_input, category, effective_verification_mode, use_search, detail_mode)
        cache = st.session_state["evidrai_cache"]
        if cache_key in cache:
            st.session_state["last_results"] = cache[cache_key]
        else:
            try:
                started_at = time.time()
                status = st.status("Starting assessment...", expanded=True)
                with status:
                    st.write("Running fast first-pass assessment...")
                quick_result = run_quick_pass(analysis_input, category, llm, search)
                quick_result["result_id"] = f"quick_{cache_key}"
                quick_result["settings"] = request_settings | {"result_mode": "fast"}
                quick_result["source_url"] = cleaned_source_url

                full_result = None
                if use_search:
                    with status:
                        st.write("Extracting the core claim and subclaims...")
                        st.write("Retrieving and ranking external sources...")
                        st.write("Checking for contradiction, support, and uncertainty...")
                        st.write("Generating the verified assessment...")
                    full_result = run_claim_pipeline(analysis_input, llm, search)
                    full_result["elapsed_seconds"] = time.time() - started_at
                    full_result["result_id"] = f"deep_{cache_key}"
                    full_result["settings"] = request_settings | {"result_mode": "deep"}
                    full_result["source_url"] = cleaned_source_url
                    status.update(label="Assessment complete", state="complete", expanded=False)
                else:
                    quick_result["elapsed_seconds"] = time.time() - started_at
                    status.update(label="Fast assessment complete", state="complete", expanded=False)

                saved = {
                    "quick_result": quick_result,
                    "full_result": full_result,
                    "source_url": cleaned_source_url,
                    "settings": request_settings,
                }
                cache[cache_key] = saved
                st.session_state["last_results"] = saved
            except EvidraiError as exc:
                st.error(exc.message)
                if developer_debug_enabled and exc.developer_detail:
                    st.caption(exc.developer_detail)
            except requests.HTTPError as exc:
                try:
                    detail = exc.response.text[:500]
                except Exception:
                    detail = str(exc)
                st.error(f"API error: {detail}")
            except Exception as exc:
                st.error("Assessment failed. Enable Developer debug panel for details.")
                if developer_debug_enabled:
                    st.exception(exc)

    saved = st.session_state.get("last_results")
    if saved:
        try:
            if saved.get("full_result"):
                render_pipeline_result(saved["full_result"])
                if saved.get("quick_result"):
                    with st.expander("Initial fast pass", expanded=False):
                        st.caption("Shown for transparency only. The verified Deep assessment above is the primary result.")
                        render_provisional_result(saved["quick_result"], saved.get("source_url", ""))
            elif saved.get("quick_result"):
                render_provisional_result(saved["quick_result"], saved.get("source_url", ""))
        except Exception as exc:
            st.error("The assessment completed, but Evidrai could not render the result. Enable Developer debug panel for details.")
            if developer_debug_enabled:
                st.exception(exc)

    if developer_debug_enabled:
        render_developer_debug_panel(
            saved,
            {
                "output_mode": detail_mode,
                "claim_category": category,
                "verification_depth": verification_mode,
            },
            llm,
            search,
        )
