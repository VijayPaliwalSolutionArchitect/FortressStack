"""Tests for the FortressStack RAG engine (pure logic, no DB required)."""

import numpy as np
import pytest

from app.rag.engine import LocalEmbeddingBackend, chunk_text


def test_chunk_text_small_text_single_chunk():
    assert chunk_text("hello world", size=100, overlap=10) == ["hello world"]


def test_chunk_text_empty():
    assert chunk_text("   ") == []


def test_chunk_text_overlap_preserved():
    text = "word " * 50
    chunks = chunk_text(text, size=40, overlap=10)
    assert len(chunks) > 1
    # Overlap means adjacent chunks share content.
    assert chunks[0].split()[-1] in chunks[1].split()[:3]


def test_chunk_text_no_oversized_chunk():
    text = "a" * 1000
    chunks = chunk_text(text, size=128, overlap=32)
    assert all(len(c) <= 128 for c in chunks)


def test_local_embedding_deterministic():
    be = LocalEmbeddingBackend()
    a = be.embed(["private AI workspace"])[0]
    b = be.embed(["private AI workspace"])[0]
    assert np.allclose(a, b)


def test_local_embedding_semantic_separation():
    be = LocalEmbeddingBackend()
    same = be.embed(["governed private AI workspace for legal firms"])[0]
    same2 = be.embed(["governed private AI workspace for legal firms"])[0]
    diff = be.embed(["pizza toppings and weather forecast"])[0]
    sim_same = float(np.dot(same, same2))
    sim_diff = float(np.dot(same, diff))
    assert sim_same > 0.99
    assert sim_diff < sim_same


def test_local_embedding_unit_norm():
    be = LocalEmbeddingBackend()
    vec = be.embed(["some text"])[0]
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-6