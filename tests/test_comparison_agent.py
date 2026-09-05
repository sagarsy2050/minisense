"""Tests for ComparisonAgent — period diffing, significance thresholds,
and the full-theme-count regression guard (see comparison_agent.py's
ALL_THEMES_TOP_N docstring for the bug this protects against).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.agents import comparison_agent  # noqa: E402
from minisense.schemas import AgentName, DateRange, TaskSpec  # noqa: E402


def _response(rid: str, d: str, rating: int, text: str, business_id: str = "b01") -> dict:
    return {
        "response_id": rid,
        "date": d,
        "business_id": business_id,
        "rating": rating,
        "response_channel": "mobile",
        "free_text": text,
    }


def test_rating_and_csat_deltas_are_computed_correctly():
    responses = [
        _response("r1", "2026-07-10", 5, "great staff"),
        _response("r2", "2026-07-11", 5, "great staff"),
        _response("r3", "2026-08-10", 2, "bad staff"),
        _response("r4", "2026-08-11", 2, "bad staff"),
    ]
    task = TaskSpec(
        agent=AgentName.COMPARISON,
        objective="compare",
        business_id="b01",
        period_a=DateRange(start="2026-07-01", end="2026-07-31"),
        period_b=DateRange(start="2026-08-01", end="2026-08-31"),
    )
    result = comparison_agent.run(task, responses)

    rating_delta = next(d for d in result.deltas if d.metric == "average_rating")
    assert rating_delta.period_a_value == 5.0
    assert rating_delta.period_b_value == 2.0
    assert rating_delta.absolute_change == -3.0
    assert rating_delta.is_significant is True

    csat_delta = next(d for d in result.deltas if d.metric == "csat_pct")
    assert csat_delta.period_a_value == 100.0
    assert csat_delta.period_b_value == 0.0
    assert csat_delta.is_significant is True


def test_small_rating_change_is_not_significant():
    # Same rating in both periods -> zero change, never flagged significant.
    responses = [
        _response("r1", "2026-07-10", 4, "fine"),
        _response("r2", "2026-08-10", 4, "fine"),
    ]
    task = TaskSpec(
        agent=AgentName.COMPARISON,
        objective="compare",
        period_a=DateRange(start="2026-07-01", end="2026-07-31"),
        period_b=DateRange(start="2026-08-01", end="2026-08-31"),
    )
    result = comparison_agent.run(task, responses)
    rating_delta = next(d for d in result.deltas if d.metric == "average_rating")
    assert rating_delta.absolute_change == 0.0
    assert rating_delta.is_significant is False


def test_theme_shift_uses_full_counts_not_top3_only():
    """Regression guard: a theme that's similar in count across periods but
    edged out of the top-3 in one of them must NOT show up as a false
    100%-drop theme shift (the real bug this fixes, see comparison_agent.py).
    """
    # 8 themes total, each mentioned a similar number of times in both
    # periods (>=5, so they clear the "not noise" floor) — no theme should
    # be flagged as a >=25% shift purely from ranking noise.
    responses = []
    themes_period_a_order = ["wait_time", "communication", "pricing", "staff", "cleanliness", "value", "equipment", "class_schedule"]
    themes_period_b_order = ["staff", "cleanliness", "pricing", "wait_time", "equipment", "value", "class_schedule", "communication"]
    i = 0
    for theme in themes_period_a_order:
        for _ in range(6):
            i += 1
            responses.append(_response(f"a{i}", "2026-07-15", 3, f"the {theme.replace('_', ' ')} was fine"))
    for theme in themes_period_b_order:
        for _ in range(6):
            i += 1
            responses.append(_response(f"b{i}", "2026-08-15", 3, f"the {theme.replace('_', ' ')} was fine"))

    task = TaskSpec(
        agent=AgentName.COMPARISON,
        objective="compare",
        period_a=DateRange(start="2026-07-01", end="2026-07-31"),
        period_b=DateRange(start="2026-08-01", end="2026-08-31"),
    )
    result = comparison_agent.run(task, responses)
    # Every theme has the same count (6) in both periods -> zero real shifts,
    # regardless of which 3 happened to be each period's "top 3".
    assert result.theme_shifts == []


def test_theme_shift_is_reported_when_counts_genuinely_diverge():
    responses = []
    for i in range(10):
        responses.append(_response(f"a{i}", "2026-07-15", 2, "the wait time was disappointing"))
    for i in range(10, 12):
        responses.append(_response(f"a{i}", "2026-07-16", 2, "the staff was disappointing"))
    for i in range(12, 14):
        responses.append(_response(f"b{i}", "2026-08-15", 2, "the wait time was disappointing"))
    for i in range(14, 24):
        responses.append(_response(f"b{i}", "2026-08-16", 2, "the staff was disappointing"))

    task = TaskSpec(
        agent=AgentName.COMPARISON,
        objective="compare",
        period_a=DateRange(start="2026-07-01", end="2026-07-31"),
        period_b=DateRange(start="2026-08-01", end="2026-08-31"),
    )
    result = comparison_agent.run(task, responses)
    shift_text = " ".join(result.theme_shifts)
    assert "wait time" in shift_text
    assert "staff" in shift_text
