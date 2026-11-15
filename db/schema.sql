-- FortressStack — PostgreSQL schema
-- Governing tables for the private AI workspace: teams, budgets, models,
-- RAG corpora/documents, audit log, and settings.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- Teams & budgets
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teams (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,
    description   TEXT DEFAULT '',
    budget_usd    NUMERIC(12,2) NOT NULL DEFAULT 50.00,
    rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
    models        JSONB NOT NULL DEFAULT '[]',          -- allowed model list
    api_key_hash  TEXT,                                  -- per-team key (hashed)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage (
    id            BIGSERIAL PRIMARY KEY,
    team_id       UUID REFERENCES teams(id) ON DELETE CASCADE,
    model         TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0,
    request_id    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_team_time ON usage (team_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Model catalogue
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS models (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,                -- e.g. llama3.1:8b
    provider      TEXT NOT NULL DEFAULT 'ollama',
    context_window INTEGER NOT NULL DEFAULT 8192,
    max_tokens    INTEGER NOT NULL DEFAULT 4096,
    cpu_only      BOOLEAN NOT NULL DEFAULT TRUE,
    resource_limit_mb INTEGER NOT NULL DEFAULT 4096,
    enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- RAG: corpora + documents + chunks
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS corpora (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id       UUID REFERENCES teams(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    description   TEXT DEFAULT '',
    embedding_model TEXT NOT NULL DEFAULT 'nomic-embed-text',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (team_id, name)
);

CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    corpus_id     UUID REFERENCES corpora(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    mime_type     TEXT NOT NULL,
    size_bytes    BIGINT NOT NULL DEFAULT 0,
    storage_path  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',     -- pending|processing|ready|failed
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID REFERENCES documents(id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    content       TEXT NOT NULL,
    embedding     VECTOR(768),                          -- pgvector; created at runtime
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, seq)
);

-- ---------------------------------------------------------------------------
-- Audit log (immutable, append-only)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    actor         TEXT NOT NULL,                        -- user / system / team
    action        TEXT NOT NULL,                        -- e.g. budget.blocked
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    detail        JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);

-- ---------------------------------------------------------------------------
-- Settings (key/value, versioned) — the "highly configurable" admin surface
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS settings (
    key           TEXT PRIMARY KEY,
    value         JSONB NOT NULL,
    description   TEXT DEFAULT '',
    updated_by    TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;