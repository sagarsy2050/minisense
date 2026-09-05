# MiniSense — Interview Preparation

100 questions grounded in the actual MiniSense implementation, organized by
the categories a Senior AI Engineer interview would cover. Format per
question: **Answer** (what to say), **MiniSense evidence** (the real file/
behavior to point to), **Watch for** (the likely follow-up and how to handle
it). Kept condensed by design — in an interview, elaborate only as far as
the interviewer's follow-up actually pulls you.

---

## A. Project understanding (1-15)

**1. Explain MiniSense in two minutes.**
Answer: A local, multi-agent system that answers business questions about
survey feedback by combining exact computed metrics with FAQ-grounded RAG,
entirely on Ollama — no cloud API. An orchestrator plans, four sub-agents
execute, a summary agent narrates.
Evidence: `agents/orchestrator.py::answer_question`.
Watch for: "Why agents, not one prompt?" → see Q2.

**2. Why a multi-agent architecture instead of one LLM call?**
Answer: Numeric correctness (CSAT, counts) needs to be exact and testable;
an LLM asked to eyeball 100k rows would approximate or hallucinate. Splitting
computation (DataAgent), retrieval (RAGAgent), comparison, and narration
(SummaryAgent) lets each piece be independently tested and be LLM-free where
correctness matters.
Evidence: `tools/metrics.py` has zero LLM calls; only `orchestrator._llm_plan`
and `summary_agent.run` touch Ollama.
Watch for: "Isn't this over-engineered for the task?" → No — it's the
minimum split that keeps numbers exact; further splitting wasn't needed.

**3. Why not just have DataAgent do everything, including planning?**
Answer: Planning needs to interpret ambiguous natural language ("this
month"); computation needs to be deterministic. Conflating them would force
either the LLM into arithmetic or hardcoded logic into intent parsing.
Evidence: `orchestrator._llm_plan` vs `data_agent.run`.

**4. What does the Orchestrator actually do, step by step?**
Answer: Validates the question → calls `plan_question` (LLM or heuristic) →
dispatches each `TaskSpec` to its agent → collects typed results → hands
everything to `SummaryAgent`.
Evidence: `orchestrator.py::answer_question`, lines 173-217.

**5. How does task decomposition actually work?**
Answer: The planner LLM is given a system prompt describing the four
agents and their fields, and returns JSON parsed into `TaskSpec` objects —
not left as raw text.
Evidence: `PLANNER_SYSTEM_PROMPT`, `_llm_plan`.

**6. How are agents selected/routed?**
Answer: By the `agent` field on each `TaskSpec` (an `AgentName` enum); the
orchestrator's dispatch loop is a simple `if/elif` on that field.
Evidence: `orchestrator.py` lines 181-204.

**7. How do agents communicate with each other?**
Answer: Never directly — always through the Orchestrator, and always via
typed dataclasses (`TaskSpec` in, `DataAgentResult`/etc. out), never raw
strings.
Evidence: `schemas.py`.

**8. Why structured outputs instead of free text between agents?**
Answer: Predictable fields mean the next stage can consume them without
parsing prose, they're independently testable, and a schema change is
caught by mypy instead of a runtime string-parsing bug.
Evidence: `DataAgentResult` dataclass; `test_metrics.py` asserts on typed
values, not text.

**9. Why are DataAgent's calculations deterministic Python instead of LLM function-calling?**
Answer: Exactness and reproducibility — `compute_csat` gives the same
answer every time for the same input; an LLM's arithmetic over large inputs
is not guaranteed to be reproducible or correct.
Evidence: `tools/metrics.py::compute_csat`.

**10. What happens when an agent/sub-call fails?**
Answer: Depends which one. RAGAgent failure (no index / Ollama down) is
caught and the pipeline degrades gracefully; a bad LLM JSON plan falls back
to a heuristic; Ollama down at summary time falls back to a deterministic
template. There is no retry logic on the Ollama HTTP calls themselves.
Evidence: `orchestrator.py` lines 188-204, `plan_question` try/except,
`summary_agent.run`'s fallback.
Watch for: "What about a genuine tool bug (bad metric)?" → Honest answer:
would propagate as an exception up through the CLI/API's generic 500
handler; there's no per-tool try/except inside `data_agent.run`.

**11. What are the biggest limitations of this system as built?**
Answer: No retry/backoff on the single external dependency (Ollama); no
direct unit tests for `RAGAgent`/`SummaryAgent`; significance thresholds in
ComparisonAgent are heuristic constants, not statistically derived; the
whole dataset is loaded into memory (fine at 100k rows, not at 10M).
Evidence: `docs/SUBMISSION_REVIEW.md` §8, §10, §13.

**12. What would you change with more time?**
Answer: Add retry/backoff around Ollama calls, direct `RAGAgent`/
`SummaryAgent` tests with mocked Ollama, and move the dataset behind a real
query layer (Postgres/DuckDB) once volume grows past a few million rows.

**13. What are you most proud of in this implementation?**
Answer: Catching and fixing a genuine bug during a real end-to-end run — the
planner anchored "this month" to wall-clock time instead of the dataset's
own date range, silently returning zero rows. Found by actually running the
CLI, not just by reading code or unit tests.
Evidence: `orchestrator.py::_dataset_today`.

**14. What was the hardest engineering problem?**
Answer: Getting ComparisonAgent's theme diffing correct — using the
top-3-limited `DataAgentResult.top_themes` for a diff silently produces a
false "100% drop" when a theme falls just outside top-3 in one period. Fixed
by recomputing full theme counts (`ALL_THEMES_TOP_N=100`) specifically for
comparison.
Evidence: `comparison_agent.py` lines 19-25, 64-69.

**15. How would you explain this to a non-technical stakeholder?**
Answer: "Ask it a plain-English question about your customer surveys, and
it gives you a real analyst's paragraph — with exact numbers, not
guesses — by combining your survey data with your FAQ policies, and it
never sends your data anywhere outside your own machine."

---

## B. Agentic AI (16-30)

**16. What's the difference between a planner agent and a sub-agent here?**
Answer: The planner (`Orchestrator`) decides *what* to do and *who* does it;
sub-agents each do exactly one thing and don't make routing decisions
themselves.

**17. How is routing implemented — is it dynamic or hardcoded?**
Answer: Dynamic when Ollama is available (LLM decides which agents/tasks
per-question); a deterministic keyword-based fallback (`_heuristic_plan`)
otherwise. Both produce the same `Plan`/`TaskSpec` shape.
Evidence: `orchestrator.py::plan_question`.

**18. Is there agent "state" across a conversation?**
Answer: No — each `answer_question` call is stateless; there's no
multi-turn memory. A follow-up question is a fresh call with no context of
the previous one. **DESIGNED BUT NOT IMPLEMENTED** for this take-home.

**19. How would you add multi-turn memory?**
Answer: Pass prior `OrchestratorRun`s (or a condensed summary) into the
planner's prompt as conversation history; would need a session id and a
store (even in-memory dict keyed by session).

**20. What is the actual tool-calling mechanism — is it LLM-native function calling?**
Answer: No — it's plain Python function calls from within `DataAgent`
(`tools.compute_csat(...)`), not an OpenAI/Anthropic-style tool-use JSON
protocol. The assignment explicitly allows this ("plain Python" is a listed
option).
Evidence: `data_agent.py` line 33.

**21. What happens on an agent timeout?**
Answer: `MINISENSE_LLM_TIMEOUT` (120s default) bounds each Ollama HTTP
call via `requests`; on expiry it raises, which is not currently caught
specifically as a timeout — it would surface as a generic exception. No
retry.

**22. Are there loops or cycles in the agent graph?**
Answer: No — the flow is a strict DAG: Orchestrator → sub-agents (in
parallel conceptually, executed sequentially in code) → SummaryAgent. No
agent calls back into a prior stage.

**23. How would you add retries?**
Answer: Wrap `ollama_client.chat_json`/`chat_text`/`embed` calls in a small
retry-with-backoff decorator, retrying only on `OllamaUnavailableError` /
connection errors, not on validation errors.

**24. How do you prevent an agent from hallucinating numbers?**
Answer: SummaryAgent's system prompt explicitly says "use ONLY the numbers
given to you. Never invent a statistic," and the numbers themselves come
from `DataAgentResult`/`ComparisonAgentResult`, computed in Python before the
LLM ever sees them — the LLM narrates, it doesn't calculate.
Evidence: `summary_agent.py::SYSTEM_PROMPT`.

**25. What are the agent boundaries, precisely?**
Answer: DataAgent never touches the FAQ; RAGAgent never touches survey
rows; ComparisonAgent only calls DataAgent (reuse, not duplication);
SummaryAgent only reads already-structured results, never raw responses.

**26. Why isn't this built on LangGraph/LangChain?**
Answer: At 5 components and 1 LLM provider, a framework's abstraction cost
(learning curve for a reviewer, indirection) outweighs its benefit; plain
dataclasses + one REST client to Ollama are easier to read end-to-end in a
take-home review.
Watch for: "What would make you reach for LangGraph?" → Multiple LLM
providers, conditional/cyclic agent graphs, or needing built-in
checkpointing/human-in-the-loop.

**27. How would you add observability for agent execution?**
Answer: Already has structured key=value logs per stage and a full
`AgentRunLog` trace returned with every answer; missing: a request-ID that
correlates logs across a single request, and exported metrics/tracing
(OpenTelemetry) for latency per agent.
Evidence: `logging_config.py`, `schemas.AgentRunLog`.

**28. How is agent output validated before use?**
Answer: The LLM planner's JSON is parsed into `TaskSpec`s; a missing/bad
`agent` field raises `ValueError`/`KeyError`, caught by `plan_question` to
fall back to the heuristic planner. Sub-agent outputs are dataclasses
constructed directly by Python code (not parsed from LLM text), so they
can't be malformed the way LLM JSON can.

**29. Single-agent vs multi-agent — when would single-agent be better?**
Answer: If the whole task were "summarize this FAQ" with no numeric
computation or comparison, a single LLM call would be simpler and cheaper.
Multi-agent earns its complexity specifically because exact computation and
retrieval need to be separated from generation.

**30. How do you keep agent prompts from growing unmanageably?**
Answer: Each prompt is scoped to exactly one agent's job (planner: routing
only; summarizer: narration only) — no agent's prompt tries to do two
things, which keeps each one short and focused.

---

## C. RAG (31-45)

**31. Walk me through the RAG pipeline end to end.**
Answer: `product_faq.md` → `chunking.chunk_markdown` (paragraph-first,
sentence-pack fallback) → `nomic-embed-text` embeddings via Ollama → FAISS
`IndexFlatIP` store → `scripts/ingest_faq.py` persists to
`storage/faq_index.faiss` → `RAGAgent.run` embeds the query and searches →
top-k `RetrievedChunk`s → injected into `SummaryAgent`'s prompt.
Evidence: `docs/SUBMISSION_REVIEW.md` §7.

**32. Why sentence-aware/paragraph chunking over fixed-size windows?**
Answer: The FAQ is Q/A pairs under markdown headings; fixed windows would
routinely split a question from its answer mid-sentence. Paragraph-first
chunking keeps each Q/A pair intact as one chunk.
Evidence: `chunking.py` docstring, `chunk_markdown`.

**33. What's the actual chunk size/overlap?**
Answer: `CHUNK_MAX_CHARS=500`, `CHUNK_OVERLAP_CHARS=80` (`.env.example`
defaults); overlap only matters on the sentence-pack fallback path, since
most paragraphs fit under 500 chars whole.

**34. What embedding model, and why?**
Answer: `nomic-embed-text` via the local Ollama server — keeps embeddings
on the same local runtime as the LLM, no separate HuggingFace download or
external API.
Evidence: `.env.example`, `rag/embeddings.py`.

**35. What vector store, and why FAISS specifically?**
Answer: FAISS `IndexFlatIP` (exact search) over L2-normalized vectors
(cosine similarity), with a NumPy brute-force fallback if `faiss` isn't
installed. FAISS chosen because the assignment names it and it's the
standard choice once a corpus grows past toy size, even though exact search
is overkill for ~12-20 chunks today.
Evidence: `vector_store.py`.

**36. Why exact search (IndexFlatIP) instead of an ANN index (HNSW/IVF)?**
Answer: The corpus is tiny (a dozen-odd chunks); ANN's speed advantage is
irrelevant at this scale and would add tuning complexity (nlist/nprobe,
recall/speed trade-offs) for zero benefit here.

**37. How is top-k configured?**
Answer: `TaskSpec.top_k`, default 4, settable per-task; `.env`'s
`MINISENSE_TOP_K_DEFAULT` sets the system default.

**38. How is the retrieval query constructed?**
Answer: `task.query_text or task.objective` — the planner LLM is expected
to fill `query_text` for RAG tasks; if it doesn't, the task's `objective`
string is used as a fallback query.
Evidence: `rag_agent.py` line 9.

**39. What happens on empty/no retrieval results?**
Answer: `VectorStore.search` returns `[]` if the store has no chunks;
`RAGAgentResult.chunks` would just be empty, and `SummaryAgent` proceeds
without FAQ context (its prompt payload's `retrieved_faq_context` is `[]`).

**40. What happens if the FAQ index hasn't been built yet?**
Answer: `retrieve()` raises `IndexNotFoundError`; the orchestrator catches
it specifically, logs a warning, and continues without RAG — the rest of
the pipeline (exact metrics) still answers the question.
Evidence: `orchestrator.py` lines 188-204.

**41. How do you prevent the FAQ from overriding actual survey data?**
Answer: They're structurally separate fields in the SummaryAgent payload
(`data_agent_result` vs `retrieved_faq_context`), and the system prompt
instructs "weave in FAQ context only where relevant" — the FAQ never
substitutes for computed metrics, it only adds business-policy context
around them.

**42. How would you evaluate RAG quality without ground-truth labels?**
Answer: Manually inspect top-k chunks for the sample questions (done in
`outputs/eval_results.md`) — check whether the top-1 chunk is the
semantically correct Q/A pair, and whether the similarity score meaningfully
separates relevant from irrelevant chunks.

**43. What's a realistic retrieval failure mode here?**
Answer: A question needing synthesis across multiple FAQ sections (e.g.
"how does staffing relate to wait times") — retrieval correctly returns
both relevant chunks independently, but connecting them causally is left
entirely to the LLM, not retrieval itself.
Evidence: `outputs/eval_results.md`, "Notes on retrieval quality".

**44. Would you add reranking or hybrid (keyword+vector) search?**
Answer: Not at this corpus size — 12-20 chunks give exact FAISS search no
room to meaningfully fail. Would reconsider both if the FAQ grew to
hundreds of pages with more query ambiguity.

**45. How is source traceability handled?**
Answer: `SummaryAgentResult.citations` carries the `chunk_id`s actually
used, surfaced in both the CLI/API output and the trace — so a claim in the
narrative can be traced back to a specific FAQ chunk.
Evidence: `summary_agent.py` line 76, `schemas.SummaryAgentResult`.

---

## D. Python / engineering (46-58)

**46. Why dataclasses for agent contracts instead of Pydantic everywhere?**
Answer: Pydantic is used specifically at the untrusted-input boundary
(`SurveyResponseRecord`, validating disk JSON) where real coercion/error
messages matter; internal agent-to-agent contracts use plain dataclasses
since both sides are trusted, already-typed Python — no validation
overhead needed.
Evidence: `schemas.py` module docstring.

**47. How is configuration managed?**
Answer: One `pydantic-settings` `Settings` class (`config.py`), loaded once
via `get_settings()` (`lru_cache`d), reading env vars/`.env`. No module
reads `os.environ` directly elsewhere — one auditable place for every knob.

**48. What happens with a genuinely unsafe config?**
Answer: Fails fast at process startup with a `pydantic.ValidationError` —
e.g. `MINISENSE_ENV=production` with no `API_AUTH_TOKEN` — not three calls
deep into a request.
Evidence: `config.py` validators.

**49. How is logging structured?**
Answer: Key=value structured logs (`logging_config.py`) at INFO by
default, one line per stage transition (plan produced, question answered,
etc.) plus request method/path/status/duration on every API call.

**50. What's the exception hierarchy and why?**
Answer: Every expected failure inherits `MiniSenseError`
(`ConfigurationError`, `DataLoadError`, `OllamaUnavailableError`,
`IndexNotFoundError`, `InvalidQuestionError`) so callers can catch "an
expected MiniSense failure" as one type instead of guessing between
`FileNotFoundError`/`ValueError`/etc.
Evidence: `exceptions.py`.

**51. How is the survey dataset cached/loaded?**
Answer: `load_responses()` is `lru_cache(maxsize=1)`'d — parsed and
validated once per process, not re-read on every question.
Evidence: `data_loader.py` line 75.

**52. Walk me through what happens to one malformed survey record.**
Answer: `SurveyResponseRecord.model_validate` raises on it individually; it
gets skipped and logged with a reason (response_id + error count); the load
only fails hard if *every* record fails.
Evidence: `data_loader.py::_validate_records`.

**53. How would you add concurrency (e.g., DataAgent + RAGAgent in parallel)?**
Answer: Both are pure functions over already-loaded data with no shared
mutable state, so they're safe to run concurrently — e.g.
`asyncio.gather`/a thread pool around the two `.run()` calls in the
orchestrator's dispatch loop. Not done currently since the whole pipeline
runs in well under a few seconds for CPU-bound work; the actual latency is
Ollama's LLM calls, which are already sequential dependencies (plan before
tasks, tasks before summary) that concurrency wouldn't shorten.

**54. What's your approach to typing/static analysis?**
Answer: `mypy` clean across all modules (`pyproject.toml`'s `[tool.mypy]`),
`from __future__ import annotations` throughout, dataclasses/pydantic give
the type checker real signal on every agent boundary.

**55. How is the FastAPI app's error handling structured?**
Answer: One exception handler per `MiniSenseError` subtype mapping to the
right HTTP status (400/503/etc.); an unhandled-exception handler logs full
detail server-side but returns a generic message to the client — never
leaks internals.
Evidence: `api.py` lines 170-218.

**56. How is rate limiting implemented, and what are its limits?**
Answer: A simple in-memory per-IP sliding window (`_check_rate_limit`).
Explicitly acknowledged as single-process/in-memory/reset-on-restart —
correct for one instance, would need Redis or a gateway for multi-instance.
Evidence: `api.py` lines 74-89, module docstring.

**57. Why `pydantic-settings` over raw `os.environ` reads scattered around?**
Answer: One validated, typed source of truth for every knob, with clear
error messages at startup instead of a `KeyError` deep in a request path.

**58. How would you structure adding a fifth sub-agent?**
Answer: Add an `AgentName` enum value, a `TaskSpec`/result dataclass pair
if needed, a `run()` function in a new `agents/` module, one dispatch
branch in the orchestrator's loop, and teach the planner prompt about it —
no existing agent's code changes.

---

## E. Data / analytics (59-68)

**59. How is CSAT actually defined here?**
Answer: % of responses rated ≥ 4 on the 1-5 scale (`compute_csat`,
`threshold=4` default) — matches the FAQ's "CSAT of 4.5+" language treating
CSAT as a satisfaction-share metric, not a raw average.
Evidence: `tools/metrics.py` lines 78-83.

**60. How does theme/complaint extraction work — is it ML-based?**
Answer: No — plain keyword regex matching against `THEME_KEYWORDS` (word
boundary search per theme's keyword list), kept in sync with the data
generator's own topic vocabulary so themes are recoverable without an LLM
call.
Evidence: `tools/metrics.py` lines 21-43, 90-96.

**61. What are the limits of keyword-based theme extraction?**
Answer: Misses synonyms/phrasing outside the keyword list, can't
disambiguate sarcasm or negation ("not slow at all" would still match
"wait"), and ties detection tightly to the synthetic generator's own
vocabulary — a real free-text corpus would need broader/fuzzier matching or
a real classifier.

**62. How is a "significant" change defined in ComparisonAgent?**
Answer: Fixed thresholds, not a statistical test: rating change ≥0.15pts,
CSAT change ≥3pts, theme mention relative change ≥25% AND the theme has
≥5 mentions in the larger period (filters tiny-count noise).
Evidence: `comparison_agent.py` lines 6-9, 27-28, 74.
Watch for: "Why not a proper significance test (t-test/chi-square)?" →
With thousands of responses per period, sampling noise isn't the practical
concern — real month-over-month drift is; a formal test would add
complexity without changing which changes actually matter operationally.

**63. How was the synthetic dataset validated?**
Answer: Hard assertions in `generate_data.py::main` — rating range 1-5,
dates within the two-month window, no duplicate `response_id`s — plus a
printed distribution report (ratings, CSAT%, by-month, by-business, by-
channel, empty-text%, distinct-text%).
Evidence: `data/generate_data.py` lines 480-505 (approx, see `main()`).

**64. Why non-uniform rating distributions instead of random?**
Answer: Real feedback isn't uniform — skewed positive base distribution,
per-business quality bias (Riverside location trends lower), a slight May
dip tied to a wait-time-complaint-spike narrative — gives ComparisonAgent
something real to detect instead of pure noise.
Evidence: `data/generate_data.py::pick_rating`.

**65. How do you avoid the free-text looking obviously synthetic?**
Answer: A large per-topic/per-sentiment template bank (not 3-4 fixed
sentences repeated thousands of times), a "humanize" pass adding
typos/casing/emojis/dropped punctuation probabilistically, and deliberate
sentiment mismatches (~10% of two-topic responses contrast one topic
against the overall rating) — real feedback isn't perfectly consistent.
Evidence: `data/generate_data.py::_humanize`, `build_free_text`'s mismatch
logic.

**66. What fraction of generated text is actually distinct?**
Answer: From the last generation run: ~18,400 distinct non-empty
`free_text` strings out of ~88,000 non-empty records (~21%) — meaningfully
varied for a template-based generator, not dominated by a handful of
sentences.

**67. How would you detect data leakage in a real (non-synthetic) dataset?**
Answer: Check for near-duplicate free-text across train/val/test splits
(the same customer complaint phrased once but appearing in two splits), and
split by a natural grouping key (customer/session) rather than by row, so
one entity's responses don't span splits.

**68. How would this scale from 100k to 10M+ survey rows?**
Answer: Move off in-memory `list[dict]` + `lru_cache` entirely — a real
datastore (Postgres/DuckDB) with indexed `date`/`business_id` columns so
`filter_responses`'s linear scan becomes an indexed query; `compute_top_themes`
would move to precomputed/incremental aggregation rather than a full
re-scan per question.
Evidence: `docs/SUBMISSION_REVIEW.md` §12.

---

## F. LLM / prompt engineering (69-78)

**69. How do you force structured JSON output from the planner LLM?**
Answer: `ollama_client.chat_json` plus a system prompt that spells out the
exact JSON shape expected (`PLANNER_SYSTEM_PROMPT`); no JSON-mode
constraint enforcement beyond the prompt itself and a parse-with-fallback
(`_llm_plan`'s try/except → heuristic planner on failure).

**70. What temperature settings are used, and why?**
Answer: Separate low(er) temperature for planning (`OLLAMA.temperature_planner`)
vs. summarization (`OLLAMA.temperature_summary`) — planning needs
consistency/determinism in routing, narration benefits from a bit more
natural variation. Exact values live in `config.py`'s `OLLAMA` settings
object.

**71. How do you prevent prompt injection from FAQ content the RAG retrieves?**
Answer: The FAQ is a static, developer-controlled document (not
user-uploaded), so injection risk here is low; if it were user-uploaded,
the mitigation would be treating retrieved text strictly as data inside a
clearly delimited context block, never as instructions — which the current
system prompt already does implicitly by presenting it as
`retrieved_faq_context` inside a JSON payload rather than concatenated raw
into the instruction text.
**PROPOSED DESIGN** if the FAQ became user-supplied: explicit
instruction-vs-data delimiting and stripping any text that looks like a
system-prompt override.

**72. How is hallucination minimized in the final narrative?**
Answer: Explicit system-prompt rule ("use ONLY the numbers given, never
invent a statistic"), all numbers pre-computed in Python before the LLM
call, and a deterministic template fallback path that has zero
hallucination risk (no LLM involved) when Ollama is unavailable.

**73. What's the fallback behavior if Ollama returns malformed output?**
Answer: For planning: caught as `ValueError`/`KeyError`, falls back to
`_heuristic_plan`. For summarization: `chat_text` either returns a string or
raises `OllamaUnavailableError` (caught, falls back to template) — there's
no separate "malformed narrative" case since free text can't be malformed
the way JSON can.

**74. How would you reduce LLM cost/latency at scale?**
Answer: Since this runs on local Ollama, "cost" is compute/time, not
dollars — cache repeated identical questions, batch embedding calls during
ingestion (already only done once via `scripts/ingest_faq.py`, not per
query), and consider a smaller/faster model for planning specifically
(narration needs more fluency than routing does).

**75. What context window considerations apply here?**
Answer: Minimal — the planner prompt is short (business index + question),
and the summarizer's payload is the structured JSON results, not raw
survey rows, so context size stays small and bounded regardless of dataset
size (100k rows never enter an LLM prompt directly).

**76. How would you choose between different Ollama models for this task?**
Answer: Planning needs reliable structured-JSON-following behavior;
summarization needs fluent, grounded prose. `llama3.1:8b` was used for
both here; a production system might use a smaller/faster model for
planning (simpler task) and reserve a larger one for narration quality.

**77. How do you evaluate whether the LLM's plan is "good"?**
Answer: No automated eval currently — evaluated manually via
`scripts/eval_questions.py`'s three sample questions, checking that the
right agents were routed and the reasoning made sense.
**Gap, honestly stated**: no regression test asserting "this question
should route to ComparisonAgent."

**78. What's your one-sentence LLM-vs-code design principle?**
Answer: "LLMs plan, interpret, and narrate; code counts, filters, and
compares" — never the reverse.

---

## G. Fine-tuning (79-90)

**79. Summarize your fine-tuning design in one minute.**
Answer: Bootstrap ~3-5k labeled examples from frontier-model labels on a
stratified sample plus human QA review, QLoRA-tune a small (3B-8B) open
instruct model on 8-way sentiment+topic classification, evaluate with
per-class F1 against a frozen held-out set and a shadow-mode comparison
against GPT-4o, serve via adapter-swapping alongside the existing LLM
service.
Evidence: `README.md` §9.

**80. Why QLoRA over full fine-tuning?**
Answer: The task (8-way classification, narrow label space) doesn't need
the base model's full weight space to move — a low-rank adapter captures
it at a fraction of the memory/compute, and keeps the base model reusable
for other tasks via adapter swapping. Full FT would only be justified if
the domain vocabulary were badly mismatched from the base model's training
distribution, which isn't the case for restaurant/retail survey text.

**81. Why QLoRA specifically over plain LoRA?**
Answer: QLoRA's quantized base weights reduce GPU memory further, letting
this run on smaller/cheaper hardware — a reasonable default when the exact
GPU budget isn't fixed in advance and dataset size doesn't demand full
LoRA's slightly higher fidelity.

**82. How many labeled examples do you actually need, and why that number?**
Answer: ~3,000-5,000 for a first pass — 8-way classification with fairly
distinct topic vocabulary needs far less data than generation tasks; the
number is a starting estimate to validate against real eval numbers, then
grown via active sampling of low-confidence/disagreement cases rather than
randomly.

**83. How would you handle class imbalance (rare complaint types)?**
Answer: Deliberately oversample rare categories during data curation so
their scarcity in raw survey data doesn't get baked into the classifier's
priors; evaluate with macro F1 (not accuracy) specifically so minority-class
performance can't hide behind majority-class performance.

**84. Why not just always use the frontier model?**
Answer: Cost doesn't scale at 10k responses/day — the whole point of the
exercise is replacing an accurate-but-expensive frontier call with a
cheap, adequate local one for this narrow, well-defined classification task.

**85. What tooling would you use for training, and why?**
Answer: Hugging Face `transformers` + `peft` + `TRL`'s `SFTTrainer` for a
first pass (well-documented, easy to reason about); Axolotl/LLaMA-Factory
if iterating on many similar fine-tunes, since their config-driven workflow
cuts per-experiment boilerplate.

**86. What metrics decide "ready to replace the frontier model"?**
Answer: Per-class precision/recall/F1 (not just aggregate accuracy, given
class imbalance) plus direct agreement-rate comparison against GPT-4o on a
frozen held-out set — with a concrete bar (matching GPT-4o's
agreement-with-human-label rate within a small margin on *every* category,
not just on average) and a shadow-mode period scoring live traffic before
switching.

**87. How would you serve the adapter without disrupting existing routes?**
Answer: Adapter-swapping on the same base model process (vLLM/TGI support
multiple LoRA adapters simultaneously) — survey-classification traffic
routes to the adapter, every other route stays on the frontier/base model,
no separate GPU deployment needed.

**88. How do you keep the fine-tuning pipeline future-proof/model-agnostic?**
Answer: Keep the label taxonomy and prompt template in versioned config,
not hardcoded — a category-set change becomes a config diff and a retrain,
not a code change; log every prediction with input+output for drift review.

**89. What would trigger a re-training cycle?**
Answer: Drift detected when today's free-text distribution statistically
diverges from the training distribution, crossing a defined threshold —
re-run the active-sampling labeling loop then, not on a fixed calendar
schedule.

**90. What's the biggest risk in this fine-tuning plan?**
Answer: Bootstrapping labels from the frontier model risks distilling its
own biases/errors uncorrected if human review is skipped — hence the
explicit human-QA-on-a-subset step rather than 100% frontier-labeled,
zero-review data.

---

## H. Production / MLOps (91-100)

**91. What's actually missing for this to be production-ready?**
Answer: Retry/backoff on Ollama calls, direct agent-level tests for
RAG/Summary, request-ID correlation in logs, a real datastore instead of
in-memory dataset caching, and metrics/tracing export — all explicitly
listed as gaps in `docs/SUBMISSION_REVIEW.md`, not hidden.

**92. How is this containerized?**
Answer: Multi-stage `Dockerfile` (no build toolchain/dev deps in the
runtime image), non-root user, `HEALTHCHECK` wired to `/health`;
`docker-compose.yml` brings up Ollama and the API on one network, with
model pulls and FAQ-index build left as explicit one-time steps (not run on
every `up`, to keep startup fast/non-flaky).

**93. What does CI actually check?**
Answer: `.github/workflows/ci.yml` — `ruff check`, `mypy` (zero errors),
`pytest` across Python 3.10-3.12 with coverage uploaded, then a Docker
build gated on the three passing — all offline, no Ollama/external service
needed, so CI is deterministic.

**94. How would you monitor this in production?**
Answer: Export the existing structured logs to a log aggregator, add
latency histograms per agent stage (currently only logged as text, not as
metrics), and alert on `OllamaUnavailableError` rate / fallback-path usage
rate as a proxy for degraded quality.

**95. How would you version the FAQ vector index or the survey dataset?**
Answer: **NOT IMPLEMENTED** currently — `storage/faq_index.faiss` is
rebuilt in place by `scripts/ingest_faq.py`. Production would want a
versioned index path (or a vector DB with native versioning) so a bad
re-ingest can be rolled back.

**96. What's your rollback strategy if a new dataset breaks answers?**
Answer: **PROPOSED DESIGN**: keep the previous `survey_responses.json`
(or datastore snapshot) addressable by version/date, and make
`MINISENSE_SURVEY_PATH` swappable without a code deploy.

**97. How would you reduce cost at 10,000+ responses/day ingest?**
Answer: That volume is trivial for the current in-memory design
(10k rows/day is nothing next to the 100k already handled); the actual
cost driver at that scale is Part 3's fine-tuning classification work, not
survey storage — see the fine-tuning cost discussion (Q84-Q87).

**98. What security review would you want before shipping this externally?**
Answer: Already covers auth (bearer token), closed-by-default CORS,
secrets via `.env`/`SecretStr` (never logged), no internal error leakage
in production, docs disabled in production. Would add: per-tenant rate
limiting (current limiter is per-IP, easy to spoof behind a shared NAT),
and a real secrets manager instead of a `.env` file for actual production
deployment.

**99. How would you scale the API itself (not just the dataset)?**
Answer: The rate limiter is explicitly single-process/in-memory — a
multi-instance deployment needs that moved to Redis (or pushed to an API
gateway), since otherwise each instance enforces its own independent limit.

**100. If you had one more day, what's the highest-leverage thing to fix?**
Answer: Direct `RAGAgent`/`SummaryAgent` unit tests with Ollama mocked,
plus one full `answer_question`-level integration test — this is the
single gap most likely to hide a real orchestrator/schema wiring bug (like
the wall-clock date bug actually found this session) without needing a
live Ollama server in CI.

---

## 30-second / 60-second / 2-minute / 5-minute pitches

**30 seconds**: "MiniSense answers plain-English questions about survey
data by routing to specialized agents — one computes exact metrics in
Python, one retrieves FAQ context via RAG, one compares time periods, and
one writes the final narrative. Everything runs locally on Ollama."

**60 seconds**: add — "The orchestrator uses an LLM to plan which agents to
call and with what structured parameters, but every number in the final
answer comes from deterministic Python functions, not the LLM — so CSAT and
complaint counts are always exact and reproducible. RAG grounds the answer
in the company's actual FAQ policies using FAISS and local embeddings, with
zero external API calls."

**2 minutes**: add — "I generated a 100k-record synthetic dataset with
realistic non-uniform distributions and text variation rather than random
noise, because a downstream system needs to prove it can handle real-world
messiness, not a toy shape. I also found and fixed a real bug during actual
end-to-end testing: the planner was resolving 'this month' against the real
wall clock instead of the dataset's own two-month window, which silently
zeroed out every time-scoped answer. The system degrades gracefully too —
if Ollama isn't running, planning falls back to keyword heuristics and
summarization falls back to a template, so the pipeline is demonstrable
with zero setup."

**5 minutes**: add the architecture diagram walk-through (§2 of
`docs/SUBMISSION_REVIEW.md`), the tool-calling example (`compute_csat`),
one real worked question with its actual trace, and close with the
fine-tuning design's shadow-mode rollout plan for Part 3.
