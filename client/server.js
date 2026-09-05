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

app.listen(PORT, () => {
  console.log(`MiniSense gateway + chat UI listening on http://localhost:${PORT}`);
  console.log(`Proxying to backend at ${API_URL}${API_TOKEN ? " (with bearer token)" : " (no token configured)"}`);
});
