"""Database connection pool (async psycopg3)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from psycopg_pool import AsyncConnectionPool

from app.core.config import config

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    """Create the global connection pool (idempotent)."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=config.database_url,
            min_size=1,
            max_size=10,
            open=False,
        )
        await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncIterator:
    """Yield a pooled connection (or a one-off if pool not initialised)."""
    if _pool is None:
        await init_pool()
    async with _pool.connection() as conn:  # type: ignore[union-attr]
        yield conn


async def fetch_one(sql: str, params: tuple | None = None) -> dict | None:
    """Run a query and return the first row as a dict."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params or ())
            row = await cur.fetchone()
            if row is None:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


async def fetch_all(sql: str, params: tuple | None = None) -> list[dict]:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params or ())
            rows = await cur.fetchall()
            cols = [d.name for d in cur.description] if cur.description else []
            return [dict(zip(cols, r)) for r in rows]


async def execute(sql: str, params: tuple | None = None) -> None:
    """Run a write query (commits on context exit)."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params or ())