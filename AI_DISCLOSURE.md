# AI Tooling Disclosure

This project — the agent implementations, RAG pipeline, synthetic data
generator, tests, notebooks, and accompanying documentation
(`docs/SUBMISSION_REVIEW.md`, `docs/whitepaper.md`,
`docs/presentation.md`) — was developed
with an **AI coding assistant** used interactively throughout development:

- Code was written, then actually executed against a local Ollama server
  (`llama3.1:8b`, `nomic-embed-text`) and the real generated dataset, not
  produced and left unverified.
- A genuine bug was found and fixed during a real end-to-end run (the
  planner resolving "this month" against wall-clock time instead of the
  dataset's own date range) — caught by running the system, not by
  inspection alone.
- The technical review, white paper, and interview-preparation documents
  were written from direct inspection of this repository's actual source
  code and real captured execution output (`outputs/eval_results.md`,
  live CLI/API runs) — not generated from the assignment brief alone.
- No other AI coding assistant (ChatGPT, GitHub Copilot, etc.) was used in
  this repository's development.
- Third-party libraries used are declared normally in
  `requirements.txt`/`requirements-dev.txt`/`pyproject.toml` and are not
  themselves AI-generated.

AI tools were used as development and documentation assistants throughout.
The final implementation was reviewed, executed, and validated — through
real runs against a live local LLM and real data — rather than accepted
unverified.
