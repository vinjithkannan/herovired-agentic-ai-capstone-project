-- Apply ONCE to existing database with psql -v ON_ERROR_STOP=1 -f; never use docker compose down -v.
CREATE TABLE IF NOT EXISTS app_users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('admin','product_owner','engineer','viewer')),
 active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS auth_sessions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 token_hash CHAR(64) NOT NULL UNIQUE, expires_at TIMESTAMPTZ NOT NULL,
 revoked_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id, expires_at);
CREATE TABLE IF NOT EXISTS security_audit (
 id BIGSERIAL PRIMARY KEY, actor_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
 event TEXT NOT NULL, object_type TEXT, object_id TEXT, detail JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_security_audit_created ON security_audit(created_at DESC);
CREATE TABLE IF NOT EXISTS evaluation_runs (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 backlog_run_id UUID NOT NULL REFERENCES backlog_runs(id) ON DELETE CASCADE,
 evaluator_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
 metrics JSONB NOT NULL, golden JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_backlog ON evaluation_runs(backlog_run_id, created_at DESC);
CREATE TABLE IF NOT EXISTS publication_recovery_audit (
 id BIGSERIAL PRIMARY KEY, publication_id UUID NOT NULL,
 actor_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
 action TEXT NOT NULL, evidence JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
