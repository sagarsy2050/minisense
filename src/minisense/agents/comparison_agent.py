"""ComparisonAgent — diffs two time periods using DataAgent's exact metrics.

A change is flagged "significant" using two simple, explainable rules
rather than a statistical test (appropriate given we usually have
thousands of responses per period, so noise is not the concern — real
month-over-month drift is):
  - rating / CSAT: absolute change >= 0.15 (rating pts) / 3 (CSAT pts)
  - theme mention counts: relative change >= 25% AND the theme appears
    at least 5 times in the larger period (filters out tiny-count noise)
"""
from __future__ import annotations

from typing import Any

from minisense.agents import data_agent
from minisense.schemas import ComparisonAgentResult, DateRange, MetricDelta, TaskSpec
from minisense.tools import metrics as tools

# Comfortably above the number of distinct themes in tools.metrics.THEME_KEYWORDS,
# so this always returns every theme's true count for a period rather than the
# top-3 that DataAgentResult.top_themes is limited to. Using the top-3-limited
# lists here would silently read a theme's count as 0 whenever it fell just
# outside the top 3 in one period but not the other, producing a false "100%
# drop" for what was actually a close ranking swap.
ALL_THEMES_TOP_N = 100

RATING_SIG_THRESHOLD = 0.15
CSAT_SIG_THRESHOLD = 3.0


def _pct_change(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return round(100.0 * (b - a) / abs(a), 2)


def _delta(name: str, a: float | None, b: float | None, sig_threshold: float) -> MetricDelta:
    abs_change = round(b - a, 3) if (a is not None and b is not None) else None
    return MetricDelta(
        metric=name,
        period_a_value=a,
        period_b_value=b,
        absolute_change=abs_change,
        pct_change=_pct_change(a, b),
        is_significant=bool(abs_change is not None and abs(abs_change) >= sig_threshold),
    )


def run(task: TaskSpec, responses: list[dict[str, Any]]) -> ComparisonAgentResult:
    period_a = task.period_a or DateRange()
    period_b = task.period_b or DateRange()

    task_a = TaskSpec(agent=task.agent, objective="metrics for period A", business_id=task.business_id, period_a=period_a)
    task_b = TaskSpec(agent=task.agent, objective="metrics for period B", business_id=task.business_id, period_a=period_b)
    result_a = data_agent.run(task_a, responses)
    result_b = data_agent.run(task_b, responses)

    deltas = [
        _delta("average_rating", result_a.average_rating, result_b.average_rating, RATING_SIG_THRESHOLD),
        _delta("csat_pct", result_a.csat_pct, result_b.csat_pct, CSAT_SIG_THRESHOLD),
        _delta("response_count", float(result_a.response_count), float(result_b.response_count), max(1.0, 0.2 * result_a.response_count)),
    ]

    # Full theme counts per period (not the top-3-limited DataAgentResult.top_themes)
    # so a theme's true count is used even when it isn't a top-3 theme in one period.
    filtered_a = tools.filter_responses(responses, task.business_id, period_a.start, period_a.end)
    filtered_b = tools.filter_responses(responses, task.business_id, period_b.start, period_b.end)
    themes_a = dict(tools.compute_top_themes(filtered_a, negative_only=False, top_n=ALL_THEMES_TOP_N))
    themes_b = dict(tools.compute_top_themes(filtered_b, negative_only=False, top_n=ALL_THEMES_TOP_N))
    theme_shifts: list[str] = []
    for theme in set(themes_a) | set(themes_b):
        a_count, b_count = themes_a.get(theme, 0), themes_b.get(theme, 0)
        larger = max(a_count, b_count)
        if larger < 5:
            continue
        rel_change = _pct_change(a_count, b_count) if a_count else (100.0 if b_count else 0.0)
        if rel_change is not None and abs(rel_change) >= 25:
            direction = "up" if b_count >= a_count else "down"
            theme_shifts.append(f"{theme.replace('_', ' ')} mentions {direction} {abs(rel_change):.0f}% ({a_count} -> {b_count})")

    return ComparisonAgentResult(period_a=period_a, period_b=period_b, deltas=deltas, theme_shifts=theme_shifts)
