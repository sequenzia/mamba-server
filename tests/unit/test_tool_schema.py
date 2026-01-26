"""Tests for tool schema conversion."""

import pytest

from mamba.core.tool_schema import (
    TOOL_DESCRIPTIONS,
    clean_schema_for_openai,
    convert_tool_to_openai_function,
    get_all_tool_definitions,
    get_json_schema,
    get_tool_definition,
    validate_tool_schema,
)
from mamba.core.tools import (
    SUPPORTED_TOOLS,
    TOOL_GENERATE_CARD,
    TOOL_GENERATE_CHART,
    TOOL_GENERATE_CODE,
    TOOL_GENERATE_FORM,
    GenerateCardArgs,
    GenerateChartArgs,
    GenerateCodeArgs,
    GenerateFormArgs,
)


class TestGetJsonSchema:
    """Tests for get_json_schema function."""

    def test_returns_schema_dict(self):
        """Test returns a dictionary schema."""
        schema = get_json_schema(GenerateFormArgs)
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_removes_title(self):
        """Test removes title from root."""
        schema = get_json_schema(GenerateFormArgs)
        assert "title" not in schema

    def test_converts_defs_to_definitions(self):
        """Test converts $defs to definitions."""
        schema = get_json_schema(GenerateFormArgs)
        # Schema may have definitions if there are nested models
        assert "$defs" not in schema


class TestCleanSchemaForOpenai:
    """Tests for clean_schema_for_openai function."""

    def test_removes_type_with_const(self):
        """Test removes type property with const value."""
        schema = {
            "properties": {
                "type": {"const": "form"},
                "title": {"type": "string"},
            },
            "required": ["type", "title"],
        }
        result = clean_schema_for_openai(schema)
        assert "type" not in result["properties"]
        assert "type" not in result["required"]

    def test_removes_type_with_default(self):
        """Test removes type property with default value."""
        schema = {
            "properties": {
                "type": {"type": "string", "default": "form"},
                "title": {"type": "string"},
            },
            "required": ["type", "title"],
        }
        result = clean_schema_for_openai(schema)
        assert "type" not in result["properties"]

    def test_removes_empty_required(self):
        """Test removes empty required list."""
        schema = {
            "properties": {"type": {"const": "form"}},
            "required": ["type"],
        }
        result = clean_schema_for_openai(schema)
        assert "required" not in result


class TestConvertToolToOpenaiFunction:
    """Tests for convert_tool_to_openai_function function."""

    def test_creates_function_definition(self):
        """Test creates valid function definition."""
        result = convert_tool_to_openai_function(
            TOOL_GENERATE_FORM,
            GenerateFormArgs,
        )

        assert result["type"] == "function"
        assert "function" in result
        assert result["function"]["name"] == TOOL_GENERATE_FORM
        assert "parameters" in result["function"]

    def test_includes_description(self):
        """Test includes description from TOOL_DESCRIPTIONS."""
        result = convert_tool_to_openai_function(
            TOOL_GENERATE_FORM,
            GenerateFormArgs,
        )

        assert result["function"]["description"] == TOOL_DESCRIPTIONS[TOOL_GENERATE_FORM]

    def test_custom_description(self):
        """Test custom description overrides default."""
        result = convert_tool_to_openai_function(
            TOOL_GENERATE_FORM,
            GenerateFormArgs,
            description="Custom description",
        )

        assert result["function"]["description"] == "Custom description"


class TestGetAllToolDefinitions:
    """Tests for get_all_tool_definitions function."""

    def test_returns_all_tools(self):
        """Test returns definitions for all supported tools."""
        definitions = get_all_tool_definitions()
        assert len(definitions) == len(SUPPORTED_TOOLS)

    def test_all_definitions_valid(self):
        """Test all definitions are valid OpenAI format."""
        definitions = get_all_tool_definitions()
        for definition in definitions:
            assert validate_tool_schema(definition)

    def test_includes_all_tool_names(self):
        """Test includes all expected tool names."""
        definitions = get_all_tool_definitions()
        names = [d["function"]["name"] for d in definitions]

        assert TOOL_GENERATE_FORM in names
        assert TOOL_GENERATE_CHART in names
        assert TOOL_GENERATE_CODE in names
        assert TOOL_GENERATE_CARD in names


class TestGetToolDefinition:
    """Tests for get_tool_definition function."""

    def test_returns_definition_for_valid_tool(self):
        """Test returns definition for valid tool."""
        definition = get_tool_definition(TOOL_GENERATE_FORM)
        assert definition is not None
        assert definition["function"]["name"] == TOOL_GENERATE_FORM

    def test_returns_none_for_invalid_tool(self):
        """Test returns None for invalid tool name."""
        definition = get_tool_definition("invalidTool")
        assert definition is None

    def test_generate_chart_definition(self):
        """Test generateChart definition."""
        definition = get_tool_definition(TOOL_GENERATE_CHART)
        assert definition is not None
        assert "chartType" in str(definition)

    def test_generate_code_definition(self):
        """Test generateCode definition."""
        definition = get_tool_definition(TOOL_GENERATE_CODE)
        assert definition is not None
        assert "language" in str(definition)

    def test_generate_card_definition(self):
        """Test generateCard definition."""
        definition = get_tool_definition(TOOL_GENERATE_CARD)
        assert definition is not None
        assert "title" in str(definition)


class TestValidateToolSchema:
    """Tests for validate_tool_schema function."""

    def test_valid_schema(self):
        """Test valid schema returns True."""
        schema = {
            "type": "function",
            "function": {
                "name": "testTool",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }
        assert validate_tool_schema(schema) is True

    def test_missing_type(self):
        """Test missing type returns False."""
        schema = {
            "function": {
                "name": "testTool",
                "parameters": {"type": "object"},
            },
        }
        assert validate_tool_schema(schema) is False

    def test_wrong_type(self):
        """Test wrong type returns False."""
        schema = {
            "type": "tool",
            "function": {
                "name": "testTool",
                "parameters": {"type": "object"},
            },
        }
        assert validate_tool_schema(schema) is False

    def test_missing_function(self):
        """Test missing function returns False."""
        schema = {"type": "function"}
        assert validate_tool_schema(schema) is False

    def test_missing_name(self):
        """Test missing name returns False."""
        schema = {
            "type": "function",
            "function": {
                "parameters": {"type": "object"},
            },
        }
        assert validate_tool_schema(schema) is False

    def test_missing_parameters(self):
        """Test missing parameters returns False."""
        schema = {
            "type": "function",
            "function": {
                "name": "testTool",
            },
        }
        assert validate_tool_schema(schema) is False

    def test_wrong_parameter_type(self):
        """Test wrong parameter type returns False."""
        schema = {
            "type": "function",
            "function": {
                "name": "testTool",
                "parameters": {"type": "array"},
            },
        }
        assert validate_tool_schema(schema) is False


class TestToolDescriptions:
    """Tests for tool descriptions."""

    def test_all_tools_have_descriptions(self):
        """Test all supported tools have descriptions."""
        for tool in SUPPORTED_TOOLS:
            assert tool in TOOL_DESCRIPTIONS
            assert len(TOOL_DESCRIPTIONS[tool]) > 0

    def test_descriptions_are_helpful(self):
        """Test descriptions contain meaningful information."""
        # Form description mentions field types
        assert "form" in TOOL_DESCRIPTIONS[TOOL_GENERATE_FORM].lower()

        # Chart description mentions chart types
        assert "chart" in TOOL_DESCRIPTIONS[TOOL_GENERATE_CHART].lower()

        # Code description mentions syntax
        assert "code" in TOOL_DESCRIPTIONS[TOOL_GENERATE_CODE].lower()

        # Card description mentions components
        assert "card" in TOOL_DESCRIPTIONS[TOOL_GENERATE_CARD].lower()
