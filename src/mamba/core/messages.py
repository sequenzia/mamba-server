"""Message format conversion utilities.

Converts between UIMessage format (frontend) and OpenAI message format.
"""

from typing import Any

from mamba.models.request import (
    TextPart,
    ToolCallPart,
    ToolInvocationPart,
    ToolResultPart,
    UIMessage,
)


def convert_text_part(part: TextPart) -> str:
    """Convert a TextPart to string content.

    Args:
        part: The text part to convert.

    Returns:
        The text content as a string.
    """
    return part.text


def convert_tool_invocation_part(part: ToolInvocationPart) -> dict[str, Any]:
    """Convert a ToolInvocationPart to OpenAI tool call format.

    Args:
        part: The tool invocation part to convert.

    Returns:
        Dictionary in OpenAI tool call format.
    """
    import json

    return {
        "id": part.toolCallId,
        "type": "function",
        "function": {
            "name": part.toolName,
            "arguments": json.dumps(part.args),
        },
    }


def convert_tool_call_part(part: ToolCallPart) -> dict[str, Any]:
    """Convert a ToolCallPart (AI SDK format) to OpenAI tool call format.

    Args:
        part: The tool call part to convert.

    Returns:
        Dictionary in OpenAI tool call format.
    """
    import json

    return {
        "id": part.toolCallId,
        "type": "function",
        "function": {
            "name": part.toolName,
            "arguments": json.dumps(part.args or {}),
        },
    }


def extract_text_content(parts: list) -> str:
    """Extract text content from message parts.

    Concatenates all TextPart text with spaces.

    Args:
        parts: List of message parts.

    Returns:
        Combined text content.
    """
    text_parts = []
    for part in parts:
        if isinstance(part, TextPart):
            text_parts.append(part.text)
    return " ".join(text_parts) if text_parts else ""


def extract_tool_calls(parts: list) -> list[dict[str, Any]]:
    """Extract tool calls from message parts.

    Handles both AI SDK format (ToolCallPart) and legacy format (ToolInvocationPart).

    Args:
        parts: List of message parts.

    Returns:
        List of tool calls in OpenAI format.
    """
    tool_calls = []
    for part in parts:
        # AI SDK format: tool-call
        if isinstance(part, ToolCallPart):
            tool_calls.append(convert_tool_call_part(part))
        # Legacy format: tool-invocation without result
        elif isinstance(part, ToolInvocationPart) and part.result is None:
            tool_calls.append(convert_tool_invocation_part(part))
    return tool_calls


def extract_tool_results(parts: list) -> list[dict[str, Any]]:
    """Extract tool results from message parts.

    Handles both AI SDK format (ToolResultPart) and legacy format (ToolInvocationPart).

    Args:
        parts: List of message parts.

    Returns:
        List of tool result messages.
    """
    import json

    results = []
    for part in parts:
        # AI SDK format: tool-result
        if isinstance(part, ToolResultPart):
            result_str = json.dumps(part.result) if isinstance(part.result, dict) else str(part.result)
            results.append({
                "tool_call_id": part.toolCallId,
                "result": result_str,
            })
        # Legacy format: tool-invocation with result
        elif isinstance(part, ToolInvocationPart) and part.result is not None:
            # Convert result dict to JSON string for OpenAI format
            result_str = json.dumps(part.result) if isinstance(part.result, dict) else str(part.result)
            results.append({
                "tool_call_id": part.toolCallId,
                "result": result_str,
            })
    return results


def convert_ui_message(message: UIMessage) -> dict[str, Any]:
    """Convert a UIMessage to OpenAI message format.

    Args:
        message: The UIMessage to convert.

    Returns:
        Dictionary in OpenAI message format.

    Raises:
        ValueError: If the message has an invalid role.
    """
    role = message.role

    # System messages just have content
    if role == "system":
        return {
            "role": "system",
            "content": extract_text_content(message.parts),
        }

    # User messages have content
    if role == "user":
        return {
            "role": "user",
            "content": extract_text_content(message.parts),
        }

    # Assistant messages may have content and/or tool calls
    if role == "assistant":
        result: dict[str, Any] = {"role": "assistant"}

        content = extract_text_content(message.parts)
        if content:
            result["content"] = content

        tool_calls = extract_tool_calls(message.parts)
        if tool_calls:
            result["tool_calls"] = tool_calls

        # Ensure at least content is present
        if "content" not in result and "tool_calls" not in result:
            result["content"] = ""

        return result

    raise ValueError(f"Invalid message role: {role}")


def convert_tool_result_to_message(
    tool_call_id: str,
    result: str,
) -> dict[str, Any]:
    """Convert a tool result to an OpenAI tool message.

    Args:
        tool_call_id: The ID of the tool call.
        result: The tool result content.

    Returns:
        Dictionary in OpenAI tool message format.
    """
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": result,
    }


def convert_messages(messages: list[UIMessage]) -> list[dict[str, Any]]:
    """Convert a list of UIMessages to OpenAI message format.

    Handles tool invocations by creating appropriate tool messages
    for results in the conversation history.

    Args:
        messages: List of UIMessages to convert.

    Returns:
        List of OpenAI format messages.

    Raises:
        ValueError: If a message has an invalid role.
    """
    result: list[dict[str, Any]] = []

    for message in messages:
        # Convert the main message
        openai_msg = convert_ui_message(message)
        result.append(openai_msg)

        # If assistant message had tool calls with results,
        # add the tool result messages
        if message.role == "assistant":
            tool_results = extract_tool_results(message.parts)
            for tool_result in tool_results:
                result.append(
                    convert_tool_result_to_message(
                        tool_result["tool_call_id"],
                        tool_result["result"],
                    )
                )

    return result
