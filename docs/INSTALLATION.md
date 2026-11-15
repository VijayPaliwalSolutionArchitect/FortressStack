# FortressStack — Installation

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

Three install paths: **full stack via Docker Compose** (recommended), **local dev**
per service, and **production VPS**. Everything is verified on Windows 11 (Git Bash)
with Python 3.14; the Docker images use Python 3.12 / Node 20.

---

## 0. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Docker + Compose v2 | runs all 9 services | `docker compose version` |
| Python 3.12+ | local dev of the two FastAPI services | `python --version` |
| Node 20+ / npm | local dev of the admin frontend only | `node --version` |
| ~8 GB RAM | Ollama CPU inference; more for bigger models | — |
| Optional NVIDIA GPU | uncomment the `deploy.resources` block on `ollama` in `docker-compose.yml` | `nvidia-smi` |

Windows notes: use Git Bash; pass `C:/...` paths to native tools; never bare `/tmp`.

---

## 1. Full stack (recommended)

```bash
cd C:/Vijay-Projects/FortressStack
cp .env.example .env        # then edit .env and set real secrets (see env-config.md)
docker compose up -d --build
docker compose ps           # wait for healthchecks (postgres, admin-backend, backend)
docker compose logs -f admin-backend
```

First `--build` pulls images (a few minutes). URLs:

| URL | Service |
|---|---|
| <http://localhost:5173> | admin console |
| <http://localhost:8000/docs> | admin API Swagger |
| <http://localhost:3000> | Open WebUI workspace |
| <http://localhost:3001> | Langfuse |
| <http://localhost:4000> | LiteLLM gateway |
| <http://localhost:4001/v1/models> | FortressStack Gateway |
| <http://localhost:80> | Caddy path-route (`/api/*` → admin-backend, else SPA) |

Validate without building: `docker compose config`.

### Model setup (Ollama)

```bash
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

`ollama pull` is the **only** outbound network call in the whole stack (model weights
from the Ollama registry). Add a model → also register it in `config/litellm/config.yaml`
(`model_list`) and `backend/config/gateway.yaml` (`models`).

### Database setup

None required manually. `db/schema.sql` is mounted into the postgres container as an
init script **and** re-applied idempotently by `admin-backend` on every boot
(`_apply_schema`, all `CREATE ... IF NOT EXISTS`). To apply by hand:

```bash
docker compose exec -T postgres psql -U fortress -d fortress < db/schema.sql
```

Schema tables: `teams`, `usage`, `models`, `corpora`, `documents`, `chunks`,
`audit_log`, `settings` (see [CODEBASE-ORGANIZATION.md](CODEBASE-ORGANIZATION.md)).

---

## 2. Local development (no Docker for the app services)

### Admin backend (:8000) — needs Postgres

```bash
cd C:/Vijay-Projects/FortressStack
docker compose up -d postgres                 # easiest way to get Postgres+pgvector

cd admin-backend
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
export FORTRESS_DATABASE_URL='postgresql://fortress:[REDACTED]@localhost:5432/fortress'
uvicorn app.main:app --reload --port 8000
```

### FortressStack Gateway (:4001) — needs Ollama

```bash
cd C:/Vijay-Projects/FortressStack && docker compose up -d ollama
cd backend
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
export FORTRESS_LOCAL_MODE=true FORTRESS_OLLAMA__BASE_URL=http://localhost:11434
uvicorn app.main:app --reload --port 4001
curl http://localhost:4001/health
```

### Admin frontend (:5173)

```bash
cd admin-frontend
npm install
npm run dev          # Vite proxies /api → http://localhost:8000 (vite.config.js)
```

Build for production: `npm run build` → `dist/` (the Dockerfile serves it via nginx).

---

## 3. Production VPS

See [DEPLOYMENT.md](DEPLOYMENT.md): dedicated VM with Docker, DNS A-records, Caddy TLS
(public hostname blocks in `deploy/caddy/Caddyfile`), Coolify alternative, backups,
hardening checklist.

---

## 4. Verification checklist

```bash
# services healthy
docker compose ps

# admin API + gateway health
curl http://localhost:8000/health
curl http://localhost:4001/health

# model catalogue through the egress-proof gateway
curl http://localhost:4001/v1/models

# tests (offline — no model, no DB)
cd admin-backend && .venv/Scripts/python.exe -m pytest        # 11 passed
cd ../backend      && ../admin-backend/.venv/Scripts/python.exe -m pytest   # 8 passed
```

Expected `GET /health` (gateway): `{"status":"ok","app":"FortressStack Gateway",
"environment":"production","local_mode":true,"models":["llama3.1:8b","qwen2.5:7b",
"nomic-embed-text"]}`.
