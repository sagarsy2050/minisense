"""Tests for configuration loading and validation.

These construct ``Settings`` directly (not the cached ``get_settings()``)
so each test gets an isolated instance reflecting only the env vars it sets.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.config import Environment, LogLevel, Settings  # noqa: E402


def test_defaults_are_valid(monkeypatch):
    monkeypatch.delenv("MINISENSE_ENV", raising=False)
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    settings = Settings(_env_file=None)
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.log_level == LogLevel.INFO
    assert settings.llm_model == "llama3.1:8b"
    assert settings.chunk_overlap_chars < settings.chunk_max_chars


def test_production_requires_auth_token(monkeypatch):
    monkeypatch.setenv("MINISENSE_ENV", "production")
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="API_AUTH_TOKEN must be set"):
        Settings(_env_file=None)


def test_production_with_auth_token_succeeds(monkeypatch):
    monkeypatch.setenv("MINISENSE_ENV", "production")
    monkeypatch.setenv("API_AUTH_TOKEN", "a-real-secret-token")
    settings = Settings(_env_file=None)
    assert settings.is_production
    assert settings.api_auth_token.get_secret_value() == "a-real-secret-token"


def test_overlap_must_be_smaller_than_chunk_size(monkeypatch):
    monkeypatch.setenv("MINISENSE_CHUNK_MAX_CHARS", "100")
    monkeypatch.setenv("MINISENSE_CHUNK_OVERLAP_CHARS", "200")
    with pytest.raises(ValueError, match="must be smaller than"):
        Settings(_env_file=None)


def test_relative_paths_resolve_to_repo_root(monkeypatch):
    monkeypatch.setenv("MINISENSE_SURVEY_PATH", "data/custom.json")
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    settings = Settings(_env_file=None)
    assert settings.survey_json_path.is_absolute()
    assert settings.survey_json_path.name == "custom.json"


def test_cors_origins_list_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("API_CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_cors_origins_empty_by_default(monkeypatch):
    monkeypatch.delenv("API_CORS_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.cors_origins_list == []


@pytest.mark.parametrize("bad_value", ["-1", "0", "601"])
def test_llm_timeout_out_of_range_is_rejected(monkeypatch, bad_value):
    monkeypatch.setenv("MINISENSE_LLM_TIMEOUT", bad_value)
    with pytest.raises(ValueError):
        Settings(_env_file=None)
