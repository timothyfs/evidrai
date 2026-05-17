from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from evidrai.api_models import AssessmentResponse, serialize_assessment_response
from evidrai.auth import AuthContext, context_from_headers, decode_supabase_access_token, unverified_token_diagnostics
from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.config import admin_token, api_allowed_origins, database_url, get_app_build, master_admin_emails, supabase_auth_configured, supabase_service_role_key, supabase_url
from evidrai.entitlements import (
    delete_user_profile,
    enforce_speech_claim_limit,
    feature_matrix,
    get_or_create_profile,
    list_user_profiles,
    require_feature,
    set_user_tier,
)
from evidrai.errors import EvidraiError, safe_error_payload
from evidrai.feedback import build_feedback_record, list_feedback_for_assessment, save_feedback
from evidrai.ingestion.url import ExtractedSource, fetch_source_url
from evidrai.pipeline.verification import (
    extract_speech_audit_claims,
    run_claim_pipeline,
    run_quick_pass,
    run_speech_audit,
    verify_speech_claim,
)
from evidrai.reports import list_reports, load_report, save_report
from evidrai.transcripts import clean_pasted_youtube_transcript, diagnose_youtube_transcript, extract_youtube_transcript, transcript_backend_status
from evidrai.utils import build_analysis_input, is_probable_url


API_VERSION = "api.v1"


app = FastAPI(
    title="Evidrai API",
    version="0.1.0",
    description="Independent API wrapper around the Evidrai verification engine.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(EvidraiError)
def evidrai_error_handler(request: Request, exc: EvidraiError) -> JSONResponse:
    include_debug = (request.query_params.get("include_debug") or "").lower() == "true"
    return JSONResponse(status_code=exc.status_code, content={"detail": safe_error_payload(exc, include_debug=include_debug)})


class ClaimCheckRequest(BaseModel):
    claim: str = ""
    source_url: str = ""
    category: str = "auto-detect"
    mode: str = Field(default="deep", pattern="^(fast|deep)$")
    include_debug: bool = False


class AssessmentCreateRequest(BaseModel):
    claim: str = ""
    source_url: str = ""
    category: str = "auto-detect"
    include_debug: bool = False


class SpeechAuditRequest(BaseModel):
    transcript: str = ""
    source_url: str = ""
    max_claims: int = Field(default=3, ge=1, le=20)
    verification_mode: str = Field(default="fast", pattern="^(fast|deep)$")
    try_youtube_captions: bool = True


class SpeechExtractRequest(BaseModel):
    transcript: str = ""
    source_url: str = ""
    max_claims: int = Field(default=3, ge=1, le=20)
    try_youtube_captions: bool = True


class SpeechVerifyRequest(BaseModel):
    claims: list[Dict[str, Any]] = Field(default_factory=list)
    source_url: str = ""
    verification_mode: str = Field(default="fast", pattern="^(fast|deep)$")


class SourceExtractRequest(BaseModel):
    source_url: str


class FeedbackCreateRequest(BaseModel):
    rating: str = Field(default="Useful", pattern="^(Useful|Partly useful|Not useful)$")
    reasons: list[str] = Field(default_factory=list)
    comment: str = ""


class AdminSetTierRequest(BaseModel):
    owner_id: str
    tier: str = Field(pattern="^(free|pro|researcher)$")
    email: str = ""


class AdminInviteUserRequest(BaseModel):
    email: str
    tier: str = Field(default="free", pattern="^(free|pro|researcher)$")
    send_invite: bool = True
    redirect_to: str = ""


class ApiEnvelope(BaseModel):
    ok: bool
    build: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None




def _supabase_admin_headers() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise HTTPException(status_code=503, detail={"code": "supabase_service_role_missing", "message": "SUPABASE_SERVICE_ROLE_KEY is required for admin user invitations."})
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _supabase_auth_url(path: str) -> str:
    url = supabase_url()
    if not url:
        raise HTTPException(status_code=503, detail={"code": "supabase_url_missing", "message": "SUPABASE_URL is required for admin user invitations."})
    return f"{url.rstrip()}/auth/v1/{path.lstrip('/')}"


def _create_or_invite_supabase_user(request: AdminInviteUserRequest) -> dict[str, Any]:
    email = request.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "A valid email address is required."})
    body: dict[str, Any] = {"email": email, "data": {"evidrai_tier": request.tier}}
    if request.redirect_to.strip():
        body["redirect_to"] = request.redirect_to.strip()
    if request.send_invite:
        endpoint = _supabase_auth_url("invite")
    else:
        endpoint = _supabase_auth_url("admin/users")
        body["email_confirm"] = True
        body["user_metadata"] = body.pop("data")
    try:
        response = requests.post(endpoint, headers=_supabase_admin_headers(), json=body, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail={"code": "supabase_admin_request_failed", "message": "Could not reach Supabase admin API.", "developer_detail": str(exc)})
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail={"code": "supabase_admin_error", "message": "Supabase could not create or invite this user.", "supabase_detail": detail})
    try:
        return response.json()
    except ValueError:
        return {}

def _clients() -> tuple[OpenAICompatibleClient, TavilySearchClient]:
    return OpenAICompatibleClient(), TavilySearchClient()


def _source_claim_from_url(source_url: str) -> str:
    extracted = fetch_source_url(source_url)
    if extracted.candidate_claims:
        return extracted.candidate_claims[0]
    return extracted.description or extracted.title or extracted.excerpt[:500]


def _validate_claim_request(claim: str, source_url: str) -> None:
    if not claim and not source_url:
        raise HTTPException(status_code=400, detail="claim or source_url is required")
    if source_url and not is_probable_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")



def _is_youtube_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "youtube.com" in lowered or "youtu.be" in lowered

def _speech_transcript_from_request(transcript: str, source_url: str, try_youtube_captions: bool) -> str:
    if source_url and not is_probable_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    cleaned = (transcript or "").strip()
    if not cleaned and source_url and try_youtube_captions and _is_youtube_url(source_url):
        transcript_result = extract_youtube_transcript(source_url)
        if transcript_result.get("ok"):
            cleaned = transcript_result.get("transcript", "").strip()
        else:
            detail = {
                "code": transcript_result.get("code") or "youtube_transcript_unavailable",
                "message": transcript_result.get("error") or "Could not extract transcript",
            }
            if transcript_result.get("title"):
                detail["title"] = transcript_result.get("title")
            raise HTTPException(status_code=422, detail=detail)

    cleaned = clean_pasted_youtube_transcript(cleaned)
    if not cleaned:
        raise HTTPException(status_code=400, detail={
            "code": "transcript_required",
            "message": "Paste a transcript to run a reliable speech/video audit. Automatic YouTube captions are optional and may be blocked by YouTube.",
        })
    return cleaned


def _run_claim_assessment(
    *,
    claim: str,
    source_url: str,
    category: str,
    mode: str,
) -> Dict[str, Any]:
    llm, search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "OPENAI_API_KEY is not configured"})

    if not claim and source_url:
        claim = _source_claim_from_url(source_url)
    analysis_input = build_analysis_input(claim, source_url)
    if mode == "deep":
        if not search.configured:
            raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "TAVILY_API_KEY is required for deep mode"})
        return run_claim_pipeline(analysis_input, llm, search)
    return run_quick_pass(analysis_input, category, llm, search)


def _auth_context_from_request(request: Request) -> AuthContext:
    context = context_from_headers(
        authorization=request.headers.get("authorization") or "",
        owner_header=request.headers.get("x-evidrai-user-id") or "",
    )
    if len(context.owner_id) > 128:
        raise HTTPException(status_code=400, detail="owner id is too long")
    return context


def _owner_id_from_request(request: Request) -> str:
    return _auth_context_from_request(request).owner_id


def _profile_from_request(request: Request):
    context = _auth_context_from_request(request)
    return context, get_or_create_profile(context.owner_id, email=context.email)


def _is_master_admin(context: AuthContext) -> bool:
    return context.authenticated and context.email.strip().lower() in master_admin_emails()


def _require_admin(request: Request) -> None:
    context = _auth_context_from_request(request)
    if _is_master_admin(context):
        return

    configured = admin_token()
    supplied = (request.headers.get("x-evidrai-admin-token") or "").strip()
    if configured and supplied == configured:
        return

    raise HTTPException(status_code=403, detail={"code": "admin_forbidden", "message": "Master admin access is required"})


def _assessment_response_from_request(request: AssessmentCreateRequest, mode: str, owner_id: str = "") -> AssessmentResponse:
    claim = (request.claim or "").strip()
    source_url = (request.source_url or "").strip()
    _validate_claim_request(claim, source_url)
    result = _run_claim_assessment(claim=claim, source_url=source_url, category=request.category, mode=mode)
    assessment = serialize_assessment_response(
        result,
        claim=claim,
        source_url=source_url,
        category=request.category,
        mode=mode,
        build=get_app_build(),
        include_debug=request.include_debug,
        owner_id=owner_id,
    )
    return save_report(assessment)


@app.post("/sources/extract", response_model=ExtractedSource)
def extract_source(request: SourceExtractRequest) -> ExtractedSource:
    source_url = (request.source_url or "").strip()
    return fetch_source_url(source_url)


@app.get("/auth/diagnostics", response_model=Dict[str, Any])
def auth_diagnostics(http_request: Request) -> Dict[str, Any]:
    authorization = http_request.headers.get("authorization") or ""
    if not authorization.lower().startswith("bearer "):
        return {"ok": True, "has_bearer": False, "diagnostics": {}}
    token = authorization.split(" ", 1)[1].strip()
    diagnostics = unverified_token_diagnostics(token)
    try:
        claims = decode_supabase_access_token(token)
        return {
            "ok": True,
            "has_bearer": True,
            "verified": True,
            "diagnostics": diagnostics,
            "claims": {"subject_present": bool(claims.get("sub")), "email_present": bool(claims.get("email"))},
        }
    except Exception as exc:
        detail = getattr(exc, "developer_detail", "")
        return {
            "ok": True,
            "has_bearer": True,
            "verified": False,
            "diagnostics": diagnostics,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "verifier_detail": detail,
        }




@app.post("/transcripts/diagnose", response_model=Dict[str, Any])
def diagnose_transcript_source(request: SourceExtractRequest) -> Dict[str, Any]:
    if not request.source_url or not is_probable_url(request.source_url):
        raise HTTPException(status_code=400, detail={"code": "invalid_source_url", "message": "source_url must start with http:// or https://"})
    if not _is_youtube_url(request.source_url):
        raise HTTPException(status_code=400, detail={"code": "unsupported_source", "message": "Transcript diagnostics currently support YouTube URLs only."})
    return diagnose_youtube_transcript(request.source_url)


@app.get("/reports", response_model=Dict[str, Any])
def reports_index(http_request: Request, limit: int = 50) -> Dict[str, Any]:
    owner_id = _owner_id_from_request(http_request)
    return {"ok": True, "owner_id": owner_id or None, "reports": list_reports(limit=limit, owner_id=owner_id)}


@app.get("/tiers", response_model=Dict[str, Any])
def tiers() -> Dict[str, Any]:
    return {"ok": True, **feature_matrix()}


@app.get("/me", response_model=Dict[str, Any])
def me(http_request: Request) -> Dict[str, Any]:
    context, profile = _profile_from_request(http_request)
    return {"ok": True, "authenticated": context.authenticated, "is_admin": _is_master_admin(context), "user": profile.to_dict(), "feature_matrix": feature_matrix()}


@app.get("/admin/users", response_model=Dict[str, Any])
def admin_users(http_request: Request, limit: int = 100) -> Dict[str, Any]:
    _require_admin(http_request)
    return {"ok": True, "users": [profile.to_dict() for profile in list_user_profiles(limit=limit)], "feature_matrix": feature_matrix()}


@app.patch("/admin/users/tier", response_model=Dict[str, Any])
def admin_set_user_tier(request: AdminSetTierRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    profile = set_user_tier(request.owner_id, request.tier, email=request.email)
    return {"ok": True, "user": profile.to_dict()}




@app.post("/admin/users/invite", response_model=Dict[str, Any])
def admin_invite_user(request: AdminInviteUserRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    created = _create_or_invite_supabase_user(request)
    owner_id = str(created.get("id") or created.get("user", {}).get("id") or "").strip()
    email = str(created.get("email") or created.get("user", {}).get("email") or request.email).strip().lower()
    profile = set_user_tier(owner_id, request.tier, email=email) if owner_id else None
    return {
        "ok": True,
        "sent_invite": request.send_invite,
        "owner_id": owner_id,
        "email": email,
        "user": profile.to_dict() if profile else None,
        "message": "Invitation sent and profile created." if request.send_invite else "User created without sending an invite email.",
    }


@app.delete("/admin/users/{owner_id}", response_model=Dict[str, Any])
def admin_delete_user(owner_id: str, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    if _auth_context_from_request(http_request).owner_id == owner_id:
        raise HTTPException(status_code=400, detail={"code": "cannot_delete_self", "message": "You cannot delete your own admin profile."})
    deleted = delete_user_profile(owner_id)
    return {"ok": True, "owner_id": owner_id, "deleted": deleted, "message": "User profile deleted. Supabase auth account was not deleted."}


@app.get("/reports/{report_id}", response_model=AssessmentResponse)
def get_report(report_id: str) -> AssessmentResponse:
    return load_report(report_id)


@app.post("/assessments/{assessment_id}/feedback", response_model=Dict[str, Any])
def create_assessment_feedback(assessment_id: str, request: FeedbackCreateRequest) -> Dict[str, Any]:
    assessment = load_report(assessment_id)
    payload = assessment.model_dump(mode="json")
    record = build_feedback_record(
        result_key=assessment.assessment_id,
        rating=request.rating,
        reasons=request.reasons,
        comment=request.comment,
        result=payload,
        source_url=assessment.request.source_url or "",
        settings=assessment.request.settings,
    )
    saved = save_feedback(record)
    return {
        "ok": saved.ok,
        "feedback_id": saved.feedback_id,
        "assessment_id": assessment.assessment_id,
        "destination": saved.destination,
        "message": saved.message,
    }


@app.get("/assessments/{assessment_id}/feedback", response_model=Dict[str, Any])
def get_assessment_feedback(assessment_id: str, limit: int = 100) -> Dict[str, Any]:
    assessment = load_report(assessment_id)
    feedback = list_feedback_for_assessment(assessment.assessment_id, limit=limit)
    return {
        "ok": True,
        "assessment_id": assessment.assessment_id,
        "feedback_count": len(feedback),
        "feedback": feedback,
    }


def runtime_status() -> Dict[str, Any]:
    llm, search = _clients()
    return {
        "ok": True,
        "api_version": API_VERSION,
        "build": get_app_build(),
        "openai_configured": llm.configured,
        "tavily_configured": search.configured,
        "storage_backend": "postgres" if database_url() else "local_json",
        "auth_configured": supabase_auth_configured(),
        "admin_configured": bool(admin_token() or master_admin_emails()),
        "transcript_backends": transcript_backend_status(),
    }


@app.get("/", response_model=Dict[str, Any])
def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "evidrai-api",
        "api_version": API_VERSION,
        "build": get_app_build(),
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/version", response_model=Dict[str, Any])
def version() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "evidrai-api",
        "api_version": API_VERSION,
        "build": get_app_build(),
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return runtime_status()


@app.get("/runtime", response_model=Dict[str, Any])
def runtime() -> Dict[str, Any]:
    return runtime_status()


@app.post("/claims/check", response_model=ApiEnvelope)
def check_claim(request: ClaimCheckRequest, http_request: Request) -> ApiEnvelope:
    claim = (request.claim or "").strip()
    source_url = (request.source_url or "").strip()
    _validate_claim_request(claim, source_url)

    context, profile = _profile_from_request(http_request)
    require_feature(profile, "deep_claims" if request.mode == "deep" else "fast_claims", authenticated=context.authenticated)
    result = _run_claim_assessment(claim=claim, source_url=source_url, category=request.category, mode=request.mode)
    assessment = serialize_assessment_response(
        result,
        claim=claim,
        source_url=source_url,
        category=request.category,
        mode=request.mode,
        build=get_app_build(),
        include_debug=request.include_debug,
        owner_id=context.owner_id,
    ).model_dump(mode="json")
    result["settings"] = {
        "result_mode": request.mode,
        "claim_category": request.category,
        "source_url": source_url,
        "build": get_app_build(),
    }
    result["assessment"] = assessment
    return ApiEnvelope(ok=True, build=get_app_build(), result=result)


@app.post("/assessments/fast", response_model=AssessmentResponse)
def create_fast_assessment(request: AssessmentCreateRequest, http_request: Request) -> AssessmentResponse:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "fast_claims", authenticated=context.authenticated)
    return _assessment_response_from_request(request, "fast", owner_id=context.owner_id)


@app.post("/assessments/deep", response_model=AssessmentResponse)
def create_deep_assessment(request: AssessmentCreateRequest, http_request: Request) -> AssessmentResponse:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "deep_claims", authenticated=context.authenticated)
    return _assessment_response_from_request(request, "deep", owner_id=context.owner_id)


@app.post("/speech/extract", response_model=ApiEnvelope)
def speech_extract(request: SpeechExtractRequest, http_request: Request) -> ApiEnvelope:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "speech_audit", authenticated=context.authenticated)
    enforce_speech_claim_limit(profile, request.max_claims)
    source_url = (request.source_url or "").strip()
    transcript = _speech_transcript_from_request(request.transcript, source_url, request.try_youtube_captions)

    llm, _search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "OPENAI_API_KEY is not configured"})

    extraction = extract_speech_audit_claims(transcript, source_url, request.max_claims, llm)
    extraction["schema_version"] = "speech_extraction.v1"
    extraction["settings"] = {
        "result_mode": "speech_extract",
        "source_url": source_url,
        "max_claims": request.max_claims,
        "build": get_app_build(),
    }
    return ApiEnvelope(ok=True, build=get_app_build(), result=extraction)


@app.post("/speech/verify", response_model=ApiEnvelope)
def speech_verify(request: SpeechVerifyRequest, http_request: Request) -> ApiEnvelope:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "speech_audit", authenticated=context.authenticated)
    enforce_speech_claim_limit(profile, len(request.claims))
    source_url = (request.source_url or "").strip()
    if source_url and not is_probable_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")
    if not request.claims:
        raise HTTPException(status_code=400, detail="at least one selected claim is required")

    llm, search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "OPENAI_API_KEY is not configured"})
    if request.verification_mode == "deep" and not search.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "TAVILY_API_KEY is required for deep speech audit"})

    mode = "deep" if request.verification_mode == "deep" else "fast"
    checked_claims = [
        verify_speech_claim(claim, index=idx, source_url=source_url, mode=mode, llm=llm, search=search)
        for idx, claim in enumerate(request.claims, start=1)
    ]
    result = {
        "schema_version": "speech_verification.v1",
        "source_url": source_url,
        "claims_checked": checked_claims,
        "claims_checked_count": len(checked_claims),
        "verification_mode": mode,
        "settings": {
            "result_mode": "speech_verify",
            "source_url": source_url,
            "verification_mode": mode,
            "build": get_app_build(),
        },
    }
    return ApiEnvelope(ok=True, build=get_app_build(), result=result)


@app.post("/speech/audit", response_model=ApiEnvelope)
def speech_audit(request: SpeechAuditRequest, http_request: Request) -> ApiEnvelope:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "speech_audit", authenticated=context.authenticated)
    enforce_speech_claim_limit(profile, request.max_claims)
    source_url = (request.source_url or "").strip()
    transcript = _speech_transcript_from_request(request.transcript, source_url, request.try_youtube_captions)

    llm, search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "OPENAI_API_KEY is not configured"})
    if request.verification_mode == "deep" and not search.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "TAVILY_API_KEY is required for deep speech audit"})

    result = run_speech_audit(transcript, source_url, request.max_claims, llm, search, verification_mode=request.verification_mode)
    result["settings"] = {
        "result_mode": "speech_audit",
        "source_url": source_url,
        "max_claims": request.max_claims,
        "verification_mode": request.verification_mode,
        "build": get_app_build(),
    }
    return ApiEnvelope(ok=True, build=get_app_build(), result=result)
