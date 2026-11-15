# FortressStack — API Reference

*Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)*

Two HTTP surfaces:

1. **Admin API** — `http://localhost:8000` (compose) — prefix `/api/v1`, code in
   `admin-backend/app/api/routes/`. Interactive docs: `/docs`.
2. **FortressStack Gateway** — `http://localhost:4001` — OpenAI-compatible, code in
   `backend/app/main.py`. Interactive docs: `/docs`.

All examples use `localhost`; in production these sit behind Caddy TLS.
Secrets in examples are `[REDACTED]`.

---

# A. Admin API (`admin-backend:8000`)

Base: `http://localhost:8000/api/v1`. Routers aggregated in `app/api/router.py`.
Every mutation writes an `audit_log` row (`core/audit.py`).

## System

```bash
curl -s http://localhost:8000/health
# {"status":"ok","app":"FortressStack","environment":"production","local_mode":true}
```

## Teams & budgets — `/api/v1/teams` (`routes/teams.py`)

```bash
# list
curl -s http://localhost:8000/api/v1/teams

# create (201)
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H 'Content-Type: application/json' -d '{
    "name": "Legal", "description": "Legal team workspace",
    "budget_usd": 200.0, "rate_limit_rpm": 120, "models": ["llama3.1:8b","qwen2.5:7b"]
  }'
# -> {"id":"<uuid>","name":"Legal","budget_usd":200.0,"rate_limit_rpm":120,"models":[...]}

# update (PATCH, any of description/budget_usd/rate_limit_rpm/models)
curl -s -X PATCH http://localhost:8000/api/v1/teams/<team_id> \
  -H 'Content-Type: application/json' -d '{"budget_usd": 150.0}'

# budget check — is estimated_cost affordable for this team?
curl -s -X POST http://localhost:8000/api/v1/teams/budget-check \
  -H 'Content-Type: application/json' \
  -d '{"team_id":"<team_id>","estimated_cost_usd": 0.42}'
# -> {"team_id":"…","budget_usd":200.0,"spent_usd":12.34,"remaining_usd":187.66,"allowed":true}
#    when not allowed: {"allowed":false,…} and an audit row action=budget.blocked

# per-team usage rollup by model
curl -s http://localhost:8000/api/v1/teams/<team_id>/usage
# -> [{"model":"llama3.1:8b","prompt_tokens":1234,"completion_tokens":567,"cost_usd":0.5,"calls":42}]
```

## Models — `/api/v1/models` (`routes/models.py`)

```bash
curl -s http://localhost:8000/api/v1/models                       # list registry
curl -s -X POST http://localhost:8000/api/v1/models \
  -H 'Content-Type: application/json' -d '{
    "name": "qwen2.5:7b", "provider": "ollama", "context_window": 32768,
    "max_tokens": 8192, "cpu_only": true, "resource_limit_mb": 8192, "enabled": true
  }'                                                              # 201
curl -s -X PATCH http://localhost:8000/api/v1/models/<model_id> \
  -H 'Content-Type: application/json' -d '{"enabled": false}'    # disable a model
```

## RAG — `/api/v1/rag` (`routes/rag.py`, engine in `rag/engine.py`)

```bash
# create a corpus (201)
curl -s -X POST http://localhost:8000/api/v1/rag/corpora \
  -H 'Content-Type: application/json' \
  -d '{"team_id":"<team_id>","name":"Policies","description":"HR + IT policies"}'

curl -s http://localhost:8000/api/v1/rag/corpora                 # list (+document_count)

# upload + ingest a document (multipart; PDF/TXT/MD/DOCX/CSV, ≤50MB → 415/413)
curl -s -X POST http://localhost:8000/api/v1/rag/corpora/<corpus_id>/documents \
  -F "file=@policy.pdf"
# -> {"document_id":"…","status":"ready","chunks":37}

curl -s http://localhost:8000/api/v1/rag/corpora/<corpus_id>/documents   # status per doc

# cited retrieval
curl -s -X POST http://localhost:8000/api/v1/rag/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"corpus_id":"<corpus_id>","query":"What is the VPN policy?","top_k":5,"threshold":0.55}'
# -> {"corpus_id":"…","query":"…","results":[{"chunk_id":"…","content":"…","score":0.81}, …]}
```

## Audit — `/api/v1/audit` (`routes/audit.py`) — read-only, append-only store

```bash
curl -s "http://localhost:8000/api/v1/audit?limit=100&offset=0&actor=admin&action=team.created"
# -> [{"id":1,"actor":"admin","action":"team.created","resource_type":"team",
#       "resource_id":"…","detail":{"name":"Legal"},"created_at":"…"}, …]

curl -s http://localhost:8000/api/v1/audit/export      # full export (up to 10k rows)
# -> {"count":N,"entries":[…]}
```

## Settings — `/api/v1/settings` (`routes/settings.py`) — versioned key/value policy

```bash
curl -s http://localhost:8000/api/v1/settings
curl -s http://localhost:8000/api/v1/settings/local_mode
curl -s -X PUT http://localhost:8000/api/v1/settings/rag.top_k \
  -H 'Content-Type: application/json' -d '{"value": 8, "description": "retrieval depth"}'
```

## Chat — `/api/v1/chat` (`routes/chat.py`) — governed pipeline

Budget check → optional RAG grounding → LiteLLM gateway → usage + audit.
Text and voice modes (`mode: "text"|"voice"`; voice STT/TTS are stubs pending audio services).

```bash
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' -d '{
    "team_id": "<team_id>",
    "message": "What is our password rotation policy?",
    "corpus_id": "<corpus_id>",        # optional RAG grounding → citations
    "model": "llama3.1:8b",            # optional; default = team default model
    "mode": "text"
  }'
# -> {"reply":"…","mode":"text","citations":[{"chunk_id":"…","content":"…","score":0.8}],
#     "model":"llama3.1:8b","usage":{"prompt_tokens":…,"completion_tokens":…},"audio_base64":null}
# budget exhausted → HTTP 402 {"detail":"team budget exhausted — blocked at gateway"}
```

---

# B. FortressStack Gateway (`backend:4001`) — OpenAI-compatible

`backend/app/main.py`. Optional Bearer auth when `require_auth=true`
(header `Authorization: Bearer [REDACTED]`). Unknown models → `404`; external egress
in local mode or upstream failure → `502`.

```bash
curl -s http://localhost:4001/health
# {"status":"ok","app":"FortressStack Gateway","environment":"production",
#  "local_mode":true,"models":["llama3.1:8b","qwen2.5:7b","nomic-embed-text"]}

curl -s http://localhost:4001/v1/models
# {"object":"list","data":[{"id":"llama3.1:8b","object":"model","owned_by":"ollama"}, …]}
# (falls back to the configured allowlist if Ollama is offline)

curl -s -X POST http://localhost:4001/v1/chat/completions \
  -H 'Content-Type: application/json' -d '{
    "model": "llama3.1:8b",
    "messages": [{"role":"system","content":"You are concise."},
                 {"role":"user","content":"Hello, Fortress!"}],
    "stream": false, "temperature": 0.7, "max_tokens": 256
  }'
# OpenAI-schema response relayed from Ollama: {"id":"chatcmpl-…","choices":[…],"usage":{…}}

curl -s -X POST http://localhost:4001/v1/embeddings \
  -H 'Content-Type: application/json' -d '{
    "model": "nomic-embed-text", "input": ["hello world", "fortress stack"]
  }'
# {"object":"list","data":[{"object":"embedding","index":0,"embedding":[…]}, …]}
```

Errors: `404 {"detail":"unknown model 'gpt-4' — not in the approved allowlist"}`;
`401` missing/invalid master key (when `require_auth`); `502` egress blocked or upstream down.

---

## Error format

FastAPI standard `{"detail": "…"}` — `404` not found / unknown model, `401` auth,
`402` budget exhausted (chat), `413` file too large, `415` unsupported MIME,
`422` ingestion/validation failure, `502` gateway egress/upstream error.
