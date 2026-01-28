# Mamba Server

## Project Overview

FastAPI backend service providing OpenAI-powered chat completions with streaming support, designed for Vercel AI SDK integration. Python 3.12+ application using Pydantic AI's Agent-based architecture with optional Mamba Agents framework integration.

**Architecture Style:** Layered/N-Tier with Streaming-First Design

**Architectural Layers:**
1. API Layer (`api/`) - HTTP concerns, request validation, route registration
2. Core/Business Layer (`core/`) - Domain logic, agent, streaming, tools
3. Infrastructure Layer (`middleware/`, `config.py`) - Cross-cutting concerns

**Key Characteristics:**
- SSE streaming for real-time chat responses
- Discriminated unions for type-safe event handling
- Factory pattern throughout (`create_app()`, `create_agent()`, `create_streaming_response()`)
- Middleware chain order matters: CORS -> RequestID -> Logging -> Auth
- Dependency injection via FastAPI `Depends()` with `Annotated` types
- Stateless design - no database, no session state

**Entry Points:**
- `src/mamba/main.py` - FastAPI app creation and middleware configuration
- `POST /chat` - Primary streaming chat endpoint
- `POST /title/generate` - Title generation endpoint
- CLI: `uvicorn mamba.main:app` or `python -m mamba`

## Code Statistics

| Metric | Value |
|--------|-------|
| Total Lines | ~4,122 lines of Python |
| Python Modules | 32 files |
| Layers | 6 (api, core, models, middleware, utils, config) |
| Handlers | 4 (chat, health, models, title) |
| Middleware | 3 (request_id, logging, auth) |
| Core Modules | 7 (agent, mamba_agent, streaming, messages, tools, tool_schema, title_utils) |
| Models | 5 (events, request, response, health, title) |
| Utilities | 2 (retry, errors) |
| Unit Test Files | 25 |

## Key Components

| Component | File | Criticality | Description |
|-----------|------|-------------|-------------|
| ChatAgent | `core/agent.py` | Critical | Core AI interaction wrapper using pydantic-ai |
| MambaAgentAdapter | `core/mamba_agent.py` | High | Mamba Agents framework integration adapter |
| create_streaming_response() | `core/streaming.py` | Critical | Factory for all SSE responses with timeout handling |
| Settings | `config.py` | Critical | Multi-source configuration management |
| StreamEvent | `models/events.py` | High | Type-safe discriminated union for stream events |
| chat() | `api/handlers/chat.py` | High | Primary streaming endpoint handler |
| convert_messages() | `core/agent.py` | High | Message format adapter (UI to pydantic-ai) |
| @with_retry() | `utils/retry.py` | Medium | Exponential backoff resilience decorator |

### Key Method Line References

**ChatAgent (`core/agent.py`):**
- `convert_messages()` - lines 101-197 - Transforms UIMessage to ModelMessage format
- `stream_text()` - lines 199-228 - Simple text streaming without tools
- `stream_events()` - lines 374-463 - Full event streaming with tool support
- `_register_tools()` - lines 260-372 - Inline tool registration

**MambaAgentAdapter (`core/mamba_agent.py`):**
- `create_research_agent()` - lines 127-176 - Factory for research agent
- `create_code_review_agent()` - lines 193-242 - Factory for code review agent
- `convert_ui_messages_to_dicts()` - lines 312-377 - Message format adapter
- `stream_mamba_agent_events()` - lines 401-473 - Adapts Mamba Agents streaming to StreamEvent format

**Streaming (`core/streaming.py`):**
- `encode_sse_event()` - lines 38-52 - Converts events to SSE format
- `stream_with_timeout()` - lines 91-158 - 5-minute default timeout, disconnect detection
- `create_streaming_response()` - lines 161-189 - Factory for all SSE responses
- `SSEStream` class - lines 192-282 - Builder pattern for event streams

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
│   │   ├── mamba_agent.py     # Mamba Agents framework adapter
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
│   ├── unit/                  # Unit tests (25 test files, mirrors src/)
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

- **Registry Pattern**: Agent registration via `@register_agent` decorator in `mamba_agent.py`

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
| Add Mamba Agent | `core/mamba_agent.py` - use `@register_agent` decorator |

## Configuration

**Priority order (highest to lowest):**
1. Environment variables (`MAMBA_*` prefix)
2. `~/mamba.env` file (user home directory)
3. `config.local.yaml` (project root)
4. `config/config.yaml` (default configuration)
5. Code defaults in `config.py`

**Key settings:**
- `MAMBA_AUTH__MODE`: `none` | `api_key` | `jwt`
- `MAMBA_OPENAI__API_KEY` or `OPENAI_API_KEY`: Required for OpenAI calls
- `MAMBA_OPENAI__BASE_URL` or `OPENAI_API_BASE_URL`: Custom API base URL (default: `https://api.openai.com/v1`)
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
| `/chat` | POST | Streaming chat (SSE response, supports `agent` param for Mamba Agents) |
| `/title/generate` | POST | Generate conversation title |
| `/models` | GET | List available models |
| `/health` | GET | Full health check |
| `/health/live` | GET | Kubernetes liveness probe |
| `/health/ready` | GET | Kubernetes readiness probe |

## Mamba Agents Integration

The server supports routing requests to pre-configured Mamba Agents via the `agent` parameter:

**Available agents:**
- `research` - Information gathering and synthesis with search tools
- `code_review` - Code analysis with complexity metrics tools

**Agent routing:**
```json
{
  "messages": [...],
  "model": "openai/gpt-4o",
  "agent": "research"
}
```

**Behavior:**
- `agent: null` or omitted -> Standard ChatAgent flow (backward compatible)
- `agent: "research"` -> Routes to research agent (ignores `tools` param)
- `agent: "invalid"` -> Streams `ErrorEvent` with available agents list

**Key files:**
- `core/mamba_agent.py` - Agent registry, factories, streaming adapter
- Agent registration uses `@register_agent` decorator pattern

**Note:** Tool implementations (`search_notes`, `analyze_complexity`) currently return placeholder/stub data. These should be replaced with real implementations for production use.

## Tools Available

The ChatAgent (standard flow) supports these UI-generating tools (return args as result for client rendering):
- `generateForm` - Interactive form components (text, select, checkbox, etc.)
- `generateChart` - Data visualizations (line, bar, pie, area)
- `generateCode` - Syntax-highlighted code blocks
- `generateCard` - Card components with media/actions

**Tool flow:**
1. Client sends `tools: ["generateForm", ...]` in request
2. Handler enables tools via `enable_tools=True`
3. Agent registers tools with Pydantic AI
4. LLM decides to call tool -> `ToolCallEvent` emitted
5. Tool executes -> Returns args dict (args = display data)
6. `ToolResultEvent` emitted
7. Client renders tool result in UI

## Module Dependencies

```
main.py (entry point)
├── api/routes.py
│   ├── api/handlers/chat.py -> core/agent.py, core/mamba_agent.py, core/streaming.py
│   ├── api/handlers/health.py -> config.py
│   ├── api/handlers/models.py -> config.py
│   └── api/handlers/title.py -> core/agent.py
├── middleware/
│   ├── auth.py -> config.py
│   ├── logging.py
│   └── request_id.py
└── config.py (settings singleton, LRU cached)

core/agent.py
├── core/messages.py
├── core/tools.py
├── core/tool_schema.py
├── models/events.py
└── models/request.py

core/mamba_agent.py
├── config.py
├── models/events.py
├── models/request.py
├── utils/errors.py
└── mamba_agents (external)
```

**Dependency Health:**
- Circular dependencies: None detected
- Layering violations: None detected
- Coupling concerns: ChatAgent moderately coupled to pydantic-ai library

## Data Flow

```
Client Request
     │
     v
┌────────────────────┐
│ Middleware Chain   │  CORS -> RequestID -> Logging -> Auth
└────────────────────┘
     │
     v
┌────────────────────┐
│ Chat Handler       │  Validates request, extracts model
└────────────────────┘
     │
     v
┌────────────────────┐
│ ChatAgent          │  Converts messages, registers tools
└────────────────────┘
     │
     v
┌────────────────────┐
│ pydantic-ai        │  Streams to OpenAI API
└────────────────────┘
     │
     v
┌────────────────────┐
│ Streaming          │  Encodes SSE, handles timeout
└────────────────────┘
     │
     v
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
- **Tool schema generation**: Pydantic model -> JSON Schema -> OpenAI function format

## External Integrations

| Integration | Type | Location | Notes |
|-------------|------|----------|-------|
| OpenAI API | REST API | `core/agent.py` via pydantic-ai | Critical dependency |
| Mamba Agents | Library | `core/mamba_agent.py` | Optional agent framework, local file path dependency |
| PyJWT | Library | `middleware/auth.py` | Optional, lazy import |

**OpenAI Configuration:**
- Base URL: `settings.openai.base_url` (default: `https://api.openai.com/v1`)
- Timeout: 60 seconds
- Max retries: 3 (exponential backoff)
- Default model: `gpt-4o`

## Strengths

1. **Clean Architecture with Clear Boundaries** - Well-separated layers with minimal cross-cutting
2. **Type Safety Throughout** - Discriminated unions, full type hints on all public APIs
3. **Production-Ready Operations** - K8s manifests, health probes, structured logging
4. **Flexible Authentication** - Three modes with lazy JWT loading for performance
5. **Well-Tested Core Logic** - 25 unit test files mirroring source structure

## Known Gaps

- No CI/CD pipeline configured
- Integration and E2E test directories exist but have limited tests
- No metrics/observability (OpenTelemetry, Prometheus)
- No rate limiting middleware
- Single AI provider (OpenAI only) - no fallback

## Recommendations

### High Priority

1. **Add CI/CD Pipeline**
   - Configure GitHub Actions for automated test, lint, and build
   - Include coverage reporting and PR checks
   - Suggested workflow: lint -> test -> build -> deploy (staging)

2. **Publish mamba-agents to PyPI**
   - Current local file path dependency reduces portability
   - Package and publish to PyPI or private registry
   - Update `pyproject.toml` to use versioned package dependency

3. **Pin pydantic-ai Conservatively**
   - Change from `>=0.0.49` to `>=0.0.49,<0.1.0`
   - 0.x versions may introduce breaking changes
   - Monitor releases and test upgrades explicitly

### Medium Priority

4. **Add OpenTelemetry Integration**
   - Implement distributed tracing for request flows
   - Add metrics for streaming latency, token counts, error rates
   - Export to Prometheus/Grafana or cloud observability platform

5. **Implement Rate Limiting**
   - Add middleware for request rate limiting per client/API key
   - Consider token-based rate limiting for LLM calls
   - Use Redis or in-memory store for distributed deployments

6. **Replace Placeholder Tool Implementations**
   - `search_notes` in mamba_agent.py returns stub data
   - `analyze_complexity` returns mock complexity metrics
   - Implement real functionality or document as examples

## Technical Debt

| Item | Location | Risk |
|------|----------|------|
| pydantic-ai version pinning | `pyproject.toml` | Using `>=0.0.49` for 0.x library risks breaking changes |
| mamba-agents local dependency | `pyproject.toml` | Local file path reduces portability across environments |
| Tool registration | `core/agent.py` | Inline in `_register_tools()` rather than from configuration |
| Duplicate tool definitions | `tools.py`, `agent.py` | Tool definitions partially duplicated |
| Settings cache | `config.py` | LRU cache requires server restart on config changes |
| Placeholder tool implementations | `core/mamba_agent.py` | `search_notes`, `analyze_complexity` return stub data |
