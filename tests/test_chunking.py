import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.rag.chunking import chunk_markdown  # noqa: E402

SAMPLE_MD = """# Section One

**Q: What is X?**
A: X is a short answer.

**Q: What is Y?**
A: Y is also a fairly short answer that stays under the char limit.

# Section Two

**Q: What is Z?**
A: """ + ("Z requires a much longer explanation. " * 20)


def test_chunks_are_nonempty_and_within_bounds():
    chunks = chunk_markdown(SAMPLE_MD, max_chars=200, overlap_chars=40)
    assert len(chunks) >= 3
    for c in chunks:
        assert c.text.strip()
        assert c.chunk_id


def test_short_paragraph_stays_one_chunk():
    chunks = chunk_markdown(SAMPLE_MD, max_chars=200, overlap_chars=40)
    joined = [c.text for c in chunks]
    assert any("X is a short answer" in t for t in joined)


def test_long_paragraph_gets_split():
    chunks = chunk_markdown(SAMPLE_MD, max_chars=200, overlap_chars=40)
    z_chunks = [c for c in chunks if "Z requires" in c.text or "much longer" in c.text]
    assert len(z_chunks) >= 2  # the long paragraph should not fit in a single 200-char chunk
