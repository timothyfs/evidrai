export type AssessmentSource = {
  id: string;
  title: string;
  url: string;
  domain: string;
  source_type: string;
  stance: string;
  evidence_category: string;
  source_role: string;
  score: number;
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
};

export type ReportSummary = {
  assessment_id: string;
  created_at: string;
  mode: string;
  claim: string;
  verdict: string;
};

export type RuntimeStatus = {
  ok: boolean;
  api_version: string;
  build: string;
  openai_configured: boolean;
  tavily_configured: boolean;
  storage_backend: string;
};

export type FeedbackRating = 'Useful' | 'Partly useful' | 'Not useful';

export type FeedbackResponse = {
  ok: boolean;
  feedback_id: string;
  assessment_id: string;
  destination: string;
  message: string;
};

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'https://evidrai.onrender.com').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message || payload?.detail || payload?.error || message;
    } catch {
      // Keep HTTP status fallback.
    }
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }

  return response.json() as Promise<T>;
}

export function getRuntime(): Promise<RuntimeStatus> {
  return request<RuntimeStatus>('/runtime');
}

export function createAssessment(input: { claim: string; source_url?: string; category: string; mode: 'fast' | 'deep' }): Promise<AssessmentResponse> {
  const path = input.mode === 'deep' ? '/assessments/deep' : '/assessments/fast';
  return request<AssessmentResponse>(path, {
    method: 'POST',
    body: JSON.stringify({
      claim: input.claim,
      source_url: input.source_url || '',
      category: input.category,
    }),
  });
}

export async function listReports(): Promise<ReportSummary[]> {
  const payload = await request<{ ok: boolean; reports: ReportSummary[] }>('/reports');
  return payload.reports || [];
}

export function getReport(id: string): Promise<AssessmentResponse> {
  return request<AssessmentResponse>(`/reports/${encodeURIComponent(id)}`);
}

export function submitFeedback(input: {
  assessment_id: string;
  rating: FeedbackRating;
  reasons: string[];
  comment: string;
}): Promise<FeedbackResponse> {
  return request<FeedbackResponse>(`/assessments/${encodeURIComponent(input.assessment_id)}/feedback`, {
    method: 'POST',
    body: JSON.stringify({
      rating: input.rating,
      reasons: input.reasons,
      comment: input.comment,
    }),
  });
}
