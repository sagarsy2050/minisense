const thread = document.getElementById("thread");
const welcome = document.getElementById("welcome");
const form = document.getElementById("ask-form");
const input = document.getElementById("question");
const submitBtn = document.getElementById("submit-btn");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const exampleChips = document.getElementById("example-chips");
const newChatBtn = document.getElementById("new-chat-btn");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");

const EXAMPLE_QUESTIONS = [
  "What are the top 3 complaints this month and how do they compare to last month?",
  "What is our overall CSAT and how does it compare to our stated CSAT target?",
  "How long do customers typically wait, and is that in line with our policy?",
  "What does the FAQ say about handling customer complaints?",
];

function fmtTime(d = new Date()) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function scrollToBottom() {
  thread.scrollTop = thread.scrollHeight;
}

function hideWelcome() {
  if (welcome) welcome.style.display = "none";
}

function addUserMessage(text) {
  hideWelcome();
  const row = document.createElement("div");
  row.className = "msg user";
  row.innerHTML = `
    <div class="avatar">You</div>
    <div class="bubble-col">
      <div class="bubble"></div>
      <div class="timestamp">${fmtTime()}</div>
    </div>`;
  row.querySelector(".bubble").textContent = text;
  thread.appendChild(row);
  scrollToBottom();
}

function addTypingIndicator() {
  const row = document.createElement("div");
  row.className = "msg agent";
  row.id = "typing-row";
  row.innerHTML = `
    <div class="avatar">MS</div>
    <div class="bubble-col">
      <div class="bubble typing-bubble">
        <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
        <span class="typing-label">thinking through your question&hellip;</span>
      </div>
    </div>`;
  thread.appendChild(row);
  scrollToBottom();
  return row;
}

function addAgentMessage({ answer, plan_reasoning, tasks, citations, trace, elapsedMs }, isError = false) {
  const row = document.createElement("div");
  row.className = "msg agent";
  const bubbleCol = document.createElement("div");
  bubbleCol.className = "bubble-col";

  const bubble = document.createElement("div");
  bubble.className = "bubble" + (isError ? " error-bubble" : "");
  bubble.textContent = answer;
  bubbleCol.appendChild(bubble);

  const tsRow = document.createElement("div");
  tsRow.className = "timestamp";
  tsRow.textContent = fmtTime() + (elapsedMs ? ` · ${(elapsedMs / 1000).toFixed(1)}s` : "");
  bubbleCol.appendChild(tsRow);

  if (!isError && (plan_reasoning || tasks?.length || citations?.length || trace)) {
    const meta = document.createElement("div");
    meta.className = "meta";

    if (tasks?.length) {
      const chips = tasks.map((t) => `<span class="chip">${t}</span>`).join("");
      meta.innerHTML += `<div>Routed to: ${chips}</div>`;
    }
    if (plan_reasoning) {
      meta.innerHTML += `<div style="margin-top:6px;">Plan: ${escapeHtml(plan_reasoning)}</div>`;
    }
    if (citations?.length) {
      meta.innerHTML += `<div style="margin-top:6px;">FAQ citations: ${citations.join(", ")}</div>`;
    }
    if (trace) {
      const details = document.createElement("details");
      details.innerHTML = `<summary>Full agent trace</summary><pre>${escapeHtml(
        JSON.stringify(trace, null, 2)
      )}</pre>`;
      meta.appendChild(details);
    }
    bubbleCol.appendChild(meta);
  }

  row.innerHTML = `<div class="avatar">MS</div>`;
  row.appendChild(bubbleCol);
  thread.appendChild(row);
  scrollToBottom();
}

async function checkStatus() {
  try {
    const r = await fetch("/api/ready");
    const body = await r.json();
    if (body.status === "ok" && body.ollama_reachable) {
      statusText.textContent = "Backend + Ollama ready";
      statusDot.className = "dot ok";
    } else if (body.survey_data_loaded) {
      statusText.textContent = "Ollama unreachable — heuristic fallback active";
      statusDot.className = "dot warn";
    } else {
      statusText.textContent = "Backend degraded: " + (body.detail || "unknown");
      statusDot.className = "dot err";
    }
  } catch {
    statusText.textContent = "Cannot reach gateway/backend";
    statusDot.className = "dot err";
  }
}

async function ask(question) {
  addUserMessage(question);
  input.value = "";
  autoGrow();
  submitBtn.disabled = true;
  const typingRow = addTypingIndicator();
  const start = performance.now();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = await res.json();
    typingRow.remove();
    const elapsedMs = performance.now() - start;
    if (!res.ok) {
      addAgentMessage({ answer: body.detail || `Error ${res.status}`, elapsedMs }, true);
    } else {
      addAgentMessage({ ...body, elapsedMs });
    }
  } catch (err) {
    typingRow.remove();
    addAgentMessage({ answer: `Network error: ${err.message}` }, true);
  } finally {
    submitBtn.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  ask(question);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

function autoGrow() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}
input.addEventListener("input", autoGrow);

newChatBtn.addEventListener("click", () => {
  thread.innerHTML = "";
  thread.appendChild(welcome);
  welcome.style.display = "block";
});

sidebarToggle?.addEventListener("click", () => sidebar.classList.toggle("open"));

exampleChips.innerHTML = EXAMPLE_QUESTIONS.map(
  (q, i) => `<button type="button" class="example-chip" data-idx="${i}">${escapeHtml(q)}</button>`
).join("");
exampleChips.addEventListener("click", (e) => {
  const btn = e.target.closest(".example-chip");
  if (!btn) return;
  ask(EXAMPLE_QUESTIONS[Number(btn.dataset.idx)]);
  sidebar.classList.remove("open");
});

checkStatus();
