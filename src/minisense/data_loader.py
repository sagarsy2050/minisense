"""Loads and validates the survey dataset, then caches it in memory.

This is the schema-validation boundary for the whole system: every record
is checked against ``SurveyResponseRecord`` (date parses, rating is 1-5,
required fields are non-blank) before anything downstream ever sees it, so
a malformed record fails loudly and specifically here rather than silently
skewing a metric three modules away. Records that fail validation are
skipped (and logged), not fatal, unless *every* record fails.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from minisense.config import get_settings
from minisense.exceptions import DataLoadError
from minisense.logging_config import get_logger
from minisense.schemas import SurveyResponseRecord

logger = get_logger(__name__)

_MAX_LOGGED_ERRORS = 5


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DataLoadError(
            f"No survey data at {path}. Run `python data/generate_data.py` first."
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataLoadError(f"Could not read survey data at {path}: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"Survey data at {path} is not valid JSON: {exc}") from exc


def _validate_records(raw_responses: list[Any], path: Path) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    error_summaries: list[str] = []

    for i, raw in enumerate(raw_responses):
        try:
            record = SurveyResponseRecord.model_validate(raw)
        except PydanticValidationError as exc:
            response_id = raw.get("response_id", "?") if isinstance(raw, dict) else "?"
            error_summaries.append(f"record #{i} (response_id={response_id}): {exc.error_count()} error(s)")
            continue
        validated.append(record.model_dump(mode="json"))

    if error_summaries:
        shown = "; ".join(error_summaries[:_MAX_LOGGED_ERRORS])
        more = f" (+{len(error_summaries) - _MAX_LOGGED_ERRORS} more)" if len(error_summaries) > _MAX_LOGGED_ERRORS else ""
        logger.warning(
            f"Skipped {len(error_summaries)} invalid survey record(s) out of "
            f"{len(raw_responses)} in {path}: {shown}{more}"
        )

    if not validated:
        raise DataLoadError(
            f"No valid survey records found in {path} "
            f"(all {len(raw_responses)} record(s) failed validation)."
        )

    return validated


@lru_cache(maxsize=1)
def load_responses() -> list[dict[str, Any]]:
    """Load, validate, and cache the survey dataset for this process.

    Cached with ``lru_cache`` because the dataset is large (tens of
    thousands of records) and read-only for the lifetime of a process —
    re-parsing and re-validating it on every question would be wasted work.
    Call ``load_responses.cache_clear()`` (tests do this) to force a reload.
    """
    survey_path = get_settings().survey_json_path
    payload = _read_json(survey_path)

    raw_responses = payload.get("responses")
    if not isinstance(raw_responses, list):
        raise DataLoadError(
            f"Survey data at {survey_path} is missing a top-level 'responses' list."
        )
    if not raw_responses:
        raise DataLoadError(f"Survey data at {survey_path} has an empty 'responses' list.")

    validated = _validate_records(raw_responses, survey_path)
    logger.info(
        f"Loaded {len(validated)} valid survey response(s) from {survey_path} "
        f"({len(raw_responses) - len(validated)} skipped)"
    )
    return validated
