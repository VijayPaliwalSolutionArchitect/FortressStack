# FortressStack — Admin Guide

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

The admin console is the React SPA at `http://localhost:5173` (compose) — six pages,
all backed by the admin API (`/api/v1/*`, see [API.md](API.md)). Code:
`admin-frontend/src/App.jsx` (nav/routes), `src/lib/api.js` (REST client), one page
per domain under `src/pages/`.

```
┌──────────────┬────────────────────────────────────────────────────┐
│ 🔐 FortressStack Admin Console                                   │
│  👥 Teams & Budgets   🧠 Models   📚 RAG Ingestion               │
│  💬 Chat / Voice      🛡️ Audit Log   ⚙️ Settings                 │
└──────────────┴────────────────────────────────────────────────────┘
```

## 1. Teams & Budgets (`Teams.jsx` → `/api/v1/teams`)

- **Create team**: name, description, `budget_usd`, `rate_limit_rpm`, allowed `models`.
  Defaults come from `config/fortress.yaml → team` ($50 / 60 rpm / `llama3.1:8b`);
  first boot also seeds a `Default` team.
- **Edit team**: PATCH budget / rpm / models — every change is audited
  (`team.updated`).
- **Budget check**: `POST /api/v1/teams/budget-check` shows `spent_usd`,
  `remaining_usd`, `allowed`. When a call would exceed budget, the chat pipeline
  returns **HTTP 402** and writes a `budget.blocked` audit entry — this is the
  "budget block in action" demo.
- **Usage**: `GET /api/v1/teams/{id}/usage` — per-model token/cost rollup.

## 2. Models (`Models.jsx` → `/api/v1/models`)

Registry of approved models: provider, context window, max tokens, `cpu_only`,
`resource_limit_mb`, `enabled` toggle (PATCH). Keep this in sync with
`config/litellm/config.yaml` (`model_list`) and `backend/config/gateway.yaml`
(`models`) — the gateways enforce the allowlist, this table is the admin record.

## 3. RAG Ingestion (`Rag.jsx` → `/api/v1/rag`)

1. Create a **corpus** per team (`POST /rag/corpora`).
2. **Upload documents** (PDF / TXT / MD / DOCX / CSV, ≤ 50 MB) —
   `POST /rag/corpora/{id}/documents` (multipart). Pipeline: parse (`pypdf` /
   `python-docx`) → chunk (512/64) → embed (local numpy backend or Ollama
   `nomic-embed-text`) → store in `chunks`. Status tracked per document
   (`pending|processing|ready|failed` + `chunk_count`).
3. **Retrieve**: `POST /rag/retrieve` — embeds the query, cosine-scores all chunks,
   returns top-k above threshold with scores (citations for chat).

## 4. Chat / Voice (`Chat.jsx` → `/api/v1/chat`)

- Pick a team + optional corpus + model, send a message.
- Pipeline: budget check → RAG citations (if corpus set) → LiteLLM gateway
  (`POST {gateway}/chat/completions`, Bearer master key from env) → usage row +
  `chat.completed` audit entry → response with `citations[]`.
- `mode: "voice"` accepts `audio_base64` (STT stub) and returns `audio_base64`
  (TTS stub) — wire `faster-whisper` / `edge-tts` (commented in requirements.txt)
  to make voice real.

## 5. Audit Log (`Audit.jsx` → `/api/v1/audit`)

- Append-only table: `actor`, dotted `action` (`team.created`, `budget.blocked`,
  `model.updated`, `document.ingest.complete`, `setting.updated`, …), resource,
  JSON `detail`, timestamp.
- Filter by `actor` / `action`, paginate with `limit`/`offset`.
- **Export**: `GET /api/v1/audit/export` (up to 10k rows) for compliance review.

## 6. Settings (`Settings.jsx` → `/api/v1/settings`)

Versioned key/value policy in Postgres: `GET` all, `GET/PUT /{key}`. Seeded keys:
`rag.chunk_size`, `rag.top_k`, `local_mode`, `backup.schedule_cron`. Changing a
setting writes `setting.updated` to the audit log — policy changes are traceable,
never ad-hoc.

## 7. Gateway access (outside the console)

Open WebUI (:3000) talks straight to LiteLLM with the master key from env.
External OpenAI-compatible clients can use the FortressStack Gateway instead:

```bash
export OPENAI_API_BASE=http://localhost:4001/v1
export OPENAI_API_KEY=[REDACTED]        # only when FORTRESS_REQUIRE_AUTH=true
curl $OPENAI_API_BASE/models
```

## 8. First-run checklist

1. `docker compose up -d --build`; set real secrets in `.env`.
2. `docker compose exec ollama ollama pull llama3.1:8b` (and `qwen2.5:7b`, `nomic-embed-text`).
3. Admin console → create a second team with a different budget (demo: two teams,
   visible budgets).
4. RAG → create corpus → upload a policy doc → Chat with the corpus → show citations.
5. Force a budget block (set a tiny budget, chat) → show the 402 + `budget.blocked`
   audit entry.
6. Audit → export.
