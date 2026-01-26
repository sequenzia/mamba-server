"""Tests for tool schema definitions."""

import pytest
from pydantic import ValidationError

from mamba.core.tools import (
    SUPPORTED_TOOLS,
    TOOL_ARG_MODELS,
    TOOL_GENERATE_CARD,
    TOOL_GENERATE_CHART,
    TOOL_GENERATE_CODE,
    TOOL_GENERATE_FORM,
    CardAction,
    CardMedia,
    ChartDataPoint,
    FormField,
    FormFieldOption,
    GenerateCardArgs,
    GenerateChartArgs,
    GenerateCodeArgs,
    GenerateFormArgs,
)


class TestFormField:
    """Tests for FormField model."""

    def test_text_field(self):
        """Test text field creation."""
        field = FormField(
            id="name",
            type="text",
            label="Your Name",
            placeholder="Enter your name",
            required=True,
        )
        assert field.id == "name"
        assert field.type == "text"
        assert field.required is True

    def test_all_field_types(self):
        """Test all 10 field types are valid."""
        field_types = [
            "text",
            "textarea",
            "select",
            "checkbox",
            "radio",
            "date",
            "slider",
            "file",
            "number",
            "email",
        ]
        for field_type in field_types:
            field = FormField(id="test", type=field_type, label="Test")
            assert field.type == field_type

    def test_invalid_field_type_rejected(self):
        """Test invalid field type is rejected."""
        with pytest.raises(ValidationError):
            FormField(id="test", type="invalid", label="Test")  # type: ignore

    def test_select_field_with_options(self):
        """Test select field with options."""
        field = FormField(
            id="country",
            type="select",
            label="Country",
            options=[
                FormFieldOption(label="USA", value="us"),
                FormFieldOption(label="UK", value="uk"),
            ],
        )
        assert len(field.options) == 2

    def test_slider_field_with_range(self):
        """Test slider field with min/max/step."""
        field = FormField(
            id="rating",
            type="slider",
            label="Rating",
            min=1,
            max=10,
            step=1,
            defaultValue=5,
        )
        assert field.min == 1
        assert field.max == 10
        assert field.step == 1


class TestGenerateFormArgs:
    """Tests for GenerateFormArgs model."""

    def test_basic_form(self):
        """Test basic form creation."""
        form = GenerateFormArgs(
            title="Contact Us",
            fields=[
                FormField(id="name", type="text", label="Name"),
                FormField(id="email", type="email", label="Email"),
            ],
        )
        assert form.type == "form"
        assert form.title == "Contact Us"
        assert len(form.fields) == 2

    def test_form_with_description(self):
        """Test form with description and submit label."""
        form = GenerateFormArgs(
            title="Feedback",
            description="Please provide your feedback",
            fields=[FormField(id="feedback", type="textarea", label="Feedback")],
            submitLabel="Send Feedback",
        )
        assert form.description == "Please provide your feedback"
        assert form.submitLabel == "Send Feedback"


class TestChartDataPoint:
    """Tests for ChartDataPoint model."""

    def test_data_point(self):
        """Test data point creation."""
        point = ChartDataPoint(label="January", value=100.5)
        assert point.label == "January"
        assert point.value == 100.5

    def test_negative_value(self):
        """Test negative values are valid."""
        point = ChartDataPoint(label="Loss", value=-50.0)
        assert point.value == -50.0


class TestGenerateChartArgs:
    """Tests for GenerateChartArgs model."""

    def test_line_chart(self):
        """Test line chart creation."""
        chart = GenerateChartArgs(
            chartType="line",
            title="Sales Trend",
            data=[
                ChartDataPoint(label="Q1", value=100),
                ChartDataPoint(label="Q2", value=150),
            ],
        )
        assert chart.type == "chart"
        assert chart.chartType == "line"

    def test_all_chart_types(self):
        """Test all chart types are valid."""
        for chart_type in ["line", "bar", "pie", "area"]:
            chart = GenerateChartArgs(
                chartType=chart_type,  # type: ignore
                title="Test",
                data=[ChartDataPoint(label="A", value=1)],
            )
            assert chart.chartType == chart_type

    def test_invalid_chart_type_rejected(self):
        """Test invalid chart type is rejected."""
        with pytest.raises(ValidationError):
            GenerateChartArgs(
                chartType="scatter",  # type: ignore
                title="Test",
                data=[],
            )


class TestGenerateCodeArgs:
    """Tests for GenerateCodeArgs model."""

    def test_basic_code(self):
        """Test basic code block creation."""
        code = GenerateCodeArgs(
            language="python",
            code="print('Hello, World!')",
        )
        assert code.type == "code"
        assert code.language == "python"
        assert "Hello" in code.code

    def test_code_with_options(self):
        """Test code block with all options."""
        code = GenerateCodeArgs(
            language="typescript",
            filename="app.ts",
            code="const x = 1;",
            editable=True,
            showLineNumbers=True,
        )
        assert code.filename == "app.ts"
        assert code.editable is True
        assert code.showLineNumbers is True


class TestCardMedia:
    """Tests for CardMedia model."""

    def test_image_media(self):
        """Test image media creation."""
        media = CardMedia(
            type="image",
            url="https://example.com/image.jpg",
            alt="Example image",
        )
        assert media.type == "image"
        assert media.alt == "Example image"

    def test_video_media(self):
        """Test video media creation."""
        media = CardMedia(
            type="video",
            url="https://example.com/video.mp4",
        )
        assert media.type == "video"

    def test_invalid_media_type_rejected(self):
        """Test invalid media type is rejected."""
        with pytest.raises(ValidationError):
            CardMedia(type="audio", url="https://example.com/audio.mp3")  # type: ignore


class TestCardAction:
    """Tests for CardAction model."""

    def test_basic_action(self):
        """Test basic action creation."""
        action = CardAction(label="Learn More", action="navigate_to_page")
        assert action.label == "Learn More"
        assert action.action == "navigate_to_page"

    def test_action_variants(self):
        """Test all action variants."""
        for variant in ["default", "secondary", "destructive", "outline"]:
            action = CardAction(
                label="Test",
                action="test_action",
                variant=variant,  # type: ignore
            )
            assert action.variant == variant


class TestGenerateCardArgs:
    """Tests for GenerateCardArgs model."""

    def test_basic_card(self):
        """Test basic card creation."""
        card = GenerateCardArgs(title="Welcome")
        assert card.type == "card"
        assert card.title == "Welcome"

    def test_full_card(self):
        """Test card with all fields."""
        card = GenerateCardArgs(
            title="Product",
            description="Great product",
            content="Detailed description...",
            media=CardMedia(type="image", url="https://example.com/img.jpg"),
            actions=[
                CardAction(label="Buy", action="purchase", variant="default"),
                CardAction(label="Learn More", action="details", variant="secondary"),
            ],
        )
        assert card.description == "Great product"
        assert card.media.url == "https://example.com/img.jpg"
        assert len(card.actions) == 2


class TestToolConstants:
    """Tests for tool constants."""

    def test_supported_tools(self):
        """Test all expected tools are supported."""
        assert TOOL_GENERATE_FORM in SUPPORTED_TOOLS
        assert TOOL_GENERATE_CHART in SUPPORTED_TOOLS
        assert TOOL_GENERATE_CODE in SUPPORTED_TOOLS
        assert TOOL_GENERATE_CARD in SUPPORTED_TOOLS
        assert len(SUPPORTED_TOOLS) == 4

    def test_tool_arg_models(self):
        """Test tool argument models are mapped correctly."""
        assert TOOL_ARG_MODELS[TOOL_GENERATE_FORM] == GenerateFormArgs
        assert TOOL_ARG_MODELS[TOOL_GENERATE_CHART] == GenerateChartArgs
        assert TOOL_ARG_MODELS[TOOL_GENERATE_CODE] == GenerateCodeArgs
        assert TOOL_ARG_MODELS[TOOL_GENERATE_CARD] == GenerateCardArgs
