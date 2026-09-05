"""FastAPI wrapper around the same orchestrator the CLI uses.

The CLI (``minisense.cli``) is the primary, always-available interface —
this is the optional HTTP surface the assignment lists as optional. Run
with:

    uvicorn minisense.api:app --host 0.0.0.0 --port 8000

Security posture (see ``.env.example`` for every knob):
- Bearer-token auth on every non-health route when ``API_AUTH_TOKEN`` is
  set (mandatory in production — enforced by ``Settings`` at startup, see
  ``minisense.config``).
- A simple in-memory per-IP rate limiter. It is intentionally simple (one
  process, in-memory, reset on restart) — fine for a single-instance
  deployment; a multi-instance deployment should push this to a shared
  store (Redis) or an API gateway instead.
- CORS is closed by default (``API_CORS_ORIGINS`` empty = no cross-origin
  access) rather than defaulting open.
- Interactive docs (``/docs``, ``/redoc``) are disabled in production, so
  the API surface isn't self-documenting to an unauthenticated scanner.
- Error responses never leak internal detail (file paths, stack traces) in
  production; the full detail always goes to the server-side log instead.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from minisense.agents.orchestrator import answer_question
from minisense.config import get_settings
from minisense.data_loader import load_responses
from minisense.exceptions import (
    DataLoadError,
    IndexNotFoundError,
    InvalidQuestionError,
    MiniSenseError,
    OllamaUnavailableError,
)
from minisense.llm.ollama_client import is_available
from minisense.logging_config import configure_logging, get_logger
from minisense.validation import validate_question

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title="MiniSense",
    description="Survey analysis multi-agent API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Rate limiting — simple in-memory sliding window per client IP.
# ---------------------------------------------------------------------------
_request_log: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    window = settings.api_rate_limit_window_s
    limit = settings.api_rate_limit_requests
    log = _request_log[client_ip]
    while log and now - log[0] > window:
        log.popleft()
    if len(log) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests per {window}s.",
        )
    log.append(now)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> None:
    token = settings.api_auth_token
    if token is None:
        # No token configured (development only — Settings forbids this in
        # production, see minisense.config._require_auth_token_in_production).
        return
    if credentials is None or credentials.credentials != token.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------
class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=settings.api_max_question_chars)


class QuestionResponse(BaseModel):
    answer: str
    plan_reasoning: str
    tasks: list[str]
    citations: list[str]
    trace: list[dict]


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    survey_data_loaded: bool
    ollama_reachable: bool
    detail: str | None = None


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Middleware: request logging + rate limiting
# ---------------------------------------------------------------------------
@app.middleware("http")
async def _log_and_rate_limit(request: Request, call_next):
    if request.url.path not in ("/health",):
        client_ip = request.client.host if request.client else "unknown"
        try:
            _check_rate_limit(client_ip)
        except HTTPException as exc:
            logger.warning(f"Rate limit hit: ip={client_ip} path={request.url.path}")
            return _http_exception_to_response(exc)

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)")
    return response


def _http_exception_to_response(exc: HTTPException):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# ---------------------------------------------------------------------------
# Exception handlers — expected MiniSenseError subtypes map to the right
# HTTP status; anything unexpected is logged in full and returns a generic
# 500 rather than leaking internals to the client.
# ---------------------------------------------------------------------------
@app.exception_handler(InvalidQuestionError)
async def _invalid_question_handler(request: Request, exc: InvalidQuestionError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.exception_handler(DataLoadError)
async def _data_load_error_handler(request: Request, exc: DataLoadError):
    from fastapi.responses import JSONResponse

    logger.error(f"DataLoadError: {exc}")
    detail = str(exc) if not settings.is_production else "Survey data is unavailable."
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": detail})


@app.exception_handler(IndexNotFoundError)
async def _index_not_found_handler(request: Request, exc: IndexNotFoundError):
    from fastapi.responses import JSONResponse

    detail = str(exc) if not settings.is_production else "FAQ retrieval is unavailable."
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": detail})


@app.exception_handler(OllamaUnavailableError)
async def _ollama_unavailable_handler(request: Request, exc: OllamaUnavailableError):
    from fastapi.responses import JSONResponse

    detail = str(exc) if not settings.is_production else "The local LLM runtime is unavailable."
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": detail})


@app.exception_handler(MiniSenseError)
async def _minisense_error_handler(request: Request, exc: MiniSenseError):
    from fastapi.responses import JSONResponse

    detail = str(exc) if not settings.is_production else "Request could not be processed."
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": detail})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse

    logger.exception(f"Unhandled exception on {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    """Liveness probe — always OK if the process is up. Not auth-gated so
    an orchestrator (k8s, docker-compose healthcheck) can call it freely."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadinessResponse, tags=["ops"])
def ready() -> ReadinessResponse:
    """Readiness probe — checks the dependencies /ask actually needs.
    Ollama being unreachable is reported but does not fail readiness, since
    the orchestrator degrades to a heuristic/template fallback rather than
    erroring (see minisense.agents.orchestrator)."""
    ollama_ok = is_available()
    try:
        load_responses()
        data_ok, detail = True, None
    except MiniSenseError as exc:
        data_ok, detail = False, str(exc)

    overall = "ok" if data_ok else "degraded"
    return ReadinessResponse(
        status=overall, survey_data_loaded=data_ok, ollama_reachable=ollama_ok, detail=detail
    )


@app.post(
    "/ask",
    response_model=QuestionResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_auth)],
    tags=["survey"],
)
def ask(req: QuestionRequest) -> QuestionResponse:
    question = validate_question(req.question)
    responses = load_responses()
    run = answer_question(question, responses)
    return QuestionResponse(
        answer=run.summary.narrative,
        plan_reasoning=run.plan.reasoning,
        tasks=[t.agent.value for t in run.plan.tasks],
        citations=run.summary.citations,
        trace=[asdict(log) for log in run.trace],
    )
