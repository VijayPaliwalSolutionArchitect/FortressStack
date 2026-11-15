"""Gateway proxy — outbound LLM / embedding calls with local-mode enforcement.

Every outbound call funnels through :func:`forward` which first runs the
:func:`assert_local` guard (local-mode egress proof), then relays the request
to the local Ollama server's OpenAI-compatible endpoints.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import GatewayConfig

# Hosts that are always considered local (never blocked in local mode).
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_local_host(host: str) -> bool:
    host = host.lower().strip()
    if host in _LOCAL_HOSTS:
        return True
    # Bare service names inside the compose network (single-label DNS) and
    # *.local names are local.
    if host.startswith("127.") or host == "1.0.0.1":
        return True
    if "." not in host:
        return True  # bare hostname, e.g. "ollama", "postgres"
    return host.endswith(".local") or host.endswith(".internal")


class ExternalEgressError(RuntimeError):
    """Raised when a local-mode gateway is asked to call an external host."""


def assert_local(url: str, local_mode: bool, allowlist: list[str] | None = None) -> str:
    """Enforce the local-mode egress rule for an outbound URL.

    Returns the URL unchanged on success; raises :class:`ExternalEgressError`
    when ``local_mode`` is true and the URL points at a non-local host that is
    not in the allowlist.
    """
    if not local_mode:
        return url
    parsed = urlparse(url)
    if _is_local_host(parsed.hostname or "") or url in (allowlist or []):
        return url
    raise ExternalEgressError(
        f"local_mode forbids external call to {url} (allowlist={allowlist or []})"
    )


def resolved_base_url(cfg: GatewayConfig) -> str:
    """Base URL to use for outbound calls, after the local-mode guard."""
    return assert_local(
        url=cfg.ollama_base_url,
        local_mode=cfg.local_mode,
        allowlist=cfg.egress_allowlist,
    )


async def forward_chat(
    cfg: GatewayConfig,
    model: str,
    messages: list[dict[str, str]],
    stream: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Proxy a chat completion to the local LLM (OpenAI-compatible response).

    URL: POST {ollama}/v1/chat/completions — Ollama implements the OpenAI
    schema natively, so the upstream response is relayed untouched.
    """
    base = resolved_base_url(cfg)
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
    payload.update({k: v for k, v in extra.items() if v is not None})
    async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
        resp = await client.post(f"{base}/v1/chat/completions", json=payload)
        resp.raise_for_status()
    return resp.json()


async def forward_embedding(
    cfg: GatewayConfig,
    model: str,
    input_texts: list[str],
) -> dict[str, Any]:
    """Proxy an embedding request to the local LLM (OpenAI-compatible response)."""
    base = resolved_base_url(cfg)
    payload = {"model": model, "input": input_texts}
    async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
        resp = await client.post(f"{base}/v1/embeddings", json=payload)
        resp.raise_for_status()
    return resp.json()


async def list_upstream_models(cfg: GatewayConfig) -> list[dict[str, Any]]:
    """List models available on the local Ollama server, filtered by allowlist."""
    base = resolved_base_url(cfg)
    allowed = set(cfg.model_names())
    try:
        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            resp = await client.get(f"{base}/v1/models")
            resp.raise_for_status()
    except httpx.HTTPError:
        # Ollama offline — report the configured allowlist instead of failing.
        return [{"id": m, "object": "model", "owned_by": "fortressstack"} for m in cfg.model_names()]
    data = resp.json()
    out: list[dict[str, Any]] = []
    for item in data.get("data", []):
        mid = item.get("id")
        if allowed and mid not in allowed:
            continue
        out.append({"id": mid, "object": "model", "owned_by": "ollama"})
    return out