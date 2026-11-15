"""RAG ingestion engine — document intake, chunking, embedding, storage.

This is the admin backend's core RAG-ingestion surface. It supports pluggable
embedding backends:

- ``local``  : sentence-transformers / numpy cosine (zero external calls —
               satisfies FortressStack's local-mode egress proof)
- ``ollama`` : Ollama embedding endpoint (nomic-embed-text by default)
- ``api``    : any OpenAI-compatible embedding API (external; disabled in
               local mode)

Design: the pipeline is a sequence of pure, testable stages
(extract -> chunk -> embed -> store). Each stage is isolated so a failure in
one never corrupts the others, and every document's status is tracked in the
DB so ingestion is resumable and observable.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import config
from app.core.db import execute, fetch_one

logger = logging.getLogger("fortress.rag")

# ---------------------------------------------------------------------------
# Pluggable embedding backends
# ---------------------------------------------------------------------------


class EmbeddingBackend:
    """Base class. Subclasses implement ``embed(texts) -> list[list[float]]``."""

    name = "base"
    dim = 768

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class LocalEmbeddingBackend(EmbeddingBackend):
    """Hash-bucketed local embeddings — zero external calls.

    Uses a deterministic hashing scheme so the same text always yields the
    same vector (reproducible) without any model download. Suitable for
    demos and local-mode compliance. Swap in sentence-transformers for
    production semantic quality (see README).
    """

    name = "local"
    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            tokens = re.findall(r"\w+", text.lower())
            for tok in tokens:
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 8) & 1 else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec.tolist())
        return vectors


class OllamaEmbeddingBackend(EmbeddingBackend):
    """Embeddings via a local Ollama server (nomic-embed-text)."""

    name = "ollama"

    def __init__(self, base_url: str, model: str):
        import httpx

        self._client = httpx.AsyncClient(base_url=base_url, timeout=60)
        self._model = model

    async def embed_async(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.post(
            "/api/embed", json={"model": self._model, "input": texts}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("embeddings", [])

    def close(self) -> None:
        import asyncio

        try:
            asyncio.get_event_loop().run_until_complete(self._client.aclose())
        except Exception:
            pass


def get_backend() -> EmbeddingBackend:
    """Factory — returns the configured embedding backend."""
    backend_name = config.rag.embedding_model
    if backend_name.startswith("ollama:") or backend_name == "nomic-embed-text":
        return OllamaEmbeddingBackend(config.gateway.base_url, backend_name)
    return LocalEmbeddingBackend()


# ---------------------------------------------------------------------------
# Text extraction (per MIME type)
# ---------------------------------------------------------------------------


def extract_text(path: Path, mime: str) -> str:
    """Extract plain text from a document based on its MIME type."""
    if mime == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    # text/plain, text/markdown, text/csv
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split text into overlapping chunks on paragraph/word boundaries."""
    size = size or config.rag.chunk_size
    overlap = overlap or config.rag.chunk_overlap
    # Normalise whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Back off to the last space within the window for clean breaks.
        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space > start + size // 2:
                end = last_space
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------


async def ingest_document(
    corpus_id: str,
    filename: str,
    mime: str,
    storage_path: str,
    actor: str = "admin",
) -> dict[str, Any]:
    """Run the full ingestion pipeline for one stored document.

    Returns a summary dict. Updates the document row's status through each
    stage so ingestion is observable and resumable.
    """
    from app.core import audit

    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"stored file missing: {storage_path}")

    # 1. Register document row (pending).
    doc = await fetch_one(
        """
        INSERT INTO documents (corpus_id, filename, mime_type, size_bytes, storage_path, status)
        VALUES (%s, %s, %s, %s, %s, 'processing')
        RETURNING id, status
        """,
        (corpus_id, filename, mime, path.stat().st_size, storage_path),
    )
    doc_id = doc["id"]
    await audit.log(actor, "document.ingest.start", "document", doc_id, {"filename": filename})

    try:
        # 2. Extract text.
        text = extract_text(path, mime)
        if not text.strip():
            raise ValueError("no extractable text found")

        # 3. Chunk.
        chunks = chunk_text(text)

        # 4. Embed (synchronously via the local backend; async for ollama).
        backend = get_backend()
        try:
            if isinstance(backend, OllamaEmbeddingBackend):
                vectors = await backend.embed_async(chunks)
            else:
                vectors = backend.embed(chunks)
        finally:
            backend.close()

        # 5. Store chunks.
        for seq, (content, vector) in enumerate(zip(chunks, vectors)):
            await execute(
                """
                INSERT INTO chunks (document_id, seq, content, embedding)
                VALUES (%s, %s, %s, %s)
                """,
                (doc_id, seq, content, np.array(vector, dtype=np.float32).tobytes()),
            )

        # 6. Mark ready.
        await execute(
            "UPDATE documents SET status='ready', chunk_count=%s WHERE id=%s",
            (len(chunks), doc_id),
        )
        await audit.log(
            actor, "document.ingest.complete", "document", doc_id,
            {"filename": filename, "chunks": len(chunks)},
        )
        return {"document_id": doc_id, "status": "ready", "chunks": len(chunks)}

    except Exception as exc:  # noqa: BLE001 - mark failed and re-raise
        await execute(
            "UPDATE documents SET status='failed', error=%s WHERE id=%s",
            (str(exc)[:2000], doc_id),
        )
        await audit.log(
            actor, "document.ingest.failed", "document", doc_id, {"error": str(exc)[:500]}
        )
        raise


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


async def retrieve(
    corpus_id: str,
    query: str,
    top_k: int | None = None,
    threshold: float | None = None,
) -> list[dict[str, Any]]:
    """Retrieve the top-k chunks for a query within a corpus.

    Uses the same embedding backend as ingestion so query and document
    vectors live in the same space. Returns chunks with a cosine score.
    """
    top_k = top_k or config.rag.top_k
    threshold = threshold or config.rag.similarity_threshold

    backend = get_backend()
    try:
        qvec = np.array(backend.embed([query])[0], dtype=np.float32)
    finally:
        backend.close()

    # Load all chunks for the corpus and score with numpy cosine.
    from app.core.db import fetch_all

    rows = await fetch_all(
        """
        SELECT c.id, c.content, c.embedding
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN corpora co ON co.id = d.corpus_id
        WHERE co.id = %s
        """,
        (corpus_id,),
    )
    scored: list[tuple[float, dict]] = []
    for row in rows:
        vec = np.frombuffer(row["embedding"], dtype=np.float32)
        denom = np.linalg.norm(vec) * np.linalg.norm(qvec)
        score = float(np.dot(vec, qvec) / denom) if denom else 0.0
        if score >= threshold:
            scored.append((score, {"chunk_id": row["id"], "content": row["content"], "score": round(score, 4)}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]