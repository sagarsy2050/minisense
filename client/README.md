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
```
