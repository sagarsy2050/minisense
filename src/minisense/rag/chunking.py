"""Chunking strategy for the FAQ document.

Strategy chosen: **sentence-aware chunking with overlap**, not fixed-size
character windows. Justification (also in the README):

- The FAQ is short (~500 words) and structured as Q/A pairs under markdown
  headings. A fixed-size window would frequently split a question from its
  answer mid-sentence, which is exactly the unit a business question needs
  retrieved whole.
- We chunk on paragraph boundaries first (blank-line separated — which in
  this doc means one Q/A pair each), then only fall back to sentence-level
  splitting if a paragraph exceeds CHUNK_MAX_CHARS, so a Q/A pair almost
  always survives as a single chunk.
- A small character overlap is kept between adjacent chunks purely as a
  safety net for the fallback path, so a sentence split right at a chunk
  boundary doesn't lose context on either side.
- Semantic chunking (embedding-similarity-based splits) was considered but
  is overkill for a document this small and structured; it would add
  latency and complexity without changing retrieval quality here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from minisense.config import CHUNK_MAX_CHARS, CHUNK_OVERLAP_CHARS

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    heading: str  # nearest markdown heading, for a bit of extra context


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _pack_sentences(sentences: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        candidate = (current + " " + sent).strip() if current else sent
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = (tail + " " + sent).strip()
        else:
            # single sentence longer than max_chars — keep it whole anyway
            chunks.append(sent)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap_chars: int = CHUNK_OVERLAP_CHARS) -> list[Chunk]:
    lines = text.splitlines()
    paragraphs: list[tuple[str, str]] = []  # (heading, paragraph_text)
    current_heading = "Introduction"
    buf: list[str] = []

    def flush():
        if buf:
            para = " ".join(buf).strip()
            if para:
                paragraphs.append((current_heading, para))
            buf.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            current_heading = stripped.lstrip("#").strip()
            continue
        if not stripped:
            flush()
            continue
        buf.append(stripped)
    flush()

    chunks: list[Chunk] = []
    idx = 0
    for heading, para in paragraphs:
        if len(para) <= max_chars:
            pieces = [para]
        else:
            pieces = _pack_sentences(_split_sentences(para), max_chars, overlap_chars)
        for piece in pieces:
            idx += 1
            chunks.append(Chunk(chunk_id=f"chunk_{idx:03d}", text=piece, heading=heading))
    return chunks
