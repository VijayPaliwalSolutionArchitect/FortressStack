# Features

Capability-by-capability, each mapped to the module that implements it. FortressStack
is a **governed private AI workspace**: the headline is not raw model access but
*control* — who can call what model, at what budget, with a complete audit trail.

## 1. Local-only LLM runtime — no cloud dependency

- **Ollama** serves models on the machine (CPU by default, GPU via a one-line deploy
  reservation in `docker-compose.yml`).
- Seeded model catalogue: `llama3.1:8b`, `qwen2.5:7b` (chat) and `nomic-embed-text`
  (embeddings), declared in both the LiteLLM config and the gateway allowlist.
- **Assets:** `docker-compose.yml` (ollama), `config/litellm/config.yaml`
  (`model_list`), `backend/config/gateway.yaml` (`models`).

## 2. Governed LLM gateway (LiteLLM) — one place to enforce policy

- Per-team **API keys and budgets** (`team_settings.max_budget`, `rpm_limit`).
- **Model routing** (`routing_strategy: simple-shuffle`, `num_retries`) and
  **automatic fallbacks** (`llama3.1:8b → qwen2.5:7b`) so a failed inference retries
  on a second local model.
- `drop_params`, request timeout, retry policy in `litellm_settings`.
- **Assets:** `config/litellm/config.yaml`.

## 3. FortressStack Gateway (backend/) — egress-proof minimal proxy

- OpenAI-compatible surface: `GET /v1/models`, `POST /v1/chat/completions`,
  `POST /v1/embeddings`, `GET /health`.
- **Local-mode egress enforcement:** `assert_local()` refuses (502,
  `ExternalEgressError`) any request whose target host is not local (loopback, bare
  compose service names, `.local`/`.internal` domains).
- **Model allowlist:** requests for any model not in `gateway.yaml` are rejected with
  404 before a network call.
- Optional master-key auth (`require_auth` + env secret).
- **Assets:** `backend/app/proxy.py`, `backend/app/config.py`, `backend/app/main.py`.

## 4. Team & budget management (admin console)

- CRUD for **teams** — name, description, `budget_usd`, `rate_limit_rpm`, allowed
  `models`.
- Defaults seeded at first boot (budget $50 / 60 rpm / `["llama3.1:8b"]`).
- Budget policy mirrors into LiteLLM at the gateway.
- **Assets:** `admin-backend/app/api/routes/teams.py`, `admin-backend/app/core/db.py`.

## 5. Model registry

- CRUD/list of approved models with routing metadata for the gateway.
- **Assets:** `admin-backend/app/api/routes/models.py`, `db/schema.sql` (`models`).

## 6. Local RAG — retrieve over your own documents

- **Ingestion:** upload → parse (`pypdf`, `python-docx`) → chunk (512 tokens /
  64 overlap) → embed → store chunks.
- **Embedding backends:** pluggable `EmbeddingBackend` — a pure-`numpy` local
  backend (no extra deps) or the Ollama `nomic-embed-text` backend.
- **Retrieval:** `retrieve()` embeds the query and returns top-k chunks by cosine
  similarity (`top_k: 5`, `similarity_threshold: 0.55`).
- **Corpora / documents / chunks** persisted in Postgres (scalable to `pgvector`
  via the commented optional dependency).
- **Assets:** `admin-backend/app/rag/engine.py`, `admin-backend/app/api/routes/rag.py`,
  `db/schema.sql` (`corpora`, `documents`, `chunks`).

## 7. Audit log — append-only, exportable

- Every admin mutation is recorded (`record(actor, action, target, payload)`).
- Queried with `limit`/`offset`/`actor`/`action` filters; full export endpoint for
  compliance review (`/api/v1/audit/export`).
- **Assets:** `admin-backend/app/core/audit.py`, `admin-backend/app/api/routes/audit.py`,
  `db/schema.sql` (`audit_log`).

## 8. Settings & governance config (layered)

- **Layered, env-overridable configuration:** built-in defaults ←
  `config/fortress.yaml` ← `FORTRESS_SECTION__KEY` environment variables.
- Sections: `gateway`, `rag`, `team`, `auth` (JWT expiry, SSO/Better-Auth),
  `observability` (Langfuse), `backup` (cron, retention, volumes).
- `config.redacted()` masks secrets before logging.
- **Assets:** `admin-backend/app/core/config.py`, `config/fortress.yaml`,
  `admin-backend/app/api/routes/settings.py`.

## 9. Workspace — chat UI with RAG

- **Open WebUI** provides a web chat with folders/RAG, wired to the gateway
  (`OPENAI_API_BASE_URLS=http://litellm:4000`) and to Ollama directly.
- **Assets:** `docker-compose.yml` (openwebui).

## 10. Observability — trace every call

- **Langfuse** captures LLM traces for cost/latency/quality review, sharing the
  Postgres instance.
- **Assets:** `docker-compose.yml` (langfuse), `config/fortress.yaml`
  (`observability`).

## 11. Admin frontend

- React 18 + Vite 6 SPA with six pages: **Teams, Models, RAG, Settings, Audit,
  Chat** — driven by a typed REST client in `src/lib/api.js`.
- Dev server proxies `/api` → `localhost:8000`; production nginx serves the build and
  proxies `/api` → `admin-backend:8000`.
- **Assets:** `admin-frontend/src/**`, `admin-frontend/vite.config.js`,
  `admin-frontend/nginx.conf`.

## 12. Deployment refinements

- **Caddy** reverse proxy with automatic TLS and a per-path dev route
  (`/api/*` → backend, everything else → SPA).
- **Volumes** for pg_data, uploads, ollama models, webui state, caddy data/config.
- **Healthchecks** on postgres, admin-backend and gateway for orchestrator
  readiness.
- **Backup posture** defined in `config/fortress.yaml` (`backup.schedule_cron`,
  `retention_days`, `include_volumes`).

## Not-yet-implemented (declared placeholders)

- Voice mode: `chat.py` TTS/STT endpoints return stub responses with
  `TODO(deployment)` markers — wire `edge-tts` / `faster-whisper` when audio
  services are added (deps are commented in `requirements.txt`).
- `sentence-transformers` and native `pgvector` columns remain optional to keep the
  base install light.