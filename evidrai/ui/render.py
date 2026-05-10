from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.pipeline.verification import run_claim_pipeline, run_quick_pass
from evidrai.rules.verdict import (
    map_confidence_label,
    map_pipeline_verdict,
    normalize_claim_support,
)
from evidrai.utils import build_analysis_input, is_probable_url, stable_request_key

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

    st.markdown("### Evidence snapshot")
    c1, c2, c3 = st.columns(3)
    c1.metric("Supporting sources", len(supporting))
    c2.metric("Contradicting sources", len(contradicting))
    c3.metric("Contextual or mixed", len(contextual))

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


def render_assessment_metrics(result: Dict[str, Any]) -> None:
    sources = result.get("sources", []) or []
    primary = sum(1 for s in sources if (s.get("source_type") or "").lower() == "primary")
    high_quality = sum(1 for s in sources if map_source_quality_label(s.get("weighted_score")) == "High")
    contradictions = sum(1 for s in sources if normalize_claim_support(s.get("claim_support")) == "Contradicts")
    elapsed = result.get("elapsed_seconds")

    st.markdown("### Assessment quality")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sources reviewed", len(sources))
    c2.metric("Primary sources", primary)
    c3.metric("High-quality sources", high_quality)
    c4.metric("Contradiction signals", contradictions)
    if elapsed is not None:
        st.caption(f"Completed in {elapsed:.1f}s")


def render_feedback_controls(result_key: str) -> None:
    feedback_store = st.session_state.setdefault("feedback_log", {})
    st.markdown("### Was this useful?")
    c1, c2, c3 = st.columns(3)
    if c1.button("Useful", key=f"fb_useful_{result_key}", use_container_width=True):
        feedback_store[result_key] = "useful"
    if c2.button("Not useful", key=f"fb_not_useful_{result_key}", use_container_width=True):
        feedback_store[result_key] = "not_useful"
    if c3.button("Sources weak", key=f"fb_sources_weak_{result_key}", use_container_width=True):
        feedback_store[result_key] = "sources_weak"
    if result_key in feedback_store:
        st.caption(f"Feedback captured: {feedback_store[result_key].replace('_', ' ')}")


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
        meta = f"{src.get('source_type', 'unknown').title()} • quality {quality} • stance {stance}"
        if src.get("weighted_score") is not None:
            meta += f" • score {src.get('weighted_score')}"
        if src.get("published_date"):
            meta += f" • {src['published_date']}"
        st.markdown(f"**[{title}]({url})**")
        st.caption(meta)
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

def render_pendulum(band: str) -> None:
    labels = ["Unsubstantiated rumor", "Weakly supported", "Mixed / uncertain", "Mostly supported", "Strongly evidenced"]
    pos_map = {label: idx for idx, label in enumerate(labels)}
    pos = pos_map.get(band, 2)
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

    render_claim_under_review(result)
    render_assessment_metrics(result)
    rule_engine = result.get("rule_engine") or {}
    if rule_engine.get("rationale"):
        st.markdown("### Rule engine check")
        st.write(rule_engine.get("rationale"))
        if rule_engine.get("risk_flags"):
            st.caption("Risk flags: " + ", ".join(rule_engine.get("risk_flags")[:8]))
    render_evidence_snapshot(result.get("sources", []) or [])

    band = result.get("pendulum_band", "")
    explanation = result.get("pendulum_explanation", "")
    if band:
        st.markdown("### Evidence position")
        render_pendulum(band)
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
        st.markdown("---")
        st.caption("Auto uses deep verification when search is configured, otherwise it falls back to the fast first-pass flow.")
        st.markdown("---")
        st.caption("The product is optimized around claim → evidence → verdict. Fast mode gives a quick first pass. Deep mode shows the evidence pipeline.")

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
        use_search = search.configured if verification_mode == "Auto" else verification_mode == "Deep"
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
        if saved.get("quick_result"):
            render_provisional_result(saved["quick_result"], saved.get("source_url", ""))
        if saved.get("full_result"):
            render_pipeline_result(saved["full_result"])
