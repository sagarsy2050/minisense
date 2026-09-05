# Contributing to MiniSense

## Dev setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # adjust as needed for local dev
```

## Before opening a PR

```bash
ruff check src/ tests/ scripts/ data/     # lint
PYTHONPATH=src mypy src/minisense          # type check
PYTHONPATH=src pytest tests/ -v            # tests (no Ollama required)
```

All three run in CI (`.github/workflows/ci.yml`) on every push and PR, plus
a Docker build check. A PR that doesn't pass all three won't merge.

## Project conventions

- **One place per concern**: config lives in `minisense/config.py`
  (validated `pydantic-settings`, never read `os.environ` elsewhere),
  errors are one of the types in `minisense/exceptions.py`, logging goes
  through `minisense/logging_config.py`.
- **Structured over free-text**: every agent-to-agent handoff is a typed
  dataclass in `minisense/schemas.py`. If you're passing a dict or a raw
  string between agents, something's wrong.
- **Validate at the boundary**: untrusted input (the survey JSON on disk,
  an API request body) gets a pydantic model and a clear rejection path;
  internal agent-to-agent data doesn't need re-validating.
- **Offline-first**: every Ollama-dependent code path needs a graceful
  fallback (see `agents/orchestrator.py`'s heuristic planner and
  `agents/summary_agent.py`'s template narrative) — CI has no Ollama
  server, and neither does a fresh clone before `ollama pull`.
- Add a test alongside any behavior change. `tests/` mirrors `src/minisense/`
  by concern, not 1:1 by file.

## Reporting issues

Open a GitHub issue with: what you ran, what you expected, what happened
instead, and your Python version / OS. Include the relevant `ts=... msg=...`
log lines if the failure logged anything (`MINISENSE_LOG_LEVEL=DEBUG` for
more detail).
