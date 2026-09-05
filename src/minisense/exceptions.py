"""MiniSense's exception hierarchy.

Every error the system raises on purpose (as opposed to a genuine bug)
inherits from ``MiniSenseError``, so callers — the CLI, the FastAPI
exception handlers, tests — can catch "an expected MiniSense failure" as
one type instead of guessing between ``FileNotFoundError``, ``ValueError``,
``RuntimeError``, etc. scattered across modules.
"""
from __future__ import annotations


class MiniSenseError(Exception):
    """Base class for all expected MiniSense errors."""


class ConfigurationError(MiniSenseError):
    """Invalid or unsafe configuration (see ``minisense.config``)."""


class DataLoadError(MiniSenseError):
    """The survey dataset is missing, unreadable, or fails validation."""


class OllamaUnavailableError(MiniSenseError):
    """The local Ollama server could not be reached or returned an error."""


class IndexNotFoundError(MiniSenseError):
    """The FAQ vector index hasn't been built yet (see ``scripts/ingest_faq.py``)."""


class InvalidQuestionError(MiniSenseError):
    """The business question failed input validation (empty, too long, etc.)."""
