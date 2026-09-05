"""RAGAgent — retrieves relevant FAQ chunks to ground the final answer."""
from __future__ import annotations

from minisense.rag.retrieve import retrieve
from minisense.schemas import RAGAgentResult, TaskSpec


def run(task: TaskSpec) -> RAGAgentResult:
    query = task.query_text or task.objective
    chunks = retrieve(query, top_k=task.top_k)
    return RAGAgentResult(query=query, chunks=chunks)
