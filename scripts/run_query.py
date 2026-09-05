"""Convenience wrapper equivalent to `python -m minisense.cli`, kept here so
everything runnable lives under scripts/ for anyone browsing the repo.

Usage: python scripts/run_query.py "your question" [--trace]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
