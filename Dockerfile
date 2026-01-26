# syntax=docker/dockerfile:1

# Build stage
FROM python:3.11-slim as builder

# Install uv for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml .
COPY README.md .

# Create virtual environment and install dependencies
ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python -e .

# Runtime stage
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd --gid 1000 mamba && \
    useradd --uid 1000 --gid mamba --shell /bin/bash --create-home mamba

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=mamba:mamba src/ src/
COPY --chown=mamba:mamba config/ config/

# Switch to non-root user
USER mamba

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
ENTRYPOINT ["python", "-m", "uvicorn", "mamba.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
