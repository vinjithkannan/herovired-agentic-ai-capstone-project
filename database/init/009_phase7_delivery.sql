-- Phase 7 scope completion. Explicit, immutable approval decisions for design and plan.
-- Apply to existing DB explicitly; init scripts do not rerun on existing volumes.
CREATE TABLE IF NOT EXISTS delivery_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    backlog_run_id UUID NOT NULL REFERENCES backlog_runs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('design','plan')),
    artifact JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','rejected')),
    decided_by UUID REFERENCES app_users(id),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(backlog_run_id,kind)
);
CREATE INDEX IF NOT EXISTS idx_delivery_artifacts_project ON delivery_artifacts(project_id,backlog_run_id);
