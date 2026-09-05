# MiniSense: Designing a Multi-Agent, Retrieval-Grounded Survey Intelligence System

*A technical engineering paper on the MiniSense take-home assessment implementation.*

## 1. Abstract

MiniSense is a small, fully local system that answers natural-language
business questions about customer survey feedback. It combines a two-level
multi-agent architecture — an LLM-driven Orchestrator routing to four typed
sub-agents — with a from-scratch retrieval-augmented generation (RAG)
pipeline grounding answers in a product FAQ. The defining engineering
decision is a strict separation between LLM responsibilities (planning,
routing, narration) and deterministic Python responsibilities (every
numeric calculation), so that exact figures like CSAT and complaint counts
are always reproducible regardless of what a language model does or does
not compute correctly. The system runs entirely against a local Ollama
server — no cloud LLM API, no network call at query time.

## 2. Business context

A business collecting thousands of survey responses per month cannot
manually read them for trends. It needs both exact, auditable numbers
(what fraction of customers were satisfied, which complaint grew) and
qualitative business context (does the FAQ's own stated policy explain an
observed pattern). Neither an analytics dashboard alone (no narrative,
no FAQ grounding) nor a chatbot alone (no guaranteed numeric accuracy) 
satisfies both needs; MiniSense is built specifically at that intersection.

## 3. Problem definition

Given a synthetic dataset of 100,000 survey responses (schema: response id,
date, business id/name, survey id/name, 1-5 rating, response channel,
free-text) spanning two months across three business locations, and a
~500-word product FAQ, answer arbitrary natural-language business questions
with (a) exact computed metrics, (b) FAQ-grounded business context where
relevant, and (c) one coherent narrative paragraph — never raw JSON, never
an unsupported claim.

## 4. System architecture

```
question -> Orchestrator (plan_question)
              |-- Ollama reachable -> LLM plan (structured JSON)
              `-- Ollama down       -> heuristic keyword plan
            -> Plan{ reasoning, tasks: [TaskSpec, ...] }
            -> dispatch loop
                 |-- DataAgent(TaskSpec)       -> DataAgentResult
                 |-- ComparisonAgent(TaskSpec) -> ComparisonAgentResult (calls DataAgent twice)
                 `-- RAGAgent(TaskSpec)        -> RAGAgentResult
            -> SummaryAgent(question, results) -> narrative + citations
            -> OrchestratorRun{ plan, results, summary, trace }
```

Every arrow crossing an agent boundary carries a typed Python dataclass
(`schemas.py`), never a raw string — the Orchestrator never hands a
sub-agent unstructured text, and no sub-agent returns free text except the
final narrative itself.

## 5. Multi-agent design

Four sub-agents, each with one job:

- **DataAgent** — filters the dataset by period/business and computes exact
  metrics via `tools/metrics.py` (CSAT, average rating, top themes, channel
  breakdown). Contains no LLM call.
- **RAGAgent** — embeds the routed query and retrieves top-k FAQ chunks via
  FAISS. Contains no LLM call beyond the embedding model itself.
- **ComparisonAgent** — calls DataAgent twice (period A, period B) and diffs
  every metric plus full theme counts, flagging changes "significant" via
  explainable fixed thresholds. Contains no LLM call.
- **SummaryAgent** — the only agent touching free-form generation; receives
  every other agent's structured output and an explicit "use only these
  numbers" system prompt, returning one narrative paragraph. Falls back to
  a deterministic template if Ollama is unreachable.

This separation exists because a single "do everything" agent would force
the LLM to also perform exact arithmetic over thousands of rows — a task
LLMs perform unreliably and cannot be meaningfully unit-tested for.

## 6. Structured agent communication

`TaskSpec` (Orchestrator to sub-agent) and `DataAgentResult` /
`RAGAgentResult` / `ComparisonAgentResult` (sub-agent to Orchestrator) are
plain Python dataclasses. This is deliberately different from
`SurveyResponseRecord`, a pydantic model reserved for the one place actual
untrusted external input (the survey JSON on disk) needs real validation
and coercion. Internal agent contracts don't need pydantic's runtime
validation because both sides are trusted, already-typed application code —
mypy catches a field mismatch at review time instead.

## 7. Deterministic tool calling

The assignment specifically required demonstrating tool calling from within
an agent. `DataAgent.run` calls `tools.metrics.compute_csat`, a pure
function: given a threshold (default 4) and a list of already-filtered
response dicts, it returns the percentage rated at or above that threshold,
or `None` for an empty period. This is real tool invocation in the sense
the assignment describes — a Python function an agent calls for a
sub-computation — not an LLM-native function-calling protocol (no
OpenAI/Anthropic tool-use JSON schema is used anywhere in this project,
consistent with the assignment's explicit allowance of "plain Python").
The underlying principle: an LLM should decide *what* needs to be computed
and *how to talk about it*; it should never be the thing computing it.

## 8. RAG architecture

The FAQ is chunked paragraph-first (blank-line boundaries, which in this
Q/A-formatted document means one question-and-answer pair per chunk), with
sentence-level packing plus overlap as a fallback only when a paragraph
exceeds the character budget. This was chosen over fixed-size windows
specifically because a fixed window would routinely split a question from
its answer mid-sentence — exactly the unit a business question needs
retrieved whole. Embeddings come from `nomic-embed-text` served locally by
Ollama (no separate model download, no external API), stored in a FAISS
`IndexFlatIP` index (cosine similarity via L2-normalized vectors), with a
NumPy brute-force fallback if FAISS isn't importable. At the FAQ's actual
size (~500 words, 12 chunks), exact search costs nothing extra over an
approximate index while removing a tuning parameter (recall vs. speed)
that has no upside at this scale.

## 9. Retrieval grounding

Retrieved chunk text is placed into `SummaryAgent`'s prompt payload
alongside — never instead of — `DataAgentResult`/`ComparisonAgentResult`.
The system prompt instructs the model to weave in FAQ context "only where
relevant" and never to invent a statistic; the FAQ provides policy/business
context, survey data provides the observed facts, and the two are kept
structurally distinct in the payload so one cannot silently override the
other.

## 10. Business question resolution — worked example

For "What are the top 3 complaints this month and how do they compare to
last month?", the real captured execution (100k-record dataset,
`llama3.1:8b`): the planner produces a two-task plan (DataAgent for current
period, ComparisonAgent for the diff); DataAgent returns top themes
`wait_time (4,248)`, `staff (4,234)`, `food_quality (4,221)` for May 2026;
ComparisonAgent reports wait-time mentions up 99% and food-quality mentions
up 27% month-over-month, with rating/CSAT/response-count deltas all below
the significance thresholds; SummaryAgent narrates this into one paragraph
correctly noting that none of the changes crossed the "significant" bar
while still flagging the trend worth watching — an inference grounded in
the structured `is_significant` flags, not invented. Full transcript:
`outputs/eval_results.md`.

## 11. Evaluation

Three FAQ-grounded questions were run end-to-end (`outputs/eval_results.md`,
`scripts/eval_questions.py`): retrieval's top-1 chunk was the exact correct
Q/A pair for both single-topic FAQ questions (CSAT target, wait-time
policy); a question requiring cross-section synthesis correctly retrieved
both relevant chunks independently but relied on the LLM, not retrieval, to
connect them causally — a known and stated limitation, not a failure this
document hides.

## 12. Fine-tuning strategy (Part 3 summary)

For classifying 10,000 daily free-text responses into 8 sentiment+topic
categories without frontier-model cost: bootstrap ~3,000-5,000 labeled
examples from a stratified frontier-model pass with human QA review (never
zero-review, to avoid distilling the frontier model's own errors), oversample
rare categories deliberately, QLoRA-tune a 3B-8B open instruct model (the
label space is narrow enough that a low-rank adapter captures it fully),
train with Hugging Face `transformers`+`peft`+`TRL`, evaluate with per-class
F1 (not aggregate accuracy, given class imbalance) against a frozen
held-out set and a direct agreement-rate comparison with GPT-4o, gate
production replacement on matching that agreement rate per-category (not
just on average) after a shadow-mode period, serve via adapter-swapping
alongside the existing LLM service so no other route is disrupted, and keep
the label taxonomy in versioned config so a category change is a retrain,
not a code change. Full 300-500 word version: `README.md` §9.

## 13. Production architecture considerations

The current design loads the entire survey dataset into a process-lifetime
in-memory cache (`lru_cache` on `load_responses`) — correct and fast at
100,000 rows, not viable past a few million without moving to an indexed
datastore (Postgres/DuckDB). The FAQ index is a single local FAISS file
with no versioning; a production system would want a rollback path for a
bad re-ingest.

## 14. Scalability

Scaling *dataset volume* (100k rows today, 10,000+/day ingest in production)
is primarily a storage/query-layer change, not an architecture change — the
Orchestrator/agent contracts stay the same, only `tools/metrics.py`'s
in-memory filtering would need to become an indexed query. Scaling *request
volume* (many concurrent users) requires moving the in-memory per-IP rate
limiter to a shared store (Redis) since the current implementation is
correct only for a single process instance.

## 15. Reliability

Graceful degradation is built in at every LLM touchpoint: planning falls
back to a deterministic keyword heuristic and summarization falls back to
a template when Ollama is unreachable, so the CLI/API always produce a real
answer end-to-end with zero external dependencies running. What is missing:
retry/backoff around the Ollama HTTP calls themselves — a transient failure
mid-call is not retried, only caught and downgraded to the fallback path.

## 16. Security

Bearer-token auth gates `/ask` (mandatory in production, enforced by
`Settings` failing fast at startup if absent); CORS is closed by default;
secrets live in a git-ignored `.env` and are never logged (`SecretStr`
redacts on repr); production mode disables `/docs`/`/redoc` and strips
internal error detail from client responses.

## 17. Observability

Structured key=value logs on every stage transition, plus a full
`AgentRunLog` execution trace returned alongside every answer — sufficient
to audit exactly which agents ran, with what task, and what they returned.
Not implemented: request-ID correlation across a single request's log
lines, and exported latency metrics/tracing (currently only in free-text
log lines, not a metrics backend).

## 18. Limitations

No multi-turn conversation memory (each question is stateless); no retry
logic on the single external dependency; theme extraction is keyword-based,
not a learned classifier, so it misses paraphrases outside its keyword
list; ComparisonAgent's significance thresholds are engineering-judgment
constants, not statistically derived; the survey dataset is synthetic, so
findings demonstrate pipeline capability, not real operational insight.

## 19. Future roadmap

Direct unit tests for `RAGAgent`/`SummaryAgent` with Ollama mocked (the
single highest-leverage remaining gap); retry/backoff around Ollama calls;
a real datastore behind `DataAgent`'s filtering once dataset volume
requires it; request-ID propagation through the trace; versioned FAQ index
storage with rollback.

## 20. Conclusion

MiniSense demonstrates that a small, fully local system can combine exact
deterministic computation, grounded retrieval, and LLM narration into one
coherent answer — with the LLM restricted to the parts of the problem
(intent, routing, prose) it is actually reliable at, and everything
numeric handled by tested, deterministic code. The architecture's honesty
about its own gaps (no retries, indirect RAG/Summary test coverage, a
synthetic dataset) is treated as part of the engineering deliverable, not
something to obscure — see `docs/SUBMISSION_REVIEW.md` for the full
code-grounded audit this paper summarizes.
