FROM python:3.12-slim AS runtime

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev group)
RUN uv sync --frozen --no-dev --no-editable

# Copy application source
COPY src ./src

# Ensure the venv bin is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default command: single ingestion run (suitable for Kubernetes CronJob)
CMD ["python", "-m", "knowledge_injector", "run-once"]
