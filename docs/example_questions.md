# MiniSense — 10 Example Questions (real executions)

Every answer below is a real, unedited run against the live system (100,000-record dataset, `llama3.1:8b` + `nomic-embed-text` via local Ollama, `python scripts/generate_example_questions_doc.py`). Reproduce any of these yourself with:

```bash
python -m minisense.cli "<question>"
```

## 1. What are the top 3 complaints this month and how do they compare to last month?

**Routed to:** DataAgent, ComparisonAgent

**DataAgent:** n=54143, avg_rating=3.645, csat_pct=62.13%, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]
**ComparisonAgent:** average_rating: 3.655 -> 3.645 (not significant); csat_pct: 62.5 -> 62.13 (not significant); response_count: 45857.0 -> 54143.0 (not significant)
**Theme shifts:** wait time mentions up 99% (2137 -> 4248); food quality mentions up 27% (3329 -> 4221)

**Answer:**

This month, customers have been complaining most about wait times, with 4,248 mentions, followed by issues with staff, with 4,234 mentions, and food quality, with 4,221 mentions. Compared to last month, wait time complaints have increased significantly, up 99% from 2,137 to 4,248, while food quality complaints have also seen a notable increase, up 27% from 3,329 to 4,221. However, average ratings and CSAT percentages have remained relatively stable, with a slight decline of 0.27% in average ratings and 0.59% in CSAT percentages. The total number of responses has increased by 18.07% from 45,857 to 54,143.

## 2. What is our overall CSAT and how does it compare to our stated CSAT target?

**Routed to:** DataAgent, RAGAgent, ComparisonAgent

**DataAgent:** n=54143, avg_rating=3.645, csat_pct=62.13%, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]
**ComparisonAgent:** average_rating: 3.645 -> 3.649 (not significant); csat_pct: 62.13 -> 62.3 (not significant); response_count: 54143.0 -> 100000.0 (significant)
**Theme shifts:** value mentions up 101% (1483 -> 2975); pricing mentions up 90% (1215 -> 2308); staff mentions up 90% (4234 -> 8036); cleanliness mentions up 95% (2252 -> 4388); menu variety mentions up 93% (542 -> 1046); billing mentions up 106% (171 -> 352); wait time mentions up 50% (4248 -> 6385); food quality mentions up 79% (4221 -> 7550)
**RAGAgent retrieved:** [chunk_007] score=0.680; [chunk_012] score=0.389; [chunk_004] score=0.382; [chunk_008] score=0.372

**Answer:**

Our overall CSAT for the month of May is 62.13%, which is below our target of 4.5+ (4 or 5 out of 5 ratings). While our CSAT has increased by 0.27% compared to the previous period, this still falls short of our goal. One area of concern is our wait time, which has increased by 50% to 6385 mentions, indicating that customers are experiencing longer wait times. On the other hand, staff mentions have increased by 90% to 8036, which may indicate that customers are appreciating the service they receive. Our average rating has also increased by 0.11% to 3.645, but this is still below our target of 4.5+.

## 3. How long do customers typically wait, and is that in line with our policy?

**Routed to:** DataAgent, RAGAgent

**DataAgent:** n=54143, avg_rating=3.645, csat_pct=62.13%, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]
**RAGAgent retrieved:** [chunk_004] score=0.697; [chunk_005] score=0.572; [chunk_011] score=0.553; [chunk_006] score=0.493

**Answer:**

According to our recent survey data, customers typically wait around 8 minutes, which is within our policy for off-peak hours. However, during peak hours, wait times can reach up to 20 minutes, especially on weekends. This suggests that our policy of aiming for under 10 minutes during off-peak hours is being met, but we may need to adjust our staffing or procedures to meet the higher demand during peak hours. Our mobile pre-order system is a useful option for customers who want to avoid waiting in line, and we're doing a good job of handling complaints, with 62% of customers reporting a satisfactory experience.

## 4. What does the FAQ say about handling customer complaints?

**Routed to:** RAGAgent, DataAgent

**DataAgent:** n=54143, avg_rating=3.645, csat_pct=62.13%, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]
**RAGAgent retrieved:** [chunk_006] score=0.713; [chunk_009] score=0.611; [chunk_008] score=0.585; [chunk_012] score=0.519

**Answer:**

According to our customer survey data, we received 54,143 responses during the month of May 2026, with an average rating of 3.645 out of 5. The CSAT (Customer Satisfaction) percentage was 62.13%, indicating that while we have room for improvement, we are meeting our customer expectations. The top complaints were related to wait times, staff, and food quality, with 4,248, 4,234, and 4,221 complaints respectively. Our FAQ policy states that all complaints are escalated to the shift manager within 15 minutes and that refunds or replacements are offered for quality issues. Additionally, we review recurring complaint categories weekly by the operations team to address systemic problems. It's worth noting that our staff training program includes a two-week onboarding process that covers customer communication and food safety, and ongoing coaching is driven by survey themes.

## 5. How did staff-related complaints change between April and May?

**Routed to:** DataAgent, DataAgent, ComparisonAgent

**DataAgent:** n=45857, avg_rating=3.655, csat_pct=62.5%, top_themes=[('staff', 3802), ('food_quality', 3329), ('wait_time', 2137)]
**ComparisonAgent:** average_rating: 3.655 -> 3.645 (not significant); csat_pct: 62.5 -> 62.13 (not significant); response_count: 45857.0 -> 54143.0 (not significant)
**Theme shifts:** wait time mentions up 99% (2137 -> 4248); food quality mentions up 27% (3329 -> 4221)

**Answer:**

Staff-related complaints remained a significant concern in May, with 3802 complaints out of 54143 total responses. This is a slight decrease from April, where 45857 responses included 3802 staff-related complaints. While the overall response count increased by 18.07% between the two months, the average rating for staff-related complaints actually decreased by 0.27% to 3.645. Furthermore, the proportion of staff-related complaints in May (62.13%) was also lower than in April (62.5%). It's worth noting that the number of mentions for "wait time" and "food quality" themes increased by 99% and 27%, respectively, but staff complaints still dominated the top themes.

## 6. What are your most popular menu items according to the FAQ?

**Routed to:** RAGAgent, DataAgent

**DataAgent:** n=54143, avg_rating=3.645, csat_pct=62.13%, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]
**RAGAgent retrieved:** [chunk_001] score=0.733; [chunk_010] score=0.577; [chunk_002] score=0.539; [chunk_003] score=0.497

**Answer:**

According to our customer feedback, the top menu items at our restaurant are the Avocado Toast, the Garden Bowl, and the Cold Brew Coffee. These items have been consistently popular among our customers, with the Avocado Toast being the most frequently mentioned. Our menu pricing is reviewed quarterly to ensure that core items like the Avocado Toast and Garden Bowl remain within a stable price band, despite seasonal specials and fluctuations in ingredient costs. We also accommodate dietary restrictions by labeling every item on the menu with vegetarian, vegan, gluten-free, and nut-free options, and our kitchen staff are trained on cross-contamination procedures for severe allergies. Overall, our menu offerings and pricing strategy seem to be meeting customer expectations, with a CSAT (customer satisfaction) rate of 62.13% and an average rating of 3.645 out of 5.

## 7. What CSAT threshold triggers a root-cause review?

**Routed to:** DataAgent, RAGAgent

**DataAgent:** n=100000, avg_rating=3.649, csat_pct=62.3%, top_themes=[('staff', 8036), ('food_quality', 7550), ('wait_time', 6385)]
**RAGAgent retrieved:** [chunk_007] score=0.707; [chunk_006] score=0.457; [chunk_008] score=0.452; [chunk_004] score=0.450

**Answer:**

Based on our customer satisfaction survey results, we have a CSAT of 62.3%, which falls below our target of 4.5+. This triggers a root-cause review with the operations team to investigate the underlying issues. Our top customer complaint themes are staff-related, food quality, and wait times, which may indicate areas for improvement. According to our policy, scores below 4.0 in any rolling 30-day window require a review, and we've reached that threshold. The operations team will review staffing levels, ticket times, and ingredient quality to address these concerns.

## 8. What is our average rating and response count for the Riverside location?

**Routed to:** DataAgent, DataAgent

**DataAgent:** n=25021, avg_rating=3.439, csat_pct=55.07%, top_themes=[('staff', 2049), ('food_quality', 1826), ('wait_time', 1741)]

**Answer:**

For the Riverside location, our customers have given us an average rating of 3.439 out of 5, with a response count of 25,021. This indicates a relatively high level of engagement from customers, but the average rating suggests there is room for improvement. The top themes that customers have mentioned in their feedback are staff, food quality, and wait time, with staff being the most commonly cited issue. In terms of how customers responded to us, the majority came through mobile devices, with 10,044 responses.

## 9. Which response channel do customers use most often?

**Routed to:** DataAgent

**DataAgent:** n=100000, avg_rating=3.649, csat_pct=62.3%, top_themes=[('staff', 8036), ('food_quality', 7550), ('wait_time', 6385)]

**Answer:**

Based on our analysis of 100,000 customer responses, we can see that customers are most likely to interact with our staff, with 8,036 mentions of this theme. In terms of response channels, mobile is the clear winner, accounting for 40,164 responses, followed closely by web with 21,966 responses. Email and in-store tablets are also used frequently, but to a lesser extent. Interestingly, kiosk interactions are relatively low, with only 17,731 responses. It's worth noting that our average customer satisfaction rating is 3.65 out of 5, with 62.3% of customers reporting a positive experience.

## 10. What is your policy on refunds or replacements for quality issues?

**Routed to:** RAGAgent, DataAgent

**DataAgent:** n=54143, avg_rating=3.645, csat_pct=62.13%, top_themes=[('wait_time', 4248), ('staff', 4234), ('food_quality', 4221)]
**RAGAgent retrieved:** [chunk_006] score=0.629; [chunk_003] score=0.517; [chunk_004] score=0.500; [chunk_010] score=0.496

**Answer:**

Our policy on refunds or replacements for quality issues is to offer them promptly, with all complaints escalated to the shift manager within 15 minutes. This is in line with our commitment to addressing systemic problems, not just one-off mistakes, as reflected in our weekly review of recurring complaint categories by the operations team. Despite our efforts, quality issues remain a concern, with food quality being the third most common theme among customer complaints, accounting for 4221 responses. This is a significant issue, particularly given that produce is sourced from local farms only three times a week. Our average wait time is also a concern, with customers experiencing waits of over 10 minutes during peak hours.
