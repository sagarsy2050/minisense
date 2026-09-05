# syntax=docker/dockerfile:1
#
# Multi-stage build: a builder stage resolves and installs pinned
# dependencies into a venv, and the final runtime image copies only that
# venv plus the application source — no build toolchain, no pip cache, no
# dev/test dependencies ship in the image that actually runs.

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Only the dependency manifest first, so this layer is cached across source
# code changes and only reinstalls when requirements.txt actually changes.
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Run as a non-root user — a container compromise shouldn't get root on the
# host's shared kernel namespace for free.
RUN groupadd --gid 1000 minisense && useradd --uid 1000 --gid minisense --create-home minisense

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MINISENSE_ENV=production

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=minisense:minisense pyproject.toml README.md ./
COPY --chown=minisense:minisense src/ ./src/
COPY --chown=minisense:minisense data/product_faq.md ./data/product_faq.md
COPY --chown=minisense:minisense data/generate_data.py ./data/generate_data.py
COPY --chown=minisense:minisense scripts/ ./scripts/

# storage/ and outputs/ are runtime-generated (FAISS index, eval results) —
# create them here so the non-root user owns them rather than relying on an
# implicit root-owned mkdir at first write.
RUN mkdir -p /app/data /app/storage /app/outputs \
    && chown -R minisense:minisense /app

COPY --chown=minisense:minisense docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app/src

USER minisense

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# The API is the container-native surface (the CLI is for interactive/local
# use). MINISENSE_ENV=production above means Settings requires
# API_AUTH_TOKEN to be set at runtime, or the process refuses to start —
# see minisense/config.py.
CMD ["uvicorn", "minisense.api:app", "--host", "0.0.0.0", "--port", "8000"]
