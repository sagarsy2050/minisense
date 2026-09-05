"""Local vector store for the FAQ chunks.

Backed by FAISS (``IndexFlatIP`` over L2-normalized vectors, i.e. cosine
similarity) when the ``faiss`` package is available. Falls back to a plain
NumPy brute-force search otherwise — the FAQ corpus is a few dozen chunks,
so brute force is instant either way; FAISS is used because the assignment
names it explicitly and because it's the right choice once the corpus
grows beyond a toy size.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from minisense.config import FAISS_INDEX_PATH, FAISS_META_PATH
from minisense.rag.chunking import Chunk

try:
    import faiss

    _HAS_FAISS = True
except ImportError:  # pragma: no cover - exercised only when faiss isn't installed
    _HAS_FAISS = False


class VectorStore:
    def __init__(self, dim: int):
        self.dim = dim
        self.chunks: list[Chunk] = []
        # Typed loosely (faiss.Index, not the narrower IndexFlatIP) because
        # VectorStore.load() may assign back whatever concrete Index subclass
        # faiss.read_index() returns for a persisted index.
        self._index: Any | None = faiss.IndexFlatIP(dim) if _HAS_FAISS else None
        self._matrix: np.ndarray | None = None  # fallback storage

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        assert vectors.shape[0] == len(chunks)
        assert vectors.shape[1] == self.dim
        self.chunks.extend(chunks)
        if _HAS_FAISS:
            assert self._index is not None  # guaranteed by _HAS_FAISS, narrows for mypy
            self._index.add(vectors)
        else:
            self._matrix = vectors if self._matrix is None else np.vstack([self._matrix, vectors])

    def search(self, query_vec: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        top_k = min(top_k, len(self.chunks))
        if _HAS_FAISS:
            assert self._index is not None
            scores, idxs = self._index.search(query_vec.reshape(1, -1), top_k)
            pairs = list(zip(idxs[0], scores[0], strict=True))
        else:
            assert self._matrix is not None  # add() must be called before search()
            sims = self._matrix @ query_vec  # cosine, since both are L2-normalized
            top_idx = np.argsort(-sims)[:top_k]
            pairs = [(i, float(sims[i])) for i in top_idx]
        return [(self.chunks[i], float(s)) for i, s in pairs if i != -1]

    def save(self, index_path: Path = FAISS_INDEX_PATH, meta_path: Path = FAISS_META_PATH) -> None:
        meta = {"dim": self.dim, "chunks": [asdict(c) for c in self.chunks], "backend": "faiss" if _HAS_FAISS else "numpy"}
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        if _HAS_FAISS:
            assert self._index is not None
            faiss.write_index(self._index, str(index_path))
        else:
            assert self._matrix is not None  # add() must be called before save()
            np.save(str(index_path) + ".npy", self._matrix)

    @classmethod
    def load(cls, index_path: Path = FAISS_INDEX_PATH, meta_path: Path = FAISS_META_PATH) -> VectorStore:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        store = cls(dim=meta["dim"])
        store.chunks = [Chunk(**c) for c in meta["chunks"]]
        if meta["backend"] == "faiss" and _HAS_FAISS:
            store._index = faiss.read_index(str(index_path))
        else:
            store._matrix = np.load(str(index_path) + ".npy")
        return store
