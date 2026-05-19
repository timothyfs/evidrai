CREATE TABLE IF NOT EXISTS trust_claim_checks (
    assessment_id TEXT PRIMARY KEY REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ,
    actor_hash TEXT,
    claim TEXT,
    source_url TEXT,
    category TEXT,
    mode TEXT,
    verdict TEXT,
    confidence TEXT,
    evidence_strength_score DOUBLE PRECISION,
    topic TEXT,
    sensitivity_tags TEXT[] NOT NULL DEFAULT '{}',
    narrative_clusters TEXT[] NOT NULL DEFAULT '{}',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trust_claim_checks_actor_hash ON trust_claim_checks(actor_hash);
CREATE INDEX IF NOT EXISTS idx_trust_claim_checks_verdict ON trust_claim_checks(verdict);
CREATE INDEX IF NOT EXISTS idx_trust_claim_checks_created_at ON trust_claim_checks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trust_claim_checks_narrative_clusters ON trust_claim_checks USING gin(narrative_clusters);

CREATE TABLE IF NOT EXISTS trust_evidence_sources (
    id BIGSERIAL PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    source_id TEXT,
    url TEXT,
    domain TEXT,
    title TEXT,
    source_type TEXT,
    stance TEXT,
    evidence_category TEXT,
    source_role TEXT,
    narrative_cluster TEXT,
    source_score DOUBLE PRECISION,
    scoring_factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trust_evidence_sources_assessment ON trust_evidence_sources(assessment_id);
CREATE INDEX IF NOT EXISTS idx_trust_evidence_sources_domain ON trust_evidence_sources(domain);
CREATE INDEX IF NOT EXISTS idx_trust_evidence_sources_stance ON trust_evidence_sources(stance);
CREATE INDEX IF NOT EXISTS idx_trust_evidence_sources_narrative_cluster ON trust_evidence_sources(narrative_cluster);

CREATE TABLE IF NOT EXISTS trust_signal_events (
    event_id TEXT PRIMARY KEY,
    assessment_id TEXT REFERENCES assessments(assessment_id) ON DELETE SET NULL,
    feedback_id TEXT,
    actor_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    signal_type TEXT NOT NULL,
    sentiment TEXT,
    target_type TEXT,
    target_id TEXT,
    source_id TEXT,
    claim_pattern TEXT,
    narrative_cluster TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_trust_signal_events_assessment ON trust_signal_events(assessment_id);
CREATE INDEX IF NOT EXISTS idx_trust_signal_events_signal_type ON trust_signal_events(signal_type);
CREATE INDEX IF NOT EXISTS idx_trust_signal_events_source_id ON trust_signal_events(source_id);
CREATE INDEX IF NOT EXISTS idx_trust_signal_events_created_at ON trust_signal_events(created_at DESC);

CREATE TABLE IF NOT EXISTS trust_counter_evidence (
    counter_evidence_id TEXT PRIMARY KEY,
    assessment_id TEXT REFERENCES assessments(assessment_id) ON DELETE SET NULL,
    feedback_id TEXT,
    actor_hash TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    url TEXT,
    text_excerpt TEXT,
    relationship TEXT NOT NULL DEFAULT 'counter_evidence',
    status TEXT NOT NULL DEFAULT 'submitted',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_trust_counter_evidence_assessment ON trust_counter_evidence(assessment_id);
CREATE INDEX IF NOT EXISTS idx_trust_counter_evidence_status ON trust_counter_evidence(status);

CREATE TABLE IF NOT EXISTS source_reliability_observations (
    observation_id TEXT PRIMARY KEY,
    domain TEXT,
    source_url TEXT,
    source_id TEXT,
    assessment_id TEXT REFERENCES assessments(assessment_id) ON DELETE SET NULL,
    feedback_id TEXT,
    actor_hash TEXT,
    signal_type TEXT NOT NULL,
    reliability_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_source_reliability_domain ON source_reliability_observations(domain);
CREATE INDEX IF NOT EXISTS idx_source_reliability_signal ON source_reliability_observations(signal_type);
