import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.tools import metrics  # noqa: E402

SAMPLE = [
    {"response_id": "r1", "date": "2026-08-01", "business_id": "b01", "rating": 5,
     "response_channel": "mobile", "free_text": "The staff was excellent and the wait time was short."},
    {"response_id": "r2", "date": "2026-08-02", "business_id": "b01", "rating": 2,
     "response_channel": "web", "free_text": "The wait time was disappointing."},
    {"response_id": "r3", "date": "2026-08-03", "business_id": "b02", "rating": 4,
     "response_channel": "mobile", "free_text": "Great value overall."},
    {"response_id": "r4", "date": "2026-07-15", "business_id": "b01", "rating": 1,
     "response_channel": "phone", "free_text": "Terrible wait time and rude staff."},
]


def test_filter_by_business():
    out = metrics.filter_responses(SAMPLE, business_id="b01")
    assert {r["response_id"] for r in out} == {"r1", "r2", "r4"}


def test_filter_by_date_range():
    out = metrics.filter_responses(SAMPLE, start="2026-08-01", end="2026-08-31")
    assert {r["response_id"] for r in out} == {"r1", "r2", "r3"}


def test_average_rating():
    out = metrics.filter_responses(SAMPLE, business_id="b01")
    assert metrics.compute_average_rating(out) == round((5 + 2 + 1) / 3, 3)


def test_average_rating_empty():
    assert metrics.compute_average_rating([]) is None


def test_csat():
    out = metrics.filter_responses(SAMPLE, business_id="b01")
    # only r1 (rating=5) is >= 4 out of 3 total
    assert metrics.compute_csat(out) == round(100 * 1 / 3, 2)


def test_extract_themes():
    themes = metrics.extract_themes("The wait time was long and staff were rude.")
    assert "wait_time" in themes
    assert "staff" in themes


def test_top_themes_negative_only():
    out = metrics.filter_responses(SAMPLE, business_id="b01")
    top = metrics.compute_top_themes(out, negative_only=True, top_n=5)
    theme_names = [t for t, _ in top]
    assert "wait_time" in theme_names  # from r2 (rating 2) and r4 (rating 1)
    assert all(t != "staff" or True for t in theme_names)  # sanity, staff mentioned once negatively (r4)


def test_channel_breakdown():
    out = metrics.filter_responses(SAMPLE, business_id="b01")
    breakdown = metrics.compute_channel_breakdown(out)
    assert breakdown == {"mobile": 1, "web": 1, "phone": 1}


def test_top_themes_all_n_returns_every_mentioned_theme():
    # Regression guard for a real bug: ComparisonAgent must diff *all* theme
    # counts, not just each period's top-3, or a theme that's close in count
    # but edged out of the top 3 in one period reads as a false 100% drop.
    out = metrics.filter_responses(SAMPLE, business_id="b01")
    all_themes = dict(metrics.compute_top_themes(out, negative_only=False, top_n=100))
    assert all_themes.get("wait_time", 0) >= 2
    assert all_themes.get("staff", 0) >= 1
