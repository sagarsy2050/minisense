"""Direct unit tests for RAGAgent — query construction and structured
output, with the vector store retrieval mocked (no FAISS index or Ollama
embeddings needed)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minisense.agents import rag_agent  # noqa: E402
from minisense.schemas import AgentName, RetrievedChunk, TaskSpec  # noqa: E402

FAKE_CHUNKS = [
    RetrievedChunk(chunk_id="chunk_001", text="CSAT target is 4.5+.", score=0.91),
    RetrievedChunk(chunk_id="chunk_002", text="Wait time under 10 minutes off-peak.", score=0.72),
]


def test_uses_query_text_when_provided():
    task = TaskSpec(agent=AgentName.RAG, objective="fallback objective", query_text="CSAT target", top_k=2)
    with patch("minisense.agents.rag_agent.retrieve", return_value=FAKE_CHUNKS) as mock_retrieve:
        result = rag_agent.run(task)
    mock_retrieve.assert_called_once_with("CSAT target", top_k=2)
    assert result.query == "CSAT target"


def test_falls_back_to_objective_when_no_query_text():
    task = TaskSpec(agent=AgentName.RAG, objective="retrieve wait time policy", query_text=None)
    with patch("minisense.agents.rag_agent.retrieve", return_value=[]) as mock_retrieve:
        result = rag_agent.run(task)
    mock_retrieve.assert_called_once_with("retrieve wait time policy", top_k=4)
    assert result.query == "retrieve wait time policy"


def test_returns_structured_chunks_unmodified():
    task = TaskSpec(agent=AgentName.RAG, objective="obj", query_text="q")
    with patch("minisense.agents.rag_agent.retrieve", return_value=FAKE_CHUNKS):
        result = rag_agent.run(task)
    assert result.chunks == FAKE_CHUNKS
    assert result.chunks[0].chunk_id == "chunk_001"
    assert result.chunks[0].score == 0.91


def test_empty_retrieval_returns_empty_chunks_not_error():
    task = TaskSpec(agent=AgentName.RAG, objective="obj", query_text="nonsense query")
    with patch("minisense.agents.rag_agent.retrieve", return_value=[]):
        result = rag_agent.run(task)
    assert result.chunks == []
