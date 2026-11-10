-- Phase 4: generated Agile backlog, traceable to a Phase 3 analysis run.
CREATE TABLE IF NOT EXISTS backlog_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  result JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_backlog_runs_project_created
  ON backlog_runs(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS epics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  backlog_run_id UUID NOT NULL REFERENCES backlog_runs(id) ON DELETE CASCADE,
  epic_key VARCHAR(40) NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  business_value TEXT NOT NULL DEFAULT '',
  source_requirement_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  UNIQUE(backlog_run_id, epic_key)
);

CREATE TABLE IF NOT EXISTS user_stories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  backlog_run_id UUID NOT NULL REFERENCES backlog_runs(id) ON DELETE CASCADE,
  epic_id UUID NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
  story_key VARCHAR(40) NOT NULL,
  title VARCHAR(255) NOT NULL,
  story_text TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_requirement_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  priority_recommendation VARCHAR(20) NOT NULL DEFAULT 'should',
  priority_rationale TEXT NOT NULL DEFAULT '',
  story_points INTEGER,
  estimate_rationale TEXT NOT NULL DEFAULT '',
  approval_status VARCHAR(30) NOT NULL DEFAULT 'pending',
  assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
  UNIQUE(backlog_run_id, story_key)
);
CREATE INDEX IF NOT EXISTS idx_user_stories_backlog ON user_stories(backlog_run_id);

CREATE TABLE IF NOT EXISTS acceptance_criteria (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
  criterion_key VARCHAR(50) NOT NULL,
  criterion_text TEXT NOT NULL,
  test_type VARCHAR(30) NOT NULL DEFAULT 'functional'
);

CREATE TABLE IF NOT EXISTS story_dependencies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  backlog_run_id UUID NOT NULL REFERENCES backlog_runs(id) ON DELETE CASCADE,
  story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
  depends_on_story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
  dependency_type VARCHAR(30) NOT NULL DEFAULT 'relates_to',
  rationale TEXT NOT NULL DEFAULT '',
  CHECK (story_id <> depends_on_story_id),
  UNIQUE(backlog_run_id, story_id, depends_on_story_id)
);
