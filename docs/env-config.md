# FortressStack — Environment Configuration

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

Configuration is **layered everywhere**: built-in defaults ← YAML files
(`config/fortress.yaml`, `config/litellm/config.yaml`, `backend/config/gateway.yaml`)
← environment variables. Secrets are **env-only** — never in YAML, never committed.
Template: [.env.example](../.env.example). Loaders: `admin-backend/app/core/config.py`
and `backend/app/config.py` (both implement `FORTRESS_SECTION__KEY` flat overrides,
bool/int coercion, pydantic validation at boot).

## 1. Compose `.env` (next to `docker-compose.yml`) — secrets

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | postgres | DB password (default `fortress` — change!) |
| `LITELLM_MASTER_KEY` | litellm, openwebui, admin-backend, backend | Gateway master key — `[REDACTED]` in docs |
| `WEBUI_SECRET_KEY` | openwebui | Session secret (default `change-me`) |
| `NEXTAUTH_SECRET` | langfuse | Auth secret (default `change-me`) |
| `LANGFUSE_SALT` | langfuse | Hashing salt (default `change-me`) |
| `LANGFUSE_ENCRYPTION_KEY` | langfuse | 32-byte encryption key (default `change-me`) |

## 2. Admin backend (`admin-backend`, :8000) — `FORTRESS_*` flat overrides

`FORTRESS_<SECTION>__<KEY>=value` maps onto the YAML tree (lowercased).

| Variable | Default (config/fortress.yaml) | Purpose |
|---|---|---|
| `FORTRESS_CONFIG_DIR` | `config` | Directory of layered YAML files |
| `FORTRESS_DATABASE_URL` | `postgresql://fortress:***@postgres:5432/fortress` | Postgres DSN (password `[REDACTED]`) |
| `FORTRESS_ENVIRONMENT` | `development` | `development\|staging\|production` |
| `FORTRESS_DEBUG` | `true` | Debug flag |
| `FORTRESS_LOCAL_MODE` | `true` | Refuse all external egress; forbids allowlist |
| `FORTRESS_GATEWAY__BASE_URL` | `http://litellm:4000` | LiteLLM gateway URL |
| `FORTRESS_GATEWAY__MASTER_KEY` | env-only secret | Gateway key (`[REDACTED]`) |
| `FORTRESS_GATEWAY__TIMEOUT_SECONDS` | `60` | Gateway call timeout |
| `FORTRESS_GATEWAY__MAX_RETRIES` | `2` | Retries |
| `FORTRESS_GATEWAY__FALLBACK_MODELS` | `[qwen2.5:7b]` | Fallback chain |
| `FORTRESS_RAG__CHUNK_SIZE` | `512` | Chunk size (chars) |
| `FORTRESS_RAG__CHUNK_OVERLAP` | `64` | Overlap |
| `FORTRESS_RAG__EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model/backend (`local` = numpy) |
| `FORTRESS_RAG__TOP_K` | `5` | Retrieval depth |
| `FORTRESS_RAG__SIMILARITY_THRESHOLD` | `0.55` | Cosine threshold |
| `FORTRESS_RAG__UPLOAD_DIR` | `/data/uploads` | Upload storage |
| `FORTRESS_RAG__MAX_FILE_MB` | `50` | Upload limit |
| `FORTRESS_TEAM__DEFAULT_BUDGET_USD` | `50.0` | New-team budget |
| `FORTRESS_TEAM__DEFAULT_RATE_LIMIT_RPM` | `60` | New-team rate limit |
| `FORTRESS_TEAM__DEFAULT_MODELS` | `[llama3.1:8b]` | New-team model allowlist |
| `FORTRESS_AUTH__JWT_SECRET` | `change-me-in-prod` | JWT secret (`[REDACTED]` in prod) |
| `FORTRESS_AUTH__JWT_EXPIRY_MINUTES` | `60` | Token lifetime |
| `FORTRESS_AUTH__SSO_ENABLED` | `true` | SSO/Better-Auth on/off |
| `FORTRESS_AUTH__TEAM_MAPPING` | `db` | `header\|db` |
| `FORTRESS_OBSERVABILITY__ENABLED` | `true` | Langfuse tracing |
| `FORTRESS_OBSERVABILITY__LANGFUSE_HOST` | `http://langfuse:3000` | Langfuse URL |
| `FORTRESS_OBSERVABILITY__PUBLIC_KEY` / `__SECRET_KEY` | empty | Langfuse keys (`[REDACTED]`) |
| `FORTRESS_BACKUP__ENABLED` | `true` | Backup policy on/off |
| `FORTRESS_BACKUP__SCHEDULE_CRON` | `0 2 * * *` | Nightly at 02:00 |
| `FORTRESS_BACKUP__DESTINATION` | `/backups` | Backup target |
| `FORTRESS_BACKUP__RETENTION_DAYS` | `30` | Retention |

## 3. FortressStack Gateway (`backend`, :4001)

| Variable | Default | Purpose |
|---|---|---|
| `FORTRESS_GATEWAY_CONFIG` | `config/gateway.yaml` | Path to gateway YAML (relative to `backend/`) |
| `FORTRESS_HOST` / `FORTRESS_PORT` | `0.0.0.0` / `4001` | Bind address |
| `FORTRESS_ENVIRONMENT` / `FORTRESS_DEBUG` | `development` / `true` | Env / debug |
| `FORTRESS_LOCAL_MODE` | `true` | Egress guard on/off (allowlist forbidden when true) |
| `FORTRESS_OLLAMA__BASE_URL` | `http://ollama:11434` | Upstream model server (must be local in local mode) |
| `FORTRESS_DEFAULT_MODEL` | `llama3.1:8b` | Default chat model |
| `FORTRESS_REQUIRE_AUTH` | `false` | Require `Authorization: Bearer <master key>` on `/v1/*` |
| `FORTRESS_TIMEOUT_SECONDS` / `FORTRESS_MAX_RETRIES` | `60` / `2` | Upstream HTTP tuning |
| `FORTRESS_ALLOWED_ORIGINS` | `*` | CORS origins (tighten in prod) |
| `LITELLM_MASTER_KEY` or `FORTRESS_GATEWAY_MASTER_KEY` | empty | Master key — **env-only, never YAML** (`[REDACTED]`) |

## 4. LiteLLM gateway container

Reads `config/litellm/config.yaml` (mounted read-only) plus `LITELLM_MASTER_KEY` and
`DATABASE_URL` from env (`os.environ/...` references in the YAML).

## Examples

```bash
# local admin backend against a compose'd postgres
export FORTRESS_DATABASE_URL='postgresql://fortress:[REDACTED]@localhost:5432/fortress'
export FORTRESS_ENVIRONMENT=development
uvicorn app.main:app --reload --port 8000     # from admin-backend/

# gateway with auth on, local-only
export FORTRESS_LOCAL_MODE=true FORTRESS_REQUIRE_AUTH=true
export LITELLM_MASTER_KEY='[REDACTED]'
uvicorn app.main:app --port 4001               # from backend/
```

## Secrets policy

Never commit `.env` (gitignored; only `.env.example` is tracked). In production put
secrets in the platform secret store (Coolify env, Docker secrets, vault) and keep
`local_mode=true` unless you deliberately disable it.
