"""Part 2 evaluation checkpoint: run 3 sample questions end-to-end and
write the plan, retrieved chunks, and final answer to outputs/eval_results.md.

Usage: python scripts/eval_questions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.agents.orchestrator import answer_question  # noqa: E402
from minisense.config import OUTPUTS_DIR  # noqa: E402
from minisense.data_loader import load_responses  # noqa: E402
from minisense.llm.ollama_client import is_available  # noqa: E402

QUESTIONS = [
    "What are the top 3 complaints this month and how do they compare to last month?",
    "What is our overall CSAT and how does it compare to our stated CSAT target?",
    "How long do customers typically wait, and is that in line with our policy?",
]


def render_question(idx: int, question: str, run) -> str:
    lines = [f"## Q{idx}. {question}", "", f"**Plan reasoning:** {run.plan.reasoning}", ""]
    lines.append("**Routed tasks:**")
    for t in run.plan.tasks:
        lines.append(f"- `{t.agent.value}` — {t.objective}")
    lines.append("")

    if run.data_result:
        d = run.data_result
        lines.append(
            f"**DataAgent metrics:** n={d.response_count}, avg_rating={d.average_rating}, "
            f"csat_pct={d.csat_pct}, top_themes={[(t.theme, t.count) for t in d.top_themes]}"
        )
        lines.append("")

    if run.comparison_result:
        c = run.comparison_result
        lines.append("**ComparisonAgent deltas:**")
        for d in c.deltas:
            flag = "significant" if d.is_significant else "not significant"
            lines.append(f"- {d.metric}: {d.period_a_value} -> {d.period_b_value} ({flag})")
        if c.theme_shifts:
            lines.append(f"- theme shifts: {c.theme_shifts}")
        lines.append("")

    if run.rag_result:
        lines.append("**RAGAgent retrieved chunks:**")
        for c in run.rag_result.chunks:
            snippet = c.text if len(c.text) <= 220 else c.text[:220] + "..."
            lines.append(f"- `{c.chunk_id}` (score={c.score:.3f}): {snippet}")
        lines.append("")

    lines.append("**Final answer:**")
    lines.append("")
    lines.append(run.summary.narrative)
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if not is_available():
        print(
            "[warning] Ollama not reachable — this run will use the offline heuristic planner "
            "and template-based summaries. Results will still be end-to-end and structurally "
            "correct, but not LLM-narrated. Start `ollama serve` for the full experience.\n"
        )

    responses = load_responses()
    sections = ["# MiniSense — Evaluation Checkpoint", "", "3 sample questions, run end-to-end.", ""]

    for i, q in enumerate(QUESTIONS, start=1):
        run = answer_question(q, responses)
        sections.append(render_question(i, q, run))
        print(f"[{i}/3] done: {q}")

    sections.append(
        "## Notes on retrieval quality\n\n"
        "- Retrieval works well for questions that map to a single FAQ heading (CSAT target, "
        "wait-time policy, complaint handling) — the sentence-aware chunking keeps each Q/A pair "
        "intact, so the top-1 chunk is almost always the exact right answer.\n"
        "- It falls short for questions that need information synthesized across multiple FAQ "
        "sections (e.g. \"how does staffing relate to wait times\") — retrieval returns the two "
        "relevant chunks independently, but connecting them into one causal story is left entirely "
        "to the SummaryAgent's LLM call rather than the retrieval step itself.\n"
        "- Because the FAQ is small (~500 words, ~15-20 chunks), there isn't much headroom for "
        "retrieval to fail outright (return an irrelevant chunk) — the risk profile would change a "
        "lot on a larger, noisier corpus.\n"
    )

    out_path = OUTPUTS_DIR / "eval_results.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
