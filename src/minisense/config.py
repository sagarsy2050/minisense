"""Central, validated configuration.

Every path, model name, and runtime knob lives here as a single
``pydantic-settings`` ``Settings`` object, loaded once from environment
variables (and a local ``.env`` file if present — see ``.env.example`` at
the repo root for every variable this recognizes). Nothing else in the
codebase reads ``os.environ`` directly, so there is exactly one place to
audit for what's configurable and exactly one place that validates it.

Import ``get_settings()`` (cached) rather than constructing ``Settings()``
yourself, so the whole process shares one validated configuration and
``.env`` is only parsed once.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Filesystem layout — not user-configurable, derived from the package
# location so it's correct regardless of the current working directory.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
STORAGE_DIR = ROOT_DIR / "storage"
OUTPUTS_DIR = ROOT_DIR / "outputs"

FAISS_INDEX_PATH = STORAGE_DIR / "faq_index.faiss"
FAISS_META_PATH = STORAGE_DIR / "faq_index.meta.json"

for _d in (DATA_DIR, STORAGE_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """All runtime configuration, validated at process startup.

    A malformed or unsafe configuration (e.g. a production deployment with
    no API auth token) fails fast here with a clear ``pydantic.ValidationError``
    rather than surfacing as a confusing runtime error three calls deep.
    """

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # -- Environment ---------------------------------------------------
    environment: Environment = Field(default=Environment.DEVELOPMENT, alias="MINISENSE_ENV")
    log_level: LogLevel = Field(default=LogLevel.INFO, alias="MINISENSE_LOG_LEVEL")

    # -- Ollama (local LLM runtime) --------------------------------------
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    llm_model: str = Field(default="llama3.1:8b", alias="MINISENSE_LLM_MODEL")
    embed_model: str = Field(default="nomic-embed-text", alias="MINISENSE_EMBED_MODEL")
    llm_timeout_s: int = Field(default=120, ge=1, le=600, alias="MINISENSE_LLM_TIMEOUT")
    temperature_planner: float = Field(default=0.0, ge=0.0, le=2.0)
    temperature_summary: float = Field(default=0.4, ge=0.0, le=2.0)

    # -- Data paths ------------------------------------------------------
    survey_json_path: Path = Field(
        default=DATA_DIR / "survey_responses.json", alias="MINISENSE_SURVEY_PATH"
    )
    faq_path: Path = Field(default=DATA_DIR / "product_faq.md", alias="MINISENSE_FAQ_PATH")

    # -- RAG / chunking ----------------------------------------------------
    chunk_max_chars: int = Field(default=500, ge=50, le=8000, alias="MINISENSE_CHUNK_MAX_CHARS")
    chunk_overlap_chars: int = Field(default=80, ge=0, le=2000, alias="MINISENSE_CHUNK_OVERLAP_CHARS")
    top_k_default: int = Field(default=4, ge=1, le=50, alias="MINISENSE_TOP_K_DEFAULT")
    embedding_dim_fallback: int = Field(default=768, ge=1)

    # -- API surface (minisense.api) --------------------------------------
    api_auth_token: SecretStr | None = Field(default=None, alias="API_AUTH_TOKEN")
    api_cors_origins: str = Field(default="", alias="API_CORS_ORIGINS")
    api_rate_limit_requests: int = Field(default=30, ge=1, le=10_000, alias="API_RATE_LIMIT_REQUESTS")
    api_rate_limit_window_s: int = Field(default=60, ge=1, le=3600, alias="API_RATE_LIMIT_WINDOW_SECONDS")
    api_max_question_chars: int = Field(default=1000, ge=1, le=20_000, alias="API_MAX_QUESTION_CHARS")

    @field_validator("api_auth_token", mode="before")
    @classmethod
    def _blank_token_means_unset(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("survey_json_path", "faq_path", mode="before")
    @classmethod
    def _resolve_relative_to_root(cls, v: str | Path) -> Path:
        p = Path(v)
        return p if p.is_absolute() else ROOT_DIR / p

    @field_validator("chunk_overlap_chars")
    @classmethod
    def _overlap_smaller_than_chunk(cls, v: int, info) -> int:
        max_chars = info.data.get("chunk_max_chars")
        if max_chars is not None and v >= max_chars:
            raise ValueError(
                f"chunk_overlap_chars ({v}) must be smaller than chunk_max_chars ({max_chars})"
            )
        return v

    @model_validator(mode="after")
    def _require_auth_token_in_production(self) -> Settings:
        if self.environment == Environment.PRODUCTION and not self.api_auth_token:
            raise ValueError(
                "API_AUTH_TOKEN must be set when MINISENSE_ENV=production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings once per process."""
    return Settings()


# ---------------------------------------------------------------------------
# Backward-compatible module-level accessors used throughout the codebase
# (``from minisense.config import OLLAMA, EMBEDDING, ...``). These are thin
# wrappers over the single validated Settings instance, not a second source
# of truth — every value here is read straight off get_settings().
# ---------------------------------------------------------------------------
class _OllamaView:
    @property
    def host(self) -> str:
        return get_settings().ollama_host

    @property
    def chat_model(self) -> str:
        return get_settings().llm_model

    @property
    def embed_model(self) -> str:
        return get_settings().embed_model

    @property
    def request_timeout_s(self) -> int:
        return get_settings().llm_timeout_s

    @property
    def temperature_planner(self) -> float:
        return get_settings().temperature_planner

    @property
    def temperature_summary(self) -> float:
        return get_settings().temperature_summary


class _EmbeddingView:
    @property
    def dim(self) -> int:
        return get_settings().embedding_dim_fallback


OLLAMA = _OllamaView()
EMBEDDING = _EmbeddingView()

SURVEY_JSON_PATH = get_settings().survey_json_path
FAQ_PATH = get_settings().faq_path
CHUNK_MAX_CHARS = get_settings().chunk_max_chars
CHUNK_OVERLAP_CHARS = get_settings().chunk_overlap_chars
TOP_K_DEFAULT = get_settings().top_k_default
