"""Embedding wrapper — routes through the local Ollama server.

Uses Ollama's own embedding models (default: ``nomic-embed-text``) rather
than a separate sentence-transformers/HuggingFace download. This keeps the
entire system — planning, summarization, *and* retrieval — on one local
runtime with zero external API calls: `ollama pull nomic-embed-text` once,
and everything after that is fully offline.
"""
from __future__ import annotations

import numpy as np

from minisense.llm import ollama_client


def embed_texts(texts: list[str]) -> np.ndarray:
    """Returns an (N, dim) float32, L2-normalized embedding matrix.

    Raises ``ollama_client.OllamaUnavailableError`` if the Ollama server
    isn't reachable or the embedding model hasn't been pulled — callers
    (``rag.ingest``, ``rag.retrieve``) let that propagate, since there is
    no meaningful offline fallback for vector search itself.
    """
    raw = ollama_client.embed(texts)
    vecs = np.array(raw, dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]
