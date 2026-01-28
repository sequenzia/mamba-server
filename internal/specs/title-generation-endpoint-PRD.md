# Product Requirements Document: Title Generation Endpoint

**Version:** 1.0.0
**Author:** Stephen Sequenzia
**Date:** 2026-01-27
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
8. [Configuration](#8-configuration)
9. [Implementation Details](#9-implementation-details)
10. [Testing Strategy](#10-testing-strategy)
11. [Risks and Mitigations](#11-risks-and-mitigations)
12. [Out of Scope](#12-out-of-scope)

---

## 1. Executive Summary

This PRD defines a new endpoint for mamba-server that generates concise, AI-powered conversation titles from a user's first message. The endpoint ports functionality from the ai-chatbot reference implementation to Python/FastAPI, using Pydantic AI for LLM integration.

The title generation endpoint provides the mamba-chat frontend with meaningful conversation titles, improving user experience over simple message truncation fallbacks.

### Key Capabilities

- **AI-Powered Title Generation**: Uses gpt-4o-mini to generate contextually relevant titles
- **Graceful Fallback**: Returns `useFallback: true` on failures, allowing client-side fallback
- **Configurable Settings**: Max length, timeout, and model are server-configurable
- **Low Latency**: Optimized for fast response times using a lightweight model

---

## 2. Problem Statement

### Current State

The mamba-chat frontend's `RealChatService.generateTitle()` method is currently a stub that always returns `{ title: 'New Conversation', useFallback: true }`. This forces the client to use local fallback logic (truncating the first message), resulting in less meaningful conversation titles.

### Desired State

A backend endpoint that:

- Generates concise, AI-powered titles from the user's first message
- Returns titles that capture the main topic or intent of the conversation
- Handles failures gracefully by signaling the client to use fallback logic
- Responds quickly to avoid impacting the chat user experience

### Impact

Without this endpoint, all conversations in mamba-chat have generic or truncated titles. With this endpoint, users see meaningful titles that help them identify and navigate their conversation history.

---

## 3. Goals and Success Metrics

### Primary Goals

| Goal | Description | Priority |
|------|-------------|----------|
| Low Latency | Fast title generation to avoid UX delays | P0 |
| API Compatibility | Match mamba-chat's expected request/response format | P0 |
| Graceful Degradation | Return fallback signal on any failure | P0 |
| Cost Efficiency | Use lightweight model (gpt-4o-mini) | P1 |

### Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Response Latency | < 2 seconds (p95) | Application logs |
| Title Quality | Relevant to conversation topic | Manual review |
| Fallback Rate | < 5% of requests | Error rate monitoring |

### Non-Goals (Out of Scope)

- Title caching or persistence
- Batch title generation
- Title regeneration or editing
- Multi-language title generation
- Integration tests with real OpenAI API

---

## 4. User Stories

### US-001: Generate Conversation Title

**As a** mamba-chat frontend
**I want to** request a title for a new conversation
**So that** users see meaningful titles in their conversation list

**Acceptance Criteria:**
- POST to `/title/generate` with `userMessage` and `conversationId`
- Receive `{ title, useFallback: false }` on success
- Title is max 50 characters, truncated at word boundary if needed
- Response within configured timeout (default 10 seconds)

### US-002: Handle Title Generation Failure

**As a** mamba-chat frontend
**I want to** receive a fallback signal when title generation fails
**So that** I can generate a fallback title locally

**Acceptance Criteria:**
- Receive `{ title: "", useFallback: true }` on any failure
- Failures include: timeout, API errors, validation errors
- Client handles fallback gracefully without error display

---

## 5. Functional Requirements

### FR-001: Title Generation Endpoint

**Description:** Accept a user message and generate a concise conversation title

**Requirements:**
- Accept POST requests to `/title/generate`
- Validate request contains `userMessage` and `conversationId`
- Generate title using configured LLM model
- Return title with `useFallback: false` on success
- Return empty title with `useFallback: true` on any failure

### FR-002: Title Truncation

**Description:** Ensure generated titles fit within maximum length

**Requirements:**
- Titles must not exceed configured `max_length` (default: 50)
- Truncate at word boundary when possible
- Add "..." suffix to truncated titles
- Preserve at least 60% of max length before word boundary truncation

### FR-003: Timeout Handling

**Description:** Enforce timeout on LLM requests

**Requirements:**
- Cancel LLM request after configured `timeout_ms` (default: 10000)
- Return fallback response on timeout
- Log timeout events for monitoring

### FR-004: Title Cleaning

**Description:** Clean generated titles for display

**Requirements:**
- Remove leading/trailing whitespace
- Remove surrounding quotes if present
- Ensure sentence case formatting

---

## 6. API Specification

### POST /title/generate

Generate a title for a conversation based on the user's first message.

#### Request

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>  (if auth enabled)
X-API-Key: <key>               (alternative auth)
```

**Body:**
```json
{
  "userMessage": "How do I implement a binary search tree in Python?",
  "conversationId": "conv_abc123xyz"
}
```

#### Response (Success)

**Status:** 200 OK

**Body:**
```json
{
  "title": "Implementing binary search trees",
  "useFallback": false
}
```

#### Response (Failure)

**Status:** 200 OK (graceful degradation)

**Body:**
```json
{
  "title": "",
  "useFallback": true
}
```

#### Response (Validation Error)

**Status:** 422 Unprocessable Entity

**Body:**
```json
{
  "detail": [
    {
      "loc": ["body", "userMessage"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success or graceful failure (check `useFallback`) |
| 401 | Authentication required/failed |
| 422 | Validation error (missing required fields) |
| 500 | Internal server error (unexpected) |

---

## 7. Data Models

### Pydantic Models

```python
from pydantic import BaseModel, Field


class TitleGenerationRequest(BaseModel):
    """Request body for title generation endpoint."""

    userMessage: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's first message in the conversation",
    )
    conversationId: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the conversation",
    )


class TitleGenerationResponse(BaseModel):
    """Response body for title generation endpoint."""

    title: str = Field(
        ...,
        description="Generated title or empty string on failure",
    )
    useFallback: bool = Field(
        ...,
        description="True if client should generate fallback title",
    )
```

---

## 8. Configuration

### Configuration Schema

Add to `src/mamba/config.py`:

```python
class TitleSettings(BaseModel):
    """Settings for title generation."""

    max_length: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Maximum title length in characters",
    )
    timeout_ms: int = Field(
        default=10000,
        ge=1000,
        le=30000,
        description="Timeout for title generation in milliseconds",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Model to use for title generation",
    )
```

### config.yaml

```yaml
# Title generation settings
title:
  max_length: 50
  timeout_ms: 10000
  model: "gpt-4o-mini"
```

### Environment Variable Overrides

```bash
MAMBA_TITLE_MAX_LENGTH=50
MAMBA_TITLE_TIMEOUT_MS=10000
MAMBA_TITLE_MODEL=gpt-4o-mini
```

---

## 9. Implementation Details

### Files to Create

| File | Description |
|------|-------------|
| `src/mamba/api/handlers/title.py` | Endpoint handler |
| `src/mamba/models/title.py` | Request/response models |
| `tests/unit/api/handlers/test_title.py` | Unit tests |

### Files to Modify

| File | Change |
|------|--------|
| `src/mamba/api/router.py` | Register `/title/generate` route |
| `src/mamba/config.py` | Add `TitleSettings` class |
| `config.yaml` | Add `title:` section with defaults |

### Prompt Specification

The following prompt is ported from the reference implementation:

```python
TITLE_PROMPT = """Generate a concise title (max {max_length} characters) for this conversation based on the user's first message.
The title should:
- Capture the main topic or intent
- Be descriptive but brief
- Not include quotes or special characters
- Be in sentence case

User message: {user_message}

Respond with ONLY the title, nothing else."""
```

### Title Truncation Algorithm

```python
def truncate_at_word_boundary(text: str, max_length: int) -> str:
    """Truncate text at word boundary with ellipsis.

    Args:
        text: The text to truncate.
        max_length: Maximum allowed length.

    Returns:
        Truncated text with "..." suffix if truncated.
    """
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    last_space = truncated.rfind(' ')

    # If we can find a word boundary in the last 40% of the text, use it
    if last_space > max_length * 0.6:
        return truncated[:last_space] + '...'

    # Otherwise, hard truncate with ellipsis
    return truncated[:max_length - 3] + '...'
```

### Handler Implementation Pattern

```python
@router.post("/title/generate")
async def generate_title(
    request: TitleGenerationRequest,
    settings: SettingsDep,
) -> TitleGenerationResponse:
    """Generate a title for a conversation.

    Returns a generated title on success, or signals fallback on failure.
    """
    try:
        # Create agent with lightweight model
        agent = create_agent(
            settings,
            model_name=settings.title.model,
            enable_tools=False,
        )

        # Build prompt
        prompt = TITLE_PROMPT.format(
            max_length=settings.title.max_length,
            user_message=request.userMessage,
        )

        # Generate with timeout
        timeout_seconds = settings.title.timeout_ms / 1000
        title = await asyncio.wait_for(
            agent.generate_text(prompt),
            timeout=timeout_seconds,
        )

        # Clean and truncate
        title = clean_title(title, settings.title.max_length)

        return TitleGenerationResponse(title=title, useFallback=False)

    except Exception as e:
        logger.warning(f"Title generation failed: {e}")
        return TitleGenerationResponse(title="", useFallback=True)
```

### Authentication

The endpoint uses the same authentication middleware as `/chat`:

- Respects `auth.mode` setting (`none`, `api_key`, `jwt`)
- Validates credentials via existing middleware chain
- Returns 401 on authentication failure

---

## 10. Testing Strategy

### Unit Tests

**Scope:** Handler logic and utility functions

**Test Cases:**

```python
# test_title.py

class TestTruncateAtWordBoundary:
    """Tests for title truncation logic."""

    def test_short_text_unchanged(self):
        """Text under max length returns unchanged."""
        assert truncate_at_word_boundary("Hello world", 50) == "Hello world"

    def test_truncates_at_word_boundary(self):
        """Long text truncates at last word boundary."""
        text = "This is a very long title that needs truncation"
        result = truncate_at_word_boundary(text, 30)
        assert result == "This is a very long title..."
        assert len(result) <= 30

    def test_hard_truncate_when_no_good_boundary(self):
        """Truncates hard when no word boundary in last 40%."""
        text = "Supercalifragilisticexpialidocious"
        result = truncate_at_word_boundary(text, 20)
        assert result == "Supercalifragilis..."
        assert len(result) == 20

    def test_exact_max_length(self):
        """Text exactly at max length unchanged."""
        text = "Exactly fifty characters long for this test case!!"
        assert len(text) == 50
        assert truncate_at_word_boundary(text, 50) == text


class TestCleanTitle:
    """Tests for title cleaning logic."""

    def test_strips_whitespace(self):
        """Removes leading/trailing whitespace."""
        assert clean_title("  Hello  ", 50) == "Hello"

    def test_removes_quotes(self):
        """Removes surrounding quotes."""
        assert clean_title('"Hello World"', 50) == "Hello World"
        assert clean_title("'Hello World'", 50) == "Hello World"

    def test_combines_cleaning_and_truncation(self):
        """Cleans then truncates."""
        text = '"This is a very long quoted title that needs work"'
        result = clean_title(text, 30)
        assert not result.startswith('"')
        assert len(result) <= 30


class TestGenerateTitleHandler:
    """Tests for the generate_title endpoint handler."""

    @pytest.mark.asyncio
    async def test_returns_title_on_success(self, mock_agent):
        """Returns generated title with useFallback=False."""
        mock_agent.generate_text.return_value = "Python binary search trees"

        response = await generate_title(
            TitleGenerationRequest(
                userMessage="How do I implement a BST?",
                conversationId="conv_123",
            ),
            settings=mock_settings,
        )

        assert response.title == "Python binary search trees"
        assert response.useFallback is False

    @pytest.mark.asyncio
    async def test_returns_fallback_on_timeout(self, mock_agent):
        """Returns useFallback=True on timeout."""
        mock_agent.generate_text.side_effect = asyncio.TimeoutError()

        response = await generate_title(
            TitleGenerationRequest(
                userMessage="Hello",
                conversationId="conv_123",
            ),
            settings=mock_settings,
        )

        assert response.title == ""
        assert response.useFallback is True

    @pytest.mark.asyncio
    async def test_returns_fallback_on_api_error(self, mock_agent):
        """Returns useFallback=True on API error."""
        mock_agent.generate_text.side_effect = Exception("API Error")

        response = await generate_title(
            TitleGenerationRequest(
                userMessage="Hello",
                conversationId="conv_123",
            ),
            settings=mock_settings,
        )

        assert response.title == ""
        assert response.useFallback is True
```

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Latency exceeds timeout** | Medium | Medium | Use lightweight model (gpt-4o-mini), configurable timeout, graceful fallback to client-side generation |

### Latency Risk Details

**Scenario:** LLM response time exceeds configured timeout, causing degraded user experience.

**Mitigation Strategies:**

1. **Model Selection**: Use `gpt-4o-mini` which has faster response times than full GPT-4 models
2. **Configurable Timeout**: Allow operators to tune timeout based on observed latency
3. **Graceful Fallback**: Return `useFallback: true` allowing client to proceed without blocking
4. **Monitoring**: Log timeout events to track and address latency issues

**Monitoring Approach:**
```python
logger.warning(
    "Title generation timed out",
    extra={
        "conversation_id": request.conversationId,
        "timeout_ms": settings.title.timeout_ms,
    }
)
```

---

## 12. Out of Scope

The following items are explicitly excluded from this implementation:

| Item | Reason |
|------|--------|
| Title caching | Adds complexity; each conversation is unique |
| Batch title generation | No current use case in mamba-chat |
| Title regeneration/editing | Client can trigger new generation if needed |
| Integration tests with OpenAI | Cost and flakiness concerns; unit tests with mocks sufficient |
| Multi-language support | English-only for initial implementation |
| Custom prompts per client | Single prompt meets current needs |

---

## Appendix A: Reference Implementation

The endpoint is ported from:
- **Source:** `/Users/sequenzia/dev/repos/ai/ai-chatbot/src/app/api/generate-title/route.ts`
- **Framework:** Next.js API route with Vercel AI SDK
- **Key Differences:**
  - Python/FastAPI instead of TypeScript/Next.js
  - Pydantic AI instead of Vercel AI SDK
  - Response format aligned with mamba-chat expectations

---

## Appendix B: Consumer Interface

The mamba-chat frontend expects:

**Request Type:**
```typescript
interface TitleGenerationRequest {
  userMessage: string;
  conversationId: string;
}
```

**Response Type:**
```typescript
interface TitleGenerationResponse {
  title: string;
  useFallback: boolean;
}
```

**Source:** `/Users/sequenzia/dev/repos/mamba-chat/src/services/chat/types.ts`

---

*Document generated by PRD Interview Agent*
*Last updated: 2026-01-27*
