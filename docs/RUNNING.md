# Running FortressStack

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

This page covers the three ways to run the stack — the full Docker Compose stack,
per-service local development, and the test suites — plus the port map and
troubleshooting.

## Prerequisites

- **Docker** with Compose v2 (`docker compose version`).
- **Python 3.12+** (3.14 confirmed working locally).
- **Node 20+** and npm (only for local frontend dev).
- ~8 GB RAM recommended; a GPU is optional (see GPU notes below).

## 1. Full stack via Docker Compose (recommended)

```bash
cd C:\Vijay-Projects\FortressStack        # Git Bash
docker compose up -d --build
```

First `--build` pulls and builds images (a few minutes on the first run). Watch
startup:

```bash
docker compose ps
docker compose logs -f admin-backend
```

Wait for `admin-backend` healthcheck to pass, then open:

| URL | What |
|-----|------|
| <http://localhost:5173> | Admin console |
| <http://localhost:8000/docs> | Admin API (Swagger) |
| <http://localhost:3000> | Open WebUI workspace (register first user) |
| <http://localhost:3001> | Langfuse |
| <http://localhost:4000> | LiteLLM gateway |
| <http://localhost:4001/v1/models> | FortressStack Gateway (backend) |

### Pull a model and chat through the gateway

```bash
docker compose exec ollama ollama pull llama3.1:8b

docker compose exec backend python - <<'PY'
import httpx
r = httpx.post("http://backend:4001/v1/chat/completions",
    json={"model": "llama3.1:8b",
          "messages": [{"role": "user", "content": "Hello, Fortress!"}]})
print(r.status_code, r.text[:500])
PY
```

### Optional GPU support

Uncomment the `deploy.resources.reservations.devices` block under the `ollama`
service in `docker-compose.yml` and re-run `docker compose up -d ollama`.

### Stop / teardown

```bash
docker compose down            # stop (keeps data volumes)
docker compose down -v         # destroy volumes too (wipes all data)
```

## 2. Port map

| Port | Service | Note |
|------|---------|------|
| 80 / 443 | Caddy | reverse-proxy entry |
| 5173 | admin-frontend (nginx SPA) | maps to container `:80` |
| 8000 | admin-backend (FastAPI) | also the dev backend port |
| 11434 | ollama | local LLM |
| 4000 | litellm | governance gateway |
| 4001 | backend (FortressStack Gateway) | egress-proof minimal gateway |
| 3000 | openwebui | maps to container `:8080` |
| 3001 | langfuse | maps to container `:3000` |
| 5432 | postgres | internal (pgvector) |

## 3. Local development (no Docker)

### Admin backend

```bash
cd admin-backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

# needs a Postgres — easiest is a compose'd one:
docker compose up -d postgres

export FORTRESS_DATABASE_URL='postgresql://fortress:fortress@localhost:5432/fortress'
uvicorn app.main:app --reload --port 8000
```

> On boot the admin backend applies `db/schema.sql` **idempotently**
> (`_apply_schema`) and seeds a default team + core settings (`_seed_defaults`), so
> a fresh local database needs no manual setup.

### FortressStack Gateway (backend)

```bash
cd backend
pip install -r requirements.txt
export FORTRESS_LOCAL_MODE=true FORTRESS_OLLAMA__BASE_URL=http://localhost:11434
uvicorn app.main:app --reload --port 4001
curl http://localhost:4001/health
```

### Admin frontend

```bash
cd admin-frontend
npm install
npm run dev        # Vite dev server on :5173, proxies /api → :8000
```

## 4. Tests

```bash
# Admin backend (config + RAG) — needs the venv from above
cd admin-backend
.venv/Scripts/python.exe -m pytest        # -> 11 passed

# Gateway (backend) — config, egress guard, HTTP surface (no live Ollama)
cd backend
../admin-backend/.venv/Scripts/python.exe -m pytest   # -> 8 passed
```

Both suites are **pure-logic** — the gateway HTTP tests stub the outbound proxy, so
no model or network is required to run them.

### Validate the compose file (no build)

```bash
docker compose config          # validates parse + interpolation
```

## 5. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `admin-backend` restarts | Postgres not healthy yet — it `depends_on` with a healthcheck; give it time. |
| `connection refused` between services | Service started before dependency; `docker compose ps` and `logs`. |
| Gateway returns 502 | Upstream Ollama down or external URL blocked by local-mode. Check `gateway.yaml` `ollama_base_url` and `local_mode`. |
| Unknown model 404 | Model not in the allowlist (`config/litellm/config.yaml` or `backend/config/gateway.yaml`); add it and rebuild. |
| SPA shows blank / 404 on refresh | nginx SPA fallback handles it — verify `admin-frontend/nginx.conf` is in place (it was missing originally; this repo now ships it). |
| Local admin backend skips schema | Needs a reachable Postgres; check `FORTRESS_DATABASE_URL`. |
| Model pull slow | Network; `docker compose exec ollama ollama pull <model>` is the only outbound call in the stack. |
| Port already in use | Change the mapped left-hand port in `docker-compose.yml` (e.g. `5174:80`). |

## 6. Config overrides (no rebuild)

Everything is layered — environment variables override YAML at runtime:

```bash
# examples
export FORTRESS_LOCAL_MODE=true
export FORTRESS_GATEWAY__BASE_URL=http://litellm:4000
export FORTRESS_RAG__CHUNK_SIZE=768
export LITELLM_MASTER_KEY=«redacted»
docker compose up -d
```

Key `FORTRESS_` variables live in `admin-backend/app/core/config.py`
(`_apply_env_overrides`, `FORTRESS_SECTION__KEY` flattening) and
`backend/app/config.py`.