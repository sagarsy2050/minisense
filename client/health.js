#!/usr/bin/env node
// CLI health check: reports gateway, backend, and Ollama status without a browser.
// Usage: node health.js  (or: npm run health)
require("dotenv").config();

const GATEWAY_URL = process.env.GATEWAY_URL || `http://localhost:${process.env.PORT || 3000}`;

async function check(label, url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) });
    const body = await r.json();
    console.log(`[${r.ok ? "OK" : "FAIL"}] ${label} (HTTP ${r.status})`);
    console.log("  " + JSON.stringify(body));
    return r.ok;
  } catch (err) {
    console.log(`[FAIL] ${label}: ${err.message}`);
    return false;
  }
}

async function main() {
  console.log(`Checking MiniSense gateway at ${GATEWAY_URL} ...\n`);
  const gatewayOk = await check("Gateway -> backend /health", `${GATEWAY_URL}/api/health`);
  const readyOk = await check("Gateway -> backend /ready", `${GATEWAY_URL}/api/ready`);
  const ollamaOk = await check("Gateway -> Ollama status", `${GATEWAY_URL}/api/ollama/status`);
  console.log("\nOverall:", gatewayOk && readyOk && ollamaOk ? "HEALTHY" : "DEGRADED/UNAVAILABLE — see detail above");
  // Set exitCode and let Node drain the event loop naturally rather than
  // calling process.exit() — a forced exit can race with AbortSignal.timeout()'s
  // internal timer handle on Windows and crash with a libuv assertion.
  process.exitCode = gatewayOk && readyOk ? 0 : 1;
}

main();
