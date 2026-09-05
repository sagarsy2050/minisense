const thread = document.getElementById("thread");
const form = document.getElementById("ask-form");
const input = document.getElementById("question");
const submitBtn = document.getElementById("submit-btn");
const statusBadge = document.getElementById("status-badge");

function addUserMessage(text) {
  const row = document.createElement("div");
  row.className = "msg user";
  row.innerHTML = `<div class="bubble"></div>`;
  row.querySelector(".bubble").textContent = text;
  thread.appendChild(row);
  thread.scrollTop = thread.scrollHeight;
}

function addAgentMessage({ answer, plan_reasoning, tasks, citations, trace }, isError = false) {
  const row = document.createElement("div");
  row.className = "msg agent";
  const bubble = document.createElement("div");
  bubble.className = "bubble" + (isError ? " error-bubble" : "");
  bubble.textContent = answer;
  row.appendChild(bubble);

  if (!isError && (plan_reasoning || tasks?.length || citations?.length || trace)) {
    const meta = document.createElement("div");
    meta.className = "meta";

    if (tasks?.length) {
      const chips = tasks.map((t) => `<span class="chip">${t}</span>`).join("");
      meta.innerHTML += `<div>Routed to: ${chips}</div>`;
    }
    if (plan_reasoning) {
      meta.innerHTML += `<div style="margin-top:6px;">Plan: ${plan_reasoning}</div>`;
    }
    if (citations?.length) {
      meta.innerHTML += `<div style="margin-top:6px;">Citations: ${citations.join(", ")}</div>`;
    }
    if (trace) {
      const details = document.createElement("details");
      details.innerHTML = `<summary>Full agent trace</summary><pre>${escapeHtml(
        JSON.stringify(trace, null, 2)
      )}</pre>`;
      meta.appendChild(details);
    }
    row.appendChild(meta);
  }

  thread.appendChild(row);
  thread.scrollTop = thread.scrollHeight;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function checkStatus() {
  try {
    const r = await fetch("/api/ready");
    const body = await r.json();
    if (body.status === "ok" && body.ollama_reachable) {
      statusBadge.textContent = "backend + Ollama ready";
      statusBadge.className = "badge ok";
    } else if (body.survey_data_loaded) {
      statusBadge.textContent = "backend up, Ollama unreachable (heuristic fallback active)";
      statusBadge.className = "badge warn";
    } else {
      statusBadge.textContent = "backend degraded: " + (body.detail || "unknown");
      statusBadge.className = "badge err";
    }
  } catch {
    statusBadge.textContent = "cannot reach gateway/backend";
    statusBadge.className = "badge err";
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  addUserMessage(question);
  input.value = "";
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = await res.json();
    if (!res.ok) {
      addAgentMessage({ answer: body.detail || `Error ${res.status}` }, true);
    } else {
      addAgentMessage(body);
    }
  } catch (err) {
    addAgentMessage({ answer: `Network error: ${err.message}` }, true);
  } finally {
    submitBtn.disabled = false;
    input.focus();
  }
});

checkStatus();
