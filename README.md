# MiniSense — A Survey Analysis Agent

A small, fully local, multi-agent AI system that answers business questions
about survey feedback, combining exact structured metrics with document-
grounded RAG over a product FAQ. Everything — planning, summarization, and
embeddings — runs against a local [Ollama](https://ollama.com) server. No
OpenAI/Anthropic API key, and no network calls at query time.

## 1. Architecture

```
                          ┌─────────────────────────┐
   business question ───▶ │   Orchestrator (Planner) │
                          └─────────────┬────────────┘
                                        │ structured TaskSpec per sub-task
                    ┌───────────────────┼────────────────────┐
                    ▼                   ▼                    ▼
             ┌─────────────┐   ┌────────────────┐    ┌──────────────┐
             │  DataAgent  │   │ ComparisonAgent │    │   RAGAgent   │
             │ (exact CSAT,│   │ (2-period diff, │    │ (FAISS top-k │
             │  ratings,   │   │  significance   │    │  over FAQ    │
             │  themes)    │   │  flags)         │    │  chunks)     │
             └──────┬──────┘   └────────┬────────┘    └──────┬───────┘
                    │  structured JSON/dataclass results       │
                    └───────────────────┬──────────────────────┘
                                        ▼
                              ┌───────────────────┐
                              │   SummaryAgent     │
                              │ (LLM narrative,    │
                              │  grounded in the    │
                              │  numbers above)     │
                              └───────────────────┘
```

- **Orchestrator** turns the natural-language question into a `Plan`
  (`schemas.Plan` → list of `schemas.TaskSpec`), one structured task per
  sub-agent, via an Ollama JSON call (`llm/ollama_client.chat_json`). If
  Ollama isn't reachable, a deterministic keyword-based heuristic
  (`agents/orchestrator._heuristic_plan`) takes over, so the system is
  demonstrable with zero setup and degrades to LLM-quality planning once
  Ollama is running.
- **DataAgent** is deliberately LLM-free. It calls plain, tested Python
  functions in `tools/metrics.py` — `compute_csat`, `compute_average_rating`,
  `compute_top_themes`, etc. — the "tool calling from within an agent" the
  assignment asks for. Numbers should always be exact and reproducible, so
  there's no LLM in this path.
- **ComparisonAgent** reuses DataAgent for two periods and diffs the *full*
  per-theme counts (not just each period's top-3) plus rating/CSAT, flagging
  a change "significant" via simple, explainable thresholds (see the
  docstring in `agents/comparison_agent.py`).
- **RAGAgent** retrieves top-k chunks from a local FAISS index built over the
  product FAQ. If the index hasn't been built yet, or Ollama is down, the
  orchestrator skips it gracefully rather than failing the whole question —
  exact metrics are still useful on their own.
- **SummaryAgent** is the only agent that touches free-form text generation.
  It receives structured JSON from every other agent and an explicit "use
  only these numbers" system prompt, and returns one narrative paragraph. It
  also has a deterministic template fallback for when Ollama is unreachable,
  so the CLI always produces *a* real answer end-to-end.

Every hop between agents is a typed dataclass (`schemas.py`) — the
Orchestrator never hands a sub-agent raw text, and no sub-agent returns
free text except SummaryAgent's final narrative.

## 2. Project structure

```
minisense/
├── src/minisense/
│   ├── agents/              orchestrator, data_agent, comparison_agent, rag_agent, summary_agent
│   ├── llm/ollama_client.py thin REST wrapper: chat_text / chat_json / embed
│   ├── rag/                 chunking, embeddings (Ollama), FAISS vector store, ingest, retrieve
│   ├── tools/metrics.py     pure functions (compute_csat, top_themes, ...) — the "tool calling" example
│   ├── config.py            validated pydantic-settings Settings (see .env.example)
│   ├── exceptions.py        MiniSenseError hierarchy
│   ├── logging_config.py    structured key=value logging setup
│   ├── validation.py        shared input validation (CLI + API)
│   ├── schemas.py           every cross-agent contract as a typed dataclass + the survey-record pydantic model
│   ├── data_loader.py       validates + caches the survey dataset
│   ├── cli.py, api.py       the two entrypoints
│   └── py.typed
├── data/                    generate_data.py, product_faq.md (survey_responses.json is generated, not committed)
├── scripts/                 ingest_faq.py, run_query.py, eval_questions.py
├── notebooks/               end_to_end_workflow.ipynb — the whole pipeline run live, in one notebook
├── client/                  optional Node.js gateway + chat UI + CLI on top of the FastAPI backend
├── tests/                   57 tests — config, data validation, agents, API, CLI (no Ollama required)
├── .github/workflows/ci.yml lint (ruff) + type-check (mypy) + tests (3.10-3.12) + docker build
├── Dockerfile, docker-compose.yml, docker-entrypoint.sh
├── .env.example             every configurable environment variable, documented
├── pyproject.toml           dependency ranges, ruff/mypy config, pytest config
├── requirements.txt / requirements-dev.txt   pinned, tested versions
├── LICENSE, CONTRIBUTING.md
└── README.md
```

## 3. Setup

### Option A — local Python

```bash
# 1. Install Ollama (https://ollama.com) and pull the two models this
#    project uses. Any locally pulled instruction model / embedding model
#    works — swap via MINISENSE_LLM_MODEL / MINISENSE_EMBED_MODEL env vars.
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama serve   # if not already running as a background service

# 2. Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # add -r requirements-dev.txt for tests/lint/type-check
cp .env.example .env                      # adjust as needed — see section 5 below

# 3. Generate the synthetic survey dataset (Appendix A) — 100k responses
#    across 3 GreenLeaf Bistro locations, two months, with realistic rating
#    drift, topic/complaint variety, and light text imperfections (typos,
#    casing, emojis) so free_text isn't dominated by a handful of templates.
#    --seed is optional (defaults to 42) and controls reproducibility.
python data/generate_data.py --count 100000 --seed 42

# 4. Build the local FAQ vector index (Appendix B, Part 2)
python scripts/ingest_faq.py

# 5. Ask a question
python -m minisense.cli "What are the top 3 complaints this month and how do they compare to last month?"
python -m minisense.cli --trace "..."     # also dump the full structured agent trace as JSON

# Optional: run the Part 2 evaluation checkpoint (3 sample questions -> outputs/eval_results.md)
python scripts/eval_questions.py

# Optional: FastAPI wrapper
uvicorn minisense.api:app --reload

# Optional: end-to-end Jupyter notebook (notebooks/end_to_end_workflow.ipynb)
# — loads the dataset, calls DataAgent's tools directly, runs RAGAgent
# retrieval, and drives the full orchestrator, with real executed output.
python -m ipykernel install --user --name minisense --display-name "MiniSense (.venv)"
jupyter notebook notebooks/end_to_end_workflow.ipynb

# Optional: Node.js chat UI + CLI + gateway on top of the FastAPI backend
# (see client/README.md) — requires `uvicorn minisense.api:app` running.
cd client && npm install && cp .env.example .env  # set MINISENSE_API_TOKEN
npm start   # chat UI at http://localhost:3000
node cli.js "What is our overall CSAT?"
```

### Option B — Docker

```bash
cp .env.example .env
echo "API_AUTH_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env

docker compose up -d
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec app python scripts/ingest_faq.py     # build the FAQ index

curl -H "Authorization: Bearer $(grep API_AUTH_TOKEN .env | cut -d= -f2)" \
     -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What is our overall CSAT?"}'
```

`docker-compose.yml` brings up Ollama and the API together on one network,
with the survey dataset auto-generated on first run (see
`docker-entrypoint.sh`) and the FAQ index built as a one-time manual step
(model pulls and index builds aren't run automatically on every `up`, since
that would make the stack slow and flaky to start).

### Tests (either option, no Ollama required)

```bash
pip install -r requirements-dev.txt
ruff check src/ tests/ scripts/ data/       # lint — clean
PYTHONPATH=src mypy src/minisense            # type check — clean across all 26 modules
PYTHONPATH=src pytest tests/ -v --cov=minisense --cov-report=term-missing
```

57 tests, ~85% line coverage. All of it — including the FastAPI auth/rate-
limit/validation tests via `TestClient` — runs fully offline; the small
number of uncovered lines are the actual Ollama HTTP call sites and the
`if __name__ == "__main__"` entrypoints, which are exercised in practice
through the CLI/API tests calling `main()`/routes directly rather than by
mocking the network boundary a second time.

The CLI, eval script, and API all work with **no Ollama running at all** —
planning falls back to a keyword heuristic and summarization falls back to a
deterministic template — so the structural correctness of the whole pipeline
can be checked immediately. Ollama is only required for LLM-quality planning
and prose, and for the RAG index build/query (embeddings also run through
Ollama, via `nomic-embed-text`, rather than a separate HuggingFace download —
this keeps the entire system on one local runtime with zero external API
calls of any kind).

## 4. Configuration

Every runtime knob is a validated field on the `Settings` class in
`minisense/config.py` (built on `pydantic-settings`), loaded once from
environment variables or a local `.env` file. See `.env.example` for the
full list with defaults and descriptions. A malformed or unsafe
configuration — e.g. `MINISENSE_ENV=production` with no `API_AUTH_TOKEN`,
or a chunk overlap larger than the chunk size — fails immediately at
startup with a clear `pydantic.ValidationError`, not three calls deep at
request time.

## 5. Security posture

The FastAPI app (`minisense.api`) is hardened for something more than a
local demo, within the scope of a single-instance deployment:

- **Auth**: bearer-token auth on `/ask` when `API_AUTH_TOKEN` is set —
  mandatory in production (`Settings` refuses to start otherwise).
- **Input validation**: every survey record is validated against a pydantic
  schema at load time (bad dates, out-of-range ratings, and blank IDs are
  rejected record-by-record with a logged reason, not silently trusted);
  every question is length- and non-emptiness-checked before it reaches
  the LLM (`minisense/validation.py`).
- **Rate limiting**: a simple in-memory per-IP sliding window
  (`API_RATE_LIMIT_REQUESTS` / `API_RATE_LIMIT_WINDOW_SECONDS`). This is
  intentionally simple — one process, in-memory, reset on restart — correct
  for a single instance; a multi-instance deployment should move this to a
  shared store (Redis) or push it to an API gateway instead.
- **CORS**: closed by default (`API_CORS_ORIGINS` empty = no cross-origin
  access), not open-by-default.
- **No internal leakage**: in production, error responses return a generic
  message while the full exception detail goes to the server-side log only
  — a client never sees an internal file path or stack trace.
- **Docs disabled in production**: `/docs` and `/redoc` 404 when
  `MINISENSE_ENV=production`, so the API isn't self-documenting to an
  unauthenticated scanner.
- **Container**: runs as a non-root user, multi-stage build (no build
  toolchain or dev dependencies in the runtime image), `HEALTHCHECK` wired
  to `/health`.
- **Secrets**: `.env` is git-ignored; `.env.example` documents every
  variable without real values. No secret is ever logged (tokens are
  `pydantic.SecretStr`, which redacts on `repr()`/`str()`).

## 6. CI

`.github/workflows/ci.yml` runs on every push and PR to `main`:

| Job | What it does |
|---|---|
| `lint` | `ruff check` over `src/`, `tests/`, `scripts/`, `data/` |
| `typecheck` | `mypy src/minisense` — zero errors required |
| `test` | `pytest` across Python 3.10, 3.11, 3.12, with coverage uploaded as an artifact |
| `docker-build` | builds the `Dockerfile` (no push) — gated on the three jobs above passing, so a broken Dockerfile is caught the same way a broken test is |

All four run fully offline (no Ollama, no external services), so CI is
deterministic and fast.

## 7. Chunking strategy (Part 2)

**Sentence-aware chunking on paragraph boundaries, not fixed-size windows.**
The FAQ is short (~500 words) and structured as Q/A pairs under markdown
headings. A fixed-size character window would routinely split a question
from its answer mid-sentence — exactly the unit a business question needs
retrieved whole. `rag/chunking.py` chunks on blank-line-separated paragraphs
first (one Q/A pair each in this document), and only falls back to
sentence-level packing if a paragraph exceeds the character budget, with a
small overlap kept between adjacent pieces as a safety net for that fallback
path. Semantic (embedding-similarity) chunking was considered but is
overkill for a document this small and this structured — it would add
latency without changing retrieval quality here.

## 8. Evaluation checkpoint (Part 2)

`scripts/eval_questions.py` runs 3 sample questions end-to-end and writes the
plan, retrieved chunks, and final answer to `outputs/eval_results.md`. Summary
of what it shows:

- Retrieval works well for questions that map to a single FAQ heading (CSAT
  target, wait-time policy, complaint handling) — sentence-aware chunking
  keeps each Q/A pair intact, so the top-1 chunk is almost always the exact
  right answer.
- It falls short on questions needing synthesis across multiple FAQ sections
  (e.g. "how does staffing relate to wait times") — retrieval returns the
  relevant chunks independently; connecting them into one causal story is
  left to SummaryAgent's LLM call, not the retrieval step itself.
- Because the FAQ is small (~500 words, ~15-20 chunks), there's little
  headroom for retrieval to fail outright; the risk profile would look very
  different on a larger, noisier corpus.

## 9. Part 3 — Fine-Tuning Design (300–500 words)

**Scenario:** classify 10,000 free-text survey responses/day into 8
sentiment+topic categories, currently done accurately but too expensively
with GPT-4o.

**Data strategy.** I'd start by running the frontier model over a stratified
historical sample (by business, rating, and channel) to bootstrap labels
cheaply, then have humans review a subset for quality control — full manual
labeling of 10k/day is not sustainable, but zero human review risks
distilling the frontier model's own biases and errors uncorrected. I'd target
roughly 3,000–5,000 labeled examples for a first LoRA pass on a small
instruction-tuned base model — this task (8-way classification with fairly
distinct topic vocabulary) needs far less data than generation tasks — then
actively sample low-confidence and disagreement cases for a second labeling
round rather than randomly growing the set, since those are what actually
move accuracy. I'd deliberately oversample rare categories (e.g. rare
complaint types) so the class imbalance in raw survey data doesn't get
baked into the classifier.

**Model & technique.** A small open model in the 3B–8B range (e.g. Llama
3.1 8B or a similarly sized instruct model) is plenty for 8-way text
classification and keeps inference cost and latency low. QLoRA over full
fine-tuning: the task is narrow and the label space is small, so a low-rank
adapter captures it fully, at a fraction of the memory/compute, and keeps
the base model reusable for other classification tasks by swapping adapters.
Full FT would only be justified if the base model's domain vocabulary were
badly mismatched (not the case for restaurant/retail survey text).

**Training pipeline.** Hugging Face `transformers` + `peft` + `TRL`'s
`SFTTrainer` for a first pass — well-documented, easy to reason about.
Axolotl or LLaMA-Factory if the team needs to iterate on many similar
fine-tunes quickly, since their config-driven workflow reduces
boilerplate per experiment. I'd structure the job as: frozen base weights,
QLoRA adapter on attention + MLP projection layers, single epoch or two over
the curated set with early stopping on a held-out validation split, standard
classification-style prompt template with the 8 categories enumerated.

**Evaluation.** Per-class precision/recall/F1 (not just overall accuracy,
given class imbalance), plus a direct agreement-rate comparison against
GPT-4o on a frozen held-out set the model never trained on. I'd set a
concrete bar before replacing the frontier model in production — e.g.
matching GPT-4o's agreement-with-human-label rate within a small margin
on every category, not just in aggregate — and run a shadow-mode period
where both models score the same live traffic before the switch.

**Serving.** Serve the adapter alongside the existing LLM service via
adapter-swapping (vLLM/TGI support multiple LoRA adapters on one base model
process), so this route doesn't require a separate GPU deployment or
disrupt other routes on the same server; route survey-classification traffic
to the adapter, everything else stays on the frontier model or base model.

**Future-proofing.** Keep label taxonomy and prompt template in a versioned
config, not hardcoded — a category set change should be a config diff and a
retrain, not a code change. Log every prediction with input+output for
periodic drift review (are today's free-text responses statistically
different from what the adapter was trained on?), and re-run the
active-sampling labeling loop whenever drift crosses a threshold rather than
on a fixed calendar schedule.

## 10. Contributing & license

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup and the pre-PR checklist
(lint/type-check/test — the same three CI runs). Licensed under the
[MIT License](LICENSE).
