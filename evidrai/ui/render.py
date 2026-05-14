from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.config import get_app_build
from evidrai.pipeline.verification import run_claim_pipeline, run_quick_pass
from evidrai.rules.verdict import (
    map_confidence_label,
    map_pipeline_verdict,
    map_source_quality_label,
    normalize_claim_support,
)
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


def render_evidence_snapshot(sources: List[Dict[str, Any]]) -> None:
    if not sources:
        return
    supporting = [s for s in sources if normalize_claim_support(s.get("claim_support")) == "Supports"]
    contradicting = [s for s in sources if normalize_claim_support(s.get("claim_support")) == "Contradicts"]
    contextual = [s for s in sources if normalize_claim_support(s.get("claim_support")) in {"Mixed", "Context"}]
    total = max(len(sources), 1)

    st.markdown("### Evidence snapshot")
    c1, c2, c3 = st.columns(3)
    c1.metric("Supporting", len(supporting))
    c2.metric("Contradicting", len(contradicting))
    c3.metric("Contextual / mixed", len(contextual))

    st.caption("Evidence mix across the reviewed source set")
    render_score_bar("Supporting", len(supporting), total)
    render_score_bar("Contradicting", len(contradicting), total)
    render_score_bar("Contextual / mixed", len(contextual), total)

    buckets = [
        ("Evidence supporting the claim", supporting),
        ("Evidence contradicting the claim", contradicting),
        ("Neutral or contextual evidence", contextual),
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


def render_feedback_controls(result_key: str) -> None:
    feedback_store = st.session_state.setdefault("feedback_log", {})
    st.markdown("### Feedback")
    st.caption("Help improve the assessment quality. This is captured for this session only for now.")

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
        feedback_store[result_key] = {
            "rating": rating,
            "reasons": reasons,
            "comment": comment.strip(),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        st.success("Feedback captured. Thank you.")

    if result_key in feedback_store:
        st.caption(f"Latest feedback: {feedback_store[result_key].get('rating', 'captured')}")


def render_methodology_note() -> None:
    with st.expander("How Evidrai reached this assessment", expanded=False):
        st.write("Claim extraction → query generation → source retrieval → source ranking → contradiction check → verdict and confidence.")
        st.write("A rule engine then checks whether the final verdict is too strong for the evidence packet and can downgrade it to stay aligned with Evidrai's verification policy.")
        st.write("Confidence reflects the quantity, quality, directness, recency, and agreement level of the reviewed evidence. It is not a claim of certainty.")


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

    render_feedback_controls(result.get("result_id", "latest"))
    render_methodology_note()


def render_provisional_result(data: Dict[str, Any], source_url: str) -> None:
    render_topline_block(
        "Provisional assessment",
        data.get("verdict", "Unverified"),
        data.get("confidence", "Low"),
        data.get("tldr") or data.get("summary") or "No summary returned.",
        data.get("one_line_correction") or data.get("user_takeaway") or "Deep verification may refine this answer.",
        badge="Fast first-pass assessment. Deep verification may update the verdict.",
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

    render_feedback_controls(data.get("result_id", "quick_latest"))


def render_legacy_result(data: Dict[str, Any], source_url: str) -> None:
    render_provisional_result(data, source_url)



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
        with st.expander("Raw latest result payload", expanded=False):
            st.json(saved)



def main() -> None:
    st.set_page_config(page_title="Evidrai", layout="wide")
    st.title("🔎 Evidrai — Claim Check")
    st.caption("Assess the evidence behind a claim, story, or post — not just how confidently it is repeated.")

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
        st.caption("Auto uses the fast first-pass flow by default to avoid unnecessary API usage. Select Deep explicitly for retrieval-backed verification.")
        st.markdown("---")
        st.caption("The product is optimized around claim → evidence → verdict. Fast mode gives a quick first pass. Deep mode shows the evidence pipeline.")
        st.markdown("---")
        st.caption(f"Build: {get_app_build()}")
        st.caption(f"OpenAI: {'configured' if llm.configured else 'missing'} • Model: {llm.model} • Base URL: {llm.base_url}")
        st.caption(f"Tavily: {'configured' if search.configured else 'missing'}")

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
        st.write("Supported, Likely supported, Misleading framing, Weakly supported or likely incorrect, Not supported by credible evidence, or Unverified.")

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
        use_search = verification_mode == "Deep"
        if verification_mode == "Deep" and not search.configured:
            st.error("Deep mode requires TAVILY_API_KEY to be configured.")
            return

        cache_key = stable_request_key(analysis_input, category, verification_mode, use_search, detail_mode)
        cache = st.session_state["evidrai_cache"]
        if cache_key in cache:
            st.session_state["last_results"] = cache[cache_key]
        else:
            try:
                started_at = time.time()
                status = st.status("Starting assessment...", expanded=True)
                with status:
                    st.write("Running fast first-pass assessment...")
                quick_result = run_quick_pass(analysis_input, category, llm)
                quick_result["result_id"] = f"quick_{cache_key}"

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
                    status.update(label="Assessment complete", state="complete", expanded=False)
                else:
                    quick_result["elapsed_seconds"] = time.time() - started_at
                    status.update(label="Fast assessment complete", state="complete", expanded=False)

                saved = {
                    "quick_result": quick_result,
                    "full_result": full_result,
                    "source_url": cleaned_source_url,
                }
                cache[cache_key] = saved
                st.session_state["last_results"] = saved
            except requests.HTTPError as exc:
                try:
                    detail = exc.response.text[:500]
                except Exception:
                    detail = str(exc)
                st.error(f"API error: {detail}")
            except Exception as exc:
                st.error(f"Error: {exc}")

    saved = st.session_state.get("last_results")
    if saved:
        try:
            if saved.get("quick_result"):
                render_provisional_result(saved["quick_result"], saved.get("source_url", ""))
            if saved.get("full_result"):
                render_pipeline_result(saved["full_result"])
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
