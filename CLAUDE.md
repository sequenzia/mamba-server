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
- Stateless design - no database, no session state

**Entry Points:**
- `src/mamba/main.py` - FastAPI app creation and middleware configuration
- `POST /chat/completions` - Primary streaming chat endpoint
- `POST /title/generate` - Title generation endpoint
- CLI: `uvicorn mamba.main:app` or `python -m mamba`

## Repository Structure

```
mamba-server/
├── src/mamba/
│   ├── api/                   # HTTP layer
│   │   ├── handlers/          # Endpoint handlers
│   │   │   ├── chat.py        # Streaming chat completions
│   │   │   ├── health.py      # Health check endpoints
│   │   │   ├── models.py      # Model listing
│   │   │   └── title.py       # Title generation
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
│   │   ├── request.py         # ChatCompletionRequest, UIMessage, MessagePart
│   │   ├── response.py        # ModelsResponse, ModelInfo
│   │   ├── health.py          # HealthResponse, ComponentHealth
│   │   └── title.py           # TitleGenerationRequest/Response
│   ├── utils/                 # Utilities
│   │   ├── errors.py          # ErrorCode enum, error classification
│   │   └── retry.py           # @with_retry decorator (exponential backoff)
│   ├── config.py              # Settings management (multi-source)
│   └── main.py                # App factory, middleware setup, exception handlers
├── tests/
│   ├── unit/                  # Unit tests (23 test files, mirrors src/)
│   ├── integration/           # Integration tests
│   ├── e2e/                   # End-to-end tests
│   └── conftest.py            # Shared fixtures
├── k8s/                       # Kubernetes manifests
│   ├── deployment.yaml        # Deployment with health probes
│   ├── service.yaml           # Service definition
│   ├── configmap.yaml         # Non-secret configuration
│   ├── secrets.yaml.example   # Secret template
│   ├── pdb.yaml               # Pod disruption budget
│   └── kustomization.yaml     # Kustomize configuration
├── config/
│   └── config.yaml            # Default configuration
├── Dockerfile                 # Multi-stage production build
└── pyproject.toml             # Dependencies, Ruff config
```

## Key Patterns

### Design Patterns

- **Factory Pattern**: All major components created via factory functions for testability
  - `create_app(settings)` in `main.py`
  - `create_agent(settings, model_name, enable_tools)` in `core/agent.py`
  - `create_streaming_response(event_generator, request)` in `core/streaming.py`

- **Discriminated Unions**: `StreamEvent` and `MessagePart` use literal type discriminators
  - `StreamEvent` uses `type` field with values: `text-delta`, `tool-call`, `tool-result`, `finish`, `error`
  - `MessagePart` uses `type` field with values: `text`, `tool-invocation`

- **Adapter Pattern**: Message conversion between UI format and Pydantic AI format in `agent.py`
  - `ChatAgent.convert_messages()` transforms UIMessage to ModelMessage

- **Decorator Pattern**: `@with_retry()` provides exponential backoff on failures
  - Retryable: 429, 500, 502, 503, 504, connection errors, timeouts
  - Non-retryable: 400, 401, 403, 404, 422

- **Dependency Injection**: Use `Annotated[Type, Depends(provider)]` for dependencies
  - `SettingsDep = Annotated[Settings, Depends(get_settings_dependency)]`

- **Builder Pattern**: `SSEStream` class for constructing event streams

- **Strategy Pattern**: Authentication modes (none, api_key, jwt) in `middleware/auth.py`

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `chat_handler.py` |
| Classes | PascalCase | `ChatAgent` |
| Functions | snake_case | `create_streaming_response` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_MODEL` |
| Type aliases | PascalCase | `StreamEvent` |
| Private methods | _leading_underscore | `_validate_api_key` |

### Code Style

- Line length: 100 characters (Ruff enforced)
- Imports: isort with sections (stdlib, third-party, local)
- Type hints: Required on all public functions
- Docstrings: Google style for public APIs

## Important Files

| Task | Files to Check |
|------|----------------|
| Add new endpoint | `api/handlers/`, `api/routes.py` |
| Modify chat logic | `core/agent.py`, `core/streaming.py` |
| Add new tool | `core/tools.py`, `core/tool_schema.py`, `models/events.py` |
| Change auth | `middleware/auth.py`, `config.py` |
| Add configuration | `config.py`, `config/config.yaml` |
| Fix streaming | `core/streaming.py`, `api/handlers/chat.py` |
| Message conversion | `core/messages.py`, `core/agent.py` |
| Error handling | `utils/errors.py`, exception handlers in `main.py` |

## Configuration

**Priority order (highest to lowest):**
1. Environment variables (`MAMBA_*` prefix)
2. `.env` file
3. `config.local.yaml`
4. `config/config.yaml`
5. Code defaults in `config.py`

**Key settings:**
- `MAMBA_AUTH__MODE`: `none` | `api_key` | `jwt`
- `MAMBA_OPENAI__API_KEY` or `OPENAI_API_KEY`: Required for OpenAI calls
- `MAMBA_OPENAI__DEFAULT_MODEL`: Default model (e.g., `gpt-4o`)
- `MAMBA_LOGGING__LEVEL`: Logging verbosity

**Nested delimiter:** Use `__` for nested settings (e.g., `MAMBA_OPENAI__TIMEOUT_SECONDS`)

**Settings classes in config.py:**
- `Settings` - Main container
- `ServerSettings` - Host, port, workers, timeout
- `AuthSettings` - Mode, api_keys, jwt config
- `OpenAISettings` - API key, base URL, timeout, retries, default model
- `LoggingSettings` - Level, format, include body
- `HealthSettings` - OpenAI check enabled, interval, timeout
- `TitleSettings` - Max length, timeout, model

## Testing

**Framework:** pytest with pytest-asyncio (`asyncio_mode = "auto"`)

**Patterns:**
- Use `@pytest.mark.asyncio` for async tests (auto mode)
- Mock HTTP with `respx` library
- Override settings via `app.dependency_overrides`
- Fixtures in `tests/conftest.py`

**Run tests:**
```bash
pytest tests/unit/ -v
pytest tests/unit/core/test_agent.py -v  # Specific file
pytest --cov=mamba  # With coverage
```

**Test organization:**
- `tests/unit/api/` - Handler tests
- `tests/unit/core/` - Agent, streaming, tools tests
- `tests/unit/middleware/` - Auth, logging, request_id tests
- `tests/unit/models/` - Schema validation tests
- `tests/unit/utils/` - Retry, error tests

## API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/completions` | POST | Streaming chat (SSE response) |
| `/title/generate` | POST | Generate conversation title |
| `/models` | GET | List available models |
| `/health` | GET | Full health check |
| `/health/live` | GET | Kubernetes liveness probe |
| `/health/ready` | GET | Kubernetes readiness probe |

## Tools Available

The agent supports these UI-generating tools (return args as result for client rendering):
- `generateForm` - Interactive form components (text, select, checkbox, etc.)
- `generateChart` - Data visualizations (line, bar, pie, area)
- `generateCode` - Syntax-highlighted code blocks
- `generateCard` - Card components with media/actions

**Tool flow:**
1. Client sends `tools: ["generateForm", ...]` in request
2. Handler enables tools via `enable_tools=True`
3. Agent registers tools with Pydantic AI
4. LLM decides to call tool → `ToolCallEvent` emitted
5. Tool executes → Returns args dict (args = display data)
6. `ToolResultEvent` emitted
7. Client renders tool result in UI

## Module Dependencies

```
main.py (entry point)
├── api/routes.py
│   ├── api/handlers/chat.py → core/agent.py, core/streaming.py
│   ├── api/handlers/health.py → config.py
│   ├── api/handlers/models.py → config.py
│   └── api/handlers/title.py → core/agent.py
├── middleware/
│   ├── auth.py → config.py
│   ├── logging.py
│   └── request_id.py
└── config.py (settings singleton, LRU cached)

core/agent.py
├── core/messages.py
├── core/tools.py
├── core/tool_schema.py
├── models/events.py
└── models/request.py
```

## Data Flow

```
Client Request
     │
     ▼
┌────────────────────┐
│ Middleware Chain   │  CORS → RequestID → Logging → Auth
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Chat Handler       │  Validates request, extracts model
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ ChatAgent          │  Converts messages, registers tools
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ pydantic-ai        │  Streams to OpenAI API
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Streaming          │  Encodes SSE, handles timeout
└────────────────────┘
     │
     ▼
SSE Response (text-delta, tool-call, tool-result, finish)
```

## Development Notes

- **Settings are LRU cached** - restart server after config changes
- **Middleware order in `main.py` is significant** - do not reorder (last added = first executed)
- **StreamEvent uses `type` as discriminator field** - add new event types with unique `type` value
- **Message conversion happens in `ChatAgent.convert_messages()`** - UI format to pydantic-ai format
- **All streaming responses must use `create_streaming_response()` factory** - ensures timeout handling
- **Health endpoints bypass authentication** - see `auth.py` line 49
- **JWT library is lazy-loaded** - only imported when jwt auth mode is used
- **Tool schema generation**: Pydantic model → JSON Schema → OpenAI function format

## External Integrations

| Integration | Type | Location | Notes |
|-------------|------|----------|-------|
| OpenAI API | REST API | `core/agent.py` via pydantic-ai | Critical dependency |
| PyJWT | Library | `middleware/auth.py` | Optional, lazy import |

**OpenAI Configuration:**
- Base URL: `settings.openai.base_url` (default: `https://api.openai.com/v1`)
- Timeout: 60 seconds
- Max retries: 3 (exponential backoff)
- Default model: `gpt-4o`

## Known Gaps

- No CI/CD pipeline configured
- Integration and E2E test directories exist but have limited tests
- No metrics/observability (OpenTelemetry, Prometheus)
- No rate limiting middleware
- Single AI provider (OpenAI only) - no fallback
- LRU cache for settings requires restart on config changes
