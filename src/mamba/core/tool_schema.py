"""Tool schema conversion for OpenAI function calling format.

Converts Pydantic tool models to OpenAI function definitions.
"""

import json
from typing import Any, Type

from pydantic import BaseModel

from mamba.core.tools import (
    SUPPORTED_TOOLS,
    TOOL_ARG_MODELS,
    TOOL_GENERATE_CARD,
    TOOL_GENERATE_CHART,
    TOOL_GENERATE_CODE,
    TOOL_GENERATE_FORM,
    GenerateCardArgs,
    GenerateChartArgs,
    GenerateCodeArgs,
    GenerateFormArgs,
)


# Tool descriptions for OpenAI function definitions
TOOL_DESCRIPTIONS: dict[str, str] = {
    TOOL_GENERATE_FORM: (
        "Generate an interactive form with various field types "
        "including text, textarea, select, checkbox, radio, date, slider, file, "
        "number, and email fields."
    ),
    TOOL_GENERATE_CHART: (
        "Generate a data visualization chart. "
        "Supports line, bar, pie, and area chart types."
    ),
    TOOL_GENERATE_CODE: (
        "Generate a code block with syntax highlighting. "
        "Supports optional filename, editability, and line numbers."
    ),
    TOOL_GENERATE_CARD: (
        "Generate a card component with title, description, content, "
        "media (image or video), and action buttons."
    ),
}


def get_json_schema(model: Type[BaseModel]) -> dict[str, Any]:
    """Get JSON Schema from a Pydantic model.

    Args:
        model: The Pydantic model class.

    Returns:
        JSON Schema dictionary.
    """
    schema = model.model_json_schema()

    # Remove the 'title' at the root level as OpenAI doesn't need it
    if "title" in schema:
        del schema["title"]

    # Move $defs to definitions if present (OpenAI prefers this format)
    if "$defs" in schema:
        schema["definitions"] = schema.pop("$defs")

    return schema


def clean_schema_for_openai(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean up JSON Schema for OpenAI compatibility.

    Removes fields that OpenAI doesn't handle well.

    Args:
        schema: The JSON Schema to clean.

    Returns:
        Cleaned schema.
    """
    # Remove 'type' field with default value from root (it's implied)
    if "properties" in schema:
        props = schema["properties"]
        if "type" in props:
            prop = props["type"]
            # If it's a literal with a const value, remove it
            if "const" in prop:
                del props["type"]
            # If it has a default, remove the field
            elif "default" in prop:
                del props["type"]

    # Update required list to remove 'type' if present
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "type"]
        if not schema["required"]:
            del schema["required"]

    return schema


def convert_tool_to_openai_function(
    tool_name: str,
    model: Type[BaseModel],
    description: str | None = None,
) -> dict[str, Any]:
    """Convert a tool to OpenAI function calling format.

    Args:
        tool_name: The name of the tool.
        model: The Pydantic model for tool arguments.
        description: Optional description override.

    Returns:
        OpenAI function definition.
    """
    schema = get_json_schema(model)
    schema = clean_schema_for_openai(schema)

    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description or TOOL_DESCRIPTIONS.get(tool_name, ""),
            "parameters": schema,
        },
    }


def get_all_tool_definitions() -> list[dict[str, Any]]:
    """Get OpenAI function definitions for all supported tools.

    Returns:
        List of OpenAI function definitions.
    """
    definitions = []

    for tool_name in SUPPORTED_TOOLS:
        model = TOOL_ARG_MODELS.get(tool_name)
        if model:
            definition = convert_tool_to_openai_function(
                tool_name,
                model,
                TOOL_DESCRIPTIONS.get(tool_name),
            )
            definitions.append(definition)

    return definitions


def get_tool_definition(tool_name: str) -> dict[str, Any] | None:
    """Get OpenAI function definition for a specific tool.

    Args:
        tool_name: The name of the tool.

    Returns:
        OpenAI function definition or None if tool not found.
    """
    if tool_name not in SUPPORTED_TOOLS:
        return None

    model = TOOL_ARG_MODELS.get(tool_name)
    if not model:
        return None

    return convert_tool_to_openai_function(
        tool_name,
        model,
        TOOL_DESCRIPTIONS.get(tool_name),
    )


def validate_tool_schema(definition: dict[str, Any]) -> bool:
    """Validate that a tool definition has required OpenAI fields.

    Args:
        definition: The tool definition to validate.

    Returns:
        True if valid, False otherwise.
    """
    if "type" not in definition or definition["type"] != "function":
        return False

    if "function" not in definition:
        return False

    func = definition["function"]
    if "name" not in func:
        return False

    if "parameters" not in func:
        return False

    params = func["parameters"]
    if "type" not in params or params["type"] != "object":
        return False

    return True
