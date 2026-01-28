# Product Requirements Document: mamba-server

**Version:** 1.0.0
**Author:** Stephen Sequenzia
**Date:** 2026-01-26
**Status:** Draft

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals and Success Metrics](#3-goals-and-success-metrics)
4. [User Stories](#4-user-stories)
5. [Functional Requirements](#5-functional-requirements)
6. [API Specification](#6-api-specification)
7. [Data Models](#7-data-models)
8. [Streaming Protocol Specification](#8-streaming-protocol-specification)
9. [Authentication Specification](#9-authentication-specification)
10. [Error Handling Specification](#10-error-handling-specification)
11. [Configuration Schema](#11-configuration-schema)
12. [Non-Functional Requirements](#12-non-functional-requirements)
13. [Architecture Overview](#13-architecture-overview)
14. [Implementation Phases](#14-implementation-phases)
15. [Testing Strategy](#15-testing-strategy)
16. [Deployment Guide](#16-deployment-guide)
17. [Open Questions and Future Considerations](#17-open-questions-and-future-considerations)

---

## 1. Executive Summary

mamba-server is a Python-based FastAPI backend service designed to replace the mock chat service currently used by the ai-chatbot frontend application. It provides a production-ready streaming chat completion API that integrates with OpenAI models through Pydantic AI's Agent-based architecture.

The service implements the Vercel AI SDK streaming protocol, enabling seamless integration with the existing React frontend while providing real AI-powered responses, tool call support, and enterprise-grade observability.

### Key Capabilities

- **Streaming Chat Completions**: SSE-based streaming responses compatible with Vercel AI SDK
- **Tool Pass-Through**: Forward tool definitions to OpenAI and return tool calls to the client
- **Flexible Authentication**: Configurable auth modes for different deployment environments
- **Production Ready**: Health checks, structured logging, and Kubernetes-native deployment

---

## 2. Problem Statement

### Current State

The ai-chatbot frontend currently operates with a `MockChatService` that simulates AI responses through pattern matching and pre-defined templates. While useful for development and demonstration, this approach:

- **Lacks Real AI Intelligence**: Responses are pattern-matched, not contextually generated
- **Limited Tool Support**: Tool calls are triggered by keyword detection, not semantic understanding
- **No Production Path**: Mock service cannot scale or integrate with real AI providers
- **Development/Production Gap**: Significant behavioral differences between mock and real AI

### Desired State

A production backend service that:

- Provides genuine AI-powered responses through OpenAI integration
- Maintains complete streaming protocol compatibility with the existing frontend
- Supports the same tool definitions with proper AI-driven tool selection
- Enables gradual migration from mock to real service with minimal frontend changes

### Impact

Without mamba-server, the ai-chatbot project remains a demonstration only. With mamba-server, it becomes a production-ready AI chat application suitable for real-world deployment.

---

## 3. Goals and Success Metrics

### Primary Goals

| Goal | Description | Priority |
|------|-------------|----------|
| Protocol Compatibility | 100% compatibility with existing ai-chatbot frontend | P0 |
| Streaming Performance | Sub-second time-to-first-token for user-perceived responsiveness | P0 |
| Production Readiness | Deployable to Kubernetes with proper health checks and observability | P0 |
| Tool Support | Pass-through tool definitions to OpenAI with proper tool call handling | P1 |

### Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Time to First Token (TTFT) | < 1 second (p95) | Application metrics |
| Request Success Rate | > 99.5% | Health check monitoring |
| Protocol Compliance | 100% event compatibility | Integration test suite |
| Error Recovery | < 3 retries for transient failures | Retry metrics |

### Non-Goals (Out of Scope)

- Multi-model provider support (Anthropic, Google, etc.) - Future consideration
- Conversation persistence/history storage - Handled by frontend
- User management and accounts - Handled by separate service
- Custom model fine-tuning - Not in initial scope
- Rate limiting - Handled by infrastructure layer

---

## 4. User Stories

### US-001: Basic Chat Interaction

**As a** frontend application
**I want to** send chat messages and receive streaming AI responses
**So that** users experience real-time, intelligent conversation

**Acceptance Criteria:**
- Messages are sent via POST /chat
- Response streams as SSE events
- Text appears progressively in the UI
- Stream terminates with finish event

### US-002: Tool-Enhanced Responses

**As a** frontend application
**I want to** receive tool calls when AI determines they're appropriate
**So that** users can interact with forms, charts, code blocks, and cards

**Acceptance Criteria:**
- Tool definitions are forwarded to OpenAI
- AI autonomously decides when to use tools
- Tool call events include toolCallId, toolName, and args
- Tool result events are properly formatted

### US-003: Health Monitoring

**As a** Kubernetes cluster
**I want to** query service health status
**So that** I can manage pod lifecycle and traffic routing

**Acceptance Criteria:**
- GET /health returns 200 when service is healthy
- Response includes readiness status
- Liveness and readiness probes differentiated
- Unhealthy dependencies reflected in status

### US-004: Model Discovery

**As a** frontend application
**I want to** retrieve available models
**So that** users can select their preferred model

**Acceptance Criteria:**
- GET /models returns list of available models
- Each model includes id, name, and provider
- List reflects actually configured/available models

### US-005: Error Recovery

**As a** frontend application
**I want to** receive graceful error responses
**So that** users see meaningful feedback instead of broken streams

**Acceptance Criteria:**
- Transient errors trigger automatic retry
- Permanent errors return structured error event
- Stream always terminates properly (finish or error)
- Error messages are user-appropriate

### US-006: Local Development

**As a** developer
**I want to** run the service locally without authentication
**So that** I can develop and test quickly

**Acceptance Criteria:**
- Service starts with uvicorn in development mode
- No authentication required in local mode
- Hot reload on code changes
- Debug logging enabled

### US-007: Secure Deployment

**As an** operations team
**I want to** deploy with proper authentication
**So that** only authorized clients can access the API

**Acceptance Criteria:**
- API key authentication supported
- JWT token validation supported
- Auth mode configurable per environment
- Invalid credentials return 401

---

## 5. Functional Requirements

### FR-001: Chat Completions Endpoint

**Description:** Accept chat messages and return streaming AI responses

**Requirements:**
- Accept JSON payload with messages array and model identifier
- Parse messages in UIMessage format (id, role, parts)
- Forward to OpenAI via Pydantic AI Agent
- Stream response as Server-Sent Events
- Support request cancellation via connection close

### FR-002: Health Check Endpoint

**Description:** Provide health status for orchestration systems

**Requirements:**
- Return 200 OK when service is operational
- Include component health status (OpenAI connectivity)
- Support both liveness and readiness semantics
- Response time < 100ms

### FR-003: Models Endpoint

**Description:** List available AI models

**Requirements:**
- Return array of model objects
- Include model id, display name, and provider
- Reflect actually available models based on configuration
- Cache model list for performance

### FR-004: Tool Pass-Through

**Description:** Forward tool definitions to OpenAI and relay tool calls

**Supported Tools:**
- `generateForm`: Interactive form generation
- `generateChart`: Data visualization charts
- `generateCode`: Syntax-highlighted code blocks
- `generateCard`: Rich content cards

**Requirements:**
- Convert frontend tool schemas to OpenAI function format
- Include tool definitions in OpenAI request
- Parse tool call responses from OpenAI
- Format as tool-call SSE events
- Handle tool results (pass-through from AI)

### FR-005: Authentication Modes

**Description:** Support configurable authentication per environment

**Modes:**
- `none`: No authentication (local development)
- `api_key`: X-API-Key header or Authorization: Bearer
- `jwt`: JWT token validation

**Requirements:**
- Auth mode set via configuration
- Middleware applies appropriate validation
- Failed auth returns 401 Unauthorized
- Successful auth proceeds to handler

### FR-006: Retry Logic

**Description:** Automatically retry transient failures

**Requirements:**
- Identify retryable errors (network, rate limit, 5xx)
- Exponential backoff: 1s, 2s, 4s
- Maximum 3 retry attempts
- Non-retryable errors fail immediately
- Log retry attempts

### FR-007: Structured Logging

**Description:** JSON-formatted logs with request tracking

**Requirements:**
- All logs in JSON format
- Include request_id in all log entries
- Log levels: DEBUG, INFO, WARNING, ERROR
- Configurable log level per environment
- Include timestamp, level, message, and context

---

## 6. API Specification

### 6.1 POST /chat

Stream chat completions from the AI model.

#### Request

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>  (if auth enabled)
X-API-Key: <key>               (alternative auth)
X-Request-ID: <uuid>           (optional, generated if missing)
```

**Body:**
```json
{
  "messages": [
    {
      "id": "msg_abc123",
      "role": "user",
      "parts": [
        {
          "type": "text",
          "text": "Create a contact form"
        }
      ]
    }
  ],
  "model": "openai/gpt-4o"
}
```

**Message Schema:**
```typescript
interface ChatRequest {
  messages: UIMessage[];
  model: string;
  tools?: ToolDefinition[];  // Optional, uses defaults if omitted
}

interface UIMessage {
  id: string;
  role: "user" | "assistant" | "system";
  parts: MessagePart[];
}

type MessagePart =
  | { type: "text"; text: string }
  | { type: "tool-invocation"; toolCallId: string; toolName: string; args: object; result?: object };
```

#### Response

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Request-ID: <uuid>
```

**Body:** Server-Sent Events stream (see Section 8)

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success, streaming response |
| 400 | Invalid request format |
| 401 | Authentication required/failed |
| 422 | Validation error (invalid model, etc.) |
| 500 | Internal server error |
| 503 | Service unavailable (OpenAI down) |

---

### 6.2 GET /health

Health check endpoint for Kubernetes probes.

#### Request

**Headers:** None required

#### Response

**Success (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-26T10:30:00Z",
  "checks": {
    "openai": {
      "status": "healthy",
      "latency_ms": 45
    }
  }
}
```

**Degraded (200 with warning):**
```json
{
  "status": "degraded",
  "version": "1.0.0",
  "timestamp": "2026-01-26T10:30:00Z",
  "checks": {
    "openai": {
      "status": "degraded",
      "latency_ms": 2500,
      "message": "High latency detected"
    }
  }
}
```

**Unhealthy (503):**
```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "timestamp": "2026-01-26T10:30:00Z",
  "checks": {
    "openai": {
      "status": "unhealthy",
      "error": "Connection refused"
    }
  }
}
```

---

### 6.3 GET /models

List available AI models.

#### Request

**Headers:**
```
Authorization: Bearer <token>  (if auth enabled)
```

#### Response

**Success (200):**
```json
{
  "models": [
    {
      "id": "openai/gpt-4o",
      "name": "GPT-4o",
      "provider": "openai",
      "description": "Most capable GPT-4 model",
      "context_window": 128000,
      "supports_tools": true
    },
    {
      "id": "openai/gpt-4o-mini",
      "name": "GPT-4o Mini",
      "provider": "openai",
      "description": "Fast and cost-effective",
      "context_window": 128000,
      "supports_tools": true
    }
  ]
}
```

---

## 7. Data Models

### 7.1 Pydantic Models

```python
from pydantic import BaseModel, Field
from typing import Literal, Union, Optional
from datetime import datetime
from enum import Enum

# === Request Models ===

class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ToolInvocationPart(BaseModel):
    type: Literal["tool-invocation"] = "tool-invocation"
    toolCallId: str
    toolName: str
    args: dict
    result: Optional[dict] = None

MessagePart = Union[TextPart, ToolInvocationPart]

class UIMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    parts: list[MessagePart]

class ChatCompletionRequest(BaseModel):
    messages: list[UIMessage]
    model: str = Field(..., pattern=r"^openai/[\w-]+$")

# === Response Models ===

class TextDeltaEvent(BaseModel):
    type: Literal["text-delta"] = "text-delta"
    textDelta: str

class ToolCallEvent(BaseModel):
    type: Literal["tool-call"] = "tool-call"
    toolCallId: str
    toolName: str
    args: dict

class ToolResultEvent(BaseModel):
    type: Literal["tool-result"] = "tool-result"
    toolCallId: str
    result: dict

class FinishEvent(BaseModel):
    type: Literal["finish"] = "finish"

class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    error: str

StreamEvent = Union[
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
    FinishEvent,
    ErrorEvent
]

# === Health Models ===

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth(BaseModel):
    status: HealthStatus
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    message: Optional[str] = None

class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    timestamp: datetime
    checks: dict[str, ComponentHealth]

# === Models Response ===

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    description: Optional[str] = None
    context_window: Optional[int] = None
    supports_tools: bool = True

class ModelsResponse(BaseModel):
    models: list[ModelInfo]
```

### 7.2 Tool Schemas

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

# === Form Tool ===

class FormFieldOption(BaseModel):
    label: str
    value: str

class FormField(BaseModel):
    id: str
    type: Literal[
        "text", "textarea", "select", "checkbox",
        "radio", "date", "slider", "file", "number", "email"
    ]
    label: str
    placeholder: Optional[str] = None
    required: Optional[bool] = None
    defaultValue: Optional[str | int | bool] = None
    options: Optional[list[FormFieldOption]] = None
    min: Optional[int] = None
    max: Optional[int] = None
    step: Optional[int] = None

class GenerateFormArgs(BaseModel):
    type: Literal["form"] = "form"
    title: str
    description: Optional[str] = None
    fields: list[FormField]
    submitLabel: Optional[str] = None

# === Chart Tool ===

class ChartDataPoint(BaseModel):
    label: str
    value: float

class GenerateChartArgs(BaseModel):
    type: Literal["chart"] = "chart"
    chartType: Literal["line", "bar", "pie", "area"]
    title: str
    description: Optional[str] = None
    data: list[ChartDataPoint]

# === Code Tool ===

class GenerateCodeArgs(BaseModel):
    type: Literal["code"] = "code"
    language: str
    filename: Optional[str] = None
    code: str
    editable: Optional[bool] = None
    showLineNumbers: Optional[bool] = None

# === Card Tool ===

class CardMedia(BaseModel):
    type: Literal["image", "video"]
    url: str
    alt: Optional[str] = None

class CardAction(BaseModel):
    label: str
    action: str
    variant: Optional[Literal["default", "secondary", "destructive", "outline"]] = None

class GenerateCardArgs(BaseModel):
    type: Literal["card"] = "card"
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    media: Optional[CardMedia] = None
    actions: Optional[list[CardAction]] = None
```

---

## 8. Streaming Protocol Specification

### 8.1 Overview

mamba-server implements the Vercel AI SDK streaming protocol using Server-Sent Events (SSE). This protocol enables real-time streaming of AI responses with support for text, tool calls, and error handling.

### 8.2 SSE Format

Each event follows the SSE specification:
```
data: <json-payload>\n\n
```

### 8.3 Event Types

#### text-delta

Incremental text content from the AI response.

```json
{"type": "text-delta", "textDelta": "Hello"}
{"type": "text-delta", "textDelta": ", how"}
{"type": "text-delta", "textDelta": " can I help?"}
```

**Behavior:**
- Emitted for each token/chunk from OpenAI
- Client concatenates textDelta values
- May include whitespace and newlines

#### tool-call

AI has decided to invoke a tool.

```json
{
  "type": "tool-call",
  "toolCallId": "tc_abc123xyz",
  "toolName": "generateForm",
  "args": {
    "type": "form",
    "title": "Contact Us",
    "fields": [
      {"id": "name", "type": "text", "label": "Your Name", "required": true},
      {"id": "email", "type": "email", "label": "Email Address", "required": true}
    ]
  }
}
```

**Behavior:**
- toolCallId is unique identifier for this invocation
- toolName matches one of the defined tools
- args contains the tool-specific parameters
- Client renders appropriate UI component

#### tool-result

Result of a tool execution (pass-through from AI).

```json
{
  "type": "tool-result",
  "toolCallId": "tc_abc123xyz",
  "result": {
    "type": "form",
    "title": "Contact Us",
    "fields": [...]
  }
}
```

**Behavior:**
- toolCallId matches the corresponding tool-call
- result echoes the tool args (for display tools)
- Client may use result for confirmation/logging

#### finish

Stream completed successfully.

```json
{"type": "finish"}
```

**Behavior:**
- Always sent as final event on success
- Client should close connection and finalize UI
- No more events will follow

#### error

An error occurred during processing.

```json
{
  "type": "error",
  "error": "Model rate limit exceeded. Please try again in a moment."
}
```

**Behavior:**
- Sent instead of finish on error
- error contains user-appropriate message
- Client should display error and allow retry

### 8.4 Event Sequences

**Text-only response:**
```
data: {"type":"text-delta","textDelta":"I"}

data: {"type":"text-delta","textDelta":"'ll help"}

data: {"type":"text-delta","textDelta":" you."}

data: {"type":"finish"}

```

**Response with tool call:**
```
data: {"type":"text-delta","textDelta":"I'll create a form for you.\n\n"}

data: {"type":"tool-call","toolCallId":"tc_123","toolName":"generateForm","args":{...}}

data: {"type":"tool-result","toolCallId":"tc_123","result":{...}}

data: {"type":"finish"}

```

**Error response:**
```
data: {"type":"text-delta","textDelta":"Let me"}

data: {"type":"error","error":"Service temporarily unavailable"}

```

### 8.5 Connection Handling

**Client Disconnect:**
- Server detects closed connection
- Cancels ongoing OpenAI request
- Cleans up resources
- No response needed

**Server Timeout:**
- 5-minute maximum stream duration
- Sends finish event before closing
- Client should handle reconnection if needed

---

## 9. Authentication Specification

### 9.1 Authentication Modes

#### Mode: none

Used for local development.

**Configuration:**
```yaml
auth:
  mode: none
```

**Behavior:**
- All requests accepted without credentials
- No authentication headers required
- Warning logged on startup

#### Mode: api_key

Simple API key authentication.

**Configuration:**
```yaml
auth:
  mode: api_key
  api_keys:
    - key: "mamba_sk_abc123"
      name: "frontend-prod"
    - key: "mamba_sk_xyz789"
      name: "frontend-staging"
```

**Request Headers (either):**
```
X-API-Key: mamba_sk_abc123
```
```
Authorization: Bearer mamba_sk_abc123
```

**Behavior:**
- Key validated against configured list
- Invalid key returns 401
- Key name logged for audit

#### Mode: jwt

JWT token validation.

**Configuration:**
```yaml
auth:
  mode: jwt
  jwt:
    secret: "${JWT_SECRET}"
    algorithm: HS256
    issuer: "auth.example.com"
    audience: "mamba-server"
```

**Request Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Token Claims:**
```json
{
  "sub": "user_123",
  "iss": "auth.example.com",
  "aud": "mamba-server",
  "exp": 1706270400,
  "iat": 1706266800
}
```

**Behavior:**
- Signature validated with secret
- Claims validated (issuer, audience, expiration)
- Invalid token returns 401
- User ID from sub claim logged

### 9.2 Error Responses

**Missing credentials:**
```json
{
  "detail": "Authentication required",
  "code": "AUTH_REQUIRED"
}
```

**Invalid credentials:**
```json
{
  "detail": "Invalid authentication credentials",
  "code": "AUTH_INVALID"
}
```

**Expired token:**
```json
{
  "detail": "Token has expired",
  "code": "AUTH_EXPIRED"
}
```

---

## 10. Error Handling Specification

### 10.1 Error Categories

| Category | Retryable | Examples |
|----------|-----------|----------|
| Client Error | No | Invalid JSON, missing fields, bad model |
| Auth Error | No | Invalid key, expired token |
| Rate Limit | Yes | OpenAI 429 response |
| Network Error | Yes | Connection timeout, DNS failure |
| Server Error | Yes | OpenAI 500, internal exception |
| Configuration | No | Missing API key, invalid config |

### 10.2 Retry Strategy

**Exponential Backoff:**
```python
delays = [1.0, 2.0, 4.0]  # seconds
max_retries = 3

for attempt, delay in enumerate(delays):
    try:
        response = await call_openai()
        return response
    except RetryableError:
        if attempt < max_retries - 1:
            await asyncio.sleep(delay)
            continue
        raise
```

**Retry Conditions:**
- HTTP 429 (Rate Limited)
- HTTP 500, 502, 503, 504
- Connection timeout
- Connection reset

**No Retry:**
- HTTP 400 (Bad Request)
- HTTP 401, 403 (Auth errors)
- HTTP 404 (Not Found)
- Validation errors

### 10.3 Fallback Responses

For certain error types, provide graceful degradation:

**Rate Limit:**
```json
{
  "type": "error",
  "error": "The service is experiencing high demand. Please try again in a moment."
}
```

**Model Unavailable:**
```json
{
  "type": "error",
  "error": "The requested model is temporarily unavailable. Please try a different model."
}
```

**Internal Error:**
```json
{
  "type": "error",
  "error": "An unexpected error occurred. Our team has been notified."
}
```

### 10.4 Error Logging

All errors logged with context:
```json
{
  "timestamp": "2026-01-26T10:30:00Z",
  "level": "ERROR",
  "message": "OpenAI request failed",
  "request_id": "req_abc123",
  "error_type": "RateLimitError",
  "error_message": "Rate limit exceeded",
  "retry_attempt": 2,
  "model": "gpt-4o",
  "user_id": "user_123"
}
```

---

## 11. Configuration Schema

### 11.1 Configuration File (config.yaml)

```yaml
# Server configuration
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  timeout_seconds: 300
  cors:
    allowed_origins:
      - "http://localhost:5173"
      - "https://chat.example.com"
    allowed_methods:
      - "GET"
      - "POST"
      - "OPTIONS"
    allowed_headers:
      - "Content-Type"
      - "Authorization"
      - "X-API-Key"
      - "X-Request-ID"

# Authentication
auth:
  mode: "api_key"  # none | api_key | jwt
  api_keys:
    - key: "${API_KEY_1}"
      name: "frontend"
  jwt:
    secret: "${JWT_SECRET}"
    algorithm: "HS256"
    issuer: "auth.example.com"
    audience: "mamba-server"

# OpenAI configuration
openai:
  api_key: "${OPENAI_API_KEY}"
  organization: "${OPENAI_ORG_ID}"
  base_url: "https://api.openai.com/v1"
  timeout_seconds: 60
  max_retries: 3
  default_model: "gpt-4o"

# Available models
models:
  - id: "openai/gpt-4o"
    name: "GPT-4o"
    provider: "openai"
    openai_model: "gpt-4o"
    description: "Most capable GPT-4 model"
    context_window: 128000
  - id: "openai/gpt-4o-mini"
    name: "GPT-4o Mini"
    provider: "openai"
    openai_model: "gpt-4o-mini"
    description: "Fast and cost-effective"
    context_window: 128000

# Logging
logging:
  level: "INFO"  # DEBUG | INFO | WARNING | ERROR
  format: "json"  # json | text
  include_request_body: false
  include_response_body: false

# Health checks
health:
  openai_check_enabled: true
  check_interval_seconds: 30
  timeout_seconds: 5
```

### 11.2 Environment Variable Overrides

All configuration values can be overridden via environment variables:

```bash
# Server
MAMBA_SERVER_HOST=0.0.0.0
MAMBA_SERVER_PORT=8000
MAMBA_SERVER_WORKERS=4

# Auth
MAMBA_AUTH_MODE=api_key
MAMBA_API_KEY_1=mamba_sk_xxx

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_ORG_ID=org-xxx

# Logging
MAMBA_LOG_LEVEL=DEBUG
```

### 11.3 Pydantic Settings Model

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal

class ServerSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    timeout_seconds: int = 300

class AuthSettings(BaseSettings):
    mode: Literal["none", "api_key", "jwt"] = "none"
    api_keys: list[dict] = []
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

class OpenAISettings(BaseSettings):
    api_key: str
    organization: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60
    max_retries: int = 3
    default_model: str = "gpt-4o"

class LoggingSettings(BaseSettings):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "text"] = "json"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MAMBA_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8"
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    openai: OpenAISettings
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
```

---

## 12. Non-Functional Requirements

### 12.1 Performance

| Metric | Requirement | Notes |
|--------|-------------|-------|
| Time to First Token | < 1 second (p95) | From request receipt to first SSE event |
| Request Throughput | 100 concurrent streams | Per server instance |
| Memory Usage | < 512MB baseline | Plus ~1MB per active stream |
| CPU Usage | < 50% at 50 concurrent | On 2-core container |

### 12.2 Reliability

| Metric | Requirement |
|--------|-------------|
| Availability | 99.9% uptime |
| Error Rate | < 0.5% of requests |
| Recovery Time | < 30 seconds after restart |
| Graceful Shutdown | Complete active streams within 30s |

### 12.3 Security

| Requirement | Implementation |
|-------------|----------------|
| Transport Security | HTTPS required in production |
| Credential Storage | Environment variables, never in code |
| Input Validation | Pydantic models for all inputs |
| Output Sanitization | No sensitive data in error messages |
| Dependency Security | Regular vulnerability scanning |
| Audit Logging | Authentication events logged |

### 12.4 Observability

| Requirement | Implementation |
|-------------|----------------|
| Structured Logging | JSON format with request_id |
| Request Tracing | X-Request-ID propagation |
| Health Endpoints | /health for K8s probes |
| Error Tracking | Structured error logs with context |

### 12.5 Scalability

| Aspect | Approach |
|--------|----------|
| Horizontal Scaling | Stateless design, multiple replicas |
| Connection Handling | Async I/O throughout |
| Resource Limits | Configurable per-request timeouts |

---

## 13. Architecture Overview

### 13.1 System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ai-chatbot Frontend                          │
│                    (React + Vercel AI SDK)                          │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTPS
                              │ SSE Streaming
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          mamba-server                                │
│                     (FastAPI + Pydantic AI)                         │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Routing    │  │   Auth       │  │   Logging    │              │
│  │   Layer      │  │   Middleware │  │   Middleware │              │
│  └──────┬───────┘  └──────────────┘  └──────────────┘              │
│         │                                                            │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Request    │  │   Agent      │  │   SSE        │              │
│  │   Handler    │──▶   Service    │──▶   Encoder    │              │
│  └──────────────┘  └──────┬───────┘  └──────────────┘              │
│                           │                                          │
└───────────────────────────┼──────────────────────────────────────────┘
                            │ HTTPS
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OpenAI API                                   │
│                    (gpt-4o, gpt-4o-mini)                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 13.2 Component Architecture

```
mamba-server/
├── src/
│   └── mamba/
│       ├── __init__.py
│       ├── main.py              # FastAPI application entry
│       ├── config.py            # Pydantic Settings
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py        # Route definitions
│       │   ├── deps.py          # Dependency injection
│       │   └── handlers/
│       │       ├── __init__.py
│       │       ├── chat.py      # POST /chat
│       │       ├── health.py    # GET /health
│       │       └── models.py    # GET /models
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py         # Pydantic AI Agent wrapper
│       │   ├── streaming.py     # SSE encoding
│       │   └── tools.py         # Tool definitions
│       │
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── auth.py          # Authentication
│       │   ├── logging.py       # Request logging
│       │   └── request_id.py    # X-Request-ID handling
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── request.py       # Request Pydantic models
│       │   ├── response.py      # Response Pydantic models
│       │   └── events.py        # SSE event models
│       │
│       └── utils/
│           ├── __init__.py
│           ├── retry.py         # Retry logic
│           └── errors.py        # Error utilities
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── config/
│   ├── config.yaml
│   └── config.local.yaml
│
├── Dockerfile
├── docker-compose.yaml
├── pyproject.toml
└── README.md
```

### 13.3 Request Flow

```
1. Request Received
   └── FastAPI receives POST /chat

2. Middleware Chain
   ├── Request ID middleware assigns/extracts X-Request-ID
   ├── Logging middleware logs request start
   └── Auth middleware validates credentials

3. Request Handling
   ├── Pydantic validates request body
   ├── Model ID mapped to OpenAI model name
   └── Messages transformed to OpenAI format

4. Agent Execution
   ├── Pydantic AI Agent initialized with tools
   ├── Streaming request sent to OpenAI
   └── Async generator yields chunks

5. Response Streaming
   ├── Chunks transformed to SSE events
   ├── Events encoded and sent to client
   └── Finish event signals completion

6. Cleanup
   ├── Logging middleware logs request end
   └── Connection closed
```

---

## 14. Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal:** Basic project structure and health endpoint

**Deliverables:**
- [ ] Project scaffolding with pyproject.toml
- [ ] FastAPI application setup
- [ ] Configuration management (Pydantic Settings)
- [ ] GET /health endpoint
- [ ] Structured logging setup
- [ ] Request ID middleware
- [ ] Unit test infrastructure

**Exit Criteria:**
- Service starts and responds to /health
- Configuration loads from file and environment
- Logs output in JSON format

### Phase 2: Core Streaming (Week 2)

**Goal:** Basic chat completions without tools

**Deliverables:**
- [ ] POST /chat endpoint
- [ ] Pydantic AI Agent integration
- [ ] OpenAI streaming connection
- [ ] SSE response encoding
- [ ] text-delta and finish events
- [ ] Error event handling
- [ ] Integration tests with OpenAI

**Exit Criteria:**
- Text-only chat works end-to-end
- Streams properly to client
- Errors handled gracefully

### Phase 3: Tool Support (Week 3)

**Goal:** Full tool pass-through implementation

**Deliverables:**
- [ ] Tool definitions (generateForm, generateChart, generateCode, generateCard)
- [ ] Tool schema conversion for OpenAI
- [ ] tool-call event emission
- [ ] tool-result event emission
- [ ] Frontend integration testing

**Exit Criteria:**
- All four tools work correctly
- Tool calls render in frontend
- Schema matches frontend expectations

### Phase 4: Production Hardening (Week 4)

**Goal:** Authentication, retry logic, observability

**Deliverables:**
- [ ] Authentication middleware (all modes)
- [ ] Retry logic with exponential backoff
- [ ] GET /models endpoint
- [ ] CORS configuration
- [ ] Enhanced health checks
- [ ] Documentation

**Exit Criteria:**
- Auth works in all modes
- Retries recover from transient failures
- Models endpoint returns configured models

### Phase 5: Deployment (Week 5)

**Goal:** Container and Kubernetes deployment

**Deliverables:**
- [ ] Dockerfile (multi-stage build)
- [ ] docker-compose.yaml for local development
- [ ] Kubernetes manifests (Deployment, Service, ConfigMap)
- [ ] Health probe configuration
- [ ] CI/CD pipeline setup
- [ ] End-to-end testing in staging

**Exit Criteria:**
- Deploys to Kubernetes
- Health probes function correctly
- Full E2E testing passes

---

## 15. Testing Strategy

### 15.1 Unit Tests

**Scope:** Individual functions and classes in isolation

**Coverage Areas:**
- Request/response model validation
- SSE event encoding
- Retry logic
- Error handling utilities
- Authentication validation
- Configuration parsing

**Framework:** pytest

**Example:**
```python
def test_text_delta_event_serialization():
    event = TextDeltaEvent(textDelta="Hello")
    assert event.model_dump() == {"type": "text-delta", "textDelta": "Hello"}

def test_chat_request_validation_rejects_invalid_model():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            messages=[],
            model="invalid-model"
        )
```

### 15.2 Integration Tests

**Scope:** Component interactions with mocked external services

**Coverage Areas:**
- API endpoint request/response cycles
- Middleware chain execution
- Agent-to-OpenAI communication (mocked)
- Streaming response assembly
- Error propagation

**Framework:** pytest + httpx + respx (for mocking)

**Example:**
```python
@pytest.mark.asyncio
async def test_chat_completions_streams_response(
    client: AsyncClient,
    mock_openai: respx.MockRouter
):
    mock_openai.post("/chat").respond(
        stream=mock_streaming_response()
    )

    async with client.stream("POST", "/chat", json={
        "messages": [{"id": "1", "role": "user", "parts": [{"type": "text", "text": "Hi"}]}],
        "model": "openai/gpt-4o"
    }) as response:
        events = [line async for line in response.aiter_lines() if line.startswith("data:")]

    assert any('"type":"text-delta"' in e for e in events)
    assert any('"type":"finish"' in e for e in events)
```

### 15.3 End-to-End Tests

**Scope:** Full system with real OpenAI API

**Coverage Areas:**
- Real streaming responses
- Tool call generation
- Error scenarios (rate limits, etc.)
- Frontend compatibility

**Framework:** pytest + real HTTP client

**Considerations:**
- Run against staging environment
- Use dedicated test API key with limits
- Include timeout handling
- Record/replay for CI (VCR pattern)

### 15.4 Contract Tests

**Scope:** API contract compliance with frontend

**Validation:**
- SSE event schema matches frontend expectations
- Request format accepted matches frontend sends
- Error response format handled by frontend

**Approach:**
- Shared JSON schemas between frontend and backend
- Automated contract validation in CI

---

## 16. Deployment Guide

### 16.1 Local Development

**Prerequisites:**
- Python 3.11+
- uv (package manager)
- OpenAI API key

**Setup:**
```bash
# Clone repository
git clone <repo-url>
cd mamba-server

# Install dependencies
uv sync

# Create local config
cp config/config.yaml config/config.local.yaml
# Edit config.local.yaml with your settings

# Set environment variables
export OPENAI_API_KEY=sk-your-key-here

# Run development server
uv run uvicorn mamba.main:app --reload --port 8000
```

**Verification:**
```bash
curl http://localhost:8000/health
```

### 16.2 Docker Development

**Build:**
```bash
docker build -t mamba-server:dev .
```

**Run:**
```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e MAMBA_AUTH_MODE=none \
  mamba-server:dev
```

**Docker Compose:**
```bash
docker-compose up
```

### 16.3 Kubernetes Deployment

**Prerequisites:**
- Kubernetes cluster
- kubectl configured
- Secrets created

**Create Secrets:**
```bash
kubectl create secret generic mamba-secrets \
  --from-literal=openai-api-key=sk-xxx \
  --from-literal=api-key=mamba_sk_xxx
```

**Deploy:**
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

**Kubernetes Manifests:**

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mamba-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mamba-server
  template:
    metadata:
      labels:
        app: mamba-server
    spec:
      containers:
        - name: mamba-server
          image: mamba-server:latest
          ports:
            - containerPort: 8000
          env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: mamba-secrets
                  key: openai-api-key
            - name: MAMBA_API_KEY_1
              valueFrom:
                secretKeyRef:
                  name: mamba-secrets
                  key: api-key
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

**service.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: mamba-server
spec:
  selector:
    app: mamba-server
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

---

## 17. Open Questions and Future Considerations

### Open Questions

| ID | Question | Impact | Owner |
|----|----------|--------|-------|
| OQ-1 | Should we implement request-level rate limiting or defer to infrastructure? | Performance, cost | TBD |
| OQ-2 | What metrics should be exposed for observability (Prometheus, etc.)? | Operations | TBD |
| OQ-3 | Should tool schemas be dynamically loaded or hard-coded? | Flexibility | TBD |
| OQ-4 | How to handle very long conversations that exceed context window? | User experience | TBD |

### Future Considerations

**Multi-Provider Support:**
- Add Anthropic (Claude) integration
- Add Google (Gemini) integration
- Provider abstraction layer

**Advanced Features:**
- Conversation memory/context management
- Response caching for identical prompts
- Custom system prompts per deployment
- Usage tracking and billing integration

**Observability Enhancements:**
- Prometheus metrics endpoint
- Distributed tracing (OpenTelemetry)
- Real-time dashboard

**Security Enhancements:**
- Request signing
- IP allowlisting
- Prompt injection detection

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| SSE | Server-Sent Events - HTTP streaming protocol for real-time updates |
| Pydantic AI | Python library for building AI agents with type safety |
| UIMessage | AI SDK message format with id, role, and parts array |
| TTFT | Time to First Token - latency from request to first response chunk |
| Tool Call | AI decision to invoke a defined function/tool |

---

## Appendix B: References

- [Vercel AI SDK Documentation](https://sdk.vercel.ai/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Pydantic AI Documentation](https://ai.pydantic.dev)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Server-Sent Events Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)

---

*Document generated by PRD Interview Agent*
*Last updated: 2026-01-26*
