"""FortressStack admin backend — FastAPI application entrypoint.

Lifespan:
    - initialises the DB connection pool,
    - applies the schema (idempotent),
    - seeds default settings & a default team,
    - wires the API router and health endpoint.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import config
from app.core.db import close_pool, execute, fetch_one, init_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fortress")


async def _apply_schema() -> None:
    """Apply db/schema.sql idempotently (CREATE IF NOT EXISTS everywhere)."""
    from pathlib import Path

    # admin-backend/app/main.py -> parents[0]=app, [1]=admin-backend, [2]=project root
    schema_path = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
    if not schema_path.exists():
        logger.warning("schema.sql not found at %s — skipping", schema_path)
        return
    sql = schema_path.read_text(encoding="utf-8")
    async with __import__("app.core.db", fromlist=["get_conn"]).get_conn() as conn:
        async with conn.cursor() as cur:
            # Split on ';' respecting that statements are simple here.
            for stmt in sql.split(";"):
                if stmt.strip():
                    await cur.execute(stmt)
        await conn.commit()
    logger.info("schema applied")


async def _seed_defaults() -> None:
    """Seed a default team and core settings if absent."""
    team = await fetch_one("SELECT id FROM teams LIMIT 1")
    if not team:
        await execute(
            """
            INSERT INTO teams (name, description, budget_usd, rate_limit_rpm, models)
            VALUES ('Default', 'Default team seeded at first boot', 50, 60, '["llama3.1:8b"]')
            """
        )
        logger.info("seeded default team")
    for key, value, desc in [
        ("rag.chunk_size", config.rag.chunk_size, "RAG chunk size (tokens)"),
        ("rag.top_k", config.rag.top_k, "RAG retrieval top-k"),
        ("local_mode", config.local_mode, "Local-mode egress proof on/off"),
        ("backup.schedule_cron", config.backup.schedule_cron, "Nightly backup cron"),
    ]:
        existing = await fetch_one("SELECT key FROM settings WHERE key=%s", (key,))
        if not existing:
            await execute(
                "INSERT INTO settings (key, value, description) VALUES (%s, %s::jsonb, %s)",
                (key, f'"{value}"', desc),
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    await _apply_schema()
    await _seed_defaults()
    logger.info("FortressStack admin backend ready (env=%s, local_mode=%s)",
                config.environment, config.local_mode)
    yield
    await close_pool()


app = FastAPI(
    title="FortressStack Admin API",
    version="1.0.0",
    description="Private AI Workspace & LLM Gateway — admin backend for teams, "
                "budgets, models, RAG ingestion, settings and audit.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production (see docs/DEPLOYMENT.md)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {
        "status": "ok",
        "app": config.app_name,
        "environment": config.environment,
        "local_mode": config.local_mode,
    }


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"app": config.app_name, "docs": "/docs", "health": "/health"}