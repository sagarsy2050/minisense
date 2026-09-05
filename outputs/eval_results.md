# MiniSense — Evaluation Checkpoint

3 sample questions, run end-to-end.

## Q1. What are the top 3 complaints this month and how do they compare to last month?

**Plan reasoning:** Break down the question into two tasks: one to get the top complaints this month and another to compare them to last month.

**Routed tasks:**
- `DataAgent` — Get the top 3 complaints this month
- `ComparisonAgent` — Compare the top 3 complaints this month to last month

**DataAgent metrics:** n=54143, avg_rating=3.645, csat_pct=62.13, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]

**ComparisonAgent deltas:**
- average_rating: 3.655 -> 3.645 (not significant)
- csat_pct: 62.5 -> 62.13 (not significant)
- response_count: 45857.0 -> 54143.0 (not significant)
- theme shifts: ['food quality mentions up 27% (3329 -> 4221)', 'wait time mentions up 99% (2137 -> 4248)']

**Final answer:**

This month, customers have been complaining about wait times, with 4,248 mentions, followed by staff issues with 4,234 mentions, and food quality concerns with 4,221 mentions. Compared to last month, food quality complaints have increased by 27% and wait time complaints have skyrocketed by 99%. Meanwhile, response count has seen an 18% increase, with 8,286 more responses this month. The average rating has dipped slightly, down to 3.645, and CSAT percentage has also decreased, down to 62.13%. It's worth noting that none of these changes are significant enough to trigger our policies for corrective action, but it's still worth keeping an eye on these trends.

## Q2. What is our overall CSAT and how does it compare to our stated CSAT target?

**Plan reasoning:** Break down the question into two tasks: one to compute the current CSAT and another to compare it to the target.

**Routed tasks:**
- `DataAgent` — Compute the current CSAT
- `RAGAgent` — Retrieve CSAT target and policy context
- `ComparisonAgent` — Compare current CSAT to target

**DataAgent metrics:** n=54143, avg_rating=3.645, csat_pct=62.13, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]

**ComparisonAgent deltas:**
- average_rating: 3.645 -> 3.649 (not significant)
- csat_pct: 62.13 -> 62.3 (not significant)
- response_count: 54143.0 -> 100000.0 (significant)
- theme shifts: ['food quality mentions up 79% (4221 -> 7550)', 'staff mentions up 90% (4234 -> 8036)', 'wait time mentions up 50% (4248 -> 6385)', 'pricing mentions up 90% (1215 -> 2308)', 'cleanliness mentions up 95% (2252 -> 4388)', 'billing mentions up 106% (171 -> 352)', 'value mentions up 101% (1483 -> 2975)', 'menu variety mentions up 93% (542 -> 1046)']

**RAGAgent retrieved chunks:**
- `chunk_007` (score=0.680): **Q: What is your CSAT target?** A: We aim for a CSAT of 4.5+ (share of survey responses rated 4 or 5 out of 5). Scores below 4.0 in any rolling 30-day window trigger a root-cause review with the operations team, coverin...
- `chunk_012` (score=0.389): **Q: Do you operate multiple locations?** A: Yes. GreenLeaf Bistro operates as a small multi-location business, and each location is tracked separately in our survey system (by `business_id`) so operations can compare pe...
- `chunk_004` (score=0.382): **Q: What is your average wait time?** A: We target under 10 minutes for counter orders during off-peak hours. Peak hours (12–1 PM and 6–8 PM) may see 15–20 minute waits, especially on weekends. Mobile pre-orders skip th...
- `chunk_008` (score=0.372): **Q: How do you use customer survey feedback?** A: Every guest receives a short survey link after checkout. Ratings and free-text comments feed into a weekly operations dashboard. Themes that appear in more than 5% of a ...

**Final answer:**

Our overall CSAT for the month of May is 62.13%, which is below our target of 4.5+ (a score of 4 or 5 out of 5). While our CSAT has increased by 0.27% compared to the previous month, this is still a significant gap from our target. Reviewing the top themes, we see that wait time, staff, and food quality are the most common concerns, with wait time mentions increasing by 50% from 4248 to 6385. It's worth noting that our response count has increased significantly, by 84.7%, to 100,000, which may skew the CSAT percentage. We should investigate the root causes of these issues and consider reviewing our staffing levels and ticket times as per our operations policy.

## Q3. How long do customers typically wait, and is that in line with our policy?

**Plan reasoning:** Decomposed the question into two tasks: one to retrieve wait time data and another to retrieve relevant policy context.

**Routed tasks:**
- `DataAgent` — Compute average wait time for the last 30 days
- `RAGAgent` — Retrieve policy context on wait times

**DataAgent metrics:** n=54143, avg_rating=3.645, csat_pct=62.13, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]

**RAGAgent retrieved chunks:**
- `chunk_004` (score=0.697): **Q: What is your average wait time?** A: We target under 10 minutes for counter orders during off-peak hours. Peak hours (12–1 PM and 6–8 PM) may see 15–20 minute waits, especially on weekends. Mobile pre-orders skip th...
- `chunk_005` (score=0.572): **Q: Can I make a reservation?** A: Reservations are accepted for parties of 6 or more, up to 30 days in advance. Smaller parties are seated first-come, first-served, with a digital waitlist visible from the entrance.
- `chunk_011` (score=0.553): **Q: What are your hours?** A: Most locations are open 7 AM–9 PM daily. A few downtown locations extend to 10 PM on Fridays and Saturdays. Exact hours are listed per-location in the app.
- `chunk_006` (score=0.493): **Q: How do you handle complaints?** A: All complaints are escalated to the shift manager within 15 minutes of being raised. Refunds or replacements are offered for quality issues, and recurring complaint categories are ...

**Final answer:**

Based on our analysis of 54,143 customer responses, we found that the most common theme of complaints was wait time, with 4248 customers mentioning it. This is concerning, as our policy targets an average wait time of under 10 minutes during off-peak hours, and up to 15-20 minutes during peak hours. However, it appears that we are not meeting these targets, as the average wait time is likely to be higher than 10 minutes. We also received 4234 complaints about staff, and 4221 about food quality. It's worth noting that our policy allows for reservations for parties of 6 or more, but smaller parties are seated first-come, first-served, which may contribute to longer wait times.

## Notes on retrieval quality

- Retrieval works well for questions that map to a single FAQ heading (CSAT target, wait-time policy, complaint handling) — the sentence-aware chunking keeps each Q/A pair intact, so the top-1 chunk is almost always the exact right answer.
- It falls short for questions that need information synthesized across multiple FAQ sections (e.g. "how does staffing relate to wait times") — retrieval returns the two relevant chunks independently, but connecting them into one causal story is left entirely to the SummaryAgent's LLM call rather than the retrieval step itself.
- Because the FAQ is small (~500 words, ~15-20 chunks), there isn't much headroom for retrieval to fail outright (return an irrelevant chunk) — the risk profile would change a lot on a larger, noisier corpus.
