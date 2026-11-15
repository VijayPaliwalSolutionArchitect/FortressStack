"""Tests for the layered configuration system."""

import os

from app.core.config import FortressConfig, _apply_env_overrides


def test_defaults_apply():
    cfg = FortressConfig()
    assert cfg.app_name == "FortressStack"
    assert cfg.rag.chunk_size == 512
    assert cfg.team.default_budget_usd == 50.0
    assert cfg.local_mode is True


def test_redacted_masks_secrets():
    cfg = FortressConfig()
    red = cfg.redacted()
    assert "change-me" not in str(red)
    assert red["auth"]["jwt_secret"] != "change-me-in-prod"


def test_env_override_flat():
    os.environ["FORTRESS_RAG__CHUNK_SIZE"] = "1024"
    os.environ["FORTRESS_LOCAL_MODE"] = "false"
    try:
        merged = _apply_env_overrides({})
        assert merged["rag"]["chunk_size"] == 1024
        assert merged["local_mode"] is False
    finally:
        del os.environ["FORTRESS_RAG__CHUNK_SIZE"]
        del os.environ["FORTRESS_LOCAL_MODE"]


def test_local_mode_forbids_egress():
    import pytest

    with pytest.raises(ValueError):
        FortressConfig(local_mode=True, egress_allowlist=["https://api.openai.com"])