"""Pure, deterministic metric functions over the survey dataset.

These are the "tools" the DataAgent calls (the assignment explicitly asks
for at least one example of tool calling, e.g. ``compute_csat``). They take
already-filtered lists of response dicts and return plain numbers/dicts —
no LLM involved anywhere in this file, which keeps the numeric answers
exact and reproducible.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from datetime import date
from typing import Any

Response = dict[str, Any]

# Keep in sync with data/generate_data.py's theme vocabulary so themes are
# recoverable from free text without an LLM call.
THEME_KEYWORDS = {
    "wait_time": ["wait time", "wait", "line", "queue"],
    "staff": ["staff"],
    "pricing": ["pricing", "price"],
    "cleanliness": ["cleanliness", "clean"],
    "communication": ["communication"],
    "value": ["value"],
    "equipment": ["equipment"],
    "class_schedule": ["class schedule", "schedule"],
    "food_quality": ["food quality", "food"],
    "menu_variety": ["menu variety", "menu"],
    "repair_quality": ["repair quality", "repair"],
    "scheduling": ["scheduling"],
    "appointment_availability": ["appointment availability", "appointment"],
    "billing": ["billing"],
    "responsiveness": ["responsiveness", "responsive"],
    "paperwork": ["paperwork"],
    "wifi_reliability": ["wifi reliability", "wifi", "wi-fi"],
    "amenities": ["amenities"],
    "vet_friendliness": ["vet friendliness", "vet"],
    "stylist_skill": ["stylist skill", "stylist"],
    "ambiance": ["ambiance", "ambience"],
}


def filter_responses(
    responses: Iterable[Response],
    business_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[Response]:
    """Filter by business_id and an inclusive ISO date range."""
    start_d = date.fromisoformat(start) if start else None
    end_d = date.fromisoformat(end) if end else None
    out = []
    for r in responses:
        if business_id and r.get("business_id") != business_id:
            continue
        d = date.fromisoformat(r["date"])
        if start_d and d < start_d:
            continue
        if end_d and d > end_d:
            continue
        out.append(r)
    return out


def compute_response_count(responses: list[Response]) -> int:
    return len(responses)


def compute_average_rating(responses: list[Response]) -> float | None:
    if not responses:
        return None
    return round(sum(r["rating"] for r in responses) / len(responses), 3)


def compute_csat(responses: list[Response], threshold: int = 4) -> float | None:
    """CSAT = % of responses rated >= threshold (default 4) on a 1-5 scale."""
    if not responses:
        return None
    satisfied = sum(1 for r in responses if r["rating"] >= threshold)
    return round(100.0 * satisfied / len(responses), 2)


def compute_channel_breakdown(responses: list[Response]) -> dict[str, int]:
    return dict(Counter(r["response_channel"] for r in responses))


def extract_themes(text: str) -> list[str]:
    text_l = text.lower()
    found = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", text_l) for kw in keywords):
            found.append(theme)
    return found


def compute_top_themes(
    responses: list[Response], negative_only: bool = False, top_n: int = 3
) -> list[tuple[str, int]]:
    """Rank themes by mention count. If negative_only, only count mentions
    coming from responses rated <= 2 (i.e. complaints)."""
    counter: Counter[str] = Counter()
    for r in responses:
        if negative_only and r["rating"] > 2:
            continue
        for theme in extract_themes(r.get("free_text", "")):
            counter[theme] += 1
    return counter.most_common(top_n)


def compute_all_metrics(
    responses: list[Response],
    business_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    top_n_themes: int = 3,
) -> dict[str, Any]:
    """Convenience wrapper the DataAgent calls: filter + run every metric."""
    filtered = filter_responses(responses, business_id, start, end)
    return {
        "response_count": compute_response_count(filtered),
        "average_rating": compute_average_rating(filtered),
        "csat_pct": compute_csat(filtered),
        "top_themes": compute_top_themes(filtered, negative_only=False, top_n=top_n_themes),
        "top_complaint_themes": compute_top_themes(filtered, negative_only=True, top_n=top_n_themes),
        "channel_breakdown": compute_channel_breakdown(filtered),
    }
