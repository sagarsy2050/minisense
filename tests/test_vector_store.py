"""Vector-store tests using synthetic vectors — these don't touch Ollama
or the network, since actual embeddings require a running local model.
They validate the add/search/save/load contract that rag/retrieve.py and
rag/ingest.py depend on.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.rag.chunking import Chunk  # noqa: E402
from minisense.rag.vector_store import VectorStore  # noqa: E402


def _unit(vec: np.ndarray) -> np.ndarray:
    return vec / np.linalg.norm(vec)


def _sample_store() -> VectorStore:
    dim = 8
    chunks = [
        Chunk(chunk_id="chunk_001", text="wait time policy", heading="Wait Times"),
        Chunk(chunk_id="chunk_002", text="CSAT target", heading="Quality"),
        Chunk(chunk_id="chunk_003", text="menu items", heading="Menu"),
    ]
    rng = np.random.default_rng(0)
    base = rng.random((3, dim)).astype("float32")
    vectors = np.array([_unit(v) for v in base], dtype="float32")
    store = VectorStore(dim=dim)
    store.add(chunks, vectors)
    return store, vectors


def test_search_returns_exact_match_as_top_hit():
    store, vectors = _sample_store()
    # Querying with the exact stored vector for chunk_002 should return it first.
    query = vectors[1]
    results = store.search(query, top_k=2)
    assert results[0][0].chunk_id == "chunk_002"
    assert len(results) == 2


def test_search_caps_top_k_to_corpus_size():
    store, vectors = _sample_store()
    results = store.search(vectors[0], top_k=100)
    assert len(results) == 3  # only 3 chunks exist


def test_save_and_load_roundtrip(tmp_path):
    store, _ = _sample_store()
    index_path = tmp_path / "idx.faiss"
    meta_path = tmp_path / "idx.meta.json"
    store.save(index_path, meta_path)

    loaded = VectorStore.load(index_path, meta_path)
    assert len(loaded.chunks) == 3
    assert {c.chunk_id for c in loaded.chunks} == {"chunk_001", "chunk_002", "chunk_003"}

    results = loaded.search(loaded.chunks and _unit(np.ones(store.dim, dtype="float32")), top_k=1)
    assert len(results) == 1
