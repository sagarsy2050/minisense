"""Convenience wrapper: `python scripts/ingest_faq.py` builds the FAQ vector index."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.rag.ingest import main  # noqa: E402

if __name__ == "__main__":
    main()
