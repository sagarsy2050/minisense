"""Tests for the FastAPI wrapper: auth, validation, rate limiting, health.

These monkeypatch environment variables *before* importing minisense.api,
since the module builds its FastAPI app (and bakes in a couple of settings,
like the auth token and question length limit) at import time.
"""
import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _fresh_api_module(monkeypatch, **env):
    """Reload minisense.config and minisense.api with a clean settings cache
    and the given environment overrides, returning the reloaded api module."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import minisense.config as config_module

    config_module.get_settings.cache_clear()

    if "minisense.api" in sys.modules:
        del sys.modules["minisense.api"]
    return importlib.import_module("minisense.api")


@pytest.fixture
def survey_path(tmp_path):
    import json

    path = tmp_path / "survey.json"
    path.write_text(
        json.dumps(
            {
                "responses": [
                    {
                        "response_id": "r1",
                        "date": "2026-05-14",
                        "business_id": "b01",
                        "business_name": "QuickFit Gym",
                        "survey_id": "s01",
                        "survey_name": "Membership Value",
                        "rating": 4,
                        "response_channel": "mobile",
                        "free_text": "Great value, a bit of a wait though.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_health_is_always_ok_no_auth_needed(monkeypatch, survey_path):
    api = _fresh_api_module(monkeypatch, MINISENSE_SURVEY_PATH=survey_path)
    client = TestClient(api.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_reports_data_loaded(monkeypatch, survey_path):
    api = _fresh_api_module(monkeypatch, MINISENSE_SURVEY_PATH=survey_path)
    api.load_responses.cache_clear()
    # Ollama reachability is irrelevant to this test's purpose (readiness
    # reports data-load status) and shouldn't depend on whether a real
    # Ollama server happens to be running on the machine executing the
    # suite, so it's mocked deterministically rather than asserted on.
    monkeypatch.setattr(api, "is_available", lambda: False)
    client = TestClient(api.app)
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["survey_data_loaded"] is True
    assert body["ollama_reachable"] is False


def test_ask_without_token_when_none_configured_succeeds(monkeypatch, survey_path):
    api = _fresh_api_module(monkeypatch, MINISENSE_SURVEY_PATH=survey_path, API_AUTH_TOKEN="")
    api.load_responses.cache_clear()
    client = TestClient(api.app)
    resp = client.post("/ask", json={"question": "What is our overall CSAT?"})
    assert resp.status_code == 200
    assert "answer" in resp.json()


def test_ask_requires_token_when_configured(monkeypatch, survey_path):
    api = _fresh_api_module(
        monkeypatch, MINISENSE_SURVEY_PATH=survey_path, API_AUTH_TOKEN="secret-token-123"
    )
    api.load_responses.cache_clear()
    client = TestClient(api.app)

    resp = client.post("/ask", json={"question": "What is our overall CSAT?"})
    assert resp.status_code == 401

    resp = client.post(
        "/ask",
        json={"question": "What is our overall CSAT?"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401

    resp = client.post(
        "/ask",
        json={"question": "What is our overall CSAT?"},
        headers={"Authorization": "Bearer secret-token-123"},
    )
    assert resp.status_code == 200


def test_ask_rejects_empty_question(monkeypatch, survey_path):
    api = _fresh_api_module(monkeypatch, MINISENSE_SURVEY_PATH=survey_path, API_AUTH_TOKEN="")
    api.load_responses.cache_clear()
    client = TestClient(api.app)
    resp = client.post("/ask", json={"question": "   "})
    assert resp.status_code == 400


def test_ask_rejects_oversized_question(monkeypatch, survey_path):
    api = _fresh_api_module(
        monkeypatch, MINISENSE_SURVEY_PATH=survey_path, API_AUTH_TOKEN="", API_MAX_QUESTION_CHARS="50"
    )
    api.load_responses.cache_clear()
    client = TestClient(api.app)
    resp = client.post("/ask", json={"question": "x" * 200})
    assert resp.status_code == 422  # pydantic model max_length rejects it first


def test_rate_limit_returns_429_once_exceeded(monkeypatch, survey_path):
    api = _fresh_api_module(
        monkeypatch,
        MINISENSE_SURVEY_PATH=survey_path,
        API_AUTH_TOKEN="",
        API_RATE_LIMIT_REQUESTS="2",
        API_RATE_LIMIT_WINDOW_SECONDS="60",
    )
    api.load_responses.cache_clear()
    client = TestClient(api.app)

    r1 = client.get("/ready")
    r2 = client.get("/ready")
    r3 = client.get("/ready")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_docs_disabled_in_production(monkeypatch, survey_path):
    api = _fresh_api_module(
        monkeypatch,
        MINISENSE_SURVEY_PATH=survey_path,
        API_AUTH_TOKEN="a-real-token",
        MINISENSE_ENV="production",
    )
    client = TestClient(api.app)
    resp = client.get("/docs")
    assert resp.status_code == 404


def test_data_load_error_maps_to_503(monkeypatch, tmp_path):
    api = _fresh_api_module(
        monkeypatch,
        MINISENSE_SURVEY_PATH=str(tmp_path / "missing.json"),
        API_AUTH_TOKEN="",
    )
    api.load_responses.cache_clear()
    client = TestClient(api.app)
    resp = client.post("/ask", json={"question": "What is our overall CSAT?"})
    assert resp.status_code == 503
