"""
FortressStack — Core Configuration
==================================

Central, layered configuration for the FortressStack admin backend.

Design principles
-----------------
1. **Layered precedence** — env vars override YAML config files override
   built-in defaults. This keeps the system *highly configurable* without
   forcing every knob into environment variables.
2. **Single source of truth** — the `FortressConfig` model is the one object
   every service reads. No scattered `os.getenv` calls.
3. **Validation at boot** — pydantic validates the whole config tree on
   startup, so a bad config fails fast with a clear message instead of
   failing deep inside a request.
4. **Secrets never logged** — API keys / tokens are redacted in any repr.

Layers (highest wins):
    defaults -> config/*.yaml -> environment variables
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator

# ---------------------------------------------------------------------------
# Config model tree
# ---------------------------------------------------------------------------


class GatewaySettings(BaseModel):
    """LiteLLM gateway connection & behaviour."""

    base_url: str = "http://litellm:4000"
    master_key: SecretStr = SecretStr("sk-fortress-master")
    timeout_seconds: float = 60.0
    max_retries: int = 2
    # Route fallback chain when the primary model is unavailable.
    fallback_models: list[str] = Field(default_factory=list)


class RagSettings(BaseModel):
    """RAG ingestion defaults (chunking, embedding, retrieval)."""

    chunk_size: int = 512
    chunk_overlap: int = 64
    embedding_model: str = "nomic-embed-text"
    top_k: int = 5
    similarity_threshold: float = 0.55
    # Where ingested documents are stored on disk before vectorisation.
    upload_dir: str = "/data/uploads"
    # Allowed MIME types for ingestion.
    allowed_mimes: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "text/plain",
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/csv",
        ]
    )
    max_file_mb: int = 50


class TeamSettings(BaseModel):
    """Default team policy applied when a team is created."""

    default_budget_usd: float = 50.0
    default_rate_limit_rpm: int = 60
    default_models: list[str] = Field(default_factory=list)


class AuthSettings(BaseModel):
    """Auth / SSO (Better Auth) integration."""

    jwt_secret: SecretStr = SecretStr("change-me-in-prod")
    jwt_expiry_minutes: int = 60
    sso_enabled: bool = True
    sso_provider: str = "better-auth"
    # Team mapping source: "header" (SSO passes team in a header) or "db".
    team_mapping: Literal["header", "db"] = "db"
    team_header: str = "X-Fortress-Team"


class ObservabilitySettings(BaseModel):
    """Langfuse tracing."""

    enabled: bool = True
    langfuse_host: str = "http://langfuse:3000"
    public_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    trace_sample_rate: float = 1.0


class BackupSettings(BaseModel):
    """Nightly backup policy."""

    enabled: bool = True
    schedule_cron: str = "0 2 * * *"  # 2am daily
    destination: str = "/backups"
    retention_days: int = 30
    include_volumes: list[str] = Field(
        default_factory=lambda: ["ollama", "openwebui", "litellm", "langfuse"]
    )


class FortressConfig(BaseModel):
    """Root configuration object — the single source of truth."""

    app_name: str = "FortressStack"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql://fortress:fortress@postgres:5432/fortress"
    # Local-mode egress proof: when true, no external network calls allowed.
    local_mode: bool = True
    egress_allowlist: list[str] = Field(default_factory=list)

    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    rag: RagSettings = Field(default_factory=RagSettings)
    team: TeamSettings = Field(default_factory=TeamSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)

    # -- validation ---------------------------------------------------------
    @field_validator("egress_allowlist")
    @classmethod
    def _egress_must_be_empty_in_local_mode(cls, v: list[str], info: Any) -> list[str]:
        """In local mode the egress allowlist must stay empty (compliance)."""
        if info.data.get("local_mode") and v:
            raise ValueError(
                "local_mode=True forbids an egress allowlist — set local_mode=False "
                "to allow external calls."
            )
        return v

    # -- helpers ------------------------------------------------------------
    def redacted(self) -> dict[str, Any]:
        """Serialise config with all secrets masked (for logs / health checks)."""
        return self.model_dump(
            exclude={"_secrets"},
            mode="json",
        )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load_yaml_layers(config_dir: Path) -> dict[str, Any]:
    """Load and deep-merge YAML files from a config directory (in order)."""
    merged: dict[str, Any] = {}
    if not config_dir.exists():
        return merged
    for path in sorted(config_dir.glob("*.yaml")):
        if path.name.startswith("_"):  # skip partials
            continue
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        # Deep merge (dicts recurse, everything else overwrites).
        _deep_merge(merged, data)
    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _apply_env_overrides(cfg: dict[str, Any], prefix: str = "FORTRESS_") -> dict[str, Any]:
    """Apply flat `FORTRESS_SECTION__KEY=value` env overrides onto the dict tree."""
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        path = env_key[len(prefix):].lower().split("__")
        node = cfg
        for part in path[:-1]:
            node = node.setdefault(part, {})
        # Coerce simple types.
        if env_val.lower() in ("true", "false"):
            node[path[-1]] = env_val.lower() == "true"
        else:
            try:
                node[path[-1]] = int(env_val)
            except ValueError:
                node[path[-1]] = env_val
    return cfg


@lru_cache(maxsize=1)
def get_config() -> FortressConfig:
    """Build the effective config once per process (cached)."""
    config_dir = Path(os.getenv("FORTRESS_CONFIG_DIR", "config"))
    merged: dict[str, Any] = _load_yaml_layers(config_dir)
    merged = _apply_env_overrides(merged)
    return FortressConfig(**merged)


# Convenience singleton.
config = get_config()