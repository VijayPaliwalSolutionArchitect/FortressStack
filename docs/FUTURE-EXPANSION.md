# FortressStack — Future Expansion & Roadmap

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

Concrete expansion plan for FortressStack (Hero Projects Playbook **Project 8 —
Private AI Workspace & LLM Gateway**). Anchored to the declared roadmap items
in [docs/PLAYBOOK-CROSSWALK.md](PLAYBOOK-CROSSWALK.md) (🟡 rows in §§4–5) and the
stubs in [docs/FEATURES.md](FEATURES.md) §12. FortressStack is the portfolio's
governance backbone — every sibling product's LLM traffic is a future customer
of this gateway.

## 1. Features (governance depth)

| # | Expansion | Grounded in | Horizon |
|---|---|---|---|
| 1.1 | **Policy template packs** (legal / healthcare / finance) — seeded prompt-injection, PII, and data-handling policies beyond today's defaults | crosswalk §4: "seeded defaults only" (`config/fortress.yaml`, `routes/settings.py`) | Next |
| 1.2 | **Retention automation** — scheduled purge/archival of chats, traces, audit rows per the `retention` policy config; export-before-purge | FR-F8 🟡: "policy config ✅, automation scripts = roadmap" | Next |
| 1.3 | **Per-team usage dashboards + monthly digest** — admin console pages over `/api/v1/teams/{id}/usage`; email digest | FR-F9 🟡: "API rollup ✅, dashboards/digest = roadmap" | Next |
| 1.4 | **SSO / Better Auth wiring** — turn `auth.sso_enabled` + `team_mapping` config into a live login flow with team auto-provisioning | FR-F5 🟡: config surface exists in `config/fortress.yaml` | Next |
| 1.5 | **GPU sizing guide per headcount** — documented sizing matrix (VRAM per concurrent user per model) in DEPLOYMENT.md | crosswalk §4 🟡: "GPU block documented; sizing guide = roadmap" | Now (doc-only) |
| 1.6 | **Voice mode** — wire the `TODO(deployment)` STT/TTS stubs in `backend/app/routes/chat.py` to `edge-tts` / `faster-whisper` (deps already commented in `requirements.txt`) | FEATURES.md §12 declared placeholder | Later |
| 1.7 | **Shared prompts & folders as first-class admin objects** — governed prompt library beyond Open WebUI; folder-level ACLs on RAG corpora | FR-F4 🟡: RAG ✅, folders/prompts via Open WebUI only | Later |
| 1.8 | **Native pgvector + sentence-transformers embeddings** — replace the optional/light path for larger corpora | FEATURES.md §12; admin-backend optional deps | Later |

## 2. Integrations

| # | Integration | Grounded in | Horizon |
|---|---|---|---|
| 2.1 | **Portfolio-wide LLM gateway** — route HelpPilot triage, StudioForge brief expansion, LedgerMind extraction, AuroraDesk/WapiDesk brains through this gateway with per-product budgets | `local_mode` egress guard in `backend/app/proxy.py`; LiteLLM `team_settings` in `config/litellm/config.yaml` | Next |
| 2.2 | **Uptime Kuma + alerting** — wire the DEPLOYMENT checklist monitors to real alerts (webhook/Telegram) | DEPLOYMENT.md hardening checklist mentions Kuma | Now |
| 2.3 | **Backup automation + tested restore drill** — cron pg_dump + volume snapshot per DEPLOYMENT.md §4, with a quarterly restore test logged to `audit_log` | FR-F8 🟡; `backup` config section | Next |
| 2.4 | **SIEM export** — stream `audit_log` export (`/api/v1/audit/export`) to customer SIEM (Splunk/Elastic) for compliance buyers | crosswalk §4 compliance persona | Later |

## 3. Scaling & platform

- **HA LiteLLM** — multiple gateway replicas behind Caddy with Redis-backed rate limits; keep `backend/` minimal proxy as the egress-proof alternative.
- **Model catalogue ops** — CI check that pulls/smoke-tests new Ollama models; canary rollout per team before global enable (`models` table `cpu_only` flag is the lever).
- **Multi-tenant SaaS packaging** — one FortressStack deploy serving many client orgs via Coolify projects + per-org Caddy hostname blocks (pattern already in `deploy/caddy/Caddyfile`).

## 4. Monetization

- **Governance retainer** — the playbook's sale is the operational posture (hardened deploy, budgets, audit, backups, egress proof), not the software: sell deploy + monthly governance review.
- **Per-seat + per-token metering** — `usage` table + `/api/v1/teams/{id}/usage` are the metering primitives; bill overage against `teams.budget_usd`.
- **Compliance bundle** — egress proof (`assert_local`, `ExternalEgressError`) + append-only audit export as the audit artifact for legal/healthcare/finance procurement.

## 5. Adjacent modules

- **FortressStack + any sibling** = "zero external data flow" demo: gateway guard + product audit trail together.
- **FortressStack + PulsePipe** — stream gateway usage/audit events into PulsePipe pipelines for portfolio-level observability.

---

*Source of truth for current behaviour: [docs/FEATURES.md](FEATURES.md),
[docs/API.md](API.md), [docs/DEPLOYMENT.md](DEPLOYMENT.md),
[docs/PLAYBOOK-CROSSWALK.md](PLAYBOOK-CROSSWALK.md).*
