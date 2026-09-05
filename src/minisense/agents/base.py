"""Shared helpers for sub-agents."""
from __future__ import annotations

from datetime import date, timedelta

from minisense.schemas import DateRange


def default_two_month_split(today: date | None = None) -> tuple[DateRange, DateRange]:
    """('this month', 'last month') as DateRanges, used when the orchestrator
    doesn't pin explicit dates for a comparison question."""
    today = today or date.today()
    this_start = today - timedelta(days=29)
    last_start = today - timedelta(days=59)
    last_end = today - timedelta(days=30)
    return (
        DateRange(start=this_start.isoformat(), end=today.isoformat()),
        DateRange(start=last_start.isoformat(), end=last_end.isoformat()),
    )
