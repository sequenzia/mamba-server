# Mamba Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready FastAPI with Pydantic AI backend service that provides OpenAI-powered chat completions with streaming support, designed for seamless integration with the Vercel AI SDK.

## Overview

Mamba Server wraps OpenAI models using Pydantic AI's Agent-based architecture, delivering real-time streaming responses via Server-Sent Events (SSE). Built with a layered architecture and streaming-first design, it provides a robust foundation for AI-powered chat applications.

### Key Features

- **Streaming Chat Completions** - Real-time responses via Server-Sent Events (SSE)
- **Vercel AI SDK Compatible** - Native support for Vercel AI SDK message format
- **Display Tools** - 4 built-in tools: `generateForm`, `generateChart`, `generateCode`, `generateCard`
- **Flexible Authentication** - Support for none, API key, or JWT authentication
- **Kubernetes Ready** - Health checks, liveness/readiness probes, and Helm-ready manifests
- **Resilient** - Exponential backoff retry for OpenAI API calls
- **Multi-source Configuration** - Environment variables and YAML file support

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [UV](https://github.com/astral-sh/uv) package manager (recommended) or pip
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/mamba-server.git
cd mamba-server

# Install dependencies with UV
uv sync

# Or with pip
pip install -e .
```

### Running the Server

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key"

# Start the server
uv run uvicorn mamba.main:app --reload

# Server runs at http://localhost:8000
```

## Configuration

Mamba Server supports multiple configuration sources with the following precedence (highest to lowest):

1. Environment variables with `MAMBA_` prefix
2. `config.local.yaml` (optional, git-ignored)
3. `config.yaml`

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `MAMBA_SERVER__HOST` | Server bind address | `0.0.0.0` |
| `MAMBA_SERVER__PORT` | Server port | `8000` |
| `MAMBA_OPENAI__MODEL` | Default OpenAI model | `gpt-4o-mini` |
| `MAMBA_AUTH__MODE` | Auth mode: `none`, `api_key`, `jwt` | `none` |
| `MAMBA_AUTH__API_KEY` | API key for authentication | - |

Use `__` as the nested delimiter (e.g., `MAMBA_OPENAI__API_KEY`).

### YAML Configuration

Create a `config.local.yaml` for local overrides:

```yaml
server:
  host: "127.0.0.1"
  port: 8000

openai:
  model: "gpt-4o"

auth:
  mode: "api_key"
  api_key: "your-secret-key"
```

## API Documentation

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Streaming chat completions via SSE |
| `/title/generate` | POST | Generate conversation titles |
| `/models` | GET | List available models |
| `/health` | GET | Full health check (dependencies included) |
| `/health/live` | GET | Liveness probe for Kubernetes |
| `/health/ready` | GET | Readiness probe for Kubernetes |

### Chat Completions

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

**Request Body:**

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "model": "gpt-4o-mini"
}
```

**Response:** Server-Sent Events stream with Vercel AI SDK format.

### Interactive Documentation

Once running, access the auto-generated API docs:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Setup

```bash
# Install with dev dependencies
uv sync --all-extras

# Or with pip
pip install -e ".[dev]"
```

### Code Quality

```bash
# Run linter
uv run ruff check src tests

# Run formatter
uv run ruff format src tests

# Auto-fix issues
uv run ruff check --fix src tests
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mamba

# Run specific test file
uv run pytest tests/test_agent.py -v
```

## Deployment

### Docker

```bash
# Build the image
docker build -t mamba-server:latest .

# Run the container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="your-api-key" \
  mamba-server:latest
```

The Dockerfile uses a multi-stage build with Python 3.11-slim and runs as a non-root user (`mamba:1000`).

### Kubernetes

Kubernetes manifests are provided in the `/k8s/` directory:

```bash
# Apply manifests
kubectl apply -f k8s/

# Or use kustomize
kubectl apply -k k8s/
```

Health probes are pre-configured:
- **Liveness:** `/health/live`
- **Readiness:** `/health/ready`

## Project Structure

```
mamba-server/
├── src/mamba/
│   ├── api/                   # HTTP layer
│   │   ├── handlers/          # Endpoint handlers (chat.py, health.py, models.py, title.py)
│   │   ├── deps.py            # FastAPI dependency injection
│   │   └── routes.py          # Route registration
│   ├── core/                  # Business logic
│   │   ├── agent.py           # ChatAgent - Pydantic AI wrapper
│   │   ├── streaming.py       # SSE encoding, timeout handling
│   │   ├── messages.py        # Message format conversion
│   │   ├── tools.py           # Tool definitions (forms, charts, code, cards)
│   │   ├── tool_schema.py     # OpenAI function format conversion
│   │   └── title_utils.py     # Title processing utilities
│   ├── middleware/            # Request processing chain
│   │   ├── auth.py            # Auth modes: none, api_key, jwt
│   │   ├── logging.py         # Structured request/response logging
│   │   └── request_id.py      # X-Request-ID propagation
│   ├── models/                # Pydantic schemas
│   │   ├── events.py          # StreamEvent discriminated union
│   │   ├── request.py         # ChatCompletionRequest, UIMessage
│   │   ├── response.py        # ModelsResponse
│   │   ├── health.py          # HealthResponse, ComponentHealth
│   │   └── title.py           # TitleGenerationRequest/Response
│   ├── utils/                 # Utilities
│   │   ├── errors.py          # ErrorCode enum, error classification
│   │   └── retry.py           # @with_retry decorator (exponential backoff)
│   ├── config.py              # Settings management (multi-source)
│   └── main.py                # FastAPI app factory, middleware setup
├── tests/
│   ├── unit/                  # Unit tests (23 test files)
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
├── k8s/                       # Kubernetes manifests
│   ├── deployment.yaml        # Deployment with health probes
│   ├── service.yaml           # Service definition
│   ├── configmap.yaml         # Configuration
│   ├── secrets.yaml.example   # Secret template
│   ├── pdb.yaml               # Pod disruption budget
│   └── kustomization.yaml     # Kustomize config
├── config/
│   └── config.yaml            # Default configuration
├── Dockerfile                 # Multi-stage production build
└── pyproject.toml             # Project configuration
```

## Tech Stack

| Category | Technologies |
|----------|--------------|
| Language | Python 3.11+ |
| Framework | FastAPI 0.115+, Pydantic 2.10+ |
| AI | Pydantic AI 0.0.30+, OpenAI |
| HTTP | httpx 0.28+, Uvicorn 0.32+ |
| Testing | pytest, pytest-asyncio, respx |
| Linting | Ruff |
| Build | Hatchling, UV |

## Architecture

Mamba Server uses a **Layered/N-Tier architecture** with a **streaming-first design**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Request                           │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                  Middleware Chain                           │
│         CORS → RequestID → Logging → Auth                   │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    API Layer                                │
│              (handlers, routes, deps)                       │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   Core Layer                                │
│         (ChatAgent, streaming, messages, tools)             │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                  External APIs                              │
│                  (OpenAI via pydantic-ai)                   │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Patterns:**
- **Factory Pattern** - `create_app()`, `create_agent()`, `create_streaming_response()` for testability
- **Discriminated Unions** - Type-safe `StreamEvent` and `MessagePart` with Pydantic discriminators
- **Adapter Pattern** - Message format conversion between UI and OpenAI formats
- **Decorator Pattern** - `@with_retry()` for exponential backoff on failures
- **Dependency Injection** - FastAPI `Depends()` with `Annotated` types

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
