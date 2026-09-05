# MiniSense Node client

A small Node.js layer on top of the Python FastAPI backend (`minisense.api`):

- **`server.js`** &mdash; Express gateway. Serves the chat UI in `public/` and proxies
  `/api/ask`, `/api/health`, `/api/ready` to the FastAPI backend, injecting the
  bearer token server-side (the browser never sees it) and adding its own
  rate limit on top of the backend's.
- **`public/`** &mdash; single-page chat UI. Type a business question, see the
  narrative answer, which sub-agents were routed to, and the full structured
  trace.
- **`cli.js`** &mdash; Node CLI client. Talks straight to the FastAPI backend
  (or through the gateway).
- **`health.js`** &mdash; CLI health check (`npm run health`). Checks the
  gateway, the FastAPI backend, and Ollama itself — the Ollama check
  (`GET /api/ollama/status`) queries Ollama's own REST API directly from
  Node (`/api/version`, `/api/tags`), independent of the Python backend, so
  it still reports Ollama's state even if the backend is down. Reports
  `healthy` (model pulled and reachable), `degraded` (Ollama up, configured
  model not pulled), or `unavailable` (Ollama unreachable) — never crashes
  the app, just reports status.

## Setup

```bash
cd client
npm install
cp .env.example .env
# set MINISENSE_API_TOKEN to the same value as API_AUTH_TOKEN in the
# Python project's .env (../.env)
```

## Run

1. Start the Python backend from the repo root:
   ```bash
   uvicorn minisense.api:app --host 0.0.0.0 --port 8000
   ```
2. Start the gateway + chat UI:
   ```bash
   npm start
   ```
   Open http://localhost:3000

## CLI usage

```bash
node cli.js "What is our overall CSAT and how does it compare to our stated CSAT target?"
node cli.js --trace "What are the top 3 complaints this month and how do they compare to last month?"
npm run health   # checks gateway + backend + Ollama, exits non-zero if degraded
```

## If Ollama isn't set up yet

1. Install Ollama: https://ollama.com
2. Start it: `ollama serve` (or it may already run as a background service)
3. Pull the two models this project uses:
   ```bash
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```
4. Verify: `npm run health` — should report `"status":"healthy"` under `ollama`.
   If it reports `degraded` with a "not found" detail, the model name in
   `MINISENSE_LLM_MODEL` (`.env`) doesn't match what you pulled — check with
   `ollama list`.
