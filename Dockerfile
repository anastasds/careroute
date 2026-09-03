# CareRoute Production Dockerfile
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency manifests
COPY pyproject.toml requirements.txt ./

# Install python dependencies
RUN uv pip install --system -r requirements.txt

# Copy source code and evaluation suite
COPY careroute ./careroute
COPY evals ./evals
COPY tests ./tests
COPY README.md ./

# Expose API port
EXPOSE 8080

# Run FastAPI service
CMD ["uvicorn", "careroute.app:app", "--host", "0.0.0.0", "--port", "8080"]

