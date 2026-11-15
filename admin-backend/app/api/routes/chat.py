"""Chat & Voice API — the text/voice dual-mode conversational surface.

Both text and voice requests converge on the same ``chat`` endpoint. Voice
input is transcribed (STT) before reaching the LLM; the LLM reply can be
returned as text and/or synthesised to speech (TTS). Every call is:

1. budget-checked against the team,
2. optionally RAG-grounded against a corpus (cited answers),
3. routed through the LiteLLM gateway,
4. traced to Langfuse,
5. written to the usage + audit tables.

This keeps Text/Voice dual mode a thin transport concern on top of one
governed pipeline.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.config import config
from app.core.db import execute
from app.rag.engine import retrieve

router = APIRouter()


class ChatRequest(BaseModel):
    team_id: str
    message: str = Field(min_length=1)
    corpus_id: str | None = None
    model: str | None = None
    mode: str = Field(default="text", pattern="^(text|voice)$")
    # Voice mode: base64 audio or a transcript already produced by STT.
    audio_base64: str | None = None
    transcript: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    reply: str
    mode: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    audio_base64: str | None = None  # TTS output for voice mode


# ---------------------------------------------------------------------------
# Voice helpers (STT / TTS) — pluggable via config
# ---------------------------------------------------------------------------


def _transcribe(audio_base64: str) -> str:
    """Speech-to-text. Default: local Faster-Whisper stub.

    In a full deployment this calls the Faster-Whisper service. The stub
    returns a placeholder so the pipeline is testable without the audio stack.
    """
    # TODO(deployment): call faster-whisper service with the decoded audio.
    return "[transcribed-from-audio]"


def _synthesize(text: str) -> str:
    """Text-to-speech. Default: local Chatterbox/edge-tts stub.

    Returns base64 audio for the voice mode reply.
    """
    # TODO(deployment): call chatterbox/edge-tts service.
    return ""


# ---------------------------------------------------------------------------
# LLM routing
# ---------------------------------------------------------------------------


async def _call_llm(
    messages: list[dict[str, str]],
    model: str,
    team_id: str,
) -> tuple[str, dict[str, Any]]:
    """Call the LiteLLM gateway (OpenAI-compatible). Returns (reply, usage)."""
    payload = {
        "model": model,
        "messages": messages,
        "user": team_id,
    }
    async with httpx.AsyncClient(timeout=config.gateway.timeout_seconds) as client:
        try:
            resp = await client.post(
                f"{config.gateway.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.gateway.master_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"LLM gateway error: {exc}") from exc
    data = resp.json()
    usage = data.get("usage", {})
    return data["choices"][0]["message"]["content"], usage


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    # 1. Resolve the message (voice -> transcript).
    message = body.transcript or body.message
    if body.mode == "voice" and body.audio_base64 and not body.transcript:
        message = _transcribe(body.audio_base64)

    # 2. Budget guard — estimate cost from token count (rough heuristic).
    est_tokens = max(len(message) // 4, 1)
    est_cost = est_tokens * 0.000002  # ~$2/M tokens
    budget = await _budget_check(body.team_id, est_cost)
    if not budget["allowed"]:
        raise HTTPException(402, "team budget exhausted — blocked at gateway")

    # 3. RAG grounding (optional).
    citations: list[dict[str, Any]] = []
    if body.corpus_id:
        citations = await retrieve(body.corpus_id, message)

    # 4. Build the prompt.
    system = "You are FortressStack, a private, governed AI assistant. Be concise and accurate."
    messages = [{"role": "system", "content": system}]
    if citations:
        context = "\n\n".join(f"[{i+1}] {c['content']}" for i, c in enumerate(citations))
        messages.append(
            {"role": "system", "content": f"Answer using ONLY the following context. Cite sources as [n].\n\n{context}"}
        )
    messages.append({"role": "user", "content": message})

    # 5. Route through the gateway.
    model = body.model or (config.team.default_models[0] if config.team.default_models else "llama3.1:8b")
    reply, usage = await _call_llm(messages, model, body.team_id)

    # 6. Voice mode -> TTS.
    audio = _synthesize(reply) if body.mode == "voice" else None

    # 7. Record usage + audit.
    await execute(
        """
        INSERT INTO usage (team_id, model, prompt_tokens, completion_tokens, cost_usd)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (body.team_id, model, usage.get("prompt_tokens", 0),
         usage.get("completion_tokens", 0), est_cost),
    )
    await audit.log(
        body.team_id, "chat.completed", "chat", None,
        {"model": model, "mode": body.mode, "citations": len(citations)},
    )

    return ChatResponse(
        reply=reply,
        mode=body.mode,
        citations=citations,
        model=model,
        usage=usage,
        audio_base64=audio,
    )


async def _budget_check(team_id: str, est_cost: float) -> dict[str, Any]:
    from app.core.db import fetch_one

    team = await fetch_one("SELECT budget_usd FROM teams WHERE id=%s", (team_id,))
    if not team:
        raise HTTPException(404, "team not found")
    spent = await fetch_one(
        "SELECT COALESCE(SUM(cost_usd),0) AS spent FROM usage WHERE team_id=%s", (team_id,)
    )
    remaining = float(team["budget_usd"]) - float(spent["spent"])
    allowed = remaining >= est_cost
    if not allowed:
        await audit.log("system", "budget.blocked", "team", team_id,
                        {"estimated": est_cost, "remaining": remaining})
    return {"allowed": allowed, "remaining": remaining}