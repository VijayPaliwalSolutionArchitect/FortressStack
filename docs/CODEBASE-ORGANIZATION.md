# Codebase Organization

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

A module-by-module walkthrough of the entire tree. Everything here is derived from
the actual source on disk, not from the feature spec.

```
FortressStack/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/                    # FortressStack Gateway — minimal private LLM proxy
├── admin-backend/              # FastAPI admin API
├── admin-frontend/             # React admin console
├── config/                     # layered runtime config
├── db/schema.sql               # idempotent PostgreSQL schema
├── deploy/caddy/Caddyfile      # reverse proxy / TLS
├── infra/                      # (placeholder) IaC
├── scripts/                    # (placeholder) helper scripts
└── docs/                       # this documentation set
```

---

## `backend/` — FortressStack Gateway

A self-contained **OpenAI-compatible LLM gateway** that enforces the private
`local_mode` posture. Shares no code with the admin backend; its only runtime
dependency is the local Ollama server.

| File | Responsibility |
|------|----------------|
| `app/main.py` | FastAPI entrypoint. Routes: `GET /health`, `GET /v1/models`, `POST /v1/chat/completions`, `POST /v1/embeddings`; optional Bearer auth (`verify_auth`); model-allowlist check; wraps upstream errors as 502. |
| `app/config.py` | `GatewayConfig` (pydantic) loaded as defaults ← `backend/config/gateway.yaml` ← `FORTRESS_*` env. Model catalogue (`GatewayModel`), `local_mode`, `egress_allowlist`, `ollama_base_url`, `master_key()`. Validation rejects an egress allowlist while `local_mode=True`. |
| `app/proxy.py` | Outbound layer. `assert_local()` = the egress guard (blocks non-local hosts in local mode); `resolved_base_url()`, `forward_chat()`, `forward_embedding()`, `list_upstream_models()` (falls back to the allowlist if Ollama is offline). |
| `config/gateway.yaml` | Seeded allowlist (`llama3.1:8b`, `qwen2.5:7b`, `nomic-embed-text`) + local-mode settings. |
| `Dockerfile` | `python:3.12-slim`, installs requirements, copies `app/` + `config/`, runs `uvicorn app.main:app`. |
| `requirements.txt` | fastapi, uvicorn, pydantic, pyyaml, httpx==0.28.1, python-dotenv. |
| `pytest.ini` / `tests/test_gateway.py` | 8 pure-logic tests: egress guard, seeded config load, allowlist validation, and the HTTP surface with the outbound proxy stubbed (no live Ollama). |
| `.venv`/ | local virtualenv (gitignored). |

## `admin-backend/` — Admin API (FastAPI)

The control plane: teams, budgets, models, RAG, settings and audit. Talks to
Postgres via an async psycopg3 pool, and to the gateway (LiteLLM) over HTTP.

| File | Responsibility |
|------|----------------|
| `app/main.py` | Entrypoint. `lifespan` = init pool → apply `db/schema.sql` idempotently → seed default team + settings. CORS, `/health`, `/`. |
| `app/api/router.py` | Aggregates routers under `/api/v1`: teams, models, rag, audit, settings, chat. |
| `app/core/config.py` | `FortressConfig` (pydantic). Layered: defaults ← `config/fortress.yaml` ← `FORTRESS_SECTION__KEY` env (`_apply_env_overrides`). Sections: `gateway`, `rag`, `team`, `auth`, `observability`, `backup`. `redacted()` masks secrets. |
| `app/core/db.py` | `init_pool/close_pool/get_conn` (psycopg3 `AsyncConnectionPool`), `fetch_one`, `fetch_all`, `execute`. |
| `app/core/audit.py` | Append-only audit: `log(...)` inserts into `audit_log`; `query(limit, offset, actor, action)` reads it back. |
| `app/rag/engine.py` | Local RAG. `EmbeddingBackend` (numpy `LocalEmbeddingBackend` or Ollama `OllamaEmbeddingBackend`), `get_backend()`, `extract_text` (pypdf/python-docx), `chunk_text` (512/64), `ingest_document`, `retrieve` (cosine top-k). |
| `app/api/routes/teams.py` | Team CRUD + budget/rate-limit/model fields. |
| `app/api/routes/models.py` | Model registry CRUD. |
| `app/api/routes/rag.py` | Corpus & document upload + query endpoints. |
| `app/api/routes/audit.py` | Read-only audit query + `/export` for compliance. |
| `app/api/routes/settings.py` | Key/value settings CRUD. |
| `app/api/routes/chat.py` | Chat proxy (→ gateway). TTS/STT endpoints are declared stubs with `TODO(deployment)` (audio services wired later). |
| `tests/test_config.py` | 4 tests: defaults, redaction, env-override flattening, local-mode egress validation. |
| `tests/test_rag_engine.py` | RAG unit tests. |
| `Dockerfile` | `python:3.12-slim`, `WORKDIR /app`, copies requirements then app, runs uvicorn. |
| `requirements.txt` | Full dep list (fastapi, psycopg, httpx, numpy, pypdf, python-docx, …) + commented heavy/optional deps. |
| `pytest.ini` | `testpaths = tests`, `pythonpath = .`. |

## `admin-frontend/` — Admin console (React)

| File | Responsibility |
|------|----------------|
| `package.json` | react 18, react-router-dom 6, vite 6, @vitejs/plugin-react. |
| `vite.config.js` | Dev server on `:5173`, proxies `/api` → `http://localhost:8000`. |
| `index.html` | SPA shell, mounts `#root`, loads `/src/main.jsx`. |
| `src/main.jsx` | React root + router setup. |
| `src/App.jsx` | Layout + route table. |
| `src/lib/api.js` | Typed REST client (`get/post/put/patch`, `uploadDocument`) targeting `/api/v1`. |
| `src/pages/` | `Teams.jsx`, `Models.jsx`, `Rag.jsx`, `Settings.jsx`, `Audit.jsx`, `Chat.jsx` — one screen per admin domain. |
| `Dockerfile` | Multi-stage: `node:20-alpine` `npm run build` → `nginx:alpine` serves `dist`. |
| `nginx.conf` | SPA fallback + `/api/` reverse proxy to `admin-backend:8000` + asset caching. |

## `config/` — layered runtime config

| File | Responsibility |
|------|----------------|
| `fortress.yaml` | Admin backend defaults (gateway base_url, rag, team, auth, observability, backup). |
| `litellm/config.yaml` | LiteLLM gateway: `model_list` (ollama models), routing/fallbacks, team budgets. |

## `db/schema.sql`

Idempotent schema (all statements `CREATE ... IF NOT EXISTS`): `teams`, `usage`
(+ time index), `models`, `corpora`, `documents`, `chunks`, `audit_log`
(+ created index), `settings`. Applied by the postgres image init script *and* by
`admin-backend/app/main.py::_apply_schema` at boot.

## `deploy/caddy/Caddyfile`

Reverse proxy: `/api/*` → `admin-backend:8000`, default → `admin-frontend:80`,
with commented blocks for real public hostnames (automatic TLS). This file is
mounted into the `caddy` service.

## `infra/` & `scripts/` (placeholders)

Reserved directories: `infra/` for optional Terraform/Ansible host provisioning
(documented in `docs/DEPLOYMENT.md`), `scripts/` for helper/backup automation.
Drop `.gitkeep` files in if you want them tracked.

## `docs/`

This documentation set: `README` (repo root), `ARCHITECTURE`, `INSTALLATION`,
`RUNNING`, `API`, `ADMIN-GUIDE`, `FEATURES`, `TECH-STACK`, `DEPLOYMENT`,
`PLAYBOOK-CROSSWALK`, `env-config`, `CODEBASE-ORGANIZATION`.

---

## Cross-cutting conventions

- **Layered config everywhere** — every service reads defaults ← YAML ← `*_ENV`.
  Never hardcode secrets; keep them in environment variables.
- **`local_mode` is the north star** — the admin config validation and the gateway
  egress guard both hard-enforce it.
- **Idempotent schema & seeding** — the app is safe to restart repeatedly.
- **Pure-logic tests** — both pytest suites run offline, no model or DB required.