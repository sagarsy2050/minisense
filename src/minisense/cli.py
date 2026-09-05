"""CLI entrypoint.

Usage:
    python -m minisense.cli "What are the top 3 complaints this month and how do they compare to last month?"
    python -m minisense.cli --trace "..."     # also print the full structured agent trace as JSON

Exit codes: 0 on success, 1 on an expected MiniSense error (bad input,
missing data, etc. — see minisense.exceptions), 2 on an unexpected
exception (a real bug — the full traceback is printed to help debugging).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from minisense.agents.orchestrator import answer_question
from minisense.data_loader import load_responses
from minisense.exceptions import MiniSenseError
from minisense.llm.ollama_client import is_available
from minisense.logging_config import configure_logging, get_logger
from minisense.validation import validate_question

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask MiniSense a business question about survey feedback.")
    parser.add_argument("question", type=str, help="natural language business question")
    parser.add_argument("--trace", action="store_true", help="print the full structured agent trace as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _build_parser().parse_args(argv)

    try:
        question = validate_question(args.question)

        if not is_available():
            logger.warning(
                "Ollama not reachable — running in offline heuristic/template mode. "
                "Start `ollama serve` (and pull the configured models) for full LLM-driven "
                "planning and narrative generation."
            )

        responses = load_responses()
        run = answer_question(question, responses)
    except MiniSenseError as exc:
        logger.error(str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception:
        logger.exception("Unexpected error while answering the question")
        print("Error: an unexpected error occurred. See logs for details.", file=sys.stderr)
        return 2

    print("=" * 80)
    print("QUESTION:", question)
    print("=" * 80)
    print("\nPLAN:")
    print(f"  reasoning: {run.plan.reasoning}")
    for t in run.plan.tasks:
        print(f"  -> {t.agent.value}: {t.objective}")

    print("\nANSWER:\n")
    print(run.summary.narrative)

    if args.trace:
        print("\n" + "=" * 80)
        print("FULL TRACE (JSON):")
        print(json.dumps([asdict(log) for log in run.trace], indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
