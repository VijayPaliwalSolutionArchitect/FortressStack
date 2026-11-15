"""Gateway configuration — layered: defaults -> YAML -> environment variables.

Precedence (highest wins):
    built-in defaults  <  backend/config/gateway.yaml  <  FORTRESS_* env vars

Secrets (the gateway master key) are never logged; they are read from the
``LITELLM_MASTER_KEY`` / ``FORTRESS_GATEWAY_MASTER_KEY`` environment variables
so they live in the environment, not in a file on disk.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator


# ---------------------------------------------------------------------------
# Model catalogue entry
# ---------------------------------------------------------------------------

class GatewayModel(BaseModel):
    """One approved model served by the gateway."""

    name: str
    provider: str = "ollama"
    mode: Literal["chat", "completion", "embedding"] = "chat"
    context_window: int = 8192
    max_tokens: int = 4096


# ---------------------------------------------------------------------------
# Gateway config
# ---------------------------------------------------------------------------

class GatewayConfig(BaseModel):
    """Root gateway configuration."""

    app_name: str = "FortressStack Gateway"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 4001

    # Local-mode egress proof: when true, ALL outbound calls must target a local
    # host. Any external host is refused. This is the FortressStack compliance
    # guarantee for legal/healthcare/finance clients.
    local_mode: bool = True
    egress_allowlist: list[str] = Field(default_factory=list)

    # Where the private models actually live.
    ollama_base_url: str = "http://ollama:11434"
    default_model: str = "llama3.1:8b"

    # Approved model catalogue (allowlist).
    models: list[GatewayModel] = Field(default_factory=list)

    master_key_env: str = "LITELLM_MASTER_KEY"  # env var name holding the key
    require_auth: bool = False  # when true, /v1/* requires Bearer master key

    timeout_seconds: float = 60.0
    max_retries: int = 2
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])

    # -- validation ---------------------------------------------------------
    @field_validator("egress_allowlist")
    @classmethod
    def _egress_empty_in_local_mode(cls, v: list[str], info: Any) -> list[str]:
        if info.data.get("local_mode") and v:
            raise ValueError(
                "local_mode=True forbids an egress allowlist — set local_mode=False "
                "to allow external calls."
            )
        return v

    # -- helpers ------------------------------------------------------------
    def master_key(self) -> SecretStr:
        """Return the master key from the environment (never from YAML/config)."""
        val = os.environ.get(self.master_key_env) or os.environ.get(
            "FORTRESS_GATEWAY_MASTER_KEY", ""
        )
        return SecretStr(val)

    def model_names(self) -> list[str]:
        return [m.name for m in self.models]

    def redacted(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _apply_env_overrides(cfg: dict[str, Any], prefix: str = "FORTRESS_") -> dict[str, Any]:
    """Apply flat ``FORTRESS_SECTION__KEY=value`` env overrides onto the tree."""
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        path = env_key[len(prefix):].lower().split("__")
        node = cfg
        for part in path[:-1]:
            node = node.setdefault(part, {})
        if env_val.lower() in ("true", "false"):
            node[path[-1]] = env_val.lower() == "true"
        else:
            try:
                node[path[-1]] = int(env_val)
            except ValueError:
                node[path[-1]] = env_val
    return cfg


@lru_cache(maxsize=1)
def get_config() -> GatewayConfig:
    """Build the effective gateway config once per process (cached)."""
    cfg_path = Path(os.getenv("FORTRESS_GATEWAY_CONFIG", "config/gateway.yaml"))
    merged: dict[str, Any] = _load_yaml(cfg_path)
    merged = _apply_env_overrides(merged)
    return GatewayConfig(**merged)


# Convenience singleton.
config: GatewayConfig = get_config()