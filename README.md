# FortressStack — Private AI Workspace & LLM Gateway in a Box

**Self-hosted AI stack that keeps your data on your hardware.** FortressStack pairs a
fully **local** large-model runtime (Ollama) with a **governed LLM gateway**
(LiteLLM) and a clean **admin console** for teams, budgets, model routing, RAG and
audit — wrapped in one `docker compose up`. There is no external API call, no data
egress, and no per-seat cloud bill.

> **Compliance premise:** the stack runs in `local_mode` by default. Every component
> that touches an LLM is wired to local endpoints, and the built-in gateway refuses
> to forward a request to an external host (`assert_local()` → `ExternalEgressError`).
> This is the FortressStack "egress-proof" guarantee for legal, healthcare, finance
> and regulated industries.
>
> *Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

---

## What's in the box

| Service | Role | Port |
|-----------------|-------------------------------------------------------------|--------|
| `postgres` | pgvector/PostgreSQL — teams, models, RAG corpora, usage, audit log | 5432 (internal) |
| `admin-backend` | FastAPI admin API — teams, budgets, models, RAG, settings, chat, audit | 8000 |
| `admin-frontend` | React + Vite admin console (served by nginx) | 5173 |
| `ollama` | Local LLM runtime (CPU/GPU) | 11434 |
| `litellm` | LLM gateway — per-team keys, budgets, routing, fallbacks | 4000 |
| `backend` | FortressStack Gateway — minimal private OpenAI-compatible proxy (egress-proof) | 4001 |
| `openwebui` | Web chat workspace with built-in RAG folders | 3000 |
| `langfuse` | LLM observability / tracing | 3001 |
| `caddy` | Reverse proxy + automatic TLS (production entry) | 80/443 |

**Two gateways, one policy:** LiteLLM (`:4000`) is the management gateway enforcing
per-team keys/budgets/routing/fallbacks — the primary production path. `backend/`
(FortressStack Gateway, `:4001`) is a self-contained OpenAI-compatible proxy with the
model allowlist + local-mode egress guard, for offline/small deployments. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Features at a glance

- Local-only model catalogue (allowlisted): `llama3.1:8b`, `qwen2.5:7b`, `nomic-embed-text`
- Per-team **budgets, rate limits, API keys, model permissions** enforced at the gateway
- **Budget blocks** audited (`budget.blocked`) and enforced pre-call (`402` on chat)
- **Local RAG**: upload PDF/TXT/MD/DOCX/CSV → parse → chunk (512/64) → embed → cosine
  top-k retrieval with citations
- **Append-only audit log** with export (`/api/v1/audit/export`) — compliance proof
- **Layered config**: defaults ← `config/*.yaml` ← `FORTRESS_*` env vars, secrets env-only
- **Admin console** (React): Teams & Budgets, Models, RAG, Chat/Voice, Audit, Settings
- Egress-proof local mode; optional Bearer master-key auth on the gateway
- 19 offline tests (11 admin-backend + 8 gateway), no model or DB required

Full mapping: [docs/FEATURES.md](docs/FEATURES.md).

## Quick start

```bash
cd C:\Vijay-Projects\FortressStack        # Git Bash on Windows
docker compose up -d --build
```

Then open:

- **Admin console** → <http://localhost:5173>
- **Chat workspace** → <http://localhost:3000> (register the first user)
- **Admin API** → <http://localhost:8000/docs>
- **Gateway** (OpenAI-compatible) → <http://localhost:4001/v1/models>
- **Observability** → <http://localhost:3001>

### Pull a model and chat through the gateway (CPU-only dev)

```bash
docker compose exec ollama ollama pull llama3.1:8b

docker compose exec backend python - <<'PY'
import httpx
r = httpx.post("http://backend:4001/v1/chat/completions",
    json={"model": "llama3.1:8b",
          "messages": [{"role": "user", "content": "Hello, Fortress!"}]})
print(r.status_code, r.text[:400])
PY
```

Detailed install (local dev without Docker, DB setup, model setup):
[docs/INSTALLATION.md](docs/INSTALLATION.md).

---

## API summary

Two HTTP surfaces, both documented with curl examples in [docs/API.md](docs/API.md):

**Admin API** — `http://localhost:8000`, prefix `/api/v1` (routes in `admin-backend/app/api/routes/`):

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Readiness + local_mode |
| `GET/POST /api/v1/teams` · `PATCH /api/v1/teams/{id}` | Team CRUD (budget, rpm, models) |
| `POST /api/v1/teams/budget-check` · `GET /api/v1/teams/{id}/usage` | Budget enforcement + spend |
| `GET/POST /api/v1/models` · `PATCH /api/v1/models/{id}` | Approved model registry |
| `GET/POST /api/v1/rag/corpora` · `GET/POST /api/v1/rag/corpora/{id}/documents` · `POST /api/v1/rag/retrieve` | RAG corpora, upload/ingest, cited retrieval |
| `GET /api/v1/audit` · `GET /api/v1/audit/export` | Append-only audit query/export |
| `GET /api/v1/settings` · `GET/PUT /api/v1/settings/{key}` | Versioned runtime policy |
| `POST /api/v1/chat` | Governed chat (budget check → optional RAG → LiteLLM → usage + audit); text & voice modes |

**FortressStack Gateway** — `http://localhost:4001`, OpenAI-compatible (routes in `backend/app/main.py`):

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Readiness + local_mode + model count |
| `GET /v1/models` | Allowlisted model catalogue |
| `POST /v1/chat/completions` | Chat proxied to local Ollama (404 unknown model, 502 egress/upstream) |
| `POST /v1/embeddings` | Embeddings proxied to local Ollama |

---

## Configuration

All config is layered: **built-in defaults ← `config/*.yaml` ← `FORTRESS_*` env vars**;
secrets (master keys, DB password) live only in environment variables / `.env`
(never committed — see [.env.example](.env.example)). Full reference:
[docs/env-config.md](docs/env-config.md).

Compose `.env` secrets: `POSTGRES_PASSWORD`, `LITELLM_MASTER_KEY`, `WEBUI_SECRET_KEY`,
`NEXTAUTH_SECRET`, `LANGFUSE_SALT`, `LANGFUSE_ENCRYPTION_KEY`.
Flat overrides use `FORTRESS_SECTION__KEY` (e.g. `FORTRESS_GATEWAY__BASE_URL`,
`FORTRESS_LOCAL_MODE`, `FORTRESS_RAG__CHUNK_SIZE`).

---

## Repository map

```
FortressStack/
├── docker-compose.yml          # the whole stack in one file (9 services)
├── backend/                    # FortressStack Gateway — private LLM proxy (FastAPI, :4001)
│   ├── app/                    #   main.py, config.py, proxy.py (egress guard)
│   ├── config/gateway.yaml     #   seeded model allowlist + local-mode settings
│   └── tests/                  #   8 gateway tests (proxy stubbed, offline)
├── admin-backend/              # FastAPI admin API (:8000)
│   ├── app/
│   │   ├── main.py             #   entrypoint + lifespan (schema apply, seed)
│   │   ├── api/routes/         #   teams, models, rag, audit, settings, chat
│   │   ├── core/               #   config (layered), db pool (psycopg3), audit
│   │   └── rag/engine.py       #   extract → chunk → embed → store → retrieve
│   └── tests/                  #   11 config + RAG tests (offline)
├── admin-frontend/             # React 18 + Vite 6 admin console (:5173)
│   └── src/                    #   pages: Teams, Models, Rag, Chat, Audit, Settings
├── config/                     # layered runtime config
│   ├── fortress.yaml           #   admin backend defaults
│   └── litellm/config.yaml     #   gateway model list + team budgets + fallbacks
├── db/schema.sql               # idempotent PostgreSQL schema (auto-applied at boot)
├── deploy/caddy/Caddyfile      # reverse proxy / TLS entry point
├── infra/ scripts/             # reserved for IaC / helper automation
├── .env.example                # env var template (placeholders only)
└── docs/                       # this documentation set
```

---

## Documentation index

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — service topology, request paths, egress proof, security posture
- [docs/INSTALLATION.md](docs/INSTALLATION.md) — prerequisites, compose install, local dev, DB & model setup, verification
- [docs/RUNNING.md](docs/RUNNING.md) — run the stack, port map, tests, troubleshooting
- [docs/API.md](docs/API.md) — admin API (`/api/v1/*`) + gateway (`/v1/*`) with curl examples
- [docs/ADMIN-GUIDE.md](docs/ADMIN-GUIDE.md) — admin console walkthrough (teams, budgets, RAG, chat, audit, settings)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — VPS/Coolify, DNS+TLS, backups, hardening, upgrades, rollback
- [docs/FEATURES.md](docs/FEATURES.md) — capabilities mapped to implementing modules
- [docs/TECH-STACK.md](docs/TECH-STACK.md) — every component, version, rationale
- [docs/CODEBASE-ORGANIZATION.md](docs/CODEBASE-ORGANIZATION.md) — per-module file walkthrough
- [docs/PLAYBOOK-CROSSWALK.md](docs/PLAYBOOK-CROSSWALK.md) — playbook Project 8 ↔ implementation map
- [docs/env-config.md](docs/env-config.md) — every environment variable with defaults

## Project status

Working baseline. `admin-backend` config + RAG tests (11) and `backend` gateway
tests (8) pass on Python 3.12/3.14; `docker compose config` validates clean.
See [docs/RUNNING.md](docs/RUNNING.md#tests). Voice mode (STT/TTS) is a declared
stub pending audio services (`edge-tts` / `faster-whisper`, commented in
`requirements.txt`).

## License

For internal use — SHIVAM ITCS (JARVIS). Tune governance/auth in
`config/fortress.yaml` and `config/litellm/config.yaml` to your compliance posture
before rollout — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
