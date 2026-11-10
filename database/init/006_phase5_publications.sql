-- Phase 5: apply explicitly to existing databases; init SQL does not rerun on old volumes.
CREATE TABLE IF NOT EXISTS external_publications (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 backlog_run_id UUID NOT NULL REFERENCES backlog_runs(id) ON DELETE CASCADE,
 story_key VARCHAR(40) NOT NULL,
 provider VARCHAR(20) NOT NULL CHECK (provider IN ('github','jira')),
 target VARCHAR(250) NOT NULL,
 state VARCHAR(20) NOT NULL DEFAULT 'reserved' CHECK (state IN ('reserved','published','uncertain','failed')),
 external_id TEXT,
 external_url TEXT,
 error_note TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE (provider, target, backlog_run_id, story_key)
);
CREATE INDEX IF NOT EXISTS idx_publications_backlog ON external_publications(backlog_run_id, created_at DESC);
