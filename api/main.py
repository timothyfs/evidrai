from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from evidrai.api_models import AssessmentResponse, EvidenceMap, serialize_assessment_response
from evidrai.assessment_jobs import AssessmentJob, get_assessment_job_store
from evidrai.auth import AuthContext, context_from_headers, decode_supabase_access_token, unverified_token_diagnostics
from evidrai.clients.llm import OpenAICompatibleClient
from evidrai.clients.search import TavilySearchClient
from evidrai.config import admin_token, api_allowed_origins, database_url, get_app_build, master_admin_emails, supabase_auth_configured, supabase_service_role_key, supabase_url, turnstile_configured, turnstile_secret_key
from evidrai.entitlements import (
    delete_user_profile,
    enforce_speech_claim_limit,
    feature_matrix,
    get_or_create_profile,
    list_user_profiles,
    require_feature,
    set_user_tier,
    update_user_profile_details,
)
from evidrai.errors import EvidraiError, safe_error_payload
from evidrai.feedback import build_feedback_record, list_feedback_for_assessment, list_recent_feedback_records, load_feedback_by_id, save_feedback
from evidrai.trust import backfill_trust_from_reports, trust_analytics_summary
from evidrai.ingestion.url import ExtractedSource, fetch_source_url
from evidrai.pipeline.verification import (
    extract_speech_audit_claims,
    run_claim_pipeline,
    run_quick_pass,
    run_speech_audit,
    verify_speech_claim,
)
from evidrai.reports import _assessment_field, create_report_share, delete_report, enforce_report_retention, list_reports, load_report, load_shared_report, save_report, set_report_metadata
from evidrai.scoring import get_scoring_policy, list_scoring_policy_history, policy_to_dict, update_scoring_policy, weight_sum
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
    bot_token: str = ""


class AssessmentCreateRequest(BaseModel):
    claim: str = ""
    source_url: str = ""
    category: str = "auto-detect"
    output_style: str = Field(default="standard", pattern="^(standard|absurdity_humour)$")
    include_debug: bool = False
    bot_token: str = ""


class SpeechAuditRequest(BaseModel):
    transcript: str = ""
    source_url: str = ""
    max_claims: int = Field(default=3, ge=1, le=20)
    verification_mode: str = Field(default="fast", pattern="^(fast|deep)$")
    try_youtube_captions: bool = True
    bot_token: str = ""


class SpeechExtractRequest(BaseModel):
    transcript: str = ""
    source_url: str = ""
    max_claims: int = Field(default=3, ge=1, le=20)
    try_youtube_captions: bool = True
    bot_token: str = ""


class SpeechVerifyRequest(BaseModel):
    claims: list[Dict[str, Any]] = Field(default_factory=list)
    source_url: str = ""
    verification_mode: str = Field(default="fast", pattern="^(fast|deep)$")
    bot_token: str = ""


class SourceExtractRequest(BaseModel):
    source_url: str


class SupportIssueRequest(BaseModel):
    issue_type: str = Field(default="bug", pattern="^(bug|support|idea|other)$")
    severity: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    subject: str = ""
    description: str = ""
    page_url: str = ""
    assessment_id: str = ""
    browser_context: Dict[str, Any] = Field(default_factory=dict)


class FeedbackCreateRequest(BaseModel):
    rating: str = Field(default="Useful", pattern="^(Useful|Partly useful|Not useful)$")
    reasons: list[str] = Field(default_factory=list)
    trust_signals: list[str] = Field(default_factory=list)
    accepted_verdict: str = Field(default="", pattern="^(|accepted|rejected|unsure)$")
    challenge_text: str = ""
    counter_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    persuasive_source_ids: list[str] = Field(default_factory=list)
    distrusted_source_ids: list[str] = Field(default_factory=list)
    comment: str = ""


class ReportShareCreateRequest(BaseModel):
    platform: str = "copy"


class ReportMetadataUpdateRequest(BaseModel):
    protected: Optional[bool] = None
    labels: Optional[list[str]] = None


class AdminSetTierRequest(BaseModel):
    owner_id: str
    tier: str = Field(pattern="^(free|pro|researcher)$")
    email: str = ""


class AdminUpdateProfileRequest(BaseModel):
    owner_id: str
    email: str = ""
    company_name: str = ""
    organisation_name: str = ""
    billing_account_name: str = ""
    billing_account_id: str = ""
    admin_notes: str = ""


class AdminBulkUserActionRequest(BaseModel):
    owner_ids: list[str]
    action: str
    tier: Optional[str] = Field(default=None, pattern="^(free|pro|researcher)$")


class AdminPasswordActionRequest(BaseModel):
    owner_id: str
    email: str = ""
    password: str = ""
    redirect_to: str = ""


class AdminInviteUserRequest(BaseModel):
    email: str
    tier: str = Field(default="free", pattern="^(free|pro|researcher)$")
    send_invite: bool = True
    redirect_to: str = ""


class AdminScoringPolicyUpdateRequest(BaseModel):
    source_score_weights: Dict[str, float] = Field(default_factory=dict)
    source_type_authority: Dict[str, float] = Field(default_factory=dict)
    source_type_independence: Dict[str, float] = Field(default_factory=dict)
    source_type_bias_risk: Dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    change_note: str = ""


class ApiEnvelope(BaseModel):
    ok: bool
    build: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AssessmentJobCreateResponse(BaseModel):
    ok: bool = True
    job_id: str
    status: str
    mode: str
    created_at: str


class AssessmentJobStatusResponse(BaseModel):
    ok: bool = True
    job_id: str
    status: str
    mode: str
    created_at: str
    updated_at: str
    completed_at: str = ""
    assessment_id: str = ""
    assessment: Optional[AssessmentResponse] = None
    error: str = ""



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




def _supabase_request(method: str, path: str, *, body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request_kwargs: dict[str, Any] = {"headers": _supabase_admin_headers(), "params": params or {}, "timeout": 20}
    if body is not None:
        request_kwargs["json"] = body
    try:
        response = requests.request(method, _supabase_auth_url(path), **request_kwargs)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail={"code": "supabase_admin_request_failed", "message": "Could not reach Supabase admin API.", "developer_detail": str(exc)})
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail={"code": "supabase_admin_error", "message": "Supabase could not complete this admin user action.", "supabase_detail": detail})
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def _send_supabase_password_reset(email: str, redirect_to: str = "") -> dict[str, Any]:
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "A valid email address is required for password reset."})
    body: dict[str, Any] = {"email": clean_email}
    if redirect_to.strip():
        body["redirect_to"] = redirect_to.strip()
    return _supabase_request("POST", "recover", body=body)


def _resend_supabase_invite(email: str, redirect_to: str = "") -> dict[str, Any]:
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "A valid email address is required to resend an invite."})
    body: dict[str, Any] = {"type": "signup", "email": clean_email}
    if redirect_to.strip():
        body["options"] = {"email_redirect_to": redirect_to.strip()}
    return _supabase_request("POST", "resend", body=body)


def _update_supabase_user_password(owner_id: str, password: str) -> dict[str, Any]:
    if not owner_id.strip():
        raise HTTPException(status_code=400, detail={"code": "owner_required", "message": "owner_id is required."})
    if len(password) < 8:
        raise HTTPException(status_code=400, detail={"code": "password_too_short", "message": "Temporary password must be at least 8 characters."})
    return _supabase_request("PUT", f"admin/user/{owner_id.strip()}", body={"password": password})


def _list_supabase_auth_users(limit: int = 1000) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    per_page = 100
    max_pages = max(1, (limit + per_page - 1) // per_page)
    for page in range(1, max_pages + 1):
        payload = _supabase_request("GET", "admin/users", params={"page": page, "per_page": per_page})
        page_users = payload.get("users") if isinstance(payload, dict) else None
        if not isinstance(page_users, list):
            return users
        users.extend([user for user in page_users if isinstance(user, dict)])
        if len(page_users) < per_page or len(users) >= limit:
            break
    return users[:limit]


def _supabase_auth_user_by_email(email: str) -> dict[str, Any] | None:
    clean_email = email.strip().lower()
    if not clean_email:
        return None
    for user in _list_supabase_auth_users():
        if str(user.get("email") or "").strip().lower() == clean_email:
            return user
    return None


def _user_profile_email(owner_id: str) -> str:
    clean_owner_id = owner_id.strip()
    if not clean_owner_id:
        return ""
    for profile in list_user_profiles(limit=1000):
        if profile.owner_id == clean_owner_id:
            return profile.email
    return ""


def _delete_supabase_auth_user(owner_id: str, email: str = "") -> bool:
    clean_owner_id = owner_id.strip()
    if not clean_owner_id:
        raise HTTPException(status_code=400, detail={"code": "owner_required", "message": "owner_id is required."})
    try:
        _supabase_request("DELETE", f"admin/users/{clean_owner_id}")
        return True
    except HTTPException as exc:
        if exc.status_code not in {400, 404} or not email.strip():
            if exc.status_code == 404:
                return False
            raise
    existing = _supabase_auth_user_by_email(email)
    existing_id = str(existing.get("id") or "").strip() if existing else ""
    if not existing_id:
        return False
    _supabase_request("DELETE", f"admin/users/{existing_id}")
    return True


def _create_or_invite_supabase_user(request: AdminInviteUserRequest) -> dict[str, Any]:
    if request.send_invite:
        existing = _supabase_auth_user_by_email(request.email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "supabase_auth_user_already_exists",
                    "message": f"Supabase Auth already has a user for {request.email.strip().lower()}. Delete that auth user first, then resend the invite.",
                    "supabase_user_id": str(existing.get("id") or ""),
                    "email": str(existing.get("email") or request.email).strip().lower(),
                },
            )
    email = request.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "A valid email address is required."})
    body: dict[str, Any] = {"email": email, "data": {"evidrai_tier": request.tier}}
    if request.redirect_to.strip():
        body["redirect_to"] = request.redirect_to.strip()
    if request.send_invite:
        return _supabase_request("POST", "invite", body=body)
    body["email_confirm"] = True
    body["user_metadata"] = body.pop("data")
    return _supabase_request("POST", "admin/users", body=body)

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
    output_style: str = "standard",
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
    fast_output_style = output_style if output_style == "absurdity_humour" else "standard"
    return run_quick_pass(analysis_input, category, llm, search, output_style=fast_output_style)


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
    profile = get_or_create_profile(context.owner_id, email=context.email)
    if _is_master_admin(context) and profile.tier != "researcher":
        profile = set_user_tier(context.owner_id, "researcher", email=context.email)
    return context, profile


def _is_master_admin(context: AuthContext) -> bool:
    return context.authenticated and context.email.strip().lower() in master_admin_emails()


def _require_authenticated(request: Request) -> AuthContext:
    context, _profile = _profile_from_request(request)
    if not context.authenticated:
        raise HTTPException(status_code=401, detail={"code": "auth_required", "message": "Sign in with an email address before using Evidrai."})
    return context


def _require_bot_check(request: Request, bot_token: str = "") -> None:
    if not turnstile_configured():
        return
    token = (bot_token or request.headers.get("x-turnstile-token") or "").strip()
    if not token:
        raise HTTPException(status_code=403, detail={"code": "bot_check_required", "message": "Bot protection check is required before running this action."})
    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": turnstile_secret_key(),
                "response": token,
                "remoteip": request.client.host if request.client else "",
            },
            timeout=8,
        )
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "bot_check_unavailable", "message": "Bot protection could not be verified. Please try again."}) from exc
    if not payload.get("success"):
        raise HTTPException(status_code=403, detail={"code": "bot_check_failed", "message": "Bot protection check failed. Please try again."})


def _require_admin(request: Request) -> None:
    context = _auth_context_from_request(request)
    if _is_master_admin(context):
        return

    configured = admin_token()
    supplied = (request.headers.get("x-evidrai-admin-token") or "").strip()
    if configured and supplied == configured:
        return

    raise HTTPException(status_code=403, detail={"code": "admin_forbidden", "message": "Master admin access is required"})


def _apply_report_retention(owner_id: str, profile: Any | None = None) -> None:
    if not owner_id:
        return
    try:
        effective_profile = profile or get_or_create_profile(owner_id)
        profile_payload = effective_profile.to_dict() if hasattr(effective_profile, "to_dict") else {}
        limit = int((profile_payload.get("limits") or {}).get("saved_reports") or 0)
        if limit > 0:
            enforce_report_retention(owner_id, limit)
    except Exception:
        # Retention cleanup should not block assessment delivery.
        pass


def _assessment_response_from_request(request: AssessmentCreateRequest, mode: str, owner_id: str = "", profile: Any | None = None) -> AssessmentResponse:
    claim = (request.claim or "").strip()
    source_url = (request.source_url or "").strip()
    _validate_claim_request(claim, source_url)
    output_style = request.output_style if mode == "fast" else "standard"
    result = _run_claim_assessment(claim=claim, source_url=source_url, category=request.category, mode=mode, output_style=output_style)
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
    saved = save_report(assessment)
    _apply_report_retention(owner_id, profile=profile)
    return saved


def _job_status_response(job: AssessmentJob, context: AuthContext) -> AssessmentJobStatusResponse:
    if job.owner_id and job.owner_id != context.owner_id and not _is_master_admin(context):
        raise HTTPException(status_code=403, detail={"code": "assessment_job_forbidden", "message": "This assessment job belongs to another account."})
    assessment = None
    assessment_id = ""
    if job.status == "completed" and job.result:
        assessment = AssessmentResponse.model_validate(job.result)
        assessment_id = assessment.assessment_id
    return AssessmentJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        mode=job.mode,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        assessment_id=assessment_id,
        assessment=assessment,
        error=job.error,
    )


def _run_assessment_job(job_id: str) -> None:
    store = get_assessment_job_store()
    try:
        job = store.mark_running(job_id)
        request = AssessmentCreateRequest.model_validate(job.request)
        assessment = _assessment_response_from_request(request, job.mode, owner_id=job.owner_id)
        store.mark_completed(job_id, assessment.model_dump(mode="json"))
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            message = str(detail.get("message") or detail.get("code") or detail)
        else:
            message = str(detail)
        store.mark_failed(job_id, message)
    except Exception as exc:
        store.mark_failed(job_id, str(exc))


def _save_speech_claim_assessment(result: Dict[str, Any], *, source_url: str, mode: str, owner_id: str = "", profile: Any | None = None) -> AssessmentResponse:
    speech_claim = result.get("speech_claim") or {}
    claim_text = (
        speech_claim.get("normalized_claim")
        or speech_claim.get("quote")
        or result.get("claim")
        or "Speech claim"
    )
    assessment = serialize_assessment_response(
        result,
        claim=str(claim_text),
        source_url=source_url,
        category="speech-video",
        mode=f"speech-{mode}",
        build=get_app_build(),
        include_debug=False,
        owner_id=owner_id,
    )
    assessment.request.settings.update(
        {
            "result_mode": "speech_verify",
            "speech_claim_id": speech_claim.get("id", ""),
            "speech_quote": speech_claim.get("quote", ""),
            "source_url": source_url,
            "build": get_app_build(),
        }
    )
    saved = save_report(assessment)
    _apply_report_retention(owner_id, profile=profile)
    return saved


def _attach_saved_speech_assessments(checked_claims: list[Dict[str, Any]], *, source_url: str, mode: str, owner_id: str = "", profile: Any | None = None) -> list[Dict[str, Any]]:
    enriched: list[Dict[str, Any]] = []
    for item in checked_claims:
        result = dict(item)
        assessment = _save_speech_claim_assessment(result, source_url=source_url, mode=mode, owner_id=owner_id, profile=profile)
        result["assessment"] = assessment.model_dump(mode="json")
        result["assessment_id"] = assessment.assessment_id
        enriched.append(result)
    return enriched


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




def _simple_public_assessment(assessment: AssessmentResponse) -> AssessmentResponse:
    reasoning: Dict[str, Any] = {}
    if isinstance(assessment.reasoning, dict):
        for key in ("humour_summary", "claim_semantics"):
            value = assessment.reasoning.get(key)
            if value:
                reasoning[key] = value
    return assessment.model_copy(
        update={
            "owner_id": None,
            "claim_breakdown": [],
            "evidence_map": EvidenceMap(),
            "sources": [],
            "reasoning": reasoning,
        }
    )


def _public_shared_payload(shared: Dict[str, Any]) -> Dict[str, Any]:
    share = dict(shared.get("share") or {})
    assessment = shared.get("assessment")
    if not isinstance(assessment, AssessmentResponse):
        assessment = AssessmentResponse.model_validate(assessment)
    access_level = share.get("access_level") or "full"
    public_assessment = assessment.model_copy(update={"owner_id": None}) if access_level == "full" else _simple_public_assessment(assessment)
    share.pop("owner_id", None)
    return {"ok": True, "share": share, "access_level": access_level, "assessment": public_assessment}


@app.post("/transcripts/diagnose", response_model=Dict[str, Any])
def diagnose_transcript_source(request: SourceExtractRequest) -> Dict[str, Any]:
    if not request.source_url or not is_probable_url(request.source_url):
        raise HTTPException(status_code=400, detail={"code": "invalid_source_url", "message": "source_url must start with http:// or https://"})
    if not _is_youtube_url(request.source_url):
        raise HTTPException(status_code=400, detail={"code": "unsupported_source", "message": "Transcript diagnostics currently support YouTube URLs only."})
    return diagnose_youtube_transcript(request.source_url)


@app.get("/reports", response_model=Dict[str, Any])
def reports_index(http_request: Request, limit: int = 50) -> Dict[str, Any]:
    context, profile = _profile_from_request(http_request)
    if not context.authenticated:
        raise HTTPException(status_code=401, detail={"code": "auth_required", "message": "Sign in with an email address before using Evidrai."})
    profile_payload = profile.to_dict() if hasattr(profile, "to_dict") else {}
    report_limit = int((profile_payload.get("limits") or {}).get("saved_reports") or limit)
    return {"ok": True, "owner_id": context.owner_id, "report_limit": report_limit, "reports": list_reports(limit=max(limit, report_limit), owner_id=context.owner_id)}




@app.post("/reports/{report_id}/share", response_model=Dict[str, Any])
def create_report_share_endpoint(report_id: str, request: ReportShareCreateRequest, http_request: Request) -> Dict[str, Any]:
    include_debug = (http_request.query_params.get("include_debug") or "").lower() == "true"
    try:
        context, profile = _profile_from_request(http_request)
        if not context.authenticated:
            raise HTTPException(status_code=401, detail={"code": "auth_required", "message": "Sign in is required to share reports."})
        assessment = load_report(report_id)
        assessment_owner = _assessment_field(assessment, "owner_id") or ""
        if (not assessment_owner or assessment_owner != context.owner_id) and not _is_master_admin(context):
            raise HTTPException(status_code=403, detail={"code": "report_forbidden", "message": "This report belongs to another account."})
        access_level = "full" if profile.features.get("share_reports") or profile.tier in {"pro", "researcher"} else "simple"
        share = create_report_share(report_id, owner_id=context.owner_id, access_level=access_level, assessment=assessment)
        return {"ok": True, "share": share, "token": share.get("token"), "assessment_id": report_id, "access_level": access_level}
    except HTTPException:
        raise
    except EvidraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=safe_error_payload(exc, include_debug=include_debug))
    except Exception as exc:
        detail: Dict[str, Any] = {"code": "share_create_failed", "message": "Could not create share link."}
        if include_debug:
            detail["developer_detail"] = f"{type(exc).__name__}: {exc}"
        raise HTTPException(status_code=500, detail=detail)


@app.get("/public/reports/{token}", response_model=Dict[str, Any])
def get_public_shared_report(token: str) -> Dict[str, Any]:
    return _public_shared_payload(load_shared_report(token))


@app.get("/tiers", response_model=Dict[str, Any])
def tiers() -> Dict[str, Any]:
    return {"ok": True, **feature_matrix()}


def _profile_admin_view(profile: Any) -> Dict[str, Any]:
    payload = profile.to_dict()
    email = str(payload.get("email") or "").strip().lower()
    admin_access = bool(email and email in master_admin_emails())
    payload["admin_access"] = admin_access
    payload["admin_access_source"] = "master_admin_email" if admin_access else "none"
    return payload


@app.get("/me", response_model=Dict[str, Any])
def me(http_request: Request) -> Dict[str, Any]:
    context, profile = _profile_from_request(http_request)
    user = profile.to_dict()
    user["admin_access"] = _is_master_admin(context)
    user["admin_access_source"] = "master_admin_email" if user["admin_access"] else "none"
    return {"ok": True, "authenticated": context.authenticated, "is_admin": _is_master_admin(context), "user": user, "feature_matrix": feature_matrix()}


@app.get("/admin/users", response_model=Dict[str, Any])
def admin_users(http_request: Request, limit: int = 100) -> Dict[str, Any]:
    _require_admin(http_request)
    return {"ok": True, "users": [_profile_admin_view(profile) for profile in list_user_profiles(limit=limit)], "feature_matrix": feature_matrix()}


@app.patch("/admin/users/tier", response_model=Dict[str, Any])
def admin_set_user_tier(request: AdminSetTierRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    profile = set_user_tier(request.owner_id, request.tier, email=request.email)
    return {"ok": True, "user": _profile_admin_view(profile)}


@app.get("/admin/scoring-policy", response_model=Dict[str, Any])
def admin_get_scoring_policy(http_request: Request, limit: int = 25) -> Dict[str, Any]:
    _require_admin(http_request)
    policy = get_scoring_policy()
    return {"ok": True, "policy": policy_to_dict(policy), "weight_sum": weight_sum(policy), "history": list_scoring_policy_history(limit=limit)}


@app.patch("/admin/scoring-policy", response_model=Dict[str, Any])
def admin_update_scoring_policy(request: AdminScoringPolicyUpdateRequest, http_request: Request) -> Dict[str, Any]:
    context = _auth_context_from_request(http_request)
    _require_admin(http_request)
    policy = update_scoring_policy(
        request.model_dump(mode="json"),
        updated_by=context.email or context.owner_id or "admin",
        change_note=request.change_note,
    )
    return {"ok": True, "policy": policy_to_dict(policy), "weight_sum": weight_sum(policy), "history": list_scoring_policy_history(limit=25)}


@app.patch("/admin/users/profile", response_model=Dict[str, Any])
def admin_update_user_profile(request: AdminUpdateProfileRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    profile = update_user_profile_details(
        request.owner_id,
        email=request.email,
        company_name=request.company_name,
        organisation_name=request.organisation_name,
        billing_account_name=request.billing_account_name,
        billing_account_id=request.billing_account_id,
        admin_notes=request.admin_notes,
    )
    return {"ok": True, "user": _profile_admin_view(profile)}


@app.post("/admin/users/bulk", response_model=Dict[str, Any])
def admin_bulk_user_action(request: AdminBulkUserActionRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    owner_ids = [owner_id.strip() for owner_id in request.owner_ids if owner_id.strip()]
    if not owner_ids:
        raise HTTPException(status_code=400, detail={"code": "owner_required", "message": "Select at least one user."})
    if request.action == "set_tier":
        if not request.tier:
            raise HTTPException(status_code=400, detail={"code": "tier_required", "message": "A target tier is required."})
        users = [_profile_admin_view(set_user_tier(owner_id, request.tier)) for owner_id in owner_ids]
        return {"ok": True, "action": request.action, "users": users}
    if request.action == "delete_profiles":
        current_owner = _auth_context_from_request(http_request).owner_id
        if current_owner in owner_ids:
            raise HTTPException(status_code=400, detail={"code": "cannot_delete_self", "message": "You cannot delete your own admin profile."})
        deleted = [{"owner_id": owner_id, "deleted": delete_user_profile(owner_id)} for owner_id in owner_ids]
        return {"ok": True, "action": request.action, "deleted": deleted}
    raise HTTPException(status_code=400, detail={"code": "unsupported_bulk_action", "message": "Unsupported bulk action."})


@app.post("/admin/users/password-reset", response_model=Dict[str, Any])
def admin_password_reset(request: AdminPasswordActionRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    _send_supabase_password_reset(request.email, redirect_to=request.redirect_to)
    return {"ok": True, "owner_id": request.owner_id, "email": request.email.strip().lower(), "message": "Password reset email sent."}


@app.patch("/admin/users/password", response_model=Dict[str, Any])
def admin_update_user_password(request: AdminPasswordActionRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    _update_supabase_user_password(request.owner_id, request.password)
    return {"ok": True, "owner_id": request.owner_id, "message": "Password updated."}



@app.post("/admin/users/resend-invite", response_model=Dict[str, Any])
def admin_resend_invite(request: AdminPasswordActionRequest, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    _resend_supabase_invite(request.email, redirect_to=request.redirect_to)
    return {"ok": True, "owner_id": request.owner_id, "email": request.email.strip().lower(), "message": "Invite email resent."}

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
        "user": _profile_admin_view(profile) if profile else None,
        "message": "Invitation sent and profile created." if request.send_invite else "User created without sending an invite email.",
    }


@app.delete("/admin/users/{owner_id}", response_model=Dict[str, Any])
def admin_delete_user(owner_id: str, http_request: Request) -> Dict[str, Any]:
    _require_admin(http_request)
    if _auth_context_from_request(http_request).owner_id == owner_id:
        raise HTTPException(status_code=400, detail={"code": "cannot_delete_self", "message": "You cannot delete your own admin account."})
    profile_email = _user_profile_email(owner_id)
    auth_deleted = _delete_supabase_auth_user(owner_id, email=profile_email)
    profile_deleted = delete_user_profile(owner_id)
    return {
        "ok": True,
        "owner_id": owner_id,
        "deleted": bool(auth_deleted or profile_deleted),
        "auth_deleted": auth_deleted,
        "profile_deleted": profile_deleted,
        "message": "Supabase auth user and Evidrai profile deleted." if auth_deleted else "Evidrai profile deleted. Supabase auth user was already missing.",
    }


@app.get("/reports/{report_id}", response_model=AssessmentResponse)
def get_report(report_id: str, http_request: Request) -> AssessmentResponse:
    assessment = load_report(report_id)
    context = _require_authenticated(http_request)
    if (not assessment.owner_id or assessment.owner_id != context.owner_id) and not _is_master_admin(context):
        raise HTTPException(status_code=403, detail={"code": "report_forbidden", "message": "This report belongs to another account."})
    return assessment


@app.patch("/reports/{report_id}/metadata", response_model=Dict[str, Any])
def update_report_metadata(report_id: str, request: ReportMetadataUpdateRequest, http_request: Request) -> Dict[str, Any]:
    context = _require_authenticated(http_request)
    assessment = load_report(report_id)
    if (not assessment.owner_id or assessment.owner_id != context.owner_id) and not _is_master_admin(context):
        raise HTTPException(status_code=403, detail={"code": "report_forbidden", "message": "This report belongs to another account."})
    owner_id = assessment.owner_id or context.owner_id
    allowed_labels = {"favourite", "reviewed", "customer-facing", "internal-only", "useful", "not-useful", "needs-follow-up"}
    labels = None
    if request.labels is not None:
        labels = []
        for label in request.labels:
            normalized = str(label).strip().lower()
            if normalized not in allowed_labels:
                raise HTTPException(status_code=400, detail={"code": "invalid_report_label", "message": f"Unsupported report label: {label}"})
            if normalized not in labels:
                labels.append(normalized)
    metadata = set_report_metadata(report_id, owner_id=owner_id, protected=request.protected, labels=labels)
    return {"ok": True, "report": metadata}


@app.delete("/reports/{report_id}", response_model=Dict[str, Any])
def delete_report_endpoint(report_id: str, http_request: Request) -> Dict[str, Any]:
    context = _require_authenticated(http_request)
    assessment = load_report(report_id)
    if (not assessment.owner_id or assessment.owner_id != context.owner_id) and not _is_master_admin(context):
        raise HTTPException(status_code=403, detail={"code": "report_forbidden", "message": "This report belongs to another account."})
    owner_id = assessment.owner_id or context.owner_id
    result = delete_report(report_id, owner_id=owner_id)
    return {"ok": True, "report": result}


@app.post("/support/issues", response_model=Dict[str, Any])
def create_support_issue(request: SupportIssueRequest, http_request: Request) -> Dict[str, Any]:
    context = _require_authenticated(http_request)
    subject = (request.subject or "").strip()[:180]
    description = (request.description or "").strip()
    if not subject and not description:
        raise HTTPException(status_code=400, detail={"code": "support_issue_empty", "message": "Describe the issue before sending it."})
    record = build_feedback_record(
        result_key="support_issue",
        rating="Issue report",
        reasons=[request.issue_type, request.severity],
        comment=description or subject,
        result={
            "assessment_id": request.assessment_id,
            "owner_id": context.owner_id,
            "support_issue": {
                "issue_type": request.issue_type,
                "severity": request.severity,
                "subject": subject,
                "description": description,
                "page_url": request.page_url,
                "browser_context": request.browser_context,
            },
        },
        source_url=request.page_url,
        settings={"support_channel": "in_app", "email": context.email},
        owner_id=context.owner_id,
    )
    saved = save_feedback(record)
    return {
        "ok": saved.ok,
        "issue_id": saved.feedback_id,
        "destination": saved.destination,
        "message": "Support issue sent for review.",
    }


@app.get("/admin/support/issues", response_model=Dict[str, Any])
def admin_support_issues(http_request: Request, limit: int = 25) -> Dict[str, Any]:
    _require_admin(http_request)
    safe_limit = max(1, min(limit, 100))
    issues = list_recent_feedback_records(limit=safe_limit, result_key="support_issue")
    return {"ok": True, "issues": issues, "count": len(issues)}


@app.post("/assessments/{assessment_id}/feedback", response_model=Dict[str, Any])
def create_assessment_feedback(assessment_id: str, request: FeedbackCreateRequest, http_request: Request) -> Dict[str, Any]:
    assessment = load_report(assessment_id)
    context = _require_authenticated(http_request)
    if (not assessment.owner_id or assessment.owner_id != context.owner_id) and not _is_master_admin(context):
        raise HTTPException(status_code=403, detail={"code": "report_forbidden", "message": "This report belongs to another account."})
    payload = assessment.model_dump(mode="json")
    record = build_feedback_record(
        result_key=assessment.assessment_id,
        rating=request.rating,
        reasons=request.reasons,
        comment=request.comment,
        result=payload,
        source_url=assessment.request.source_url or "",
        settings=assessment.request.settings,
        trust_signals=request.trust_signals,
        accepted_verdict=request.accepted_verdict,
        challenge_text=request.challenge_text,
        counter_evidence=request.counter_evidence,
        persuasive_source_ids=request.persuasive_source_ids,
        distrusted_source_ids=request.distrusted_source_ids,
        owner_id=context.owner_id,
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


@app.get("/feedback/{feedback_id}", response_model=Dict[str, Any])
def get_feedback(feedback_id: str) -> Dict[str, Any]:
    feedback = load_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail={"code": "feedback_not_found", "message": "Feedback not found."})
    return {
        "ok": True,
        "feedback_id": feedback_id,
        "assessment_id": feedback.get("assessment_id", ""),
        "feedback": feedback,
    }


@app.get("/admin/trust/analytics", response_model=Dict[str, Any])
def admin_trust_analytics(http_request: Request, limit: int = 20) -> Dict[str, Any]:
    _require_admin(http_request)
    return trust_analytics_summary(limit=limit)


@app.post("/admin/trust/backfill", response_model=Dict[str, Any])
def admin_trust_backfill(http_request: Request, limit: int = 1000) -> Dict[str, Any]:
    _require_admin(http_request)
    result = backfill_trust_from_reports(limit=limit)
    result["analytics"] = trust_analytics_summary(limit=20)
    return result


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
    _require_bot_check(http_request, request.bot_token)
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
    _require_bot_check(http_request, request.bot_token)
    return _assessment_response_from_request(request, "fast", owner_id=context.owner_id, profile=profile)


@app.post("/assessments/deep", response_model=AssessmentResponse)
def create_deep_assessment(request: AssessmentCreateRequest, http_request: Request) -> AssessmentResponse:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "deep_claims", authenticated=context.authenticated)
    _require_bot_check(http_request, request.bot_token)
    return _assessment_response_from_request(request, "deep", owner_id=context.owner_id, profile=profile)


@app.post("/assessment-jobs/{mode}", response_model=AssessmentJobCreateResponse)
def create_assessment_job(mode: str, request: AssessmentCreateRequest, http_request: Request, background_tasks: BackgroundTasks) -> AssessmentJobCreateResponse:
    if mode not in {"fast", "deep"}:
        raise HTTPException(status_code=404, detail="Not Found")
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "deep_claims" if mode == "deep" else "fast_claims", authenticated=context.authenticated)
    _require_bot_check(http_request, request.bot_token)
    _validate_claim_request((request.claim or "").strip(), (request.source_url or "").strip())
    store = get_assessment_job_store()
    job = store.create(owner_id=context.owner_id, mode=mode, request=request.model_dump(mode="json"))
    background_tasks.add_task(_run_assessment_job, job.job_id)
    return AssessmentJobCreateResponse(job_id=job.job_id, status=job.status, mode=job.mode, created_at=job.created_at)


@app.get("/assessment-jobs/{job_id}", response_model=AssessmentJobStatusResponse)
def get_assessment_job(job_id: str, http_request: Request) -> AssessmentJobStatusResponse:
    context = _auth_context_from_request(http_request)
    job = get_assessment_job_store().load(job_id)
    return _job_status_response(job, context)


@app.post("/speech/extract", response_model=ApiEnvelope)
def speech_extract(request: SpeechExtractRequest, http_request: Request) -> ApiEnvelope:
    context, profile = _profile_from_request(http_request)
    require_feature(profile, "speech_audit", authenticated=context.authenticated)
    _require_bot_check(http_request, request.bot_token)
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
    # Bot protection is enforced on /speech/extract. Verification is the second
    # stage of the same signed-in, entitlement-limited workflow; requiring a
    # fresh Turnstile token here causes single-use token failures after a
    # successful extraction.
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
    checked_claims = _attach_saved_speech_assessments(checked_claims, source_url=source_url, mode=mode, owner_id=context.owner_id, profile=profile)
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
    _require_bot_check(http_request, request.bot_token)
    enforce_speech_claim_limit(profile, request.max_claims)
    source_url = (request.source_url or "").strip()
    transcript = _speech_transcript_from_request(request.transcript, source_url, request.try_youtube_captions)

    llm, search = _clients()
    if not llm.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "OPENAI_API_KEY is not configured"})
    if request.verification_mode == "deep" and not search.configured:
        raise HTTPException(status_code=503, detail={"code": "configuration_error", "message": "TAVILY_API_KEY is required for deep speech audit"})

    result = run_speech_audit(transcript, source_url, request.max_claims, llm, search, verification_mode=request.verification_mode)
    mode = "deep" if request.verification_mode == "deep" else "fast"
    result["claims_checked"] = _attach_saved_speech_assessments(
        list(result.get("claims_checked") or []),
        source_url=source_url,
        mode=mode,
        owner_id=context.owner_id,
        profile=profile,
    )
    result["claims_checked_count"] = len(result["claims_checked"])
    result["settings"] = {
        "result_mode": "speech_audit",
        "source_url": source_url,
        "max_claims": request.max_claims,
        "verification_mode": request.verification_mode,
        "build": get_app_build(),
    }
    return ApiEnvelope(ok=True, build=get_app_build(), result=result)
