"""Structured data contracts.

The assignment explicitly requires: (a) the orchestrator hands each
sub-agent a *structured* task spec, not raw text, and (b) each sub-agent
returns *structured* output, not free-form text. Every shape that crosses an
agent boundary is defined here as a dataclass so both sides are typed.

``SurveyResponseRecord`` (a pydantic model, not a dataclass) is the one
exception: it's the schema-validation boundary for untrusted input coming
off disk (``data_loader.load_responses``), where real type coercion and
error messages matter, rather than an internal agent-to-agent contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date as date_type
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def to_dict(obj: Any) -> dict:
    """Recursively convert a dataclass (possibly nested) into a plain dict."""
    return asdict(obj)


# ---------------------------------------------------------------------------
# Survey data validation boundary (Appendix A schema)
# ---------------------------------------------------------------------------
class SurveyResponseRecord(BaseModel):
    """One validated survey response record.

    Mirrors the assignment's Appendix A schema. Used only at load time
    (``data_loader.load_responses``) to reject malformed records with a
    clear error instead of letting a bad record (missing field, out-of-range
    rating, unparsable date) silently corrupt a downstream metric.
    """

    response_id: str = Field(min_length=1)
    date: date_type
    business_id: str = Field(min_length=1)
    business_name: str = Field(min_length=1)
    survey_id: str = Field(min_length=1)
    survey_name: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    response_channel: str = Field(min_length=1)
    free_text: str = Field(default="", max_length=5000)

    @field_validator("response_id", "business_id", "business_name", "survey_id", "survey_name", "response_channel")
    @classmethod
    def _strip_and_require_nonblank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


# ---------------------------------------------------------------------------
# Orchestrator -> sub-agent task spec
# ---------------------------------------------------------------------------
class AgentName(str, Enum):
    DATA = "DataAgent"
    RAG = "RAGAgent"
    COMPARISON = "ComparisonAgent"
    SUMMARY = "SummaryAgent"


@dataclass
class DateRange:
    start: str | None = None  # ISO date "YYYY-MM-DD", None = no lower bound
    end: str | None = None    # None = no upper bound


@dataclass
class TaskSpec:
    """A single structured instruction routed to exactly one sub-agent."""
    agent: AgentName
    objective: str                       # short human-readable purpose, for tracing/logs
    business_id: str | None = None    # None = all businesses
    period_a: DateRange | None = None  # primary (or "current") period
    period_b: DateRange | None = None  # comparison ("previous") period, ComparisonAgent only
    query_text: str | None = None      # for RAGAgent semantic search
    top_k: int = 4
    metrics: list[str] = field(default_factory=list)  # which DataAgent metrics to compute


@dataclass
class Plan:
    """Output of the Orchestrator's planning step."""
    question: str
    tasks: list[TaskSpec]
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Sub-agent structured outputs
# ---------------------------------------------------------------------------
@dataclass
class ThemeCount:
    theme: str
    count: int


@dataclass
class DataAgentResult:
    period: DateRange
    business_id: str | None
    response_count: int
    average_rating: float | None
    csat_pct: float | None           # % of responses rated >= 4 (1-5 scale)
    top_themes: list[ThemeCount]
    channel_breakdown: dict[str, int]


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float


@dataclass
class RAGAgentResult:
    query: str
    chunks: list[RetrievedChunk]


@dataclass
class MetricDelta:
    metric: str
    period_a_value: float | None
    period_b_value: float | None
    absolute_change: float | None
    pct_change: float | None
    is_significant: bool


@dataclass
class ComparisonAgentResult:
    period_a: DateRange
    period_b: DateRange
    deltas: list[MetricDelta]
    theme_shifts: list[str]   # short human-readable notes, e.g. "wait time complaints +40%"


@dataclass
class SummaryAgentResult:
    narrative: str
    citations: list[str]   # chunk_ids used, for traceability


@dataclass
class AgentRunLog:
    """One entry in the execution trace returned alongside the final answer."""
    agent: str
    task: dict
    result: dict
