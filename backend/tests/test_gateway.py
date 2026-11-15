"""Tests for the FortressStack Gateway (backend) — no live Ollama required.

These exercise the pure logic (config loading, local-mode egress guard, model
allowlist) plus the HTTP surface (via FastAPI TestClient) with the outbound
proxy stubbed so no real network call is made.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

import app.proxy as proxy_module
from app.config import GatewayConfig
from app.proxy import ExternalEgressError, assert_local, _is_local_host


# ---------------------------------------------------------------------------
# Local-mode egress guard
# ---------------------------------------------------------------------------

def test_local_hosts_are_local():
    assert _is_local_host("127.0.0.1")
    assert _is_local_host("localhost")
    assert _is_local_host("ollama")  # bare compose service name
    assert _is_local_host("postgres.internal")


def test_external_host_blocked_in_local_mode():
    with pytest.raises(ExternalEgressError):
        assert_local("https://api.openai.com/v1/chat/completions", local_mode=True)


def test_external_allowed_when_not_local_mode():
    url = assert_local("https://api.openai.com/v1", local_mode=False)
    assert url == "https://api.openai.com/v1"


def test_allowlist_override():
    url = "https://api.openai.com/v1"
    assert assert_local(url, local_mode=True, allowlist=[url]) == url


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_loads_from_seeded_file():
    path = Path(__file__).resolve().parents[1] / "config" / "gateway.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = GatewayConfig(**data)
    assert cfg.app_name == "FortressStack Gateway"
    assert cfg.local_mode is True
    assert "llama3.1:8b" in cfg.model_names()
    assert len(cfg.models) == 3
    assert cfg.master_key().get_secret_value() == ""  # key is env-only


def test_local_mode_forbids_egress_allowlist():
    with pytest.raises(ValueError):
        GatewayConfig(local_mode=True, egress_allowlist=["https://api.openai.com"])


# ---------------------------------------------------------------------------
# HTTP surface (proxy stubbed)
# ---------------------------------------------------------------------------

def _stub_proxy(monkeypatch):
    """Point forwarding at canned responses so no real network call happens."""
    async def fake_chat(cfg, model, messages, **extra):
        return {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "hello from fortress"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
        }

    async def fake_models(cfg):
        return [{"id": m, "object": "model"} for m in cfg.model_names()]

    monkeypatch.setattr(proxy_module, "forward_chat", fake_chat)
    monkeypatch.setattr(proxy_module, "list_upstream_models", fake_models)


def test_gateway_client_flow(monkeypatch):
    _stub_proxy(monkeypatch)
    from app.main import app

    client = TestClient(app)
    with client:
        # Health is real (no proxy needed).
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["local_mode"] is True

        # Models come from the allowlist via the stub.
        r = client.get("/v1/models")
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()["data"]]
        assert "llama3.1:8b" in ids

        # Chat completion is proxied to the stub.
        r = client.post(
            "/v1/chat/completions",
            json={
                "model": "llama3.1:8b",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 200
        assert r.json()["choices"][0]["message"]["content"] == "hello from fortress"


def test_unknown_model_rejected(monkeypatch):
    _stub_proxy(monkeypatch)
    from app.main import app
    client = TestClient(app)
    with client:
        r = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 404
        assert "allowlist" in r.json()["detail"]