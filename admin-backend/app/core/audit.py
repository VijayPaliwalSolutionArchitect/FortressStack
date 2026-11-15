"""Immutable, append-only audit logger.

Every governed action (budget block, model change, document ingest, approval)
is recorded here. The log is append-only by design: there is no UPDATE path in
the schema, and the service exposes no delete/update endpoint. This is the
compliance proof FortressStack sells to legal/healthcare/finance clients.

Conventions
-----------
- `action` uses a dotted verb.noun form, e.g. ``budget.blocked``,
  ``model.updated``, ``document.ingested``.
- `actor` is the authenticated user, team, or "system".
- `detail` is a JSONB blob of extra context (never secrets).
"""

from __future__ import annotations

import json
from typing import Any

from app.core.db import execute


async def log(
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append one audit entry. Never raises on audit failure (best-effort)."""
    try:
        await execute(
            """
            INSERT INTO audit_log (actor, action, resource_type, resource_id, detail)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                actor,
                action,
                resource_type,
                resource_id,
                json.dumps(detail or {}),
            ),
        )
    except Exception:  # pragma: no cover - audit must not break the request
        # Log to stderr; the request proceeds. Audit is best-effort by design.
        import sys

        print(f"[audit] failed to write entry: {action}", file=sys.stderr)


async def query(
    limit: int = 100,
    offset: int = 0,
    actor: str | None = None,
    action: str | None = None,
) -> list[dict]:
    """Read audit entries, newest first, with optional filters."""
    from app.core.db import fetch_all

    where: list[str] = []
    params: list[Any] = []
    if actor:
        where.append("actor = %s")
        params.append(actor)
    if action:
        where.append("action = %s")
        params.append(action)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.extend([limit, offset])
    return await fetch_all(
        f"""
        SELECT id, actor, action, resource_type, resource_id, detail, created_at
        FROM audit_log
        {clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )