# FortressStack — Private AI Workspace & LLM Gateway in a Box

**Self-hosted AI stack that keeps your data on your hardware.** FortressStack pairs a
fully **local** large-model runtime (Ollama) with a **governed LLM gateway**
(LiteLLM) and a clean **admin console** for teams, budgets, model routing, RAG and
audit — wrapped in one `docker compose up`. There is no external API call, no data
egress, and no per-seat cloud bill.

> **Compliance premise:** the stack runs in `local_mode` by default. Every component
> that touches an LLM is wired to local endpoints, and the built-in gateway refuses
> to forward a request to an external host. This is the FortressStack
> "egress-proof" guarantee for legal, healthcare, finance and regulated industries.

---

## What's in the box

| Service         | Role                                                        | Port   |
|-----------------|-------------------------------------------------------------|--------|
| `postgres`      | pgvector/PostgreSQL — teams, models, RAG corpora, audit log | 5432   |
| `admin-backend` | FastAPI admin API — budgets, models, RAG, settings, audit   | 8000   |
| `admin-frontend`| React + Vite admin console (served by nginx)                | 5173   |
| `ollama`        | Local LLM runtime (CPU/GPU)                                 | 11434  |
| `litellm`       | LLM gateway — per-team keys, budgets, routing, fallbacks    | 4000   |
| `backend`       | FortressStack Gateway — minimal private OpenAI-compatible proxy (egress-proof) | 4001 |
| `openwebui`     | Web chat UI with built-in RAG folders                       | 3000   |
| `langfuse`      | LLM observability / tracing                                 | 3001   |
| `caddy`         | Reverse proxy + automatic TLS (production entry)            | 80/443 |

---

## Quick start

```bash
docker compose up -d --build
```

Then open:

- **Admin console** → <http://localhost:5173>
- **Chat workspace** → <http://localhost:3000> (register the first user)
- **Admin API** → <http://localhost:8000/docs>
- **Gateway** (OpenAI-compatible) → <http://localhost:4001/v1/models>
- **Observability** → <http://localhost:3001>

### Run it on CPU-only dev

```bash
# pull a small model for testing
docker compose exec ollama ollama pull llama3.1:8b

# then chat via the gateway
docker compose exec backend python - <<'PY'
import httpx
r = httpx.post("http://backend:4001/v1/chat/completions",
    json={"model": "llama3.1:8b",
          "messages": [{"role": "user", "content": "Hello, Fortress!"}]})
print(r.status_code, r.text[:400])
PY
```

---

## Documentation

| Doc | What you'll find |
|-----|------------------|
| [Architecture](docs/ARCHITECTURE.md) | Service topology, data flow, request paths, egress proof |
| [Tech stack](docs/TECH-STACK.md) | Every component, runtime and version |
| [Features](docs/FEATURES.md) | Capabilities mapped to the modules that implement them |
| [Run it](docs/RUNNING.md) | Install, run (compose + local), test, ports, troubleshooting |
| [Deployment](docs/DEPLOYMENT.md) | Production, TLS, env vars, backups, hardening |
| [Codebase organization](docs/CODEBASE-ORGANIZATION.md) | Per-module walkthrough of every directory |

---

## Repository map

```
FortressStack/
├── docker-compose.yml          # the whole stack in one file
├── backend/                    # FortressStack Gateway — private LLM proxy
│   ├── app/                    #   config.py, proxy.py, main.py (FastAPI)
│   ├── config/gateway.yaml     #   seeded model allowlist + local-mode settings
│   └── tests/                  #   gateway unit/integration tests
├── admin-backend/              # FastAPI admin API (teams, budgets, RAG, audit)
│   ├── app/
│   │   ├── main.py             #   entrypoint + lifespan (schema, seed)
│   │   ├── api/                #   routers: teams, models, rag, audit, settings, chat
│   │   ├── core/               #   config, db pool, audit log
│   │   └── rag/                #   local embedding + chunking + retrieval
│   └── tests/                  #   config + RAG unit tests
├── admin-frontend/             # React 18 + Vite admin console
│   └── src/                    #   pages + lib/api.js client
├── config/                     # layered runtime config
│   ├── fortress.yaml           #   admin backend defaults
│   └── litellm/config.yaml     #   gateway model list + team budgets
├── db/schema.sql               # idempotent PostgreSQL schema (auto-applied)
├── deploy/caddy/Caddyfile      # reverse-proxy / TLS
├── infra/                      # optional Terraform/Ansible (see DEPLOYMENT.md)
├── scripts/                    # helper scripts (see RUNNING.md)
└── docs/                       # this documentation set
```

---

## Project status

Working baseline. `admin-backend` config + RAG unit tests (11) and the `backend`
gateway tests (8) pass on Python 3.12/3.14; `docker compose config` validates clean.
See [Running](docs/RUNNING.md#tests) for how to run the test suites.

## License

For internal use. Tune the governance/auth sections in `config/fortress.yaml` and
`config/litellm/config.yaml` to your compliance posture before wide rollout — see
[DEPLOYMENT.md](docs/DEPLOYMENT.md#hardening).