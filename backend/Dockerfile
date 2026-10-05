# =====================================================================
# Noesis Backend — Production Dockerfile
# =====================================================================
# Multi-stage build keeps final image tiny (~250 MB) by discarding
# build toolchains after compilation.
#
# Build:  docker build -t noesis-backend -f Dockerfile .
# Run:    docker run --rm -p 8000:8000 --env-file .env noesis-backend
# =====================================================================

# --- Stage 1: Builder ------------------------------------------------
FROM python:3.14-slim-bookworm AS builder

WORKDIR /build

# System deps: uv + gcc (for any native wheels).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gcc python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/root/.local/bin:$PATH

# Install uv (https://github.com/astral-sh/uv)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml ./

# Install runtime deps into a venv we can COPY to the final stage.
RUN uv venv --python 3.12 /opt/venv \
    && uv pip install --python /opt/venv/bin/python \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.30.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.5.0" \
        "langchain>=0.3.0" \
        "langchain-core>=0.3.0" \
        "langchain-openai>=0.2.0" \
        "langchain-anthropic>=0.2.0" \
        "langchain-google-genai>=2.0.0" \
        "langchain-community>=0.3.0" \
        "langgraph>=0.2.0" \
        "openai>=1.50.0" \
        "anthropic>=0.37.0" \
        "google-generativeai>=0.8.0" \
        "httpx>=0.27.0" \
        "sqlalchemy>=2.0.35" \
        "aiosqlite>=0.20.0" \
        "qdrant-client>=1.11.0" \
        "redis>=5.0.0" \
        "python-dotenv>=1.0.0" \
        "structlog>=24.4.0" \
        "pypdf>=5.0.0" \
        "python-docx>=1.1.0" \
        "markdownify>=0.13.0" \
        "beautifulsoup4>=4.12.0" \
        "tenacity>=9.0.0" \
        "python-jose[cryptography]>=3.3.0" \
        "passlib[bcrypt]>=1.7.4" \
        "slowapi>=0.1.9" \
        "orjson>=3.10.0"

# --- Stage 2: Final runtime image -----------------------------------
FROM python:3.14-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="Noesis Backend" \
      org.opencontainers.image.description="An Operating System for Autonomous Intelligence — Backend API" \
      org.opencontainers.image.source="https://github.com/noesis/noesis"

# Runtime deps: SQLite shared lib + CA certs (for HTTPS calls to providers).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsqlite3-0 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH=/opt/venv/bin:$PATH \
    APP_ENV=production

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy backend source tree
COPY noesis/ ./noesis/

# SQLite DB + uploaded documents live on a volume so they survive restarts.
RUN mkdir -p /app/data /app/uploads
VOLUME ["/app/data", "/app/uploads"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/livez || exit 1

# Drop from root → nobody for least-privilege runtime.
USER 65534:65534

CMD ["uvicorn", "noesis.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--workers", "2", \
     "--log-level", "info"]
