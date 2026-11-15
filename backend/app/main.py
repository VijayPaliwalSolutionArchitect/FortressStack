"""FortressStack Gateway — FastAPI entrypoint (private, OpenAI-compatible).

Endpoints
---------
- ``GET  /health``            readiness + local-mode + model count
- ``GET  /v1/models``         approved model catalogue (from allowlist)
- ``POST /v1/chat/completions`` OpenAI-compatible chat proxy to local Ollama
- ``POST /v1/embeddings``     OpenAI-compatible embedding proxy to local Ollama

Model allowlist and egress rules come from ``backend/config/gateway.yaml``
(see :mod:`app.config`).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import proxy
from app.config import GatewayConfig, config as cfg
from app.proxy import ExternalEgressError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fortress.gateway")

app = FastAPI(
    title="FortressStack Gateway",
    version="1.0.0",
    description="Private, OpenAI-compatible LLM gateway with local-mode egress "
                "enforcement and a model allowlist.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth guard (optional master-key auth, disabled by default)
# ---------------------------------------------------------------------------

def verify_auth(
    cfg_: GatewayConfig = Depends(lambda: cfg),
    authorization: str | None = Header(default=None),
) -> None:
    if not cfg_.require_auth:
        return
    expected = cfg_.master_key().get_secret_value()
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, "missing or invalid gateway master key")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str


class ChatCompletionsRequest(BaseModel):
    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class EmbeddingsRequest(BaseModel):
    model: str = Field(min_length=1)
    input: list[str] | str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": cfg.app_name,
        "environment": cfg.environment,
        "local_mode": cfg.local_mode,
        "models": cfg.model_names(),
    }


@router.get("/v1/models", tags=["chat"])
async def list_models(_: None = Depends(verify_auth)) -> dict[str, Any]:
    data = await proxy.list_upstream_models(cfg)
    return {"object": "list", "data": data}


@router.post("/v1/chat/completions", tags=["chat"])
async def chat_completions(
    body: ChatCompletionsRequest,
    _: None = Depends(verify_auth),
) -> dict[str, Any]:
    if body.model not in cfg.model_names():
        raise HTTPException(
            404, f"unknown model '{body.model}' — not in the approved allowlist"
        )
    messages = [m.model_dump() for m in body.messages]
    try:
        return await proxy.forward_chat(
            cfg,
            model=body.model,
            messages=messages,
            stream=body.stream,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except ExternalEgressError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - upstream (Ollama) errors
        raise HTTPException(502, f"upstream LLM error: {exc}") from exc


@router.post("/v1/embeddings", tags=["embeddings"])
async def embeddings(
    body: EmbeddingsRequest,
    _: None = Depends(verify_auth),
) -> dict[str, Any]:
    texts = [body.input] if isinstance(body.input, str) else body.input
    try:
        return await proxy.forward_embedding(cfg, model=body.model, input_texts=texts)
    except ExternalEgressError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"upstream embedding error: {exc}") from exc


# Register the /health, /v1/models, /v1/chat/completions, /v1/embeddings routes.
app.include_router(router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "app": cfg.app_name,
        "docs": "/docs",
        "health": "/health",
        "openai_base": f"http://{cfg.host}:{cfg.port}/v1",
    }