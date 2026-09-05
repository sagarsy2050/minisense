# MiniSense — Presentation Content (15 slides)

Content for a reviewer/interview presentation. Concise by design — detail
lives in `docs/SUBMISSION_REVIEW.md` and `docs/whitepaper.md`, not here.

---

### Slide 1 — Title
**MiniSense — Survey Analysis Agent**
Senior AI Engineer take-home assessment
Local multi-agent system • RAG-grounded • zero cloud APIs

---

### Slide 2 — Problem & business objective
- Businesses collect thousands of survey responses; manual analysis doesn't scale.
- Need: natural-language question → exact numbers + business context → one narrative answer.
- Objective: prove agentic system design, retrieval grounding, and pragmatic engineering judgment under a 6-9 hour scope.

---

### Slide 3 — Requirements
- Part 1: two-level multi-agent pipeline, structured contracts, ≥1 tool-calling example
- Part 2: RAG over the product FAQ — chunk, embed, store, retrieve, integrate, evaluate on 3 questions
- Part 3: 300-500 word fine-tuning design for an 8-class classification scale-out

---

### Slide 4 — Solution architecture
```
question -> Orchestrator (plan) -> DataAgent / RAGAgent / ComparisonAgent
                                          -> SummaryAgent -> narrative
```
- All planning, embeddings, and narration run on local Ollama (`llama3.1:8b`, `nomic-embed-text`)
- Every number in the final answer is computed by deterministic Python, never the LLM

---

### Slide 5 — Multi-agent workflow
- Orchestrator: NL question → structured `Plan` of `TaskSpec`s (LLM-driven, keyword-heuristic fallback)
- DataAgent / RAGAgent / ComparisonAgent execute in isolation, return typed dataclasses
- SummaryAgent: structured results → one narrative paragraph, "use only these numbers" constraint

---

### Slide 6 — Data generation & dataset design
- 100,000 synthetic records, Appendix A schema, 2-month window (Apr-May 2026), 3 business locations
- Non-uniform rating distribution (per-location bias, monthly drift) — not random noise
- Text realism: large per-topic template bank + humanizing pass (typos/casing/emojis) + ~10% deliberate sentiment mismatches
- Validated: rating range, date window, no duplicate IDs, printed distribution report

---

### Slide 7 — DataAgent & tool calling
```
DataAgent.run(task, responses)
  -> tools.filter_responses(...)
  -> tools.compute_csat(filtered)        <- required tool-calling example
  -> tools.compute_top_themes(filtered)
  -> DataAgentResult(...)
```
- Zero LLM calls in this path — numbers must be exact and reproducible
- LLM plans and narrates; Python counts

---

### Slide 8 — RAG pipeline
```
FAQ (~500 words) -> paragraph-first chunking (12 chunks)
                  -> nomic-embed-text (Ollama)
                  -> FAISS IndexFlatIP (cosine)
                  -> top-k retrieval -> RAGAgentResult
```
- Chunking keeps each FAQ Q/A pair intact — avoids splitting question from answer mid-sentence

---

### Slide 9 — Example business question
> "What are the top 3 complaints this month and how do they compare to last month?"
- Routed to DataAgent (current period) + ComparisonAgent (period diff)
- Real result: wait-time mentions +99% MoM, food-quality +27%, no metric crossed the significance threshold

---

### Slide 10 — Retrieval + final answer example
Question: *"What is our overall CSAT and how does it compare to our stated CSAT target?"*
- Top-1 retrieved chunk (score 0.680): the FAQ's exact CSAT-target Q/A
- Final answer grounds the "4.5+ target" claim in that retrieved text, alongside the real computed CSAT (62.13%)
- Full transcript: `outputs/eval_results.md`

---

### Slide 11 — Fine-tuning strategy
```
Frontier-labeled sample (stratified) + human QA
        -> ~3-5k examples -> QLoRA on a 3-8B instruct model
        -> per-class F1 + shadow-mode vs. GPT-4o
        -> adapter-swap serving alongside existing routes
```
- QLoRA chosen: narrow 8-way label space doesn't need full fine-tuning's weight movement; quantized base cuts GPU cost

---

### Slide 12 — Evaluation & quality strategy
- 57 automated tests (config, validation, metrics, chunking, vector store, orchestrator routing, API), all offline
- 3 real RAG evaluation questions with retrieved chunks + final answers committed (`outputs/eval_results.md`)
- A real correctness bug was found and fixed via actual end-to-end runs, not just unit tests (see next slide)

---

### Slide 13 — Engineering decisions & trade-offs
| Decision | Trade-off accepted |
|---|---|
| Plain Python, no LangGraph/LangChain | Simpler to review at this scale; would need multi-provider work to grow |
| "This month" anchored to dataset's own max date, not wall-clock | Fixes a real bug found this session; wrong choice for live-ingest data |
| FAISS exact search over ANN | Zero tuning at this corpus size; wouldn't scale to a huge document set |
| No retry/backoff on Ollama calls | Simpler code; a real production gap |

---

### Slide 14 — Limitations & future improvements
- No multi-turn memory; no retry/backoff on the single external dependency
- RAGAgent/SummaryAgent covered only indirectly by tests, not directly
- Dataset is synthetic — demonstrates pipeline capability, not real operational insight
- Next: direct agent-level tests with mocked Ollama, request-ID tracing, real datastore behind DataAgent at scale

---

### Slide 15 — Conclusion
- Built: a local, multi-agent, RAG-grounded survey analysis system meeting every required assessment component
- Learned: separating "LLM decides/narrates" from "code computes" is what makes numeric answers trustworthy
- Verified: real end-to-end runs against a live Ollama server and a 100k-record dataset, not just passing unit tests
- Next: harden the one external dependency (Ollama) and close the direct agent-test gap
