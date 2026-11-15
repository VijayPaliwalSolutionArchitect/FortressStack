"""Settings API — the "highly configurable" admin surface.

Key/value settings stored in PostgreSQL (versioned, audited). This lets an
admin change runtime policy (chunk size, budgets, egress, backup schedule)
without touching code or redeploying.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import audit
from app.core.db import execute, fetch_all, fetch_one

router = APIRouter()


class SettingPut(BaseModel):
    value: Any
    description: str = ""


@router.get("")
async def list_settings() -> list[dict[str, Any]]:
    return await fetch_all("SELECT key, value, description, updated_by, updated_at FROM settings ORDER BY key")


@router.get("/{key}")
async def get_setting(key: str) -> dict[str, Any]:
    row = await fetch_one("SELECT * FROM settings WHERE key=%s", (key,))
    if not row:
        raise HTTPException(404, "setting not found")
    return row


@router.put("/{key}")
async def put_setting(key: str, body: SettingPut, actor: str = "admin") -> dict[str, Any]:
    await execute(
        """
        INSERT INTO settings (key, value, description, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (key) DO UPDATE
        SET value=EXCLUDED.value, description=EXCLUDED.description,
            updated_by=EXCLUDED.updated_by, updated_at=now()
        """,
        (key, json.dumps(body.value), body.description, actor),
    )
    await audit.log(actor, "setting.updated", "setting", key, {"value": body.value})
    return await fetch_one("SELECT * FROM settings WHERE key=%s", (key,))