"""Teams & budgets API — create teams, set budgets/rate-limits/models, and
enforce budget blocks at the gateway level."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.db import execute, fetch_all, fetch_one

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    budget_usd: float = Field(default=50.0, ge=0)
    rate_limit_rpm: int = Field(default=60, ge=1)
    models: list[str] = Field(default_factory=list)


class TeamUpdate(BaseModel):
    description: str | None = None
    budget_usd: float | None = Field(default=None, ge=0)
    rate_limit_rpm: int | None = Field(default=None, ge=1)
    models: list[str] | None = None


class BudgetCheck(BaseModel):
    team_id: str
    estimated_cost_usd: float = Field(default=0.0, ge=0)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_teams() -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT id, name, description, budget_usd, rate_limit_rpm, models, created_at
        FROM teams ORDER BY name
        """
    )


@router.post("", status_code=201)
async def create_team(body: TeamCreate, actor: str = "admin") -> dict[str, Any]:
    row = await fetch_one(
        """
        INSERT INTO teams (name, description, budget_usd, rate_limit_rpm, models)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, name, budget_usd, rate_limit_rpm, models
        """,
        (body.name, body.description, body.budget_usd, body.rate_limit_rpm, body.models),
    )
    await audit.log(actor, "team.created", "team", row["id"], {"name": body.name, "budget": body.budget_usd})
    return row


@router.patch("/{team_id}")
async def update_team(team_id: str, body: TeamUpdate, actor: str = "admin") -> dict[str, Any]:
    existing = await fetch_one("SELECT * FROM teams WHERE id=%s", (team_id,))
    if not existing:
        raise HTTPException(404, "team not found")
    fields: list[str] = []
    params: list[Any] = []
    for key in ("description", "budget_usd", "rate_limit_rpm", "models"):
        val = getattr(body, key)
        if val is not None:
            fields.append(f"{key}=%s")
            params.append(val)
    if not fields:
        return existing
    params.append(team_id)
    await execute(f"UPDATE teams SET {', '.join(fields)}, updated_at=now() WHERE id=%s", tuple(params))
    await audit.log(actor, "team.updated", "team", team_id, {"changed": fields})
    return await fetch_one("SELECT * FROM teams WHERE id=%s", (team_id,))


@router.post("/budget-check")
async def budget_check(body: BudgetCheck) -> dict[str, Any]:
    """Check whether a team has budget left for an estimated call cost."""
    team = await fetch_one(
        "SELECT id, name, budget_usd FROM teams WHERE id=%s", (body.team_id,)
    )
    if not team:
        raise HTTPException(404, "team not found")
    spent = await fetch_one(
        "SELECT COALESCE(SUM(cost_usd),0) AS spent FROM usage WHERE team_id=%s",
        (body.team_id,),
    )
    remaining = float(team["budget_usd"]) - float(spent["spent"])
    allowed = remaining >= body.estimated_cost_usd
    if not allowed:
        await audit.log(
            "system", "budget.blocked", "team", body.team_id,
            {"estimated": body.estimated_cost_usd, "remaining": remaining},
        )
    return {
        "team_id": body.team_id,
        "budget_usd": float(team["budget_usd"]),
        "spent_usd": float(spent["spent"]),
        "remaining_usd": round(remaining, 4),
        "allowed": allowed,
    }


@router.get("/{team_id}/usage")
async def team_usage(team_id: str) -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT model, SUM(prompt_tokens) AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens,
               SUM(cost_usd) AS cost_usd,
               COUNT(*) AS calls
        FROM usage WHERE team_id=%s
        GROUP BY model ORDER BY cost_usd DESC
        """,
        (team_id,),
    )