"""Tool schema definitions for AI chat tools."""

from typing import Literal

from pydantic import BaseModel


# === Form Tool Types ===


class FormFieldOption(BaseModel):
    """Option for select/radio form fields."""

    label: str
    value: str


class FormField(BaseModel):
    """Form field definition."""

    id: str
    type: Literal[
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
    label: str
    placeholder: str | None = None
    required: bool | None = None
    defaultValue: str | int | bool | None = None
    options: list[FormFieldOption] | None = None
    min: int | None = None
    max: int | None = None
    step: int | None = None


class GenerateFormArgs(BaseModel):
    """Arguments for generateForm tool."""

    type: Literal["form"] = "form"
    title: str
    description: str | None = None
    fields: list[FormField]
    submitLabel: str | None = None


# === Chart Tool Types ===


class ChartDataPoint(BaseModel):
    """Data point for charts."""

    label: str
    value: float


class GenerateChartArgs(BaseModel):
    """Arguments for generateChart tool."""

    type: Literal["chart"] = "chart"
    chartType: Literal["line", "bar", "pie", "area"]
    title: str
    description: str | None = None
    data: list[ChartDataPoint]


# === Code Tool Types ===


class GenerateCodeArgs(BaseModel):
    """Arguments for generateCode tool."""

    type: Literal["code"] = "code"
    language: str
    filename: str | None = None
    code: str
    editable: bool | None = None
    showLineNumbers: bool | None = None


# === Card Tool Types ===


class CardMedia(BaseModel):
    """Media content for cards."""

    type: Literal["image", "video"]
    url: str
    alt: str | None = None


class CardAction(BaseModel):
    """Action button for cards."""

    label: str
    action: str
    variant: Literal["default", "secondary", "destructive", "outline"] | None = None


class GenerateCardArgs(BaseModel):
    """Arguments for generateCard tool."""

    type: Literal["card"] = "card"
    title: str
    description: str | None = None
    content: str | None = None
    media: CardMedia | None = None
    actions: list[CardAction] | None = None


# === Tool Definitions ===

# Tool names for reference
TOOL_GENERATE_FORM = "generateForm"
TOOL_GENERATE_CHART = "generateChart"
TOOL_GENERATE_CODE = "generateCode"
TOOL_GENERATE_CARD = "generateCard"

# All supported tools
SUPPORTED_TOOLS = [
    TOOL_GENERATE_FORM,
    TOOL_GENERATE_CHART,
    TOOL_GENERATE_CODE,
    TOOL_GENERATE_CARD,
]

# Map tool names to their argument models
TOOL_ARG_MODELS = {
    TOOL_GENERATE_FORM: GenerateFormArgs,
    TOOL_GENERATE_CHART: GenerateChartArgs,
    TOOL_GENERATE_CODE: GenerateCodeArgs,
    TOOL_GENERATE_CARD: GenerateCardArgs,
}
