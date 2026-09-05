# MiniSense — Final Submission Readiness Report

## Overall status: READY FOR SUBMISSION

The repository satisfies every required element of the assessment brief
(README + runnable code + design writeup), all 57 automated tests pass, and
the full pipeline was verified against a live local Ollama server and a
real 100,000-record dataset — not just read for correctness. Gaps that
exist are stated explicitly below, not hidden.

## Overall score: 87 / 100

| Category | Weight | Score | Why |
|---|---:|---:|---|
| Architecture | 15 | 14 | Clean agent/tool/RAG separation; no cyclic or ambiguous routing |
| Implementation | 20 | 18 | All required agents implemented and verified live; minor: no retry/backoff on Ollama |
| Agentic AI | 15 | 13 | Real structured planning/routing; no multi-turn memory (not required) |
| RAG | 15 | 13 | Real chunking/embedding/FAISS/retrieval, evaluated on 3 real questions; small corpus limits stress-testing retrieval failure modes |
| Data/Analytics | 10 | 9 | 100k realistic, validated, non-uniform dataset; keyword-based theme extraction is a known simplification |
| Testing | 10 | 8 | 57 passing tests, one flaky env-coupled test found and fixed this session; RAGAgent/SummaryAgent lack direct unit tests |
| Documentation | 5 | 5 | README, technical review, white paper, interview prep, executed notebook |
| Production thinking | 5 | 4 | Explicit scalability/security/observability review; no implemented retry/versioning |
| Interview readiness | 5 | 5 | 100-question grounded prep doc, pitches at 4 lengths |

Scores reflect evidence gathered from actually reading the code and running
the system this session — not a template score.

## Top 10 strengths

1. Strict separation of LLM responsibilities (plan/route/narrate) from deterministic code (every number) — the assignment's core engineering test.
2. All four optional sub-agents implemented (brief requires 2 of 4).
3. Real tool-calling example (`compute_csat`) traced end to end into the final narrative.
4. Graceful degradation: heuristic planner + template narrative when Ollama is down — pipeline never hard-fails.
5. A genuine bug (wall-clock vs. dataset-date anchoring) found and fixed via actual execution, not just review.
6. Sentence-aware FAQ chunking correctly justified against the document's actual Q/A structure.
7. ComparisonAgent recomputes full theme counts specifically to avoid a false "100% drop" artifact from top-3-limited data — a subtle correctness fix.
8. Non-uniform, validated, realistically varied synthetic dataset (not random noise).
9. 57 tests, all offline/no-Ollama-required, CI-enforced lint+typecheck+test+Docker build.
10. Documentation is grounded in real evidence (execution traces, actual retrieved chunks) rather than the assignment's illustrative examples.

## Top 10 risks

1. No retry/backoff around the single external dependency (Ollama) — a transient failure degrades rather than retries.
2. `RAGAgent`/`SummaryAgent` have no direct unit tests (only indirect coverage).
3. ComparisonAgent's significance thresholds are engineering-judgment constants, not statistically derived.
4. Theme extraction is keyword-based — misses paraphrases outside its keyword list.
5. In-memory dataset caching won't scale past a few million rows without a real datastore.
6. No FAQ index versioning/rollback.
7. Rate limiter is single-process/in-memory — not correct for multi-instance deployment as-is.
8. No multi-turn conversation memory (each question is stateless) — not required, but worth knowing if asked.
9. Dataset is synthetic — findings demonstrate pipeline capability, not real operational insight.
10. No request-ID correlation across a single request's log lines.

## Top 10 fixes before submission (prioritized)

| # | Fix | Priority | Status |
|---|---|---|---|
| 1 | Fix hardcoded sandbox output path + missing `--count` in `data/generate_data.py` | P0 | **Fixed this session** |
| 2 | Fix "this month" wall-clock anchoring bug in `orchestrator.py` | P0 | **Fixed this session** |
| 3 | Merge/dedupe the two overlapping survey JSON files into one canonical dataset | P0 | **Fixed this session** |
| 4 | Un-ignore `outputs/eval_results.md` in `.gitignore` (required Part 2 deliverable) | P0 | **Fixed this session** |
| 5 | Fix `test_api.py` test coupled to real Ollama-running state | P1 | **Fixed this session** |
| 6 | Enrich free-text template variety + realistic imperfections | P1 | **Fixed this session** |
| 7 | Add `RAGAgent`/`SummaryAgent` direct unit tests with mocked Ollama | P1 | Not done — recommended next |
| 8 | Add retry/backoff around `ollama_client` calls | P1 | Not done — recommended next |
| 9 | Add request-ID correlation to logs/trace | P2 | Not done — future enhancement |
| 10 | FAQ index versioning/rollback path | P2 | Not done — future enhancement |

## Exact files changed this session

| File | Problem | Change | Test added |
|---|---|---|---|
| `data/generate_data.py` | Hardcoded `/mnt/user-data/outputs/...` path, no `--count`/`--seed` args, thin template variety | Added `argparse`, fixed output path, expanded template banks, added `_humanize()`, sentiment-mismatch logic, richer validation report | N/A (script, no test file touches it) |
| `src/minisense/agents/orchestrator.py` | `date.today()` used for "this month"/"last month", zeroing results outside the dataset's real window | Added `_dataset_today()`, anchored both `_llm_plan` and `_heuristic_plan` to it | Verified via real CLI runs (pre/post fix) |
| `tests/test_api.py` | `test_ready_reports_data_loaded` asserted `ollama_reachable is False` by relying on Ollama not running on the test machine | Mock `is_available` explicitly | Existing test fixed, now environment-independent |
| `.gitignore` | `outputs/*.md` silently excluded the required Part 2 checkpoint file | Un-ignored `outputs/eval_results.md` specifically | N/A |
| `data/survey_responses.json` | Two overlapping/duplicate generated files present | Merged + deduped by `response_id` into one 100,000-record canonical file | Schema/dedup verified inline during the merge |

## How to run

See `README.md` §3. Condensed:
```bash
ollama pull llama3.1:8b && ollama pull nomic-embed-text && ollama serve
pip install -r requirements.txt
cp .env.example .env
python data/generate_data.py --count 100000 --seed 42
python scripts/ingest_faq.py
python -m minisense.cli "What is our overall CSAT and how does it compare to our stated CSAT target?"
```

## How to reproduce the RAG evaluation examples

```bash
python scripts/eval_questions.py   # regenerates outputs/eval_results.md
```
Or open and run `notebooks/minisense_business_analysis.ipynb` end to end,
which reproduces the same three questions live plus a fuller business
analysis of the dataset.

## Known limitations

See §18 of `docs/whitepaper.md` and §11 of `docs/SUBMISSION_REVIEW.md` for
the full, honest list — summarized: no retry logic, indirect RAG/Summary
test coverage, synthetic dataset, keyword-based theme extraction,
in-memory-only data storage.

## Future improvements

See §19 of `docs/whitepaper.md`.

## AI tools / external resources disclosure

See `AI_DISCLOSURE.md`.
