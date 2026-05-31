export type AssessmentSource = {
  id: string;
  title: string;
  url: string;
  domain: string;
  source_type: string;
  stance: string;
  evidence_category: string;
  source_role: string;
  narrative_cluster?: string;
  score: number;
  scoring_factors?: Record<string, number>;
  summary: string;
  classification_reason: string;
};

export type AssessmentResponse = {
  schema_version: string;
  assessment_id: string;
  created_at: string;
  build: string;
  mode: string;
  request: {
    claim: string;
    source_url?: string | null;
    category: string;
    settings: Record<string, unknown>;
  };
  verdict: {
    label: string;
    confidence: string;
    summary: string;
    key_caveat: string;
    evidence_strength_score?: number | null;
  };
  claim_breakdown: Array<{
    id: string;
    text: string;
    dimension: string;
    assessment: string;
    confidence: string;
    rationale: string;
    supporting_source_ids: string[];
    contradicting_source_ids: string[];
  }>;
  evidence_map: Record<string, string[]>;
  sources: AssessmentSource[];
  reasoning: Record<string, unknown>;
  owner_id?: string | null;
};

export type ReportSummary = {
  assessment_id: string;
  created_at: string;
  mode: string;
  claim: string;
  verdict: string;
  owner_id?: string | null;
  protected?: boolean;
  labels?: string[];
  deleted_at?: string;
};

export type ReportShare = {
  token: string;
  assessment_id: string;
  owner_id?: string | null;
  access_level?: 'simple' | 'full';
  created_at?: string;
  revoked_at?: string;
};

export type PublicReportResponse = {
  ok: boolean;
  access_level: 'simple' | 'full';
  share: ReportShare;
  assessment: AssessmentResponse;
};

export type TierName = 'free' | 'pro' | 'researcher';

export type AccountProfile = {
  owner_id: string;
  label: string;
  plan: 'Free' | 'Pro' | 'Researcher / Journalist' | 'Loading plan…';
};

export type TierDefinition = {
  tier: TierName;
  label: string;
  description: string;
  features: Record<string, boolean>;
  limits: Record<string, number>;
};

export type UserProfile = {
  owner_id: string;
  email: string;
  tier: TierName;
  tier_label: 'Free' | 'Pro' | 'Researcher / Journalist';
  subscription_status: string;
  trial_started_at?: string;
  trial_ends_at?: string;
  payment_provider_customer_id?: string;
  company_name?: string;
  organisation_name?: string;
  billing_account_name?: string;
  billing_account_id?: string;
  admin_notes?: string;
  admin_access?: boolean;
  admin_access_source?: 'master_admin_email' | 'none' | string;
  features: Record<string, boolean>;
  limits: Record<string, number>;
};

export type MeResponse = {
  ok: boolean;
  authenticated: boolean;
  is_admin?: boolean;
  user: UserProfile;
  feature_matrix: { schema_version: string; tiers: TierDefinition[] };
};

export type AuthDiagnosticsResponse = {
  ok: boolean;
  has_bearer: boolean;
  verified?: boolean;
  diagnostics?: Record<string, unknown>;
  claims?: Record<string, unknown>;
  error_type?: string;
  error?: string;
};

export type RuntimeStatus = {
  ok: boolean;
  api_version: string;
  build: string;
  openai_configured: boolean;
  tavily_configured: boolean;
  storage_backend: string;
  auth_configured?: boolean;
  admin_configured?: boolean;
};

export type FeedbackRating = 'Useful' | 'Partly useful' | 'Not useful';

export type TrustAnalyticsResponse = {
  ok: boolean;
  backend: string;
  summary?: {
    claim_checks?: number;
    evidence_sources?: number;
    trust_signals?: number;
    counter_evidence?: number;
    disputed_claims?: number;
  };
  recent_claim_checks?: Array<{ assessment_id: string; claim?: string; verdict?: string; confidence?: string; created_at?: string }>;
  verdict_distribution?: Array<{ value?: string; verdict?: string; count: number }>;
  top_source_domains?: Array<{ value?: string; domain?: string; count: number }>;
  top_signals: Array<{ signal_type?: string; value?: string; count: number }>;
  most_disputed_claims: Array<{ claim?: string; value?: string; count: number }>;
  source_reliability_observations?: Array<{ domain?: string; source_url?: string; reliability_delta?: number; observations?: number }>;
};

export type FeedbackResponse = {
  ok: boolean;
  feedback_id: string;
  assessment_id: string;
  destination: string;
  message: string;
};

export type SupportIssue = {
  feedback_id?: string;
  issue_id?: string;
  captured_at?: string;
  owner_id?: string;
  comment?: string;
  reasons?: string[];
  source_url?: string;
  assessment_id?: string;
  assessment_output?: { support_issue?: { issue_type?: string; severity?: string; subject?: string; description?: string; page_url?: string; browser_context?: Record<string, unknown> } };
};

export type SupportIssueResponse = {
  ok: boolean;
  issue_id: string;
  destination: string;
  message: string;
};

export type AssessmentJobCreateResponse = {
  ok: boolean;
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  mode: 'fast' | 'deep';
  created_at: string;
};

export type AssessmentJobStatusResponse = {
  ok: boolean;
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  mode: 'fast' | 'deep';
  created_at: string;
  updated_at: string;
  completed_at?: string;
  assessment_id?: string;
  assessment?: AssessmentResponse | null;
  error?: string;
};

export type SpeechClaim = {
  id: string;
  quote: string;
  normalized_claim: string;
  timestamp?: string;
  speaker?: string;
  topic?: string;
  claim_type?: string;
  checkability?: string;
  priority?: string;
  why_it_matters?: string;
  verification_query?: string;
};

export type SpeechExtractionResult = {
  schema_version: string;
  title: string;
  speaker: string;
  source_url: string;
  summary: string;
  claims: SpeechClaim[];
  skipped_rhetoric: string[];
  extraction_notes: string[];
  transcript_truncated: boolean;
  transcript_chars_used: number;
  transcript_chars_original: number;
};

export type SpeechCheckedClaim = {
  speech_claim?: SpeechClaim;
  audit_index?: number;
  assessment_id?: string;
  assessment?: AssessmentResponse;
  verdict?: string;
  verified_verdict?: string;
  confidence?: string;
  verified_confidence?: string;
  tldr?: string;
  summary?: string;
  pendulum_band?: string;
  sources?: AssessmentSource[];
};

export type SpeechVerificationResult = {
  schema_version: string;
  source_url: string;
  claims_checked: SpeechCheckedClaim[];
  claims_checked_count: number;
  verification_mode: 'fast' | 'deep';
};

export type SpeechAuditResult = SpeechExtractionResult & SpeechVerificationResult & {
  claims_extracted: SpeechClaim[];
  claims_needing_attention_count: number;
};

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'https://evidrai.onrender.com').replace(/\/$/, '');

const ACCOUNT_KEY = 'evidrai_account_profile';
const ANONYMOUS_ACCOUNT_KEY = 'evidrai_anonymous_account_profile';
let accessToken = '';


function userFacingError(message: string, code = ''): string {
  const lower = message.toLowerCase();
  const cleanCode = code.toLowerCase();
  if (cleanCode === 'youtube_bot_check' || lower.includes('youtube blocked automatic transcript access')) {
    return 'YouTube blocked automatic transcript access for this video. Paste the transcript into the Transcript box and run the speech/video audit again.';
  }
  if (lower === 'load failed' || lower.includes('failed to fetch') || lower.includes('networkerror')) {
    return 'The request could not reach the Evidrai API. This is usually a network/CORS or deployment configuration issue, not your browser. Please try again after the latest deploy.';
  }
  return message;
}

function randomId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `anon_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

export function setAccessToken(token: string) {
  accessToken = token;
}

export function setAccountProfile(profile: AccountProfile) {
  if (typeof window !== 'undefined') window.localStorage.setItem(ACCOUNT_KEY, JSON.stringify(profile));
}

export function getAnonymousAccountProfile(): AccountProfile {
  if (typeof window === 'undefined') return { owner_id: 'server', label: 'Anonymous browser', plan: 'Free' };
  const saved = window.localStorage.getItem(ANONYMOUS_ACCOUNT_KEY);
  if (saved) return JSON.parse(saved) as AccountProfile;
  const profile: AccountProfile = { owner_id: `anon_${randomId()}`, label: 'Anonymous browser', plan: 'Free' };
  window.localStorage.setItem(ANONYMOUS_ACCOUNT_KEY, JSON.stringify(profile));
  return profile;
}

export function getAccountProfile(): AccountProfile {
  if (typeof window === 'undefined') return { owner_id: 'server', label: 'Anonymous browser', plan: 'Free' };
  const saved = window.localStorage.getItem(ACCOUNT_KEY);
  if (saved) return JSON.parse(saved) as AccountProfile;
  const profile = getAnonymousAccountProfile();
  window.localStorage.setItem(ACCOUNT_KEY, JSON.stringify(profile));
  return profile;
}

async function request<T>(path: string, init?: RequestInit, options?: { sameOrigin?: boolean }): Promise<T> {
  const account = getAccountProfile();
  let response: Response;
  try {
    response = await fetch(`${options?.sameOrigin ? '' : API_BASE_URL}${path}`, {
      ...init,
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        'X-Evidrai-User-Id': account.owner_id,
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...(init?.headers || {}),
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Load failed';
    throw new Error(userFacingError(message));
  }

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    let errorCode = '';
    try {
      const payload = await response.json();
      const detail = payload?.detail;
      const upstreamDetail = typeof detail === 'object' && detail?.upstream_detail ? detail.upstream_detail : null;
      const upstreamNested = typeof upstreamDetail === 'object' && upstreamDetail?.detail ? upstreamDetail.detail : null;
      const upstreamMessage = typeof upstreamNested === 'string' ? upstreamNested : (typeof upstreamNested === 'object' ? upstreamNested?.message : '');
      const upstreamCode = typeof upstreamNested === 'object' ? upstreamNested?.code : '';
      const detailCode = typeof detail === 'object' ? detail?.code : '';
      const fallback = typeof detail === 'object' && detail?.fallback ? ` ${detail.fallback}` : '';
      const baseMessage = upstreamMessage || detail?.message || payload?.error || message;
      const diagnosticCode = upstreamCode || detailCode;
      errorCode = String(diagnosticCode || '');
      const diagnostic = diagnosticCode ? ` (${diagnosticCode})` : '';
      message = typeof detail === 'string' ? detail : `${baseMessage}${diagnostic}${fallback}`;
    } catch {
      // Keep HTTP status fallback.
    }
    throw new Error(userFacingError(typeof message === 'string' ? message : JSON.stringify(message), errorCode));
  }

  return response.json() as Promise<T>;
}

export function getRuntime(): Promise<RuntimeStatus> {
  return request<RuntimeStatus>('/runtime');
}

export function getMe(): Promise<MeResponse> {
  return request<MeResponse>('/me');
}

export function getAuthDiagnostics(): Promise<AuthDiagnosticsResponse> {
  return request<AuthDiagnosticsResponse>('/auth/diagnostics');
}

export function getTiers(): Promise<{ ok: boolean; schema_version: string; tiers: TierDefinition[] }> {
  return request<{ ok: boolean; schema_version: string; tiers: TierDefinition[] }>('/tiers');
}

export function createAssessment(input: { claim: string; source_url?: string; category: string; mode: 'fast' | 'deep'; output_style?: 'standard' | 'absurdity_humour'; bot_token?: string }): Promise<AssessmentResponse> {
  const path = input.mode === 'deep' ? '/assessments/deep' : '/assessments/fast';
  return request<AssessmentResponse>(path, {
    method: 'POST',
    body: JSON.stringify({
      claim: input.claim,
      source_url: input.source_url || '',
      category: input.category,
      output_style: input.output_style || 'standard',
      bot_token: input.bot_token || '',
    }),
  });
}

export function createAssessmentJob(input: { claim: string; source_url?: string; category: string; mode: 'fast' | 'deep'; output_style?: 'standard' | 'absurdity_humour'; bot_token?: string }): Promise<AssessmentJobCreateResponse> {
  return request<AssessmentJobCreateResponse>(`/assessment-jobs/${input.mode}`, {
    method: 'POST',
    body: JSON.stringify({
      claim: input.claim,
      source_url: input.source_url || '',
      category: input.category,
      output_style: input.output_style || 'standard',
      bot_token: input.bot_token || '',
    }),
  });
}

export function getAssessmentJob(jobId: string): Promise<AssessmentJobStatusResponse> {
  return request<AssessmentJobStatusResponse>(`/assessment-jobs/${encodeURIComponent(jobId)}`);
}

export async function listReports(): Promise<ReportSummary[]> {
  const payload = await request<{ ok: boolean; reports: ReportSummary[]; report_limit?: number }>('/reports');
  return payload.reports || [];
}

export function getReport(id: string): Promise<AssessmentResponse> {
  return request<AssessmentResponse>(`/reports/${encodeURIComponent(id)}`);
}

export function updateReportMetadata(id: string, input: { protected?: boolean; labels?: string[] }): Promise<{ ok: boolean; report: ReportSummary }> {
  return request<{ ok: boolean; report: ReportSummary }>(`/reports/${encodeURIComponent(id)}/metadata`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
}

export function deleteReport(id: string): Promise<{ ok: boolean; report: ReportSummary & { deleted?: boolean } }> {
  return request<{ ok: boolean; report: ReportSummary & { deleted?: boolean } }>(`/reports/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function createReportShare(id: string, platform = 'copy'): Promise<{ ok: boolean; token: string; assessment_id: string; access_level: 'simple' | 'full'; share: ReportShare }> {
  return request<{ ok: boolean; token: string; assessment_id: string; access_level: 'simple' | 'full'; share: ReportShare }>(`/api/reports/${encodeURIComponent(id)}/share`, {
    method: 'POST',
    body: JSON.stringify({ platform }),
  }, { sameOrigin: true });
}

export async function getPublicSharedReport(token: string): Promise<PublicReportResponse> {
  const response = await fetch(`${API_BASE_URL}/public/reports/${encodeURIComponent(token)}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<PublicReportResponse>;
}

export function listAdminUsers(): Promise<{ ok: boolean; users: UserProfile[]; feature_matrix: { schema_version: string; tiers: TierDefinition[] } }> {
  return request<{ ok: boolean; users: UserProfile[]; feature_matrix: { schema_version: string; tiers: TierDefinition[] } }>('/admin/users');
}

export function setAdminUserTier(input: { owner_id: string; tier: TierName; email?: string }): Promise<{ ok: boolean; user: UserProfile }> {
  return request<{ ok: boolean; user: UserProfile }>('/admin/users/tier', {
    method: 'PATCH',
    body: JSON.stringify({ owner_id: input.owner_id, tier: input.tier, email: input.email || '' }),
  });
}

export function inviteAdminUser(input: { email: string; tier: TierName; send_invite: boolean; redirect_to?: string }): Promise<{ ok: boolean; sent_invite: boolean; owner_id: string; email: string; user: UserProfile | null; message: string }> {
  return request<{ ok: boolean; sent_invite: boolean; owner_id: string; email: string; user: UserProfile | null; message: string }>('/admin/users/invite', {
    method: 'POST',
    body: JSON.stringify({ email: input.email, tier: input.tier, send_invite: input.send_invite, redirect_to: input.redirect_to || '' }),
  });
}

export function deleteAdminUser(owner_id: string): Promise<{ ok: boolean; owner_id: string; deleted: boolean; auth_deleted: boolean; profile_deleted: boolean; message: string }> {
  return request<{ ok: boolean; owner_id: string; deleted: boolean; auth_deleted: boolean; profile_deleted: boolean; message: string }>(`/admin/users/${encodeURIComponent(owner_id)}`, {
    method: 'DELETE',
  });
}

export function updateAdminUserProfile(input: { owner_id: string; email?: string; company_name?: string; organisation_name?: string; billing_account_name?: string; billing_account_id?: string; admin_notes?: string }): Promise<{ ok: boolean; user: UserProfile }> {
  return request<{ ok: boolean; user: UserProfile }>('/admin/users/profile', {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
}

export function bulkAdminUsers(input: { owner_ids: string[]; action: 'set_tier' | 'delete_profiles'; tier?: TierName }): Promise<{ ok: boolean; action: string; users?: UserProfile[]; deleted?: Array<{ owner_id: string; deleted: boolean }> }> {
  return request<{ ok: boolean; action: string; users?: UserProfile[]; deleted?: Array<{ owner_id: string; deleted: boolean }> }>('/admin/users/bulk', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function sendAdminPasswordReset(input: { owner_id: string; email: string; redirect_to?: string }): Promise<{ ok: boolean; owner_id: string; email: string; message: string }> {
  return request<{ ok: boolean; owner_id: string; email: string; message: string }>('/admin/users/password-reset', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function updateAdminUserPassword(input: { owner_id: string; email?: string; password: string }): Promise<{ ok: boolean; owner_id: string; message: string }> {
  return request<{ ok: boolean; owner_id: string; message: string }>('/admin/users/password', {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
}

export function resendAdminInvite(input: { owner_id: string; email: string; redirect_to?: string }): Promise<{ ok: boolean; owner_id: string; email: string; message: string }> {
  return request<{ ok: boolean; owner_id: string; email: string; message: string }>('/admin/users/resend-invite', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export type TrustBackfillResponse = {
  ok: boolean;
  reports_seen: number;
  captured: number;
  failed: number;
  failures: Array<{ assessment_id: string; error: string }>;
  analytics?: TrustAnalyticsResponse;
};

export function getTrustAnalytics(limit = 20): Promise<TrustAnalyticsResponse> {
  return request<TrustAnalyticsResponse>(`/admin/trust/analytics?limit=${encodeURIComponent(String(limit))}`);
}

export function backfillTrustAnalytics(limit = 1000): Promise<TrustBackfillResponse> {
  return request<TrustBackfillResponse>(`/admin/trust/backfill?limit=${encodeURIComponent(String(limit))}`, { method: 'POST' });
}

export function submitSupportIssue(input: {
  issue_type: 'bug' | 'support' | 'idea' | 'other';
  severity: 'low' | 'normal' | 'high' | 'urgent';
  subject: string;
  description: string;
  page_url?: string;
  assessment_id?: string;
  browser_context?: Record<string, unknown>;
}): Promise<SupportIssueResponse> {
  return request<SupportIssueResponse>('/support/issues', {
    method: 'POST',
    body: JSON.stringify({
      issue_type: input.issue_type,
      severity: input.severity,
      subject: input.subject,
      description: input.description,
      page_url: input.page_url || '',
      assessment_id: input.assessment_id || '',
      browser_context: input.browser_context || {},
    }),
  });
}

export function listSupportIssues(limit = 25): Promise<{ ok: boolean; issues: SupportIssue[]; count: number }> {
  return request<{ ok: boolean; issues: SupportIssue[]; count: number }>(`/admin/support/issues?limit=${encodeURIComponent(String(limit))}`);
}

export function submitFeedback(input: {
  assessment_id: string;
  rating: FeedbackRating;
  reasons: string[];
  trust_signals?: string[];
  accepted_verdict?: 'accepted' | 'rejected' | 'unsure' | '';
  challenge_text?: string;
  counter_evidence?: Array<Record<string, string>>;
  persuasive_source_ids?: string[];
  distrusted_source_ids?: string[];
  comment: string;
}): Promise<FeedbackResponse> {
  return request<FeedbackResponse>(`/assessments/${encodeURIComponent(input.assessment_id)}/feedback`, {
    method: 'POST',
    body: JSON.stringify({
      rating: input.rating,
      reasons: input.reasons,
      trust_signals: input.trust_signals || [],
      accepted_verdict: input.accepted_verdict || '',
      challenge_text: input.challenge_text || '',
      counter_evidence: input.counter_evidence || [],
      persuasive_source_ids: input.persuasive_source_ids || [],
      distrusted_source_ids: input.distrusted_source_ids || [],
      comment: input.comment,
    }),
  });
}

export async function extractSpeechClaims(input: {
  transcript: string;
  source_url?: string;
  max_claims: number;
  try_youtube_captions?: boolean;
  bot_token?: string;
}): Promise<SpeechExtractionResult> {
  const payload = await request<{ ok: boolean; result: SpeechExtractionResult }>('/speech/extract', {
    method: 'POST',
    body: JSON.stringify({
      transcript: input.transcript,
      source_url: input.source_url || '',
      max_claims: input.max_claims,
      try_youtube_captions: input.try_youtube_captions ?? true,
      bot_token: input.bot_token || '',
    }),
  });
  return payload.result;
}

export async function verifySpeechClaims(input: {
  claims: SpeechClaim[];
  source_url?: string;
  verification_mode: 'fast' | 'deep';
  bot_token?: string;
}): Promise<SpeechVerificationResult> {
  const payload = await request<{ ok: boolean; result: SpeechVerificationResult }>('/speech/verify', {
    method: 'POST',
    body: JSON.stringify({
      claims: input.claims,
      source_url: input.source_url || '',
      verification_mode: input.verification_mode,
      bot_token: input.bot_token || '',
    }),
  });
  return payload.result;
}

export async function runSpeechAudit(input: {
  transcript: string;
  source_url?: string;
  max_claims: number;
  verification_mode: 'fast' | 'deep';
  try_youtube_captions?: boolean;
}): Promise<SpeechAuditResult> {
  const payload = await request<{ ok: boolean; result: SpeechAuditResult }>('/speech/audit', {
    method: 'POST',
    body: JSON.stringify({
      transcript: input.transcript,
      source_url: input.source_url || '',
      max_claims: input.max_claims,
      verification_mode: input.verification_mode,
      try_youtube_captions: input.try_youtube_captions ?? true,
    }),
  });
  return payload.result;
}
