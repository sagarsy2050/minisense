"""Structured logging setup.

Call ``configure_logging()`` once at process start (the CLI, API, and every
script under ``scripts/`` do this) and get module loggers everywhere else
with ``logging.getLogger(__name__)``. Log level comes from
``Settings.log_level`` (``MINISENSE_LOG_LEVEL``), so it's one env var to
turn on debug output anywhere, including inside a container.

Format is a single-line, greppable ``key=value`` style rather than free
text, so logs stay usable once they're flowing into `docker logs` or a log
aggregator instead of a developer's terminal.
"""
from __future__ import annotations

import logging
import sys

from minisense.config import get_settings

_CONFIGURED = False


class _KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = (
            f'ts={self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")} '
            f"level={record.levelname} "
            f"logger={record.name} "
            f'msg="{record.getMessage()}"'
        )
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def configure_logging(force: bool = False) -> None:
    """Idempotent: safe to call from multiple entrypoints/tests."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    settings = get_settings()
    root = logging.getLogger("minisense")
    root.setLevel(settings.log_level.value)
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_KeyValueFormatter())
    root.addHandler(handler)
    root.propagate = False

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
