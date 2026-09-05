"""One-off script: run 10 real business questions through the live
Orchestrator and write question + actual answer + routing + key metrics to
docs/example_questions.md. Not part of the assessment deliverable pipeline
(ingest_faq.py / eval_questions.py cover that) — this is purely a curated
"try these" reference doc built from genuine executions, not illustrative
examples.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.agents.orchestrator import answer_question  # noqa: E402
from minisense.data_loader import load_responses  # noqa: E402

QUESTIONS = [
    "What are the top 3 complaints this month and how do they compare to last month?",
    "What is our overall CSAT and how does it compare to our stated CSAT target?",
    "How long do customers typically wait, and is that in line with our policy?",
    "What does the FAQ say about handling customer complaints?",
    "How did staff-related complaints change between April and May?",
    "What are your most popular menu items according to the FAQ?",
    "What CSAT threshold triggers a root-cause review?",
    "What is our average rating and response count for the Riverside location?",
    "Which response channel do customers use most often?",
    "What is your policy on refunds or replacements for quality issues?",
]


def render(idx: int, question: str, run) -> str:
    lines = [f"## {idx}. {question}", "", f"**Routed to:** {', '.join(t.agent.value for t in run.plan.tasks)}", ""]
    if run.data_result:
        d = run.data_result
        lines.append(
            f"**DataAgent:** n={d.response_count}, avg_rating={d.average_rating}, "
            f"csat_pct={d.csat_pct}%, top_themes={[(t.theme, t.count) for t in d.top_themes]}"
        )
    if run.comparison_result:
        c = run.comparison_result
        sig = [f"{dd.metric}: {dd.period_a_value} -> {dd.period_b_value} ({'significant' if dd.is_significant else 'not significant'})" for dd in c.deltas]
        lines.append("**ComparisonAgent:** " + "; ".join(sig))
        if c.theme_shifts:
            lines.append("**Theme shifts:** " + "; ".join(c.theme_shifts))
    if run.rag_result and run.rag_result.chunks:
        lines.append("**RAGAgent retrieved:** " + "; ".join(f"[{ch.chunk_id}] score={ch.score:.3f}" for ch in run.rag_result.chunks))
    lines.append("")
    lines.append("**Answer:**")
    lines.append("")
    lines.append(run.summary.narrative)
    lines.append("")
    return "\n".join(lines)


def main():
    responses = load_responses()
    out_lines = [
        "# MiniSense — 10 Example Questions (real executions)",
        "",
        "Every answer below is a real, unedited run against the live system "
        "(100,000-record dataset, `llama3.1:8b` + `nomic-embed-text` via local "
        "Ollama, `python scripts/generate_example_questions_doc.py`). "
        "Reproduce any of these yourself with:",
        "",
        "```bash",
        'python -m minisense.cli "<question>"',
        "```",
        "",
    ]
    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i}/{len(QUESTIONS)}] {q}", flush=True)
        run = answer_question(q, responses)
        out_lines.append(render(i, q, run))

    out_path = Path(__file__).resolve().parents[1] / "docs" / "example_questions.md"
    out_path.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
