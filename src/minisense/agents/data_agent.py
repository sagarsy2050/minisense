"""DataAgent — parses the survey JSON and computes exact metrics.

This agent is deliberately LLM-free: every number it returns comes from
``minisense.tools.metrics``, which are plain, testable Python functions.
This is the "tool calling from within an agent" the assignment asks for —
``compute_csat`` etc. are called here exactly like an LLM function-call
would invoke them, just without an LLM in the loop for something that
should always be exact.
"""
from __future__ import annotations

from typing import Any

from minisense.schemas import DataAgentResult, DateRange, TaskSpec, ThemeCount
from minisense.tools import metrics as tools


def run(task: TaskSpec, responses: list[dict[str, Any]]) -> DataAgentResult:
    period = task.period_a or DateRange()
    filtered = tools.filter_responses(responses, task.business_id, period.start, period.end)

    # Called directly (not bundled into a dict first) so each value keeps its
    # real type — a dict mixing int/float/list[tuple]/dict[str,int] values
    # collapses to a single union type under static analysis, which then
    # can't verify any of the DataAgentResult field assignments below.
    top_themes = tools.compute_top_themes(filtered, negative_only=False, top_n=3)

    return DataAgentResult(
        period=period,
        business_id=task.business_id,
        response_count=tools.compute_response_count(filtered),
        average_rating=tools.compute_average_rating(filtered),
        csat_pct=tools.compute_csat(filtered),
        top_themes=[ThemeCount(theme=t, count=c) for t, c in top_themes],
        channel_breakdown=tools.compute_channel_breakdown(filtered),
    )
