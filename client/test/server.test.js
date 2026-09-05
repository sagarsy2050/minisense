// Tests for the Node gateway (server.js). Uses Node's built-in test runner
// (node:test) — no extra dev dependency needed. The Python backend and
// Ollama's HTTP API are mocked via global.fetch so these run fully offline,
// independent of whether the real backend/Ollama happen to be running.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

process.env.MINISENSE_API_URL = "http://backend.test";
process.env.MINISENSE_API_TOKEN = "test-token-123";
process.env.OLLAMA_HOST = "http://ollama.test";
process.env.MINISENSE_LLM_MODEL = "llama3.1:8b";
process.env.GATEWAY_RATE_LIMIT_REQUESTS = "1000"; // high enough that tests never trip it
process.env.PORT = "0";

const app = require("../server.js");

let server;
let baseUrl;
let originalFetch;

test.before(() => {
  server = app.listen(0);
  const { port } = server.address();
  baseUrl = `http://127.0.0.1:${port}`;
});

test.after(() => {
  server.close();
});

test.beforeEach(() => {
  originalFetch = global.fetch;
});

test.afterEach(() => {
  global.fetch = originalFetch;
});

test("GET / serves the chat UI", async () => {
  const res = await originalFetch(`${baseUrl}/`);
  assert.equal(res.status, 200);
  const text = await res.text();
  assert.match(text, /<title>MiniSense<\/title>/);
});

test("GET /api/health proxies the backend's /health", async () => {
  global.fetch = async (url) => {
    assert.equal(url, "http://backend.test/health");
    return { status: 200, json: async () => ({ status: "ok" }) };
  };
  const res = await originalFetch(`${baseUrl}/api/health`);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "ok" });
});

test("GET /api/health returns 502 with a clear message when the backend is unreachable", async () => {
  global.fetch = async () => {
    throw new Error("ECONNREFUSED");
  };
  const res = await originalFetch(`${baseUrl}/api/health`);
  assert.equal(res.status, 502);
  const body = await res.json();
  assert.match(body.detail, /Cannot reach MiniSense backend/);
});

test("POST /api/ask rejects a blank question with 400, without calling the backend", async () => {
  let called = false;
  global.fetch = async () => {
    called = true;
    return { status: 200, json: async () => ({}) };
  };
  const res = await originalFetch(`${baseUrl}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: "   " }),
  });
  assert.equal(res.status, 400);
  assert.equal(called, false);
});

test("POST /api/ask proxies to the backend and injects the bearer token server-side", async () => {
  let capturedUrl, capturedHeaders, capturedBody;
  global.fetch = async (url, opts) => {
    capturedUrl = url;
    capturedHeaders = opts.headers;
    capturedBody = JSON.parse(opts.body);
    return {
      status: 200,
      json: async () => ({ answer: "62.13% CSAT.", plan_reasoning: "r", tasks: ["DataAgent"], citations: [], trace: [] }),
    };
  };
  const res = await originalFetch(`${baseUrl}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: "What is our CSAT?" }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.answer, "62.13% CSAT.");
  assert.equal(capturedUrl, "http://backend.test/ask");
  assert.equal(capturedHeaders.Authorization, "Bearer test-token-123");
  assert.equal(capturedBody.question, "What is our CSAT?");
});

test("POST /api/ask surfaces the backend's own error status and body", async () => {
  global.fetch = async () => ({ status: 429, json: async () => ({ detail: "Rate limit exceeded" }) });
  const res = await originalFetch(`${baseUrl}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: "hello" }),
  });
  assert.equal(res.status, 429);
  assert.equal((await res.json()).detail, "Rate limit exceeded");
});

test("GET /api/ollama/status reports healthy when Ollama is up and the model is pulled", async () => {
  global.fetch = async (url) => {
    if (url === "http://ollama.test/api/version") return { ok: true, status: 200 };
    if (url === "http://ollama.test/api/tags") {
      return { ok: true, json: async () => ({ models: [{ name: "llama3.1:8b" }, { name: "nomic-embed-text:latest" }] }) };
    }
    throw new Error(`unexpected fetch url: ${url}`);
  };
  const res = await originalFetch(`${baseUrl}/api/ollama/status`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "healthy");
  assert.equal(body.ollama.available, true);
  assert.equal(body.ollama.modelAvailable, true);
  assert.deepEqual(body.ollama.pulledModels, ["llama3.1:8b", "nomic-embed-text:latest"]);
});

test("GET /api/ollama/status reports degraded when Ollama is up but the model isn't pulled", async () => {
  global.fetch = async (url) => {
    if (url === "http://ollama.test/api/version") return { ok: true, status: 200 };
    if (url === "http://ollama.test/api/tags") return { ok: true, json: async () => ({ models: [{ name: "some-other-model" }] }) };
    throw new Error(`unexpected fetch url: ${url}`);
  };
  const res = await originalFetch(`${baseUrl}/api/ollama/status`);
  const body = await res.json();
  assert.equal(body.status, "degraded");
  assert.equal(body.ollama.modelAvailable, false);
  assert.match(body.detail, /not found/);
});

test("GET /api/ollama/status reports unavailable when Ollama cannot be reached at all", async () => {
  global.fetch = async () => {
    throw new Error("connect ECONNREFUSED");
  };
  const res = await originalFetch(`${baseUrl}/api/ollama/status`);
  const body = await res.json();
  assert.equal(body.status, "unavailable");
  assert.equal(body.ollama.available, false);
  assert.match(body.detail, /Cannot reach Ollama/);
});
