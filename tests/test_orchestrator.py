"""Tests for the Orchestrator's heuristic (Ollama-unavailable) path — the
planner, business-name resolution, and graceful RAG degradation when no
FAQ index has been built. All run fully offline.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.agents import orchestrator  # noqa: E402
from minisense.exceptions import IndexNotFoundError  # noqa: E402
from minisense.schemas import AgentName  # noqa: E402

RESPONSES = [
    {
        "response_id": "r1",
        "date": "2026-08-01",
        "business_id": "b01",
        "business_name": "QuickFit Gym",
        "rating": 4,
        "response_channel": "mobile",
        "free_text": "the staff was excellent",
    },
    {
        "response_id": "r2",
        "date": "2026-08-02",
        "business_id": "b02",
        "business_name": "GreenLeaf Bistro",
        "rating": 2,
        "response_channel": "web",
        "free_text": "the wait time was disappointing",
    },
]


def test_heuristic_plan_routes_simple_question_to_data_and_rag():
    with patch("minisense.agents.orchestrator.ollama_client.is_available", return_value=False):
        plan = orchestrator.plan_question("What is our overall CSAT?", RESPONSES)
    agents_used = [t.agent for t in plan.tasks]
    assert AgentName.DATA in agents_used
    assert AgentName.RAG in agents_used
    assert AgentName.COMPARISON not in agents_used
    assert "heuristic" in plan.reasoning.lower()


def test_heuristic_plan_detects_comparison_keywords():
    with patch("minisense.agents.orchestrator.ollama_client.is_available", return_value=False):
        plan = orchestrator.plan_question(
            "How does this month compare to last month?", RESPONSES
        )
    agents_used = [t.agent for t in plan.tasks]
    assert AgentName.COMPARISON in agents_used


def test_heuristic_plan_resolves_named_business():
    with patch("minisense.agents.orchestrator.ollama_client.is_available", return_value=False):
        plan = orchestrator.plan_question("How is QuickFit Gym doing?", RESPONSES)
    data_task = next(t for t in plan.tasks if t.agent == AgentName.DATA)
    assert data_task.business_id == "b01"


def test_heuristic_plan_business_id_none_when_not_named():
    with patch("minisense.agents.orchestrator.ollama_client.is_available", return_value=False):
        plan = orchestrator.plan_question("What is our overall CSAT?", RESPONSES)
    data_task = next(t for t in plan.tasks if t.agent == AgentName.DATA)
    assert data_task.business_id is None


def test_answer_question_end_to_end_without_ollama_or_faq_index():
    """Full offline run: no Ollama (heuristic plan + template summary), no
    FAQ index built (RAGAgent should be skipped, not raise)."""
    with patch("minisense.agents.orchestrator.ollama_client.is_available", return_value=False), patch(
        "minisense.agents.rag_agent.run",
        side_effect=IndexNotFoundError("no index"),
    ):
        run = orchestrator.answer_question("What is our overall CSAT?", RESPONSES)

    assert run.data_result is not None
    assert run.rag_result is None
    assert run.summary.narrative  # a real (fallback) narrative was produced
    assert any(step.agent == "RAGAgent" and step.result.get("skipped") for step in run.trace)


def test_answer_question_produces_comparison_result_for_comparative_question():
    with patch("minisense.agents.orchestrator.ollama_client.is_available", return_value=False), patch(
        "minisense.agents.rag_agent.run",
        side_effect=IndexNotFoundError("no index"),
    ):
        run = orchestrator.answer_question(
            "How does this month compare to last month?", RESPONSES
        )
    assert run.comparison_result is not None
