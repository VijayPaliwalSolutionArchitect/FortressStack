"""RAG API — corpora management, document upload + ingestion, and retrieval.

This is the admin backend's RAG-ingestion surface: upload documents, trigger
the ingestion pipeline, list corpus contents, and query a corpus.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core import audit
from app.core.config import config
from app.core.db import execute, fetch_all, fetch_one
from app.rag.engine import ingest_document, retrieve

router = APIRouter()


class CorpusCreate(BaseModel):
    team_id: str
    name: str = Field(min_length=1)
    description: str = ""


class RetrieveRequest(BaseModel):
    corpus_id: str
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    threshold: float | None = Field(default=None, ge=0, le=1)


# ---------------------------------------------------------------------------
# Corpora
# ---------------------------------------------------------------------------


@router.get("/corpora")
async def list_corpora() -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT c.id, c.team_id, c.name, c.description, c.embedding_model,
               c.created_at, t.name AS team_name,
               (SELECT COUNT(*) FROM documents d WHERE d.corpus_id = c.id) AS document_count
        FROM corpora c JOIN teams t ON t.id = c.team_id
        ORDER BY c.created_at DESC
        """
    )


@router.post("/corpora", status_code=201)
async def create_corpus(body: CorpusCreate, actor: str = "admin") -> dict[str, Any]:
    row = await fetch_one(
        """
        INSERT INTO corpora (team_id, name, description)
        VALUES (%s, %s, %s)
        RETURNING id, team_id, name, description
        """,
        (body.team_id, body.name, body.description),
    )
    await audit.log(actor, "corpus.created", "corpus", row["id"], {"name": body.name})
    return row


# ---------------------------------------------------------------------------
# Documents & ingestion
# ---------------------------------------------------------------------------


@router.get("/corpora/{corpus_id}/documents")
async def list_documents(corpus_id: str) -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT id, filename, mime_type, size_bytes, status, chunk_count, error, created_at
        FROM documents WHERE corpus_id=%s ORDER BY created_at DESC
        """,
        (corpus_id,),
    )


@router.post("/corpora/{corpus_id}/documents", status_code=201)
async def upload_document(
    corpus_id: str,
    file: UploadFile = File(...),
    actor: str = "admin",
) -> dict[str, Any]:
    """Upload a document and run the ingestion pipeline synchronously."""
    if file.content_type not in config.rag.allowed_mimes:
        raise HTTPException(415, f"unsupported file type: {file.content_type}")

    # Enforce size limit.
    upload_dir = Path(config.rag.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name  # strip path traversal
    dest = upload_dir / f"{uuid.uuid4().hex}_{safe_name}"

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > config.rag.max_file_mb * 1024 * 1024:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"file exceeds {config.rag.max_file_mb}MB limit")
            out.write(chunk)

    try:
        result = await ingest_document(
            corpus_id, safe_name, file.content_type, str(dest), actor=actor
        )
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"ingestion failed: {exc}") from exc


@router.post("/retrieve")
async def retrieve_chunks(body: RetrieveRequest) -> dict[str, Any]:
    """Retrieve top-k relevant chunks for a query within a corpus (cited RAG)."""
    corpus = await fetch_one("SELECT id FROM corpora WHERE id=%s", (body.corpus_id,))
    if not corpus:
        raise HTTPException(404, "corpus not found")
    results = await retrieve(
        body.corpus_id, body.query, top_k=body.top_k, threshold=body.threshold
    )
    return {"corpus_id": body.corpus_id, "query": body.query, "results": results}