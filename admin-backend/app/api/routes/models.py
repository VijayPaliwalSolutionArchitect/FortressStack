"""Models API — manage the approved model catalogue (Ollama) with per-model
resource limits, CPU/GPU profile and enable/disable."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.db import execute, fetch_all, fetch_one

router = APIRouter()


class ModelCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: str = "ollama"
    context_window: int = 8192
    max_tokens: int = 4096
    cpu_only: bool = True
    resource_limit_mb: int = 4096
    enabled: bool = True


@router.get("")
async def list_models() -> list[dict[str, Any]]:
    return await fetch_all(
        "SELECT * FROM models ORDER BY name"
    )


@router.post("", status_code=201)
async def create_model(body: ModelCreate, actor: str = "admin") -> dict[str, Any]:
    row = await fetch_one(
        """
        INSERT INTO models (name, provider, context_window, max_tokens, cpu_only, resource_limit_mb, enabled)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (body.name, body.provider, body.context_window, body.max_tokens,
         body.cpu_only, body.resource_limit_mb, body.enabled),
    )
    await audit.log(actor, "model.created", "model", row["id"], {"name": body.name})
    return row


@router.patch("/{model_id}")
async def update_model(model_id: str, body: dict[str, Any], actor: str = "admin") -> dict[str, Any]:
    existing = await fetch_one("SELECT * FROM models WHERE id=%s", (model_id,))
    if not existing:
        raise HTTPException(404, "model not found")
    allowed = {"context_window", "max_tokens", "cpu_only", "resource_limit_mb", "enabled"}
    fields, params = [], []
    for key, val in body.items():
        if key in allowed:
            fields.append(f"{key}=%s")
            params.append(val)
    if fields:
        params.append(model_id)
        await execute(f"UPDATE models SET {', '.join(fields)} WHERE id=%s", tuple(params))
        await audit.log(actor, "model.updated", "model", model_id, {"changed": list(body.keys())})
    return await fetch_one("SELECT * FROM models WHERE id=%s", (model_id,))