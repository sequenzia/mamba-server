# Mamba Server

## Project Overview

FastAPI backend service providing OpenAI-powered chat completions with streaming support, designed for Vercel AI SDK integration. Python 3.11+ application using Pydantic AI's Agent-based architecture.

**Architecture Style:** Layered/N-Tier with Streaming-First Design

**Key Characteristics:**
- SSE streaming for real-time chat responses
- Discriminated unions for type-safe event handling
- Factory pattern throughout (`create_app()`, `create_agent()`, `create_streaming_response()`)
- Middleware chain order matters: CORS → RequestID → Logging → Auth
- Dependency injection via FastAPI `Depends()` with `Annotated` types

**Entry Points:**
- `src/mamba/main.py` - FastAPI app creation and middleware configuration
- `POST /chat/completions` - Primary streaming chat endpoint
- CLI: `uvicorn mamba.main:app` or `python -m mamba`

## Repository Structure

```
mamba-server/
├── src/mamba/
│   ├── api/                 # HTTP layer
│   │   ├── handlers/        # Endpoint handlers (chat.py, models.py, health.py)
│   │   ├── dependencies.py  # FastAPI dependency injection
│   │   └── router.py        # Route registration
│   ├── core/                # Business logic
│   │   ├── agent.py         # ChatAgent - Pydantic AI wrapper
│   │   ├── streaming.py     # SSE encoding, timeout handling
│   │   └── tools.py         # Tool definitions (forms, charts, code, cards)
│   ├── middleware/          # Request processing chain
│   │   ├── auth.py          # Auth modes: none, api_key, jwt
│   │   ├── logging.py       # Request/response logging
│   │   └── request_id.py    # X-Request-ID propagation
│   ├── models/              # Pydantic schemas
│   │   ├── chat.py          # ChatRequest, ChatResponse
│   │   ├── events.py        # StreamEvent discriminated union
│   │   └── messages.py      # MessagePart union types
│   ├── config.py            # Settings with YAML + env vars
│   └── main.py              # App factory, exception handlers
├── tests/
│   ├── unit/                # Mirrors src/ structure
│   ├── integration/         # (empty - needs implementation)
│   └── conftest.py          # Shared fixtures
├── config.yaml              # Default configuration
└── pyproject.toml           # Dependencies, Ruff config
```

## Key Patterns

- **Factory Pattern**: All major components created via factory functions for testability
- **Dependency Injection**: Use `Annotated[Type, Depends(provider)]` for dependencies
- **Discriminated Unions**: `StreamEvent` and `MessagePart` use literal type discriminators
- **Adapter Pattern**: Message conversion between UI format and Pydantic AI format in `agent.py`
- **Decorator Pattern**: `@with_retry()` provides exponential backoff on failures

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `chat_handler.py` |
| Classes | PascalCase | `ChatAgent` |
| Functions | snake_case | `create_streaming_response` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_MODEL` |
| Type aliases | PascalCase | `StreamEvent` |

### Code Style

- Line length: 100 characters (Ruff enforced)
- Imports: isort with sections (stdlib, third-party, local)
- Type hints: Required on all public functions
- Docstrings: Google style for public APIs

## Important Files

| Task | Files to Check |
|------|----------------|
| Add new endpoint | `api/handlers/`, `api/router.py` |
| Modify chat logic | `core/agent.py`, `core/streaming.py` |
| Add new tool | `core/tools.py`, `models/events.py` |
| Change auth | `middleware/auth.py`, `config.py` |
| Add configuration | `config.py`, `config.yaml` |
| Fix streaming | `core/streaming.py`, `api/handlers/chat.py` |

## Configuration

**Priority order (highest to lowest):**
1. Environment variables (`MAMBA_*` prefix)
2. `.env` file
3. `config.local.yaml`
4. `config.yaml`
5. Code defaults in `config.py`

**Key settings:**
- `MAMBA_AUTH_MODE`: `none` | `api_key` | `jwt`
- `MAMBA_OPENAI_API_KEY`: Required for OpenAI calls
- `MAMBA_MODEL`: Default model (e.g., `gpt-4o`)
- `MAMBA_LOG_LEVEL`: Logging verbosity

## Testing

**Framework:** pytest with pytest-asyncio

**Patterns:**
- Use `@pytest.mark.asyncio` for async tests
- Mock HTTP with `respx` library
- Override settings via `app.dependency_overrides`
- Fixtures in `tests/conftest.py`

**Run tests:**
```bash
pytest tests/unit/ -v
pytest tests/unit/core/test_agent.py -v  # Specific file
```

## API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/completions` | POST | Streaming chat (SSE response) |
| `/models` | GET | List available models |
| `/health` | GET | Full health check |
| `/health/live` | GET | Kubernetes liveness probe |
| `/health/ready` | GET | Kubernetes readiness probe |

## Tools Available

The agent supports these UI-generating tools:
- `generateForm` - Interactive form components
- `generateChart` - Data visualizations (line, bar, pie, area)
- `generateCode` - Syntax-highlighted code blocks
- `generateCard` - Card components with media/actions

## Development Notes

- Settings are LRU cached - restart server after config changes
- Middleware order in `main.py` is significant - do not reorder
- StreamEvent uses `event_type` as discriminator field
- Message conversion happens in `ChatAgent._convert_messages()`
- All streaming responses must use `create_streaming_response()` factory

## Known Gaps

- No CI/CD pipeline configured
- Integration and E2E test directories are empty
- No metrics/observability (OpenTelemetry, Prometheus)
- No rate limiting middleware
- Single AI provider (OpenAI only) - no fallback
