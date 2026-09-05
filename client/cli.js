#!/usr/bin/env node
// Node CLI client for MiniSense. Talks to the FastAPI backend directly
// (or through the Node gateway, if MINISENSE_API_URL points at it).
//
// Usage:
//   node cli.js "What is our overall CSAT?"
//   node cli.js --trace "What is our overall CSAT?"
require("dotenv").config();

const API_URL = process.env.MINISENSE_API_URL || "http://localhost:8000";
const API_TOKEN = process.env.MINISENSE_API_TOKEN || "";

function parseArgs(argv) {
  const args = argv.slice(2);
  const trace = args.includes("--trace");
  const question = args.filter((a) => a !== "--trace").join(" ").trim();
  return { question, trace };
}

async function main() {
  const { question, trace } = parseArgs(process.argv);
  if (!question) {
    console.error('Usage: node cli.js [--trace] "<business question>"');
    process.exit(1);
  }

  const headers = { "Content-Type": "application/json" };
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`;

  let res;
  try {
    res = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers,
      body: JSON.stringify({ question }),
    });
  } catch (err) {
    console.error(`Could not reach MiniSense backend at ${API_URL}: ${err.message}`);
    console.error("Is `uvicorn minisense.api:app` (or the Node gateway) running?");
    process.exit(1);
  }

  const body = await res.json();
  if (!res.ok) {
    console.error(`Error ${res.status}:`, body.detail || body);
    process.exit(1);
  }

  console.log("=".repeat(80));
  console.log("QUESTION:", question);
  console.log("=".repeat(80));
  console.log("\nPLAN:");
  console.log("  reasoning:", body.plan_reasoning);
  for (const t of body.tasks) console.log("  ->", t);
  console.log("\nANSWER:\n");
  console.log(body.answer);
  if (body.citations?.length) {
    console.log("\nCITATIONS:");
    for (const c of body.citations) console.log(" -", c);
  }
  if (trace) {
    console.log("\nTRACE:");
    console.log(JSON.stringify(body.trace, null, 2));
  }
}

main();
