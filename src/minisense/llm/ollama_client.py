"""Minimal client for a local Ollama server.

No SDK dependency — just ``requests`` against Ollama's REST API
(http://localhost:11434 by default). Two entry points:

- ``chat_json``: ask the model for a JSON object matching a described
  shape (used by the Orchestrator to produce a Plan, and used wherever we
  need structured output back from the LLM).
- ``chat_text``: ask for free-form prose (used by SummaryAgent for the
  final narrative).
- ``embed``: batch text -> vector, via Ollama's own embedding models (e.g.
  ``nomic-embed-text``). Routing embeddings through Ollama too — rather than
  a separate sentence-transformers/HuggingFace download — is what keeps the
  whole system on one local runtime with zero external API calls.

If Ollama is unreachable, all three raise ``OllamaUnavailableError`` so callers
can fall back to a deterministic offline path instead of crashing — see
``minisense.agents.orchestrator`` and ``minisense.agents.summary_agent``.
"""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from minisense.config import OLLAMA
from minisense.exceptions import OllamaUnavailableError  # re-exported for callers
from minisense.logging_config import get_logger

logger = get_logger(__name__)


def _post(path: str, payload: dict) -> dict:
    try:
        resp = requests.post(f"{OLLAMA.host}{path}", json=payload, timeout=OLLAMA.request_timeout_s)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        logger.warning(f"Ollama request to {path} failed: {exc}")
        raise OllamaUnavailableError(
            f"Could not reach Ollama at {OLLAMA.host} (model={OLLAMA.chat_model}). "
            f"Is `ollama serve` running and have you pulled the model? "
            f"(`ollama pull {OLLAMA.chat_model}`) Original error: {exc}"
        ) from exc


def _extract_json(raw: str) -> dict:
    """Ollama's json format usually returns clean JSON, but some models
    wrap it in prose or code fences — strip those defensively."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            raw = brace.group(0)
    return json.loads(raw)


def chat_text(system: str, user: str, temperature: float = 0.4) -> str:
    data = _post(
        "/api/chat",
        {
            "model": OLLAMA.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    return data.get("message", {}).get("content", "").strip()


def chat_json(system: str, user: str, temperature: float = 0.0) -> dict[str, Any]:
    data = _post(
        "/api/chat",
        {
            "model": OLLAMA.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    content = data.get("message", {}).get("content", "")
    try:
        return _extract_json(content)
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error(f"Model {OLLAMA.chat_model} did not return valid JSON: {content!r}")
        raise ValueError(f"Model did not return valid JSON. Raw content: {content!r}") from exc


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Ollama's embedding endpoint.

    Tries the newer batch endpoint (``/api/embed``, accepts a list of
    inputs in one request) first, then falls back to the older
    single-text ``/api/embeddings`` endpoint (looped) for compatibility
    with older Ollama versions.
    """
    try:
        data = _post("/api/embed", {"model": OLLAMA.embed_model, "input": texts})
        if "embeddings" in data:
            return data["embeddings"]
    except OllamaUnavailableError:
        raise
    except (KeyError, TypeError):
        pass  # fall through to the legacy per-text endpoint

    vectors = []
    for text in texts:
        data = _post("/api/embeddings", {"model": OLLAMA.embed_model, "prompt": text})
        vectors.append(data["embedding"])
    return vectors


def is_available() -> bool:
    try:
        requests.get(f"{OLLAMA.host}/api/tags", timeout=3)
        return True
    except requests.exceptions.RequestException as exc:
        logger.debug(f"Ollama not reachable at {OLLAMA.host}: {exc}")
        return False
