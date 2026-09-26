FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast, reliable, reproducible dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install production dependencies only using frozen lockfile
RUN uv sync --frozen --no-dev --no-install-project

# Production runtime image
FROM python:3.12-slim

WORKDIR /app

ENV PORT=8080 \
    HOST=0.0.0.0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy virtualenv and runtime assets
COPY --from=builder /app/.venv /app/.venv
COPY server.py ./
COPY dashboard/ ./dashboard/
COPY records/ ./records/
COPY src/ ./src/

# Security: Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["python", "server.py"]
