# MiniSense — Final Assessment Analysis

A direct, point-by-point mapping of this submission against the take-home
brief as written (Parts 1–3 and Appendices A–B), with evidence gathered
from real execution this session — not from reading the code alone.
Repository: `github.com/sagarsy2050/minisense`, commit `eb2a9ff`.

## Verdict: submission satisfies every required element of the brief

67/67 Python tests + 9/9 Node tests pass in a **fresh `git clone`** (not
just in-place); the FastAPI backend, Node gateway, and CLI all produce
real, correct answers against a live local Ollama server and the full
100,000-record dataset; the RAG evaluation checkpoint and fine-tuning
writeup are both present and within spec.

---

## Part 1 — Multi-Agent Pipeline

| Requirement (verbatim from brief) | Status | Evidence |
|---|---|---|
| Orchestrator receives a NL business question | MET | `cli.py`/`api.py::ask` → `orchestrator.answer_question(question, responses)` |
| Breaks it into sub-tasks, routes to sub-agents | MET | `orchestrator.plan_question` → `Plan.tasks: list[TaskSpec]`, dispatch loop routes by `TaskSpec.agent` |
| Synthesizes sub-agent results into final business-language answer | MET | `SummaryAgent.run` — real example: *"This month, customers have been complaining about wait times, with 4,248 mentions... Compared to last month, wait time complaints have increased significantly, up 99%..."* |
| Structured task spec to each sub-agent (not raw text) | MET | `TaskSpec` dataclass (`agent`, `objective`, `business_id`, `period_a`/`period_b`, `query_text`, `top_k`) |
| Sub-agents return structured output (JSON/dataclass) | MET | `DataAgentResult`, `RAGAgentResult`, `ComparisonAgentResult` — typed dataclasses, not strings |
| Final answer is a coherent narrative, not raw numbers | MET | See `docs/example_questions.md` — 10 real narrative answers |
| ≥1 tool-calling example (e.g. `compute_csat(responses)`) | MET | `data_agent.py:33` calls `tools.metrics.compute_csat(filtered)` — the exact pattern the brief names |
| ≥2 of the 4 listed sub-agents | MET (4 of 4) | `DataAgent`, `RAGAgent`, `ComparisonAgent`, `SummaryAgent` all implemented |

**On framework choice**: the brief explicitly allows "plain Python" as an
alternative to LangGraph/LangChain/OpenAI-function-calling — this
submission uses plain Python with a direct Ollama REST client, a
deliberate choice given the scope (5 components, 1 LLM provider) documented
in `docs/SUBMISSION_REVIEW.md` §9, Decision 2.

---

## Part 2 — RAG Pipeline

| Requirement (verbatim from brief) | Status | Evidence |
|---|---|---|
| Chunk the document, justify strategy | MET | Paragraph-first / sentence-pack fallback (`rag/chunking.py`) — justified against the FAQ's Q/A structure in the module docstring and README §7 |
| Embed with a model of choice | MET | `nomic-embed-text` via local Ollama (`.env.example`) |
| Store in a local vector store (FAISS/Chroma/similar) | MET | FAISS `IndexFlatIP` (`rag/vector_store.py`), NumPy fallback if FAISS unavailable |
| Retrieve top-k chunks given a RAGAgent query | MET | `rag/retrieve.py::retrieve(query, top_k)` |
| Inject retrieved chunks into final prompt alongside DataAgent metrics | MET | `summary_agent.py` payload carries both `data_agent_result` and `retrieved_faq_context` in one call |
| Evaluation checkpoint: 3 sample questions, chunks + answers shown | MET | `outputs/eval_results.md` (committed) + 10 more in `docs/example_questions.md` |
| Comment on where retrieval worked/fell short | MET | `outputs/eval_results.md` §"Notes on retrieval quality" — works well on single-heading questions, falls short on cross-section synthesis |

**Real retrieval example** (from this session's live run, not illustrative):
question *"What CSAT threshold triggers a root-cause review?"* → top-1
retrieved chunk `chunk_007` (score 0.707) is the FAQ's exact CSAT-target
Q/A; the final answer correctly cites "scores below 4.0 in any rolling
30-day window."

---

## Part 3 — Fine-Tuning Design

| Requirement | Status | Evidence |
|---|---|---|
| 300–500 words in the README | MET | `README.md` §9, **421 words** (trimmed this session from an initial 541-word draft that exceeded the limit) |
| Data strategy + labeled-example estimate | MET | Stratified frontier-model bootstrap + human QA review; ~3,000–5,000 examples estimated |
| Model & technique (LoRA/QLoRA/Full FT) + rationale | MET | Llama 3.1 8B, QLoRA — narrow label space justifies low-rank adapter over full FT |
| Training pipeline / tooling | MET | HF `transformers` + `peft` + `TRL`'s `SFTTrainer`; Axolotl/LLaMA-Factory for scaled iteration |
| Evaluation metrics + production-readiness bar | MET | Per-class F1 (not aggregate accuracy), agreement-rate vs. GPT-4o, shadow-mode gate |
| Serving alongside existing LLM service | MET | Adapter-swapping (vLLM/TGI multi-LoRA), no separate deployment |
| Future-proofing | MET | Versioned label taxonomy/prompt config, drift-triggered re-labeling |

---

## Appendix A — Dataset

| Requirement | Status | Evidence |
|---|---|---|
| 50,000–100,000 records | MET | 100,000 (`data/generate_data.py --count 100000`) |
| Varied ratings | MET | Non-uniform distribution: `{1: 8664, 2: 12487, 3: 16549, 4: 29868, 5: 32432}` — per-location bias + monthly drift, not uniform random |
| CSAT scores 1–5 | MET (via `rating` field) | The brief's Appendix A schema itself has no separate CSAT field — CSAT is computed as an aggregate (% rated ≥4) from `rating`, consistent with the FAQ's own "CSAT of 4.5+" framing as a share metric, not a per-response score |
| Dates spanning two months | MET | 2026-04-01 to 2026-05-31 |
| Realistic free-text responses | MET | Large per-topic/sentiment template bank (not 3–4 repeated sentences) + humanizing pass (typos, casing, emojis) + ~10% deliberate sentiment/rating mismatches; ~21% distinct non-empty strings across 100k rows |
| Schema fields | MET | `response_id`, `date`, `business_id`, `business_name`, `survey_id`, `survey_name`, `rating`, `response_channel`, `free_text` — matches Appendix A (the brief's own sample JSON has a syntax error, missing comma after `business_name`; the implemented schema uses the corrected 9-field shape) |
| "This is intentionally left for the candidate to generate" | MET, and iterated on | Generator was fixed this session (originally wrote to a hardcoded sandbox path unrelated to this project and ignored `--count`) and enriched for realism — see `docs/final_report.md` for the exact before/after |

---

## Appendix B — Product FAQ

| Requirement | Status | Evidence |
|---|---|---|
| Expand sample FAQ to ~500 words | MET | 581 words (`data/product_faq.md`) — close to the approximate target |
| Additional business context, candidate's own construction | MET | Extended with menu detail, staffing/training notes, multi-location structure, loyalty program, complaint-escalation detail, hours, reservations — all consistent with (and referenced by) the survey dataset's business_id/survey structure |
| GreenLeaf Bistro CSAT target (4.5+) and review threshold (<4.0) preserved | MET | `chunk_007` in the FAQ index, retrieved correctly in every CSAT-related test question this session |

---

## What was NOT required but included anyway

The brief allows a CLI or notebook as the primary interface (FastAPI is
explicitly optional). This submission includes all three: `cli.py`,
`api.py`, and two executed notebooks — plus an optional Node.js gateway/
chat UI/CLI (`client/`) on top of the FastAPI backend, which is additional
scope beyond the brief, not a substitute for it.

## Honest gaps (stated, not hidden)

- No retry/backoff around the single external dependency (Ollama).
- No multi-turn conversation memory (each question is stateless) —
  not required by the brief.
- `ComparisonAgent`'s significance thresholds are engineering-judgment
  constants, not statistically derived — reasonable at this scope, stated
  explicitly in `docs/SUBMISSION_REVIEW.md` §9.

Full detail on all of the above: `docs/SUBMISSION_REVIEW.md` (from-source
technical review) and `docs/final_report.md` (exact files changed, test
results, release blockers — none currently open).

## Bottom line

Every explicitly required element of the brief — the two-level agent
architecture with structured contracts and tool calling, the full RAG
pipeline with a justified chunking strategy and a 3-question evaluation
checkpoint, and the 300–500 word fine-tuning design — is implemented,
tested (67+9 tests passing in a fresh clone), and verified against a real
local Ollama server, not merely present in the code.
