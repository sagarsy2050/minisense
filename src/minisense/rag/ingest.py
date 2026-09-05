"""Build the local vector index from the FAQ document."""
from __future__ import annotations

from pathlib import Path

from minisense.config import EMBEDDING, FAQ_PATH
from minisense.rag.chunking import chunk_markdown
from minisense.rag.embeddings import embed_texts
from minisense.rag.vector_store import VectorStore


def build_index(faq_path: Path = FAQ_PATH) -> VectorStore:
    text = faq_path.read_text(encoding="utf-8")
    chunks = chunk_markdown(text)
    vectors = embed_texts([c.text for c in chunks])
    store = VectorStore(dim=vectors.shape[1] or EMBEDDING.dim)
    store.add(chunks, vectors)
    return store


def main() -> None:
    store = build_index()
    store.save()
    print(f"Indexed {len(store.chunks)} chunks from {FAQ_PATH} -> storage/")


if __name__ == "__main__":
    main()
