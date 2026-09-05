"""Top-k retrieval over the persisted FAQ vector store."""
from __future__ import annotations

from pathlib import Path

from minisense.config import FAISS_INDEX_PATH, FAISS_META_PATH, TOP_K_DEFAULT
from minisense.exceptions import IndexNotFoundError
from minisense.rag.embeddings import embed_query
from minisense.rag.vector_store import VectorStore
from minisense.schemas import RetrievedChunk

_store: VectorStore | None = None


def _index_exists() -> bool:
    return FAISS_INDEX_PATH.exists() or Path(str(FAISS_INDEX_PATH) + ".npy").exists()


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        if not _index_exists():
            raise IndexNotFoundError(
                "No FAQ index found. Run `python -m minisense.rag.ingest` "
                "(or `python scripts/ingest_faq.py`) first."
            )
        _store = VectorStore.load(FAISS_INDEX_PATH, FAISS_META_PATH)
    return _store


def retrieve(query: str, top_k: int = TOP_K_DEFAULT) -> list[RetrievedChunk]:
    store = _get_store()
    qvec = embed_query(query)
    results = store.search(qvec, top_k)
    return [RetrievedChunk(chunk_id=c.chunk_id, text=c.text, score=score) for c, score in results]
