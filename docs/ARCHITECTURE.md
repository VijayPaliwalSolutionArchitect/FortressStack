# Architecture

FortressStack is a **single-node, self-hosted AI workspace** built as a composition of
independent services wired through Docker Compose. Everything runs on the host's own
hardware; no data leaves the machine in the default `local_mode` posture.

## Service topology

```
                         ┌─────────────────────────────┐
                         │         Caddy :80/:443      │  TLS + reverse proxy
                         └──────┬──────────┬───────────┘
                                │          │
        admin console  ◄────────┘          └────────►  Web UI (Open WebUI) :3000
        (nginx SPA)  :5173                                     │
             │                                                  │
             │ /api/v1                                /api/llm  │
             ▼                                                  ▼
 ┌────────────────────┐   CTRL(teams,budgets,   ┌────────────────────┐
 │  admin-backend     │◄───────── models ───────►│  litellm :4000     │  governance gateway
 │  FastAPI :8000     │   gateway base_url       │  keys·budgets·route│
 └─────┬──────────────┘                          └─────────┬──────────┘
       │                                   ┌───────────────▼──────────────┐
       │                                   │         ollama :11434         │  local models
       │                                   │  (llama3.1, qwen2.5, embed)  │
       │                                   └───────────────▲──────────────┘
       │                                   ┌───────────────┴──────────────┐
       │                                   │  backend :4001                │  FortressStack Gateway
       │                                   │  (minimal OpenAI-compatible)  │  (optional, egress-proof)
       │                                   └──────────────────────────────┘
       │                                                        ▲
       │                                                        │ local indexing
       ▼                                                        ▼
 ┌────────────────────┐          ┌────────────────────────────────────────┐
 │  postgres :5432     │◄─────────│  admin-backend /rag  (embeddings,      │
 │  (pgvector)         │          │  chunks, retrieval)                    │
 └────────────────────┘          └────────────────────────────────────────┘
       ▲                                     ▲
       └─────────  langfuse :3001  ◄─────────┘   LLM tracing/observability
```

## The two gateways (why both?)

- **LiteLLM** (`:4000`) is the *management* gateway — per-team keys, budgets,
  round-robin routing and automatic fallbacks (`llama3.1:8b → qwen2.5:7b`). The admin
  console speaks to it through config `gateway.base_url`. **This is the primary
  production path.**
- **`backend`** (FortressStack Gateway, `:4001`) is a *minimal, self-contained*
  OpenAI-compatible proxy built in Python. It enforces the local-mode egress rule and
  a model allowlist with no external dependencies. Use it when you want a tiny
  gateway or an offline-friendly fallback without LiteLLM.

Either way, **no outbound HTTPS call is ever made** in the default posture.

## Request paths

### 1. Admin console → governance gateway (primary)

```
Browser → nginx (SPA, :5173) → /api/v1/* → admin-backend:8000
                                   └─ POST /chat/completions... gateway call
admin-backend ──config.gateway.base_url──► litellm:4000 ──► ollama:11434
```

The admin backend stores the *policy* (team budgets, allowed models) in its own
`teams`/`models` tables; LiteLLM mirrors that policy in its config so the gateway
enforces it at call time. The audit log records every admin action.

### 2. Workspace chat → gateway directly

```
Open WebUI (:3000) ──OPENAI_API_BASE_URLS──► litellm:4000 ──► ollama:11434
```

### 3. RAG ingestion & retrieval (admin backend)

```
Upload ──► /api/v1/rag/corpora/{id}/documents
        parse (pypdf / python-docx)
        chunk (512 tok / 64 overlap)
        embed (LocalEmbeddingBackend in numpy, or Ollama nomic-embed-text)
        store chunks in postgres
Retrieve ──► /api/v1/rag/query  (embed query → cosine over chunks → top-k)
```

## Security posture

| Layer | Control |
|-------|---------|
| Egress | `local_mode: true` — FortressStack Gateway raises `ExternalEgressError` on any non-local URL; admin config forbids an egress allowlist under `local_mode` (validated at boot) |
| Model surface | allowlists in `config/litellm/config.yaml` and `backend/config/gateway.yaml`; unknown models rejected with 404 before any network call |
| Secrets | master keys come from **environment variables** (`LITELLM_MASTER_KEY`), never from YAML; config `redacted()` masks secrets in logs |
| Audit | append-only `audit_log` table — every team/model/settings change is recorded with actor + payload |
| TLS | Caddy reverse proxy (`deploy/caddy/Caddyfile`) with automatic certificates for public hostnames |
| Auth | admin API has an optional JWT/sso config (`config/fortress.yaml` → `auth`); tighten CORS per docs/DEPLOYMENT.md |

## Startup order (lifespan)

1. `postgres` becomes healthy (`pg_isready`).
2. `admin-backend` starts → `init_pool()` → `_apply_schema()` (runs `db/schema.sql`
   idempotently, `CREATE ... IF NOT EXISTS`) → `_seed_defaults()` (default team +
   core settings rows).
3. `litellm`, `ollama`, `backend`, `openwebui`, `langfuse` start; `caddy` fronts them.

Because every statement in `db/schema.sql` is idempotent and the postgres image also
mounts it as an init script, the schema is safe to apply on every boot.