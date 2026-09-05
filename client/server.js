// MiniSense Node gateway: serves the chat UI and proxies /api/* to the
// Python FastAPI backend, injecting the bearer token server-side so it
// never reaches the browser.
require("dotenv").config();

const path = require("path");
const express = require("express");
const rateLimit = require("express-rate-limit");

const PORT = process.env.PORT || 3000;
const API_URL = process.env.MINISENSE_API_URL || "http://localhost:8000";
const API_TOKEN = process.env.MINISENSE_API_TOKEN || "";
const OLLAMA_URL = process.env.OLLAMA_HOST || "http://localhost:11434";
const OLLAMA_MODEL = process.env.MINISENSE_LLM_MODEL || "llama3.1:8b";
const RATE_LIMIT_REQUESTS = Number(process.env.GATEWAY_RATE_LIMIT_REQUESTS || 30);
const RATE_LIMIT_WINDOW_MS = Number(process.env.GATEWAY_RATE_LIMIT_WINDOW_MS || 60000);

const app = express();
app.use(express.json({ limit: "16kb" }));
app.use(express.static(path.join(__dirname, "public")));

app.use(
  "/api/",
  rateLimit({
    windowMs: RATE_LIMIT_WINDOW_MS,
    max: RATE_LIMIT_REQUESTS,
    standardHeaders: true,
    legacyHeaders: false,
    message: { detail: "Rate limit exceeded on the gateway." },
  })
);

function backendHeaders(extra) {
  const headers = { "Content-Type": "application/json", ...extra };
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`;
  return headers;
}

app.get("/api/health", async (_req, res) => {
  try {
    const r = await fetch(`${API_URL}/health`);
    res.status(r.status).json(await r.json());
  } catch (err) {
    res.status(502).json({ detail: `Cannot reach MiniSense backend at ${API_URL}: ${err.message}` });
  }
});

app.get("/api/ready", async (_req, res) => {
  try {
    const r = await fetch(`${API_URL}/ready`);
    res.status(r.status).json(await r.json());
  } catch (err) {
    res.status(502).json({ detail: `Cannot reach MiniSense backend at ${API_URL}: ${err.message}` });
  }
});

// Direct Node-side Ollama check (independent of the Python backend) — hits
// Ollama's own REST API so this gateway can report Ollama status even if
// the FastAPI backend itself is down.
app.get("/api/ollama/status", async (_req, res) => {
  const base = {
    application: "MiniSense",
    ollama: { baseUrl: OLLAMA_URL, modelConfigured: OLLAMA_MODEL, available: false, modelAvailable: false },
  };
  let versionResp;
  try {
    versionResp = await fetch(`${OLLAMA_URL}/api/version`, { signal: AbortSignal.timeout(3000) });
  } catch (err) {
    return res.status(200).json({ ...base, status: "unavailable", detail: `Cannot reach Ollama at ${OLLAMA_URL}: ${err.message}` });
  }
  if (!versionResp.ok) {
    return res.status(200).json({ ...base, status: "unavailable", detail: `Ollama returned HTTP ${versionResp.status}` });
  }
  base.ollama.available = true;

  try {
    const tagsResp = await fetch(`${OLLAMA_URL}/api/tags`, { signal: AbortSignal.timeout(3000) });
    const tags = await tagsResp.json();
    const names = (tags.models || []).map((m) => m.name);
    base.ollama.modelAvailable = names.includes(OLLAMA_MODEL);
    base.ollama.pulledModels = names;
  } catch (err) {
    return res.status(200).json({ ...base, status: "degraded", detail: `Ollama reachable but /api/tags failed: ${err.message}` });
  }

  const status = base.ollama.modelAvailable ? "healthy" : "degraded";
  const detail = base.ollama.modelAvailable ? null : `Configured model '${OLLAMA_MODEL}' not found — run: ollama pull ${OLLAMA_MODEL}`;
  res.status(200).json({ ...base, status, detail });
});

app.post("/api/ask", async (req, res) => {
  const question = typeof req.body?.question === "string" ? req.body.question.trim() : "";
  if (!question) {
    return res.status(400).json({ detail: "Field 'question' is required." });
  }
  try {
    const r = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: backendHeaders(),
      body: JSON.stringify({ question }),
    });
    const body = await r.json();
    res.status(r.status).json(body);
  } catch (err) {
    res.status(502).json({ detail: `Cannot reach MiniSense backend at ${API_URL}: ${err.message}` });
  }
});

// Only bind a port when run directly (`node server.js`), not when required
// by the test suite — lets tests start the app on an ephemeral port instead.
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`MiniSense gateway + chat UI listening on http://localhost:${PORT}`);
    console.log(`Proxying to backend at ${API_URL}${API_TOKEN ? " (with bearer token)" : " (no token configured)"}`);
  });
}

module.exports = app;
