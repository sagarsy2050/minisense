"""SummaryAgent — turns structured sub-agent results into one narrative
paragraph, grounded in both the exact numbers and the retrieved FAQ
context. Falls back to a deterministic template if Ollama is unreachable,
so the pipeline is still demonstrable without a running model.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from minisense.config import OLLAMA
from minisense.exceptions import OllamaUnavailableError
from minisense.llm import ollama_client
from minisense.logging_config import get_logger
from minisense.schemas import (
    ComparisonAgentResult,
    DataAgentResult,
    RAGAgentResult,
    SummaryAgentResult,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the SummaryAgent inside MiniSense, a survey-analytics assistant.
You will be given the original business question plus structured JSON output from
other agents: exact numeric metrics (DataAgent), a period-over-period comparison
(ComparisonAgent, optional), and retrieved FAQ excerpts (RAGAgent, optional).

Write ONE coherent narrative paragraph (4-7 sentences) that answers the question
in plain business language.
Rules:
- Use ONLY the numbers given to you. Never invent a statistic.
- Weave in relevant FAQ context (e.g. targets, policies) only where it's relevant.
- If a comparison is provided, explicitly call out what changed and by how much.
- Do not mention "DataAgent", "RAGAgent", or JSON — write as a human analyst would.
- Do not use markdown formatting."""


def _fallback_narrative(
    question: str,
    data_result: DataAgentResult | None,
    comparison: ComparisonAgentResult | None,
    rag: RAGAgentResult | None,
) -> str:
    """A deterministic, template-based narrative used only when Ollama is
    unavailable, so the pipeline still produces a real answer end-to-end."""
    parts = [f"Regarding \"{question}\":"]
    if data_result:
        parts.append(
            f"Across {data_result.response_count} responses"
            + (f" for business {data_result.business_id}" if data_result.business_id else "")
            + f", the average rating was {data_result.average_rating} with a CSAT of {data_result.csat_pct}%."
        )
        if data_result.top_themes:
            top = ", ".join(f"{t.theme.replace('_', ' ')} ({t.count})" for t in data_result.top_themes)
            parts.append(f"The most frequently mentioned themes were {top}.")
    if comparison and comparison.deltas:
        sig = [d for d in comparison.deltas if d.is_significant]
        if sig:
            bits = ", ".join(f"{d.metric.replace('_', ' ')} changed by {d.absolute_change}" for d in sig)
            parts.append(f"Compared to the prior period, {bits}.")
        if comparison.theme_shifts:
            parts.append("Notable theme shifts: " + "; ".join(comparison.theme_shifts) + ".")
    if rag and rag.chunks:
        parts.append("Related policy context: " + rag.chunks[0].text)
    parts.append("[Generated via offline fallback — start `ollama serve` for a fully narrative answer.]")
    return " ".join(parts)


def run(
    question: str,
    data_result: DataAgentResult | None = None,
    comparison: ComparisonAgentResult | None = None,
    rag: RAGAgentResult | None = None,
) -> SummaryAgentResult:
    citations = [c.chunk_id for c in rag.chunks] if rag else []

    if not ollama_client.is_available():
        logger.info("Ollama unavailable — using deterministic fallback narrative")
        return SummaryAgentResult(
            narrative=_fallback_narrative(question, data_result, comparison, rag),
            citations=citations,
        )

    payload = {
        "question": question,
        "data_agent_result": asdict(data_result) if data_result else None,
        "comparison_agent_result": asdict(comparison) if comparison else None,
        "retrieved_faq_context": [c.text for c in rag.chunks] if rag else [],
    }
    try:
        narrative = ollama_client.chat_text(
            SYSTEM_PROMPT,
            json.dumps(payload, indent=2),
            temperature=OLLAMA.temperature_summary,
        )
    except OllamaUnavailableError as exc:
        logger.warning(f"Ollama became unavailable mid-run ({exc}); using fallback narrative")
        narrative = _fallback_narrative(question, data_result, comparison, rag)

    return SummaryAgentResult(narrative=narrative, citations=citations)
