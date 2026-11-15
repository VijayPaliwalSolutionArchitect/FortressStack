# FortressStack — Playbook Crosswalk (Project 8: Private AI Workspace & LLM Gateway)

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

Maps the Hero Projects Playbook chapter for **Project 8** (glance → demand → reference
architecture → PRD/personas/MoSCoW → FRs → NFRs → KPIs → work breakdown → deliverables →
benefits → deployment → portfolio) to what exists in this repo.

## 1. Snapshot (playbook Table 66)

| Playbook | In this repo |
|---|---|
| One-line pitch: self-hosted AI workspace, private models over company documents, quotas/budgets/audit, zero external data flow | README; `local_mode` egress guard in `backend/app/proxy.py`; config validation in both `config.py` files |
| Category: private AI infrastructure · LLM gateway · observability | 9-service compose: ollama, litellm, openwebui, langfuse, postgres, caddy + own gateway & admin stack |
| Core stack: Ollama · Open WebUI · LiteLLM · Langfuse · Better Auth | compose services `ollama`, `openwebui`, `litellm`, `langfuse`; SSO/Better-Auth config section (`config/fortress.yaml → auth`) |
| Demo URL `fortress.shivamitcs.com`, two teams with visible budgets | Caddy hostname blocks in `deploy/caddy/Caddyfile`; Teams page + `budget-check` |

## 2. Demand (§8.1)

Playbook: orgs that banned public chatbots want the same experience privately; the
sale is the **operational posture** (hardened deploy, model policy, budgets, audit,
backups, retainer), not the software. Repo evidence: `docs/DEPLOYMENT.md` hardening
checklist, append-only `audit_log` + `/api/v1/audit/export`, `backup` config section.

## 3. Reference architecture (Table 67 — five layers)

| Layer | Playbook components | Implementation |
|---|---|---|
| Model serving | Ollama runtimes, CPU/GPU sizing, catalogue | `ollama` service (+ optional GPU `deploy.resources` block); catalogue in `config/litellm/config.yaml` + `backend/config/gateway.yaml` + admin `models` table |
| Gateway | LiteLLM routing, budgets & quotas, per-team keys | `litellm` service + `config/litellm/config.yaml` (`team_settings`, `fallbacks`); mirrored policy in admin `teams` table; minimal alternative `backend/` (:4001) |
| Experience | Open WebUI workspace, RAG folders, shared prompts | `openwebui` service wired to `litellm:4000`; admin RAG corpora as the governed alternative (`/api/v1/rag`) |
| Observability | Langfuse traces, usage dashboards, Uptime Kuma | `langfuse` service; `usage` table + `/api/v1/teams/{id}/usage`; Kuma on the DEPLOYMENT checklist |
| Platform | Coolify deploy, nightly backups, SSO (Better Auth) | compose (Coolify-ready), `backup` config section + DEPLOYMENT.md §4, `auth` section (sso_enabled, better-auth) |

## 4. PRD — objectives & personas (§8.3, Tables 68–69)

| Item | Status | Where |
|---|---|---|
| Deployable in <1 working day | ✅ one `docker compose up -d --build` | INSTALLATION.md |
| Demonstrable budget enforcement | ✅ `budget-check`, 402 on chat, `budget.blocked` audit | `routes/teams.py`, `routes/chat.py` |
| Auditability | ✅ append-only `audit_log` + export | `core/audit.py`, `routes/audit.py` |
| Zero external data flow in local mode | ✅ `assert_local()` + boot validation forbidding allowlist under local_mode | `backend/app/proxy.py`, both `config.py` |
| Two teams with different budgets/model permissions | ✅ Teams page + `teams` table | ADMIN-GUIDE.md |
| GPU sizing guide per headcount | 🟡 GPU block documented; sizing guide = roadmap | docker-compose.yml comment, DEPLOYMENT.md |
| Policy template pack (legal/clinic/finance) | 🟡 seeded defaults only | `config/fortress.yaml`, `routes/settings.py` |
| Staff persona: private chat over internal docs | ✅ Open WebUI + RAG corpora/chat citations | compose, `routes/chat.py` |
| IT manager persona: budgets/keys/policy/audit/backups | ✅ | FEATURES.md §§2–8 |
| Compliance persona: egress proof, retention, audit export | 🟡 egress proof ✅, audit export ✅; retention automation = roadmap | DEPLOYMENT.md hardening |

## 5. Functional requirements (Table 70)

| FR | Requirement | Status | Where |
|----|-------------|--------|-------|
| FR-F1 | Deploy full stack via compose/Coolify < 1 day | ✅ | INSTALLATION.md, DEPLOYMENT.md |
| FR-F2 | Approved model catalogue with resource limits | ✅ | `models` table (`resource_limit_mb`, `cpu_only`), gateway allowlists |
| FR-F3 | Per-team keys, budgets, rate limits at gateway | ✅ | `config/litellm/config.yaml` team_settings; admin `teams`; `budget-check`; 402 chat |
| FR-F4 | Team workspaces with RAG folders + shared prompts | 🟡 RAG ✅ (corpora/retrieve), folders/prompts via Open WebUI | `routes/rag.py`, compose openwebui |
| FR-F5 | SSO with team mapping | 🟡 config surface (`auth.sso_enabled`, `team_mapping`) — wire Better Auth at deploy | `config/fortress.yaml`, DEPLOYMENT.md |
| FR-F6 | Auditable usage store with export | ✅ | `audit_log`, `usage`, `/api/v1/audit/export` |
| FR-F7 | Local-mode egress verification | ✅ | `assert_local()`, `ExternalEgressError`, tests |
| FR-F8 | Retention + nightly backups with tested restore | 🟡 policy config ✅, automation scripts = roadmap | `config/fortress.yaml → backup`, DEPLOYMENT.md §4 |
| FR-F9 | Per-team usage dashboards + monthly digest | 🟡 API rollup ✅, dashboards/digest = roadmap | `/api/v1/teams/{id}/usage`, Langfuse |

## 6. NFRs

- One-command backup/restore, one config file per policy → DEPLOYMENT.md §§4, 8; layered `config/*.yaml`.
- Sub-3s first token on CPU-class demo profile; GPU profiles documented → ollama service + compose GPU block.
- Availability 99.5% / fail-safe → healthchecks in compose; rollback procedure in DEPLOYMENT.md §8.

## 7. KPIs (playbook success metrics → where they live)

| KPI | Target (PRD §8.3) | Where enforced / measured |
|---|---|---|
| Deployability | Full stack up via compose/Coolify in < 1 working day | `docker-compose.yml` single `up -d --build`; INSTALLATION.md / DEPLOYMENT.md |
| Budget enforcement | 100% of over-budget calls rejected | LiteLLM budgets (`config/litellm/config.yaml`) + `teams.budget_usd`; `budget-check` + `402` on chat |
| Zero external data flow | local mode with egress proof | `assert_local()` / `ExternalEgressError` (`backend/app/proxy.py`), boot validation forbidding allowlist under `local_mode`, offline tests |
| Demo governance | Two teams with different budgets/model permissions; a budget block in action | `teams` table + seeded defaults; admin console Teams page; `budget.blocked` audit events |
| Audit completeness | Every admin action traceable to actor + payload + time | append-only `audit_log`, `GET /api/v1/audit`, `/api/v1/audit/export` |
| Latency | Sub-3s first token on CPU-class demo models | ollama CPU profile (`llama3.1:8b`, `qwen2.5:7b`); GPU profiles in DEPLOYMENT.md |

## 8. Work breakdown (playbook estimate: 6 working days)

| Work item | In this repo | Est. effort |
|---|---|---|
| Compose assembly: 9 services + Caddy TLS | `docker-compose.yml`, `deploy/caddy/Caddyfile` | ~1 day |
| Governance gateway: LiteLLM policy + minimal private gateway | `config/litellm/config.yaml`, `backend/` (allowlists, egress guard, auth) | ~1.5 days |
| Admin backend: teams / models / RAG / audit / settings / chat | `admin-backend/app/` (FastAPI + psycopg3 + pgvector) | ~2 days |
| Admin console (React) | `admin-frontend/` (Vite build → nginx) | ~1 day |
| Tests + docs | `backend/tests/`, `admin-backend/tests/`, `docs/` | ~0.5 day |

## 9. Deliverables & acceptance checks (mapped to FR-F1…F9)

| FR | Deliverable | Acceptance check today |
|----|-------------|----------------------|
| FR-F1 | One-command stack | `docker compose up -d --build` → `/health` on admin-backend (:8000) and gateway (:4001) |
| FR-F2 | Approved model catalogue | `ollama pull llama3.1:8b`; registered in both allowlists; `GET /v1/models` lists it |
| FR-F3 | Per-team keys / budgets / rate limits | `POST /api/v1/teams` with budget; over-budget chat → `402` + `budget.blocked` audit |
| FR-F4 | Workspace + RAG | Open WebUI (:3000) → litellm:4000; upload doc → `POST /api/v1/rag/retrieve` returns cited chunks |
| FR-F5 | SSO + team mapping | `auth` section in `config/fortress.yaml` (`FORTRESS_AUTH__*`); wire Better Auth at deploy |
| FR-F6 | Auditable usage + export | change a team → row in `audit_log`; `GET /api/v1/audit/export` |
| FR-F7 | Local-mode egress proof | unknown/external model → `404` / `ExternalEgressError`; pytest suites green offline |
| FR-F8 | Retention + nightly backups | `FORTRESS_BACKUP__*` policy; pg_dump + volume snapshots per DEPLOYMENT.md §4 |
| FR-F9 | Usage dashboards / digest | `usage` table + `GET /api/v1/teams/{id}/usage`; Langfuse (:3001) dashboards |

## 10. Benefits (before → after for the target buyers)

| Before | After — FortressStack |
|---|---|
| Public chatbots banned by policy | Private workspace with zero external data flow (`local_mode` egress guard) |
| Unmanaged internal AI experiments | Governed gateway: team keys, budgets, rate limits, routing/fallbacks |
| Unpredictable AI spend | Per-team budget caps enforced at call time (`402` on breach) |
| Compliance cannot prove data stays inside | Egress guard + append-only audit export + retention/backup policy |
| Renewals/procurement demand AI governance proof | Auditable admin console + Langfuse observability out of the box |

## 11. Deployment & portfolio (playbook platform flow)

VPS + Coolify + Caddy TLS at `fortress.shivamitcs.com`, Uptime Kuma monitors, nightly
encrypted backups → [DEPLOYMENT.md](DEPLOYMENT.md). Portfolio angle: sell governance
(budgets, audit, egress proof) to legal/healthcare/finance — the code-level proof
points are `proxy.assert_local`, `audit_log`, and `budget.blocked` events.
