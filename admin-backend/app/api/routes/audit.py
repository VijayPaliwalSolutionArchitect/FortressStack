"""Audit API — read-only access to the immutable audit log with export."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core import audit

router = APIRouter()


@router.get("")
async def list_audit(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    actor: str | None = None,
    action: str | None = None,
) -> list[dict[str, Any]]:
    return await audit.query(limit=limit, offset=offset, actor=actor, action=action)


@router.get("/export")
async def export_audit() -> dict[str, Any]:
    """Full audit export for compliance review (CSV-ready payload)."""
    rows = await audit.query(limit=10000)
    return {"count": len(rows), "entries": rows}