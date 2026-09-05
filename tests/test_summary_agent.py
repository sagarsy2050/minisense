"""Direct unit tests for SummaryAgent — the deterministic offline fallback
(no Ollama) and the Ollama-backed path with chat_text mocked. No real
network/model calls in either case."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.agents import summary_agent  # noqa: E402
from minisense.schemas import (  # noqa: E402
    ComparisonAgentResult,
    DataAgentResult,
    DateRange,
    MetricDelta,
    RAGAgentResult,
    RetrievedChunk,
    ThemeCount,
)

DATA_RESULT = DataAgentResult(
    period=DateRange(start="2026-05-01", end="2026-05-31"),
    business_id=None,
    response_count=54143,
    average_rating=3.645,
    csat_pct=62.13,
    top_themes=[ThemeCount(theme="wait_time", count=4248), ThemeCount(theme="staff", count=4234)],
    channel_breakdown={"mobile": 20000, "web": 10000},
)


def test_fallback_narrative_used_when_ollama_unavailable():
    with patch("minisense.agents.summary_agent.ollama_client.is_available", return_value=False):
        result = summary_agent.run("What is our overall CSAT?", data_result=DATA_RESULT)
    assert "62.13" in result.narrative
    assert "3.645" in result.narrative
    assert "offline fallback" in result.narrative.lower()
    assert result.citations == []


def test_fallback_narrative_includes_top_themes():
    with patch("minisense.agents.summary_agent.ollama_client.is_available", return_value=False):
        result = summary_agent.run("What are the top complaints?", data_result=DATA_RESULT)
    assert "wait time" in result.narrative.lower()
    assert "staff" in result.narrative.lower()


def test_fallback_narrative_includes_comparison_when_significant():
    comparison = ComparisonAgentResult(
        period_a=DateRange(start="2026-04-01", end="2026-04-30"),
        period_b=DateRange(start="2026-05-01", end="2026-05-31"),
        deltas=[
            MetricDelta(metric="csat_pct", period_a_value=50.0, period_b_value=62.13,
                        absolute_change=12.13, pct_change=24.26, is_significant=True),
        ],
        theme_shifts=["wait time mentions up 99% (2137 -> 4248)"],
    )
    with patch("minisense.agents.summary_agent.ollama_client.is_available", return_value=False):
        result = summary_agent.run("How did CSAT change?", data_result=DATA_RESULT, comparison=comparison)
    assert "12.13" in result.narrative
    assert "wait time mentions up 99%" in result.narrative


def test_fallback_narrative_never_invents_numbers_without_data():
    with patch("minisense.agents.summary_agent.ollama_client.is_available", return_value=False):
        result = summary_agent.run("What is our overall CSAT?")
    assert result.narrative  # still produces *something*
    assert "62.13" not in result.narrative  # no data given, no fabricated figure


def test_ollama_path_returns_citations_from_rag_chunks():
    rag = RAGAgentResult(
        query="CSAT target",
        chunks=[RetrievedChunk(chunk_id="chunk_007", text="CSAT target is 4.5+.", score=0.68)],
    )
    with patch("minisense.agents.summary_agent.ollama_client.is_available", return_value=True), patch(
        "minisense.agents.summary_agent.ollama_client.chat_text",
        return_value="Our CSAT is below the stated target.",
    ) as mock_chat:
        result = summary_agent.run("What is our CSAT target?", data_result=DATA_RESULT, rag=rag)

    assert result.narrative == "Our CSAT is below the stated target."
    assert result.citations == ["chunk_007"]
    mock_chat.assert_called_once()


def test_ollama_failure_mid_call_falls_back_to_template():
    from minisense.exceptions import OllamaUnavailableError

    with patch("minisense.agents.summary_agent.ollama_client.is_available", return_value=True), patch(
        "minisense.agents.summary_agent.ollama_client.chat_text",
        side_effect=OllamaUnavailableError("connection reset"),
    ):
        result = summary_agent.run("What is our overall CSAT?", data_result=DATA_RESULT)

    assert "62.13" in result.narrative
    assert "offline fallback" in result.narrative.lower()
