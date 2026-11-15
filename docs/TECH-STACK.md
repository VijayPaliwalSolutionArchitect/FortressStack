# Technology Stack & Versions

Every stack component, its role, and the exact runtime/version requirement. Derived
from `Dockerfile`s, `requirements.txt`, `package.json`, and `docker-compose.yml`.

## Orchestration

| Tool | Role |
|------|------|
| Docker Compose | Single-file orchestration of all 9 services (`docker-compose.yml`) |
| Caddy 2 (alpine) | Reverse proxy + automatic TLS |

## Data layer

| Component | Base image | Role |
|-----------|-----------|------|
| PostgreSQL | `pgvector/pgvector:pg16` (Postgres 16 + vector extension) | Teams, models, usage, corpora, documents, chunks, audit_log, settings |
| Booting | `db/schema.sql` mounted at `/docker-entrypoint-initdb.d/01-schema.sql` (compose) **and** applied idempotently by the admin backend at startup | schema bootstrap |
| Driver | `psycopg[binary]≥3.2.10`, `psycopg_pool≥3.2` | async PostgreSQL client + connection pool |

## Admin backend (Python / FastAPI)

| Package | Constraint (from `admin-backend/requirements.txt`) |
|---------|-----------------------------------------------------|
| Python | 3.12 (Dockerfile), 3.14 (local dev confirmed) |
| fastapi | ≥0.115 |
| uvicorn[standard] | ≥0.34 |
| pydantic | ≥2.10 |
| python-dotenv | ==1.0.1 |
| pyyaml | ≥6.0 |
| httpx | ==0.28.1 |
| numpy | ≥2.2 |
| pypdf | ≥5.1 |
| python-docx | ≥1.1 |
| python-multipart | ==0.0.20 |

Optional/heavy (commented out in `requirements.txt`): `sentence-transformers` (better
local embeddings), `pgvector` (native vector column), `litellm`, `langfuse` SDK,
`edge-tts` (TTS), `faster-whisper` (STT).

## FortressStack Gateway (backend/, Python)

| Package | Constraint |
|---------|-----------|
| Python | 3.12 (Dockerfile) |
| fastapi | ≥0.115 |
| uvicorn[standard] | ≥0.34 |
| pydantic | ≥2.10 |
| pyyaml | ≥6.0 |
| httpx | ==0.28.1 (pinned to match the admin backend stack) |

## Frontend (React)

From `admin-frontend/package.json` (Vite 6, React 18):

| Package | Version |
|---------|---------|
| react / react-dom | ^18.3.1 |
| react-router-dom | ^6.28.0 |
| vite | ^6.0.3 |
| @vitejs/plugin-react | ^4.3.4 |
| Node runtime (build) | node:20-alpine |
| Serve | nginx:alpine + `nginx.conf` (SPA + `/api` reverse proxy) |

## Model serving & LLM tooling

| Component | Image / tool | Role |
|-----------|--------------|------|
| Ollama | `ollama/ollama:latest` | Local LLM runtime; models `llama3.1:8b`, `qwen2.5:7b`, `nomic-embed-text` |
| LiteLLM | `ghcr.io/berriai/litellm:main-latest` | Governance gateway (keys, budgets, routing, fallbacks, `config/litellm/config.yaml`) |
| Open WebUI | `ghcr.io/open-webui/open-webui:main` | Chat workspace with RAG folders |
| Langfuse | `langfuse/langfuse:3` | LLM tracing and observability |

## Python standard library used

- `hashlib`, `re`, `pathlib`, `contextlib`, `logging` — RAG chunking, text
  extraction, app wiring.
- `urllib.request` — container healthchecks.

## Dev / test tooling

| Tool | Where |
|------|-------|
| pytest ≥ (9.x confirmed) + `pytest.ini` | `admin-backend/`, `backend/` |
| `pythonpath = .` in pytest.ini | lets tests import `app.*` without install |
| fastapi TestClient + monkeypatch | gateway HTTP tests (no live Ollama needed) |

## Network / proxy

- Caddyfile at `deploy/caddy/Caddyfile` — `/api/*` → `admin-backend:8000`, default
  everything → `admin-frontend:80`. Public-hostname blocks provided (commented) for
  real domains with automatic TLS.