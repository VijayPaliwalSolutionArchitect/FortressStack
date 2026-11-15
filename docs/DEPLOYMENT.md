# Deployment

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

Production guidance for FortressStack: TLS/domains, environment configuration,
backups, hardening, and notes on the optional `infra/` directory.

## Hosting model

FortressStack is a **single-node** stack. The reference deployment is a dedicated
VM (or a small bare-metal box) running Docker, reachable over HTTPS via Caddy. Options:

1. **Compute** — a VM with ≥8 GB RAM (more for larger models), any Linux with Docker +
   Compose v2. Add an NVIDIA GPU and uncomment the ollama `deploy.resources` block to
   offload inference.
2. **Storage** — keep data volumes (`pg_data`, `ollama`, `openwebui`, `uploads`) on a
   persistent disk; back them up nightly (see Backups).

## 1. DNS + TLS (Caddy)

Point **A records** for each public hostname at the server IP, then uncomment/adapt
the blocks in `deploy/caddy/Caddyfile`. Caddy obtains and renews Let's Encrypt
certificates automatically for real public domains.

Suggested hostname layout:

```
admin.example.com        → admin-frontend:80        (admin console)
app.example.com          → openwebui:8080           (workspace UI)
tracing.example.com      → langfuse:3000            (observability)
gateway.example.com      → backend:4001             (FortressStack Gateway)
```

The per-path dev route already forwards `/api/*` → `admin-backend:8000` and the rest
→ the SPA, so a single `admin.example.com` is enough to get started.

## 2. Environment configuration

Create a `.env` next to `docker-compose.yml` (the compose file interpolates it). Do
**not** commit it (it is gitignored).

```dotenv
# Secrets — CHANGE all of these
POSTGRES_PASSWORD=change-me-strong
LITELLM_MASTER_KEY=sk-fortress-<long-random>
WEBUI_SECRET_KEY=<random>
NEXTAUTH_SECRET=<random>          # langfuse
LANGFUSE_SALT=<random>
LANGFUSE_ENCRYPTION_KEY=<random>  # 32-byte key, see langfuse docs

# Admin backend overrides (optional)
# FORTRESS_ENVIRONMENT=production
# FORTRESS_LOCAL_MODE=true
# FORTRESS_GATEWAY__BASE_URL=http://litellm:4000
```

Then `docker compose up -d --build` and confirm `docker compose config` maps the
secrets.

## 3. Model management

```bash
# pull a model into the persistent ollama volume
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

When you add a model, register it in BOTH:
- `config/litellm/config.yaml` → `model_list` (+ optional `team_settings` allowlist);
- `backend/config/gateway.yaml` → `models` (if you use the minimal gateway).

## 4. Backups

Backup policy is configured in `config/fortress.yaml` (`backup` section):
chronograph `schedule_cron`, `retention_days`, `include_volumes`. The volumes named
there (`ollama`, `openwebui`, `litellm`, `langfuse`) plus `pg_data` and `uploads`
hold all application state.

Recommended cadence (the cron above targets daily):
- nightly `pg_dump` of the `fortress` database;
- nightly volume snapshot of the named volumes;
- retain ≥30 days; test restores periodically.

`scripts/` is reserved for helper smoke-tests and backup automation you add.

## 5. Production hardening checklist

- [ ] Replace every `change-me` secret in your `.env` with strong random values.
- [ ] Set `FORTRESS_ENVIRONMENT=production` (disables debug).
- [ ] Keep `FORTRESS_LOCAL_MODE=true` unless you deliberately allow external calls —
      the gateway refuses non-local hosts in this mode and validation forbids an
      egress allowlist under it.
- [ ] Tighten admin-backend CORS from `allow_origins=["*"]` to your real domains
      (`admin-backend/app/main.py`).
- [ ] Enable gateway auth: set `require_auth: true` in
      `backend/config/gateway.yaml` and export `LITELLM_MASTER_KEY` /
      `FORTRESS_GATEWAY_MASTER_KEY`; the `/v1/*` endpoints then demand a Bearer key.
- [ ] Review `config/fortress.yaml` `auth` section (JWT expiry, SSO). Put the admin
      console behind SSO/Better-Auth for multi-user environments.
- [ ] Restrict Caddy exposure: only publish the ports/hostnames you actually use;
      keep `5432` internal (no host port).
- [ ] On shared hosts, add a `deploy.resources` CPU/memory limit per service.
- [ ] Enable housekeeping on Langfuse (retention) so traces don't grow unbounded.

## 6. Optional `infra/` automation

The `infra/` directory is reserved for Terraform/Ansible provisioning of the host
VM (cloud, or static). A typical plan:

```text
infra/
├── main.tf          # provider + compute instance (e.g. Hetzner/DigitalOcean/AWS)
├── security.tf      # security group — only 22, 80, 443 exposed
├── ansible/
│   ├── docker.yml   # install Docker + Compose on the host
│   └── deploy.yml   # rsync compose + volumes, docker compose up -d --build
└── README.md
```

Because the app itself is pure Compose, the infra layer stays thin and portable.

## 7. Upgrades

```bash
git pull                 # pull the latest compose/config
docker compose pull      # refresh images
docker compose up -d --build   # rebuild changed services, keep volumes
docker compose ps        # verify health
```

`db/schema.sql` is idempotent (`CREATE ... IF NOT EXISTS`), and the admin backend
applies it on every boot, so app-code upgrades with new tables migrate safely without
manual SQL steps.

## 8. Rollback

Compose + volumes make rollback simple: stop the new stack, `docker compose down`,
then `git checkout` the previous compose/config and `docker compose up -d --build`.
Data volumes are untouched unless you pass `-v`.