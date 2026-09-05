"""Tests for the CLI entrypoint — validation errors, exit codes, and a
successful offline run (no Ollama required).
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense import cli  # noqa: E402
from minisense.config import get_settings  # noqa: E402
from minisense.data_loader import load_responses  # noqa: E402

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
    load_responses.cache_clear()
    get_settings.cache_clear()
    yield
    load_responses.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def survey_path(tmp_path, monkeypatch):
    path = tmp_path / "survey.json"
    path.write_text(json.dumps({"responses": [VALID_RECORD]}), encoding="utf-8")
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", str(path))
    return path


def test_empty_question_returns_exit_code_1(capsys, survey_path):
    exit_code = cli.main(["   "])
    assert exit_code == 1
    assert "Error" in capsys.readouterr().err


def test_oversized_question_returns_exit_code_1(monkeypatch, capsys, survey_path):
    monkeypatch.setenv("API_MAX_QUESTION_CHARS", "20")
    get_settings.cache_clear()
    exit_code = cli.main(["x" * 100])
    assert exit_code == 1
    assert "exceeds" in capsys.readouterr().err


def test_successful_run_prints_answer_and_returns_zero(capsys, survey_path):
    with patch("minisense.cli.is_available", return_value=False):
        exit_code = cli.main(["What is our overall CSAT?"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "ANSWER:" in out
    assert "QUESTION: What is our overall CSAT?" in out


def test_trace_flag_prints_json_trace(capsys, survey_path):
    with patch("minisense.cli.is_available", return_value=False):
        exit_code = cli.main(["--trace", "What is our overall CSAT?"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "FULL TRACE (JSON):" in out
    trace_json = out.split("FULL TRACE (JSON):")[1].strip()
    parsed = json.loads(trace_json)
    assert isinstance(parsed, list)
    assert any(step["agent"] == "DataAgent" for step in parsed)


def test_missing_survey_data_returns_exit_code_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", str(tmp_path / "missing.json"))
    with patch("minisense.cli.is_available", return_value=False):
        exit_code = cli.main(["What is our overall CSAT?"])
    assert exit_code == 1
    assert "No survey data" in capsys.readouterr().err
