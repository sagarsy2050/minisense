"""
generate_data.py — Synthetic survey response generator for MiniSense.

Produces a JSON file matching the Appendix A schema:
  {
    "responses": [
      {
        "response_id": "r000001",
        "date": "2026-04-01",
        "business_id": "b01",
        "business_name": "GreenLeaf Bistro - Downtown",
        "survey_id": "s01",
        "survey_name": "Dine-In Experience",
        "rating": 4,
        "response_channel": "mobile",
        "free_text": "..."
      },
      ...
    ]
  }

Design notes (why it's built this way):
- The fictional business is GreenLeaf Bistro (matches the Appendix B FAQ),
  run as 3 locations, so DataAgent/RAGAgent answers stay internally consistent
  (menu items, wait-time targets, CSAT target all line up with the FAQ).
- 3 surveys per location cover the natural feedback moments: dine-in,
  takeout/delivery, and the loyalty program.
- Dates span exactly two calendar months (April & May 2026) so the
  assignment's ComparisonAgent has a real "this month vs last month" to work
  with — not just noise.
- Free text is assembled from topic + sentiment template fragments rather
  than one giant list of canned sentences, so wording varies a lot across
  100k rows while staying tightly correlated with the numeric rating (a 1-2
  star row reads negative, a 4-5 star row reads positive, mismatches would
  make the dataset useless for testing DataAgent's theme extraction).
- Two deliberate signals are baked in for the eval questions:
    1. "wait_time" complaints are ~1.7x more likely in May than April,
       concentrated in low ratings -> a real month-over-month top-complaint
       shift for ComparisonAgent to surface.
    2. The Riverside location trends ~0.4 stars lower on average than the
       other two -> a location-level CSAT gap DataAgent can pick up on.
- ~12% of rows have an empty free_text (people who rate but don't comment),
  which is realistic and forces DataAgent to handle missing text gracefully.
"""

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

N_RECORDS = 100_000

# ---------------------------------------------------------------------------
# Businesses (locations of the same fictional chain used in the FAQ doc)
# ---------------------------------------------------------------------------
BUSINESSES = [
    {"business_id": "b01", "business_name": "GreenLeaf Bistro - Downtown", "quality_bias": 0.0},
    {"business_id": "b02", "business_name": "GreenLeaf Bistro - Uptown", "quality_bias": 0.15},
    {"business_id": "b03", "business_name": "GreenLeaf Bistro - Riverside", "quality_bias": -0.4},
]
BUSINESS_WEIGHTS = [0.42, 0.33, 0.25]

# ---------------------------------------------------------------------------
# Surveys
# ---------------------------------------------------------------------------
SURVEYS = [
    {"survey_id": "s01", "survey_name": "Dine-In Experience"},
    {"survey_id": "s02", "survey_name": "Takeout & Delivery"},
    {"survey_id": "s03", "survey_name": "Loyalty Program Feedback"},
]
SURVEY_WEIGHTS = [0.55, 0.35, 0.10]

CHANNELS = ["mobile", "web", "kiosk", "email", "in_store_tablet"]
CHANNEL_WEIGHTS = [0.40, 0.22, 0.18, 0.12, 0.08]

# ---------------------------------------------------------------------------
# Date range: two full months
# ---------------------------------------------------------------------------
START_DATE = date(2026, 4, 1)
END_DATE = date(2026, 5, 31)
ALL_DATES = [START_DATE + timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1)]

def date_weight(d: date) -> float:
    # Slightly busier on weekends (Fri/Sat), slightly busier overall in May
    w = 1.0
    if d.weekday() in (4, 5):  # Fri, Sat
        w *= 1.35
    if d.month == 5:
        w *= 1.12
    return w

DATE_WEIGHTS = [date_weight(d) for d in ALL_DATES]

# ---------------------------------------------------------------------------
# Topic vocabulary, tied to the FAQ content (menu items, wait time, CSAT, etc.)
# ---------------------------------------------------------------------------
MENU_ITEMS = ["Avocado Toast", "Garden Bowl", "Cold Brew Coffee", "Grilled Salmon Salad",
              "Veggie Wrap", "Berry Parfait", "Sourdough Club Sandwich", "Mushroom Risotto"]

POSITIVE = {
    "food_quality": [
        "The {item} was fresh and beautifully plated.",
        "Loved the {item} - best version I've had in the city.",
        "Food quality has been consistently excellent, especially the {item}.",
        "The {item} arrived hot and tasted great.",
        "really good {item} today, everything tasted fresh",
        "Ingredients tasted high quality, you can tell it's made fresh.",
        "The {item} was cooked perfectly, exactly what I wanted.",
        "Best {item} I've had at any location so far.",
        "Flavor on the {item} was spot on.",
        "Perfectly seasoned and generous portion for the {item}.",
    ],
    "wait_time": [
        "We were seated right away and food came out fast.",
        "Order was ready well under 10 minutes, exactly as expected.",
        "Quick service even during a busy lunch rush.",
        "No wait at all today, very impressed with the speed.",
        "surprisingly fast for a Friday evening",
        "In and out in under 10 minutes, even during the dinner rush.",
        "Barely waited despite the line at the counter.",
        "Food came out faster than I expected for a peak hour.",
        "quick",
        "Service was snappy today, no complaints on timing.",
    ],
    "staff": [
        "Our server was friendly and attentive the whole time.",
        "Staff went out of their way to accommodate a dietary request.",
        "The team at the counter was upbeat and welcoming.",
        "Great, knowledgeable staff who recommended a dish we loved.",
        "staff were super nice, made the visit",
        "Everyone behind the counter was smiling and helpful.",
        "Manager came by to check on us, nice touch.",
        "Friendly crew, felt genuinely welcomed.",
        "Staff remembered our usual order, appreciated that.",
    ],
    "cleanliness": [
        "Dining area was spotless and well organized.",
        "Tables and restrooms were very clean.",
        "Everything felt tidy and well maintained.",
        "very clean location, noticeably well kept",
        "Restrooms were clean, tables wiped down promptly.",
        "Place looked freshly cleaned when we walked in.",
    ],
    "price_value": [
        "Great value for the portion size.",
        "Prices are fair for the quality you get.",
        "Worth every penny, will definitely be back.",
        "good value, portions are generous for the price",
        "Reasonably priced for the quality of food.",
        "Fair prices, no complaints about the bill.",
    ],
    "ambiance": [
        "Loved the atmosphere - cozy and not too loud.",
        "Nice music and lighting, great spot to relax.",
        "The seating area has a really pleasant vibe.",
        "nice vibe, good spot to work from too",
        "Comfortable seating and a relaxed atmosphere.",
        "Great spot for a quiet lunch, not too crowded.",
    ],
    "order_accuracy": [
        "Order was exactly right, nothing missing.",
        "They got every substitution correct on our order.",
        "got everything I ordered, no mistakes",
        "Order accuracy has been perfect the last few visits.",
        "Double-checked my order and it was all correct.",
    ],
    "loyalty_program": [
        "The rewards program is easy to use and the points add up fast.",
        "Redeeming points for the {item} was simple and quick.",
        "Really like the birthday reward perk in the loyalty app.",
        "love the loyalty app, easy to redeem points",
        "Points added up quickly, redeemed a free item already.",
    ],
    "online_ordering": [
        "The app made ordering ahead really easy.",
        "Online order was ready exactly on time.",
        "app worked great, order was ready when I got there",
        "Mobile ordering saved us a lot of time today.",
    ],
    "availability": [
        "Everything I wanted was in stock today.",
        "good, they had the {item} for once",
        "Glad the {item} was available, it sells out fast.",
    ],
}

NEGATIVE = {
    "food_quality": [
        "The {item} was cold by the time it reached the table.",
        "{item} was underseasoned and disappointing.",
        "Portion size for the {item} felt smaller than usual.",
        "The {item} didn't match the description on the menu.",
        "food was cold, sent it back",
        "The {item} tasted like it had been sitting out for a while.",
        "Quality has gone downhill lately, especially the {item}.",
        "not fresh at all, kind of disappointed tbh",
        "{item} was bland, needed way more seasoning.",
        "Inconsistent - the {item} was great last time, not this time.",
    ],
    "wait_time": [
        "Waited almost 25 minutes just to be seated during off-peak hours.",
        "Order took way longer than the 10 minute target you advertise.",
        "Service was very slow today, over 20 minutes for a simple order.",
        "Line at the counter barely moved for 15+ minutes.",
        "waited forever, not worth it for lunch",
        "20+ minutes for a coffee and a sandwich, way too long.",
        "Peak hour wait was brutal, over 25 minutes today.",
        "took way too long...",
        "Line was out the door and moved painfully slowly.",
        "Way past the advertised wait time, staff seemed short-handed.",
    ],
    "staff": [
        "Staff seemed overwhelmed and forgot part of our order.",
        "Server was inattentive and never checked back on us.",
        "Felt rushed by the staff, not a great experience.",
        "Nobody acknowledged us for several minutes after we sat down.",
        "staff was kind of rude honestly",
        "Server seemed annoyed when we asked a question.",
        "Understaffed today, everyone looked stressed.",
        "no one greeted us, had to flag someone down",
        "Staff attitude was not great during a busy period.",
    ],
    "cleanliness": [
        "Table was sticky and hadn't been wiped down.",
        "Restroom needed attention.",
        "Floor near the counter was messy during our visit.",
        "tables were dirty, had to wipe it ourselves",
        "Restroom was out of paper towels and not very clean.",
        "Noticed crumbs and spills that hadn't been cleaned up.",
    ],
    "price_value": [
        "Prices have gone up but portions feel smaller.",
        "Didn't feel like good value for what we paid.",
        "A bit overpriced compared to similar spots nearby.",
        "kind of pricey for what you get",
        "Got charged for an extra item I didn't order - billing issue.",
        "Bill was higher than expected, had to ask for a correction.",
        "Not great value lately, prices keep creeping up.",
    ],
    "ambiance": [
        "Very loud and hard to have a conversation.",
        "Seating area felt cramped during the lunch rush.",
        "way too loud for a weekday lunch",
        "Crowded and noisy, hard to relax.",
    ],
    "order_accuracy": [
        "Order was missing an item we paid for.",
        "Got the wrong substitution on our sandwich.",
        "missing an item again, second time this month",
        "Order was wrong, had to go back and get it fixed.",
        "Paid for an add-on that never showed up in the order.",
        "Received someone else's order by mistake.",
    ],
    "loyalty_program": [
        "Loyalty points didn't apply correctly to my order.",
        "App glitched when I tried to redeem a reward.",
        "points never showed up after my last visit",
        "Rewards app crashed twice trying to redeem a coupon.",
    ],
    "online_ordering": [
        "Online order system crashed twice before it went through.",
        "Pickup time in the app didn't match how long it actually took.",
        "app kept freezing, had to restart it 3 times",
        "Mobile order wasn't ready even 15 minutes past pickup time.",
    ],
    "availability": [
        "The {item} was sold out when we got there.",
        "Wanted to order the {item} but it wasn't available.",
        "out of the {item} again, third time this happens",
        "Menu said available but they were out of {item} in store.",
    ],
}

NEUTRAL = {
    "food_quality": [
        "The {item} was fine, nothing special.",
        "Food was okay, about what I expected.",
        "it was decent, nothing to write home about",
        "Food quality was consistent with past visits, nothing new.",
    ],
    "wait_time": [
        "Wait was about average, nothing notable either way.",
        "Service speed was acceptable.",
        "wait wasn't bad, about what I expected",
        "Took a little while but nothing out of the ordinary.",
    ],
    "staff": [
        "Staff were polite but not especially memorable.",
        "Service was fine overall.",
        "staff was fine, nothing stood out",
        "Nothing wrong with the service, just average.",
    ],
    "cleanliness": [
        "Place looked reasonably clean.",
        "No complaints about cleanliness, nothing standout either.",
        "clean enough, no issues there",
    ],
    "price_value": [
        "Pricing seemed about average for this kind of place.",
        "Fair enough for what we got.",
        "price was okay, about what you'd expect",
    ],
    "ambiance": [
        "Atmosphere was okay for a quick meal.",
        "Nothing wrong with the space, just average.",
        "fine for a quick bite, nothing special about the vibe",
    ],
    "order_accuracy": [
        "Order was mostly correct.",
        "Got what we ordered, no issues.",
        "order was right, no complaints",
    ],
    "loyalty_program": [
        "Rewards program is fine, could be more generous.",
        "Points system works as expected.",
        "loyalty program is okay, nothing exciting",
    ],
    "online_ordering": [
        "Online ordering worked, took a couple tries to load.",
        "App was okay, a little slow.",
        "app worked fine, a bit clunky though",
    ],
    "availability": [
        "The {item} was available, no issues there.",
        "everything on the menu was in stock today",
    ],
}

# Free-form connector fragments used to occasionally stitch two topic
# sentences together with a contrasting conjunction, producing the kind of
# "positive overall, but one thing was off" mixed feedback real surveys are
# full of (see build_free_text's mismatch handling below).
CONTRAST_CONNECTORS = ["but", "however,", "although", "still,", "that said,"]

# Cheap, deliberately light-touch "humanizing" transforms applied to a
# minority of rows so 100k records don't all read as clean, well-punctuated
# template output. Kept probabilistic and non-destructive to meaning.
EMOJIS = [" 😊", " 😞", " 🙂", " 😤", "", "", "", ""]  # weight toward no emoji
ABBREVIATIONS = {"you": "u", "your": "ur", "though": "tho", "because": "bc", "thanks": "thx"}


def _humanize(text: str) -> str:
    if not text:
        return text
    r = random.random()
    if r < 0.06:
        text = text.lower()
    if r < 0.05:
        text = text.rstrip(".!?") + "..."
    elif r < 0.09:
        text = text.rstrip(".!?") + "!!"
    elif r < 0.11:
        text = text.rstrip(".!?")  # dropped end punctuation
    if random.random() < 0.05:
        for word, abbr in ABBREVIATIONS.items():
            if word in text.split():
                text = text.replace(f" {word} ", f" {abbr} ", 1)
                break
    if random.random() < 0.08:
        text += random.choice(EMOJIS)
    return text

# Topics weighted so wait_time and food_quality dominate, as in most real feedback
TOPIC_WEIGHTS_APRIL = {
    "food_quality": 0.23, "wait_time": 0.14, "staff": 0.16, "cleanliness": 0.08,
    "price_value": 0.10, "ambiance": 0.08, "order_accuracy": 0.08,
    "loyalty_program": 0.05, "online_ordering": 0.05, "availability": 0.03,
}
# May: wait_time complaints spike (staffing shortage narrative), everything else normalizes down slightly
TOPIC_WEIGHTS_MAY = {
    "food_quality": 0.19, "wait_time": 0.24, "staff": 0.14, "cleanliness": 0.07,
    "price_value": 0.09, "ambiance": 0.07, "order_accuracy": 0.07,
    "loyalty_program": 0.05, "online_ordering": 0.05, "availability": 0.03,
}

TOPICS = list(TOPIC_WEIGHTS_APRIL.keys())


def weighted_choice(items, weights):
    return random.choices(items, weights=weights, k=1)[0]


def pick_rating(business_bias: float, month: int) -> int:
    # Base distribution skewed positive, shifted by per-location quality_bias
    # and a slight May dip (matches the wait_time complaint spike).
    base = [0.08, 0.12, 0.16, 0.30, 0.34]  # ratings 1..5
    month_shift = -0.03 if month == 5 else 0.0
    bias = business_bias + month_shift
    # Shift probability mass toward higher or lower ratings based on bias
    weights = []
    for i, p in enumerate(base):
        star = i + 1
        adj = p * (1 + bias * (star - 3) * 0.35)
        weights.append(max(adj, 0.001))
    total = sum(weights)
    weights = [w / total for w in weights]
    return random.choices([1, 2, 3, 4, 5], weights=weights, k=1)[0]


def build_free_text(rating: int, month: int) -> str:
    if random.random() < 0.12:
        return ""  # no comment left

    topic_weights = TOPIC_WEIGHTS_MAY if month == 5 else TOPIC_WEIGHTS_APRIL
    n_topics = 1 if random.random() < 0.65 else 2
    chosen_topics = random.choices(TOPICS, weights=list(topic_weights.values()), k=n_topics)
    chosen_topics = list(dict.fromkeys(chosen_topics))  # dedupe, keep order

    sentiment_bank = POSITIVE if rating >= 4 else (NEGATIVE if rating <= 2 else NEUTRAL)
    # ~10% of the time, deliberately mismatch one topic's sentiment against the
    # overall rating (e.g. a 5-star visit that still mentions a long wait) —
    # real feedback rarely agrees on every dimension even when the headline
    # rating is clear.
    mismatch = len(chosen_topics) == 2 and random.random() < 0.10
    mismatch_bank = NEGATIVE if sentiment_bank is not NEGATIVE else POSITIVE

    sentences = []
    for idx, topic in enumerate(chosen_topics):
        bank = mismatch_bank if (mismatch and idx == 1) else sentiment_bank
        template = random.choice(bank[topic])
        if "{item}" in template:
            template = template.format(item=random.choice(MENU_ITEMS))
        if idx == 1 and mismatch:
            template = f"{random.choice(CONTRAST_CONNECTORS)} {template[0].lower()}{template[1:]}"
        sentences.append(template)

    text = " ".join(sentences)
    return _humanize(text)


def make_response(i: int) -> dict:
    d = random.choices(ALL_DATES, weights=DATE_WEIGHTS, k=1)[0]
    business = random.choices(BUSINESSES, weights=BUSINESS_WEIGHTS, k=1)[0]
    survey = random.choices(SURVEYS, weights=SURVEY_WEIGHTS, k=1)[0]
    channel = weighted_choice(CHANNELS, CHANNEL_WEIGHTS)
    rating = pick_rating(business["quality_bias"], d.month)
    free_text = build_free_text(rating, d.month)

    return {
        "response_id": f"r{i:06d}",
        "date": d.isoformat(),
        "business_id": business["business_id"],
        "business_name": business["business_name"],
        "survey_id": survey["survey_id"],
        "survey_name": survey["survey_name"],
        "rating": rating,
        "response_channel": channel,
        "free_text": free_text,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=N_RECORDS, help="Number of survey records to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "survey_responses.json",
        help="Output path for the generated JSON file",
    )
    args = parser.parse_args()
    random.seed(args.seed)

    responses = [make_response(i + 1) for i in range(args.count)]
    out = {"responses": responses}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1)

    # Validation report (Appendix A schema fields only; CSAT/complaint rate
    # are aggregate stats derived here for the log, not per-record fields).
    from collections import Counter
    from statistics import median

    ratings = Counter(r["rating"] for r in responses)
    months = Counter(r["date"][:7] for r in responses)
    biz = Counter(r["business_name"] for r in responses)
    channels = Counter(r["response_channel"] for r in responses)
    empty_text = sum(1 for r in responses if r["free_text"] == "")
    unique_texts = len({r["free_text"] for r in responses if r["free_text"]})
    non_empty = len(responses) - empty_text

    rating_values = [r["rating"] for r in responses]
    avg_rating = sum(rating_values) / len(rating_values)
    csat_pct = sum(1 for r in rating_values if r >= 4) / len(rating_values) * 100

    assert all(1 <= r["rating"] <= 5 for r in responses), "rating out of range"
    assert all(r["date"][:7] in ("2026-04", "2026-05") for r in responses), "date outside two-month window"
    assert len({r["response_id"] for r in responses}) == len(responses), "duplicate response_id"

    print("Records generated:", len(responses), f"(seed={args.seed})")
    print("Rating distribution:", dict(sorted(ratings.items())))
    print(f"Average rating: {avg_rating:.2f}  Median rating: {median(rating_values):.1f}")
    print(f"CSAT (% rated 4-5): {csat_pct:.1f}%")
    print("By month:", dict(months))
    print("By business:", dict(biz))
    print("By channel:", dict(channels))
    print(f"Empty free_text: {empty_text} ({empty_text / len(responses):.1%})")
    print(f"Unique non-empty free_text strings: {unique_texts} / {non_empty} "
          f"({unique_texts / non_empty:.1%} distinct)")


if __name__ == "__main__":
    main()
