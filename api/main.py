from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.config import get_app_build
from evidrai.pipeline.verification import run_claim_pipeline, run_quick_pass, run_speech_audit
from evidrai.transcripts import clean_pasted_youtube_transcript, extract_youtube_transcript
from evidrai.utils import build_analysis_input, is_probable_url


app = FastAPI(
    title="Evidrai API",
    version="0.1.0",
    description="Phase 1 API wrapper around the Evidrai verification engine.",
)


class ClaimCheckRequest(BaseModel):
    claim: str = ""
    source_url: str = ""
    category: str = "auto-detect"
    mode: str = Field(default="deep", pattern="^(fast|deep)$")


class SpeechAuditRequest(BaseModel):
    transcript: str = ""
    source_url: str = ""
    max_claims: int = Field(default=5, ge=1, le=10)
    try_youtube_captions: bool = True


class ApiEnvelope(BaseModel):
    ok: bool
    build: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _clients() -> tuple[OpenAICompatibleClient, TavilySearchClient]:
    return OpenAICompatibleClient(), TavilySearchClient()


@app.get("/health")
def health() -> Dict[str, Any]:
    llm, search = _clients()
    return {
        "ok": True,
        "build": get_app_build(),
        "openai_configured": llm.configured,
        "tavily_configured": search.configured,
    }


@app.post("/claims/check", response_model=ApiEnvelope)
def check_claim(request: ClaimCheckRequest) -> ApiEnvelope:
    claim = (request.claim or "").strip()
    source_url = (request.source_url or "").strip()
    if not claim and not source_url:
        raise HTTPException(status_code=400, detail="claim or source_url is required")
    if source_url and not is_probable_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    llm, search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    analysis_input = build_analysis_input(claim, source_url)
    if request.mode == "deep":
        if not search.configured:
            raise HTTPException(status_code=503, detail="TAVILY_API_KEY is required for deep mode")
        result = run_claim_pipeline(analysis_input, llm, search)
    else:
        result = run_quick_pass(analysis_input, request.category, llm, search)
    result["settings"] = {
        "result_mode": request.mode,
        "claim_category": request.category,
        "source_url": source_url,
        "build": get_app_build(),
    }
    return ApiEnvelope(ok=True, build=get_app_build(), result=result)


@app.post("/speech/audit", response_model=ApiEnvelope)
def speech_audit(request: SpeechAuditRequest) -> ApiEnvelope:
    transcript = (request.transcript or "").strip()
    source_url = (request.source_url or "").strip()
    if source_url and not is_probable_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    if not transcript and source_url and request.try_youtube_captions:
        transcript_result = extract_youtube_transcript(source_url)
        if transcript_result.get("ok"):
            transcript = transcript_result.get("transcript", "").strip()
        else:
            raise HTTPException(status_code=422, detail=transcript_result.get("error") or "Could not extract transcript")

    transcript = clean_pasted_youtube_transcript(transcript)
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript is required, or provide a YouTube URL with accessible captions")

    llm, search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    if not search.configured:
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY is required for speech audit")

    result = run_speech_audit(transcript, source_url, request.max_claims, llm, search)
    result["settings"] = {
        "result_mode": "speech_audit",
        "source_url": source_url,
        "max_claims": request.max_claims,
        "build": get_app_build(),
    }
    return ApiEnvelope(ok=True, build=get_app_build(), result=result)
