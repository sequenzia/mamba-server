# Codebase Analysis Report

> **Generated:** 2026-01-27
> **Scope:** /Users/sequenzia/dev/repos/mamba-server
> **Branch:** add-mamba-agents

---

## Executive Summary

Mamba-server is a well-architected FastAPI backend service that provides OpenAI-powered chat completions with Server-Sent Events (SSE) streaming, designed specifically for integration with the Vercel AI SDK. The codebase follows a clean Layered/N-Tier architecture with streaming-first design principles, demonstrating strong separation of concerns across API, Core/Business, and Infrastructure layers.

The system operates as an intelligent proxy layer between client applications and OpenAI's API, adding authentication, message format conversion, tool orchestration, and optional routing to specialized AI agents. A notable design decision is the completely stateless architecture - no conversation history or session state is maintained, with clients responsible for managing context.

Overall, this is a production-ready codebase with excellent type safety, comprehensive unit tests, and Kubernetes-ready deployment manifests. The main areas for improvement are the absence of a CI/CD pipeline, limited integration/E2E testing, and lack of observability instrumentation.

---

## Project Overview

| Attribute | Value |
|-----------|-------|
| **Project Name** | mamba-server |
| **Primary Language(s)** | Python 3.12+ |
| **Framework(s)** | FastAPI, Pydantic AI |
| **Repository Type** | Single Application |
| **Lines of Code** | ~3,275 lines of Python |
| **Python Modules** | 31 files |
| **Unit Test Files** | 25 files |

### Purpose

Mamba-server serves as a backend proxy for AI-powered chat applications, providing a standardized interface compatible with the Vercel AI SDK. It handles the complexity of streaming responses, tool orchestration, and multi-format message conversion while exposing a clean REST API with SSE streaming support.

The server supports two operational modes: a standard ChatAgent flow using Pydantic AI for direct OpenAI communication, and an optional MambaAgent flow that routes requests to pre-configured specialized agents (such as research or code review assistants).

---

## Architecture

### Architecture Style

**Primary Pattern:** Layered/N-Tier Architecture with Streaming-First Design

The codebase exhibits clear horizontal layering with well-defined responsibilities and strict dependency flow. Dependencies move strictly downward: API handlers depend on core modules, which depend on models and utilities. No circular dependencies exist in the codebase.

This architectural choice enables strong testability (each layer can be tested in isolation), clear code organization (developers know where to find specific functionality), and maintainability (changes to one layer have minimal impact on others).

The streaming-first design manifests in the pervasive use of async generators, SSE encoding utilities, and timeout handling throughout the request lifecycle.

**Secondary Patterns:**
- Factory Pattern for testability and composition
- Adapter Pattern for multi-protocol message conversion
- Registry Pattern for extensible agent management
- Chain of Responsibility for middleware

### System Diagram

```
                              ┌─────────────────────────────────────────┐
                              │            mamba-server                  │
                              ├─────────────────────────────────────────┤
                              │                                         │
┌──────────┐                  │  ┌───────────────────────────────────┐  │
│  Client  │ ─── Request ───▶ │  │        Middleware Chain           │  │
│   App    │                  │  │  CORS → RequestID → Logging → Auth│  │
└──────────┘                  │  └───────────────┬───────────────────┘  │
     ▲                        │                  │                      │
     │                        │                  ▼                      │
     │                        │  ┌───────────────────────────────────┐  │
     │                        │  │          API Layer                │  │
     │                        │  │  chat.py │ health.py │ models.py  │  │
     │                        │  └───────────────┬───────────────────┘  │
     │                        │                  │                      │
     │                        │         ┌────────┴────────┐            │
     │                        │         ▼                 ▼            │
     │                        │  ┌────────────┐    ┌────────────┐      │
     │                        │  │ ChatAgent  │    │MambaAgent  │      │
     │                        │  │(Pydantic AI│    │ Adapter    │      │
     │                        │  └─────┬──────┘    └─────┬──────┘      │
     │                        │        │                 │             │
     │                        │        └────────┬────────┘             │
     │                        │                 ▼                      │
     │                        │  ┌───────────────────────────────────┐  │
     │                        │  │        Streaming Layer            │  │
     │                        │  │   SSE Encoding │ Timeout Handling │  │
     │                        │  └───────────────┬───────────────────┘  │
     │                        │                  │                      │
     │                        └──────────────────┼──────────────────────┘
     │                                           │
     │                                           ▼
     │                               ┌───────────────────┐
     └────────── SSE Stream ──────── │    OpenAI API     │
                                     └───────────────────┘
```

### Architectural Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **API Layer** | `src/mamba/api/` | HTTP concerns, request validation, route registration |
| **Core/Business Layer** | `src/mamba/core/` | Domain logic, agent orchestration, streaming, tools |
| **Infrastructure Layer** | `src/mamba/middleware/`, `config.py` | Cross-cutting concerns (auth, logging, config) |
| **Models Layer** | `src/mamba/models/` | Pydantic schemas for data validation |
| **Utilities Layer** | `src/mamba/utils/` | Shared utilities (retry, errors) |

### Key Modules

| Module | Purpose | Location |
|--------|---------|----------|
| ChatAgent | Core AI wrapper using Pydantic AI | `core/agent.py` |
| MambaAgentAdapter | Agent registry and routing | `core/mamba_agent.py` |
| Streaming | SSE encoding and timeout handling | `core/streaming.py` |
| Settings | Multi-source configuration | `config.py` |
| StreamEvent | Discriminated union for events | `models/events.py` |
| ChatHandler | Primary endpoint logic | `api/handlers/chat.py` |
| AuthMiddleware | Authentication modes | `middleware/auth.py` |

#### ChatAgent

**Purpose:** Primary wrapper around Pydantic AI for all OpenAI interactions

**Key Components:**
- `convert_messages()` - Transforms UIMessage format to Pydantic AI ModelMessage format
- `stream_text()` - Yields text deltas for simple streaming use cases
- `stream_events()` - Full event streaming with tool call handling
- `_register_tools()` - Registers UI-generating tools (form, chart, code, card)

**Relationships:** Used by `chat.py` and `title.py` handlers. Depends on `messages.py`, `tools.py`, and `models/events.py`.

#### MambaAgentAdapter

**Purpose:** Registry-based agent management for specialized AI agents

**Key Components:**
- `_AGENT_REGISTRY` - Dictionary storing registered agents
- `@register_agent` - Decorator for adding new agents
- `create_research_agent()` - Factory for research/search agent
- `create_code_review_agent()` - Factory for code analysis agent
- `stream_mamba_agent_events()` - Adapts Mamba Agents streaming to StreamEvent format

**Relationships:** Used by `chat.py` handler when `agent` parameter is specified. Depends on external `mamba-agents` library.

#### Streaming

**Purpose:** All SSE response generation and timeout handling

**Key Components:**
- `create_streaming_response()` - Factory for all SSE responses
- `stream_with_timeout()` - 5-minute default timeout with client disconnect detection
- `encode_sse_event()` - Converts events to SSE wire format
- `SSEStream` - Builder class for programmatic event construction

**Relationships:** Used by all streaming endpoints. Critical path for all real-time responses.

---

## Technology Stack

### Languages & Frameworks

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Primary language |
| FastAPI | >=0.115.0 | Async HTTP framework |
| Pydantic | >=2.10.0 | Data validation and serialization |
| pydantic-ai | >=0.0.49 | OpenAI agent wrapper |
| uvicorn | >=0.32.0 | ASGI server |

### Dependencies

#### Production Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework with automatic OpenAPI docs |
| `pydantic` | Request/response model validation |
| `pydantic-settings` | Multi-source configuration management |
| `pydantic-ai` | Agent-based AI interaction wrapper |
| `httpx` | Async HTTP client for external calls |
| `uvicorn` | Production ASGI server |
| `mamba-agents` | Specialized agent framework (local) |
| `PyJWT` | JWT token validation (optional, lazy-loaded) |

#### Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing framework |
| `pytest-asyncio` | Async test support |
| `pytest-cov` | Coverage reporting |
| `respx` | HTTP mocking for httpx |
| `ruff` | Linting and formatting |
| `hatch` | Build backend |

### Build & Tooling

| Tool | Purpose |
|------|---------|
| Hatchling | Python package build backend |
| UV | Fast package manager |
| Docker | Multi-stage containerization |
| Kubernetes | Orchestration (manifests provided) |
| Ruff | Linting (line length: 100, isort sections) |

---

## Code Organization

### Directory Structure

```
mamba-server/
├── src/mamba/                  # Main application package
│   ├── api/                    # HTTP layer
│   │   ├── handlers/           # Endpoint implementations
│   │   │   ├── chat.py         # Streaming chat completions
│   │   │   ├── health.py       # Health check endpoints
│   │   │   ├── models.py       # Model listing
│   │   │   └── title.py        # Title generation
│   │   ├── deps.py             # FastAPI dependencies
│   │   └── routes.py           # Route registration
│   ├── core/                   # Business logic
│   │   ├── agent.py            # ChatAgent - Pydantic AI wrapper
│   │   ├── mamba_agent.py      # Mamba Agents adapter
│   │   ├── streaming.py        # SSE encoding, timeouts
│   │   ├── messages.py         # Message format conversion
│   │   ├── tools.py            # Tool definitions
│   │   ├── tool_schema.py      # OpenAI function format
│   │   └── title_utils.py      # Title processing
│   ├── middleware/             # Request processing chain
│   │   ├── auth.py             # Auth modes (none/api_key/jwt)
│   │   ├── logging.py          # Structured logging
│   │   └── request_id.py       # X-Request-ID propagation
│   ├── models/                 # Pydantic schemas
│   │   ├── events.py           # StreamEvent union
│   │   ├── request.py          # ChatCompletionRequest
│   │   ├── response.py         # ModelsResponse
│   │   ├── health.py           # HealthResponse
│   │   └── title.py            # TitleRequest/Response
│   ├── utils/                  # Shared utilities
│   │   ├── errors.py           # Error classification
│   │   └── retry.py            # Exponential backoff
│   ├── config.py               # Settings management
│   └── main.py                 # App factory, middleware setup
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests (25 files)
│   ├── integration/            # Integration tests (empty)
│   ├── e2e/                    # E2E tests (empty)
│   └── conftest.py             # Shared fixtures
├── k8s/                        # Kubernetes manifests
│   ├── deployment.yaml         # Deployment with probes
│   ├── service.yaml            # Service definition
│   ├── configmap.yaml          # Configuration
│   ├── secrets.yaml.example    # Secret template
│   ├── pdb.yaml                # Pod disruption budget
│   └── kustomization.yaml      # Kustomize config
├── config/
│   └── config.yaml             # Default configuration
├── Dockerfile                  # Multi-stage build
└── pyproject.toml              # Dependencies, build config
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `chat_handler.py`, `tool_schema.py` |
| Classes | PascalCase | `ChatAgent`, `StreamEvent` |
| Functions | snake_case | `create_streaming_response` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_STREAM_TIMEOUT` |
| Type Aliases | PascalCase | `StreamEvent`, `SettingsDep` |
| Private Methods | _leading_underscore | `_register_tools`, `_validate_api_key` |

### Code Patterns

The codebase consistently uses these patterns:

1. **Factory Pattern**
   - Where: `main.py`, `core/agent.py`, `core/streaming.py`
   - How: `create_app()`, `create_agent()`, `create_streaming_response()` enable testability and composition

2. **Discriminated Unions**
   - Where: `models/events.py`, `models/request.py`
   - How: `StreamEvent` uses `type` field with literal values (text-delta, tool-call, tool-result, finish, error)

3. **Adapter Pattern**
   - Where: `core/agent.py`, `core/mamba_agent.py`
   - How: `convert_messages()` transforms between UI and Pydantic AI formats

4. **Registry Pattern**
   - Where: `core/mamba_agent.py`
   - How: `_AGENT_REGISTRY` with `@register_agent` decorator for extensibility

5. **Dependency Injection**
   - Where: `api/deps.py`, all handlers
   - How: `Annotated[Type, Depends(provider)]` pattern throughout

---

## Entry Points

| Entry Point | Type | Location | Purpose |
|-------------|------|----------|---------|
| `/chat` | HTTP POST | `api/handlers/chat.py` | Primary streaming chat endpoint |
| `/title/generate` | HTTP POST | `api/handlers/title.py` | Conversation title generation |
| `/models` | HTTP GET | `api/handlers/models.py` | List available models |
| `/health` | HTTP GET | `api/handlers/health.py` | Full health check |
| `/health/live` | HTTP GET | `api/handlers/health.py` | Kubernetes liveness probe |
| `/health/ready` | HTTP GET | `api/handlers/health.py` | Kubernetes readiness probe |

### Primary Entry Point

The main entry point for users is `POST /chat`, which accepts a JSON body with messages, model selection, optional tools, and an optional `agent` parameter. The endpoint returns an SSE stream of events including text deltas, tool calls, tool results, and a finish event.

```bash
# CLI entry point
uvicorn mamba.main:app --host 0.0.0.0 --port 8000

# Or via module
python -m mamba
```

---

## Data Flow

```
┌─────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌─────────┐
│  Input  │───▶│ Middleware │───▶│  Handler   │───▶│   Agent    │───▶│ OpenAI  │
│ Request │    │   Chain    │    │ Validation │    │ Processing │    │   API   │
└─────────┘    └────────────┘    └────────────┘    └────────────┘    └─────────┘
                                                          │
                                                          ▼
┌─────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   SSE   │◀───│   Stream   │◀───│   Event    │◀───│  Response  │
│Response │    │  Encoding  │    │ Generation │    │  Parsing   │
└─────────┘    └────────────┘    └────────────┘    └────────────┘
```

### Request Lifecycle

1. **Entry:** Request arrives at FastAPI, passes through ASGI middleware chain
2. **Middleware:** CORS headers added, Request ID generated, request logged, authentication validated
3. **Validation:** Pydantic validates request body against `ChatCompletionRequest` model
4. **Routing:** Handler checks for `agent` parameter to determine flow (ChatAgent vs MambaAgent)
5. **Processing:** Messages converted to appropriate format, tools registered if requested
6. **Streaming:** OpenAI API called with streaming enabled, response chunks yielded
7. **Encoding:** Each chunk converted to appropriate `StreamEvent` type
8. **Response:** Events SSE-encoded (`data: {...}\n\n`) and streamed to client

---

## External Integrations

| Integration | Type | Purpose | Configuration |
|-------------|------|---------|---------------|
| OpenAI API | REST API | LLM inference | `config.py` - base_url, timeout, retries |
| Mamba Agents | Library | Agent routing | Local file dependency in pyproject.toml |
| PyJWT | Library | JWT validation | Lazy import when auth.mode=jwt |

### OpenAI API

The primary external integration is with OpenAI's API via the pydantic-ai library.

**Configuration:**
- Base URL: Configurable via `MAMBA_OPENAI__BASE_URL` (default: `https://api.openai.com/v1`)
- Timeout: 60 seconds
- Max Retries: 3 with exponential backoff
- Default Model: `gpt-4o`

**Error Handling:**
- Retryable: 429 (rate limit), 500, 502, 503, 504, connection errors, timeouts
- Non-retryable: 400, 401, 403, 404, 422

### Mamba Agents

Optional integration for specialized agent routing.

**Available Agents:**
- `research` - Information gathering with search tools
- `code_review` - Code analysis with complexity metrics

**Routing:** Specified via `agent` parameter in request body.

---

## Testing

### Test Framework(s)

- **Unit Testing:** pytest with pytest-asyncio (auto mode)
- **Mocking:** respx for HTTP mocking, unittest.mock for general mocking
- **Coverage:** pytest-cov

### Test Organization

```
tests/
├── unit/                       # 25 test files
│   ├── api/                    # Handler tests
│   │   └── handlers/           # Individual handler tests
│   ├── core/                   # Agent, streaming, tools tests
│   ├── middleware/             # Auth, logging, request_id tests
│   ├── models/                 # Schema validation tests
│   └── utils/                  # Retry, error tests
├── integration/                # Integration tests (empty)
├── e2e/                        # End-to-end tests (empty)
└── conftest.py                 # Shared fixtures
```

### Test Commands

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/core/test_agent.py -v

# Run with coverage
pytest --cov=mamba

# Run with verbose output
pytest tests/unit/ -v --tb=short
```

### Coverage Areas

| Area | Coverage | Notes |
|------|----------|-------|
| API Handlers | Good | All handlers have corresponding tests |
| Core Logic | Good | Agent, streaming, tools well-tested |
| Middleware | Good | Auth, logging, request_id covered |
| Models | Good | Schema validation tests present |
| Integration | Missing | Directory exists but empty |
| E2E | Missing | Directory exists but empty |

---

## Configuration

### Configuration Sources (Priority Order)

1. Environment variables (`MAMBA_*` prefix)
2. `~/mamba.env` file (user home directory)
3. `config.local.yaml` (project root)
4. `config/config.yaml` (default configuration)
5. Code defaults in `config.py`

### Key Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Auth Mode | `MAMBA_AUTH__MODE` | `none` | Authentication mode (none/api_key/jwt) |
| OpenAI Key | `MAMBA_OPENAI__API_KEY` | - | OpenAI API key (required) |
| Base URL | `MAMBA_OPENAI__BASE_URL` | OpenAI default | Custom API endpoint |
| Default Model | `MAMBA_OPENAI__DEFAULT_MODEL` | `gpt-4o` | Default model for requests |
| Log Level | `MAMBA_LOGGING__LEVEL` | `INFO` | Logging verbosity |

### Settings Classes

```
Settings (main container)
├── ServerSettings      # host, port, workers, timeout
├── AuthSettings        # mode, api_keys, jwt_config
├── OpenAISettings      # api_key, base_url, timeout, retries
├── LoggingSettings     # level, format, include_body
├── HealthSettings      # openai_check_enabled, interval
└── TitleSettings       # max_length, timeout, model
```

---

## Recommendations

### Strengths

These aspects of the codebase are well-executed:

1. **Clean Architecture with Strong Boundaries**

   The layered architecture with clear separation of concerns makes the codebase easy to navigate and maintain. Each layer has a single responsibility, and dependencies flow strictly downward. This enables independent testing and reduces the impact of changes.

2. **Type Safety Throughout**

   The consistent use of discriminated unions (`StreamEvent`, `MessagePart`), full Pydantic models, and type hints on all public functions catches errors at development time and provides excellent IDE support. The type system serves as living documentation.

3. **Production-Ready Operations**

   The included Kubernetes manifests with health probes, multi-stage Docker build with non-root user, and structured JSON logging demonstrate production readiness. The deployment configuration follows best practices including pod disruption budgets.

4. **Flexible Authentication System**

   Three authentication modes (none, api_key, jwt) with lazy JWT loading provides flexibility for different deployment scenarios. The bypass for health endpoints follows Kubernetes patterns.

5. **Comprehensive Unit Test Coverage**

   25 unit test files mirroring the source structure provide good coverage of core functionality. The test organization makes it easy to find and maintain tests.

6. **Robust Streaming Infrastructure**

   The streaming layer with timeout handling (5-minute default), client disconnect detection, and proper SSE encoding ensures reliable real-time communication.

### Areas for Improvement

These areas could benefit from attention:

1. **No CI/CD Pipeline**
   - **Issue:** No GitHub Actions or similar CI/CD configuration exists
   - **Impact:** Manual testing and deployment processes, risk of untested code reaching production
   - **Suggestion:** Add `.github/workflows/ci.yml` with test, lint, and Docker build jobs; enable branch protection requiring passing checks

2. **Integration and E2E Tests Missing**
   - **Issue:** Test directories exist but contain only `__init__.py` files
   - **Impact:** No automated verification of component interactions or user workflows
   - **Suggestion:** Add integration tests for the chat completion flow and E2E tests for common user scenarios

3. **No Observability Stack**
   - **Issue:** No OpenTelemetry, Prometheus metrics, or distributed tracing
   - **Impact:** Limited visibility into production behavior and performance
   - **Suggestion:** Integrate OpenTelemetry for tracing, add `/metrics` endpoint for Prometheus

4. **No Rate Limiting**
   - **Issue:** No protection against request flooding or abuse
   - **Impact:** Vulnerability to DoS attacks, potential for runaway costs
   - **Suggestion:** Add rate limiting middleware with token bucket algorithm, return proper 429 responses

5. **Single Provider Lock-in**
   - **Issue:** Only OpenAI is supported with no fallback mechanism
   - **Impact:** Single point of failure, no cost optimization options
   - **Suggestion:** Abstract provider interface to enable multi-provider support (Anthropic, Google, etc.)

### Technical Debt

| Item | Location | Risk Level | Recommendation |
|------|----------|------------|----------------|
| pydantic-ai version pinning | `pyproject.toml` | Medium | Change `>=0.0.49` to `>=0.0.49,<0.1.0` to avoid breaking changes |
| mamba-agents local path | `pyproject.toml` | Medium | Publish to PyPI or private registry for reproducible builds |
| Inline tool registration | `core/agent.py` | Low | Move tool definitions to configuration for flexibility |
| LRU cache for settings | `config.py` | Low | Document requirement to restart server after config changes |
| Placeholder tool implementations | `core/mamba_agent.py` | Medium | Implement real `search_notes` and `analyze_complexity` tools |

### Suggested Next Steps

For developers new to this codebase:

1. **Start with `config.py` and `main.py`** to understand configuration and app initialization
2. **Explore `core/agent.py`** to see how ChatAgent wraps Pydantic AI and handles message conversion
3. **Trace a request through `api/handlers/chat.py`** to understand the full streaming flow
4. **Run the unit tests** (`pytest tests/unit/ -v`) to see expected behaviors
5. **Try the `/chat` endpoint** with a simple curl command to see SSE streaming in action

---

## Appendix: Module Dependency Graph

```
main.py (entry point)
├── api/routes.py
│   ├── api/handlers/chat.py
│   │   ├── core/agent.py
│   │   ├── core/mamba_agent.py
│   │   └── core/streaming.py
│   ├── api/handlers/health.py
│   │   └── config.py
│   ├── api/handlers/models.py
│   │   └── config.py
│   └── api/handlers/title.py
│       └── core/agent.py
├── middleware/
│   ├── auth.py
│   │   └── config.py
│   ├── logging.py
│   └── request_id.py
└── config.py

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
- Circular dependencies: None
- Layering violations: None
- Coupling concerns: ChatAgent moderately coupled to pydantic-ai library

---

## Appendix: API Quick Reference

### POST /chat

Primary streaming chat endpoint.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "model": "gpt-4o",
  "tools": ["generateForm", "generateChart"],
  "agent": null
}
```

**Response:** SSE stream with events:
- `text-delta` - Incremental text content
- `tool-call` - Tool invocation with arguments
- `tool-result` - Tool execution result
- `finish` - Stream completion marker
- `error` - Error information

### POST /title/generate

Generate a conversation title.

**Request:**
```json
{
  "messages": [...]
}
```

**Response:**
```json
{
  "title": "Discussion about Python async patterns"
}
```

### GET /models

List available models.

**Response:**
```json
{
  "models": [
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"}
  ]
}
```

### GET /health

Full health check with component status.

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "openai": {"status": "healthy", "latency_ms": 150}
  }
}
```

---

*Report generated by Codebase Analysis Workflow on 2026-01-27*
