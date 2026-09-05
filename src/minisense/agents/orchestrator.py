"""Orchestrator (Planner) Agent.

1. Turns a natural-language business question into a structured Plan
   (a list of TaskSpec, one per sub-agent) — via an LLM JSON call when
   Ollama is reachable, or a deterministic keyword-based heuristic
   otherwise, so the whole system stays runnable with zero setup.
2. Executes each TaskSpec against the matching sub-agent.
3. Hands the collected structured results to SummaryAgent for the final
   narrative, and returns everything (plan + per-agent results + trace)
   for inspection / the evaluation checkpoint.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from minisense.agents import comparison_agent, data_agent, rag_agent, summary_agent
from minisense.agents.base import default_two_month_split
from minisense.config import OLLAMA
from minisense.exceptions import IndexNotFoundError, OllamaUnavailableError
from minisense.llm import ollama_client
from minisense.logging_config import get_logger
from minisense.schemas import (
    AgentName,
    AgentRunLog,
    ComparisonAgentResult,
    DataAgentResult,
    DateRange,
    Plan,
    RAGAgentResult,
    SummaryAgentResult,
    TaskSpec,
)

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Orchestrator (Planner) inside MiniSense, a survey-analytics
multi-agent system. Given a business question, break it into a JSON plan of sub-tasks routed to
these sub-agents:

- DataAgent: computes exact metrics (average_rating, csat_pct, top_themes, response_count) for
  one period, optionally scoped to one business_id.
- ComparisonAgent: compares two periods (period_a = earlier/baseline, period_b = later/current)
  and surfaces significant changes. Use this whenever the question asks to compare time periods
  or asks how something changed.
- RAGAgent: retrieves relevant excerpts from the product FAQ document to add business/policy
  context (targets, definitions, policies). Include this whenever FAQ context would help answer
  (e.g. mentions of CSAT targets, complaint handling, wait time policy).

Known business_id values (use null if the question doesn't name a specific business):
{business_index}

Respond with ONLY a JSON object of this exact shape:
{{
  "reasoning": "one sentence on how you decomposed the question",
  "tasks": [
    {{
      "agent": "DataAgent" | "RAGAgent" | "ComparisonAgent",
      "objective": "short description of this task",
      "business_id": "<id or null>",
      "period_a": {{"start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"}} | null,
      "period_b": {{"start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"}} | null,
      "query_text": "<text to search the FAQ with, RAGAgent only>" | null
    }}
  ]
}}
Today's date is {today}. "This month" = the last 30 days, "last month" = the 30 days before that.
Include at least one DataAgent task in every plan. Only include ComparisonAgent if the question
is explicitly comparative. Only include RAGAgent if FAQ/policy context is relevant."""


def _business_index(responses: list[dict[str, Any]]) -> dict[str, str]:
    return {r["business_name"]: r["business_id"] for r in responses}


def _dataset_today(responses: list[dict[str, Any]]) -> date:
    """Anchor 'this month' / 'last month' to the most recent date actually
    present in the survey dataset, not the real wall-clock date — the
    synthetic/demo dataset covers a fixed two-month window, so resolving
    relative time against `date.today()` would return zero rows whenever the
    system is run outside that window."""
    if not responses:
        return date.today()
    return max(date.fromisoformat(r["date"]) for r in responses)


def _parse_date_range(d: dict | None) -> DateRange | None:
    if not d:
        return None
    return DateRange(start=d.get("start") or None, end=d.get("end") or None)


def _resolve_business_id(name_or_id: str | None, name_to_id: dict[str, str]) -> str | None:
    if not name_or_id:
        return None
    if name_or_id in name_to_id.values():
        return name_or_id
    return name_to_id.get(name_or_id)


def _llm_plan(question: str, responses: list[dict[str, Any]]) -> Plan:
    name_to_id = _business_index(responses)
    system = PLANNER_SYSTEM_PROMPT.format(
        business_index=json.dumps(name_to_id, indent=2),
        today=_dataset_today(responses).isoformat(),
    )
    raw = ollama_client.chat_json(system, question, temperature=OLLAMA.temperature_planner)
    tasks = []
    for t in raw.get("tasks", []):
        tasks.append(
            TaskSpec(
                agent=AgentName(t["agent"]),
                objective=t.get("objective", ""),
                business_id=_resolve_business_id(t.get("business_id"), name_to_id),
                period_a=_parse_date_range(t.get("period_a")),
                period_b=_parse_date_range(t.get("period_b")),
                query_text=t.get("query_text"),
            )
        )
    if not any(t.agent == AgentName.DATA for t in tasks):
        tasks.insert(0, TaskSpec(agent=AgentName.DATA, objective="fallback overall metrics"))
    return Plan(question=question, tasks=tasks, reasoning=raw.get("reasoning", ""))


def _heuristic_plan(question: str, responses: list[dict[str, Any]]) -> Plan:
    """Deterministic fallback used when Ollama isn't running."""
    name_to_id = _business_index(responses)
    q_lower = question.lower()
    business_id = None
    for name, bid in name_to_id.items():
        if name.lower() in q_lower:
            business_id = bid
            break

    tasks: list[TaskSpec] = []
    is_comparative = any(kw in q_lower for kw in ["compare", "vs", "versus", "last month", "previous month", "change", "trend"])

    if is_comparative:
        this_month, last_month = default_two_month_split(_dataset_today(responses))
        tasks.append(
            TaskSpec(
                agent=AgentName.COMPARISON,
                objective="compare this month vs last month",
                business_id=business_id,
                period_a=last_month,
                period_b=this_month,
            )
        )
        tasks.append(
            TaskSpec(agent=AgentName.DATA, objective="current period overall metrics", business_id=business_id, period_a=this_month)
        )
    else:
        tasks.append(TaskSpec(agent=AgentName.DATA, objective="overall metrics", business_id=business_id))

    tasks.append(TaskSpec(agent=AgentName.RAG, objective="retrieve related FAQ context", query_text=question, top_k=4))
    return Plan(question=question, tasks=tasks, reasoning="heuristic fallback (Ollama unavailable): keyword-based routing")


def plan_question(question: str, responses: list[dict[str, Any]]) -> Plan:
    if ollama_client.is_available():
        try:
            plan = _llm_plan(question, responses)
            logger.info(f"LLM plan produced {len(plan.tasks)} task(s) for question: {question!r}")
            return plan
        except (OllamaUnavailableError, ValueError, KeyError) as exc:
            logger.warning(f"LLM planning failed ({exc}); falling back to heuristic planner")
    plan = _heuristic_plan(question, responses)
    logger.info(f"Heuristic plan produced {len(plan.tasks)} task(s) for question: {question!r}")
    return plan


@dataclass
class OrchestratorRun:
    plan: Plan
    data_result: DataAgentResult | None
    comparison_result: ComparisonAgentResult | None
    rag_result: RAGAgentResult | None
    summary: SummaryAgentResult
    trace: list[AgentRunLog]


def answer_question(question: str, responses: list[dict[str, Any]]) -> OrchestratorRun:
    plan = plan_question(question, responses)
    trace: list[AgentRunLog] = []

    data_result: DataAgentResult | None = None
    comparison_result: ComparisonAgentResult | None = None
    rag_result: RAGAgentResult | None = None

    for task in plan.tasks:
        if task.agent == AgentName.DATA:
            data_result = data_agent.run(task, responses)
            trace.append(AgentRunLog(agent="DataAgent", task=asdict(task), result=asdict(data_result)))
        elif task.agent == AgentName.COMPARISON:
            comparison_result = comparison_agent.run(task, responses)
            trace.append(AgentRunLog(agent="ComparisonAgent", task=asdict(task), result=asdict(comparison_result)))
        elif task.agent == AgentName.RAG:
            try:
                rag_result = rag_agent.run(task)
                trace.append(AgentRunLog(agent="RAGAgent", task=asdict(task), result=asdict(rag_result)))
            except (IndexNotFoundError, OllamaUnavailableError) as exc:
                # No FAQ index yet, or Ollama unreachable for embeddings — the
                # rest of the pipeline (exact metrics, comparisons) is still
                # fully useful without FAQ grounding, so degrade gracefully
                # rather than failing the whole question.
                logger.warning(f"RAGAgent skipped: {exc}")
                trace.append(
                    AgentRunLog(
                        agent="RAGAgent",
                        task=asdict(task),
                        result={"error": str(exc), "skipped": True},
                    )
                )

    summary = summary_agent.run(question, data_result, comparison_result, rag_result)
    trace.append(AgentRunLog(agent="SummaryAgent", task={"question": question}, result=asdict(summary)))
    logger.info(f"Answered question with {len(trace)} agent step(s): {question!r}")

    return OrchestratorRun(
        plan=plan,
        data_result=data_result,
        comparison_result=comparison_result,
        rag_result=rag_result,
        summary=summary,
        trace=trace,
    )
