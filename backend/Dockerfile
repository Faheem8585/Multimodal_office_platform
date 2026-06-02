# syntax=docker/dockerfile:1.7
# Multi-stage build for the FastAPI backend (API + Celery worker share this image).

# --- Builder: install deps into an isolated venv ---
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app

# Install CPU-only torch first to avoid pulling multi-GB CUDA wheels, then the
# project with all runtime extras (ml, documents, storage, worker, llm, ...).
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2" \
    && pip install ".[full]"

# --- Runtime: slim image with only OS deps needed at run time ---
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Tesseract for OCR; poppler for PDF rasterisation; libgomp for torch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root.
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY pyproject.toml ./
COPY scripts ./scripts
RUN chmod +x scripts/entrypoint.sh && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Default command runs the API; the worker overrides this (see compose/helm).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
