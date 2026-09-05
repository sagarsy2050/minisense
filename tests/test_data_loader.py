"""Tests for the survey-data loading and validation boundary."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.config import get_settings  # noqa: E402
from minisense.data_loader import load_responses  # noqa: E402
from minisense.exceptions import DataLoadError  # noqa: E402

VALID_RECORD = {
    "response_id": "r1",
    "date": "2026-05-14",
    "business_id": "b01",
    "business_name": "QuickFit Gym",
    "survey_id": "s01",
    "survey_name": "Membership Value",
    "rating": 4,
    "response_channel": "mobile",
    "free_text": "The food was great but the wait time was too long.",
}


@pytest.fixture(autouse=True)
def _clear_caches():
    """Every test gets a fresh load_responses() and Settings() cache, since
    both are process-wide lru_cache singletons that would otherwise leak
    state (and the wrong survey path) between tests."""
    load_responses.cache_clear()
    get_settings.cache_clear()
    yield
    load_responses.cache_clear()
    get_settings.cache_clear()


def _write_survey(tmp_path: Path, records: list[dict], monkeypatch) -> Path:
    path = tmp_path / "survey.json"
    path.write_text(json.dumps({"responses": records}), encoding="utf-8")
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", str(path))
    return path


def test_loads_valid_records(tmp_path, monkeypatch):
    _write_survey(tmp_path, [VALID_RECORD], monkeypatch)
    responses = load_responses()
    assert len(responses) == 1
    assert responses[0]["response_id"] == "r1"
    assert responses[0]["date"] == "2026-05-14"


def test_missing_file_raises_data_load_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", str(tmp_path / "does_not_exist.json"))
    with pytest.raises(DataLoadError, match="No survey data at"):
        load_responses()


def test_malformed_json_raises_data_load_error(tmp_path, monkeypatch):
    path = tmp_path / "survey.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", str(path))
    with pytest.raises(DataLoadError, match="not valid JSON"):
        load_responses()


def test_missing_responses_key_raises_data_load_error(tmp_path, monkeypatch):
    path = tmp_path / "survey.json"
    path.write_text(json.dumps({"not_responses": []}), encoding="utf-8")
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", str(path))
    with pytest.raises(DataLoadError, match="missing a top-level 'responses' list"):
        load_responses()


def test_invalid_records_are_skipped_not_fatal(tmp_path, monkeypatch):
    bad_date = {**VALID_RECORD, "response_id": "r2", "date": "not-a-date"}
    bad_rating = {**VALID_RECORD, "response_id": "r3", "rating": 9}
    blank_id = {**VALID_RECORD, "response_id": "  "}
    _write_survey(tmp_path, [VALID_RECORD, bad_date, bad_rating, blank_id], monkeypatch)
    responses = load_responses()
    assert len(responses) == 1
    assert responses[0]["response_id"] == "r1"


def test_all_records_invalid_raises_data_load_error(tmp_path, monkeypatch):
    bad_rating = {**VALID_RECORD, "rating": 0}
    _write_survey(tmp_path, [bad_rating], monkeypatch)
    with pytest.raises(DataLoadError, match="failed validation"):
        load_responses()


def test_empty_responses_list_raises_data_load_error(tmp_path, monkeypatch):
    _write_survey(tmp_path, [], monkeypatch)
    with pytest.raises(DataLoadError, match="empty 'responses' list"):
        load_responses()


def test_free_text_is_optional_and_defaults_to_empty(tmp_path, monkeypatch):
    record = {k: v for k, v in VALID_RECORD.items() if k != "free_text"}
    _write_survey(tmp_path, [record], monkeypatch)
    responses = load_responses()
    assert responses[0]["free_text"] == ""
