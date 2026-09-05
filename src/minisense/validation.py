"""Input validation shared by the CLI and the API.

Kept as one function so both entrypoints reject the same malformed input
the same way, instead of the API and CLI silently drifting apart.
"""
from __future__ import annotations

from minisense.config import get_settings
from minisense.exceptions import InvalidQuestionError


def validate_question(question: str) -> str:
    """Validate and normalize a business question.

    Guards against the obvious bad inputs before they reach the LLM: empty
    input, and pathologically long input (which would otherwise be
    forwarded as-is into an Ollama prompt — wasted local compute at best,
    an attempted prompt-injection/DoS payload at worst).
    """
    if question is None:
        raise InvalidQuestionError("question must not be null.")

    normalized = question.strip()
    if not normalized:
        raise InvalidQuestionError("question must not be empty.")

    max_len = get_settings().api_max_question_chars
    if len(normalized) > max_len:
        raise InvalidQuestionError(
            f"question is {len(normalized)} characters, which exceeds the "
            f"{max_len}-character limit (API_MAX_QUESTION_CHARS)."
        )

    return normalized
