-- Phase 6.1. Apply once with psql -1 -v ON_ERROR_STOP=1. Existing backlogs remain unchanged.
CREATE TABLE IF NOT EXISTS backlog_clarifications (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 project_id UUID NOT NULL REFERENCES projects(id),
 source_backlog_id UUID NOT NULL REFERENCES backlog_runs(id),
 story_key TEXT NOT NULL,
 proposal JSONB NOT NULL,
 rationale TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','rejected','superseded')),
 proposed_by UUID NOT NULL REFERENCES app_users(id),
 decided_by UUID REFERENCES app_users(id),
 decided_at TIMESTAMPTZ,
 decision_note TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_phase61_clarifications ON backlog_clarifications(source_backlog_id,story_key,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_phase61_one_active ON backlog_clarifications(source_backlog_id, story_key) WHERE status IN ('proposed','approved');
CREATE TABLE IF NOT EXISTS backlog_finalizations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 source_backlog_id UUID NOT NULL REFERENCES backlog_runs(id),
 new_backlog_id UUID NOT NULL UNIQUE REFERENCES backlog_runs(id),
 actor_id UUID NOT NULL REFERENCES app_users(id),
 clarification_ids JSONB NOT NULL,
 quality_summary JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(source_backlog_id)
);
