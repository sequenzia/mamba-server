"""Utility functions for title processing."""


def truncate_at_word_boundary(text: str, max_length: int) -> str:
    """Truncate text at word boundary if it exceeds max_length.

    Args:
        text: The text to truncate.
        max_length: Maximum allowed length.

    Returns:
        The text unchanged if under max_length, or truncated at word boundary
        with "..." suffix. Hard truncates if no good word boundary found.
    """
    if max_length <= 0:
        return ""

    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    # If word boundary in last 40%, use it
    if last_space > max_length * 0.6:
        return truncated[:last_space] + "..."

    # Otherwise hard truncate (need room for "...")
    return truncated[: max_length - 3] + "..."


def clean_title(title: str, max_length: int) -> str:
    """Clean and normalize a generated title.

    Strips whitespace, removes surrounding quotes, and truncates if needed.

    Args:
        title: The raw title to clean.
        max_length: Maximum allowed length after cleaning.

    Returns:
        Cleaned and truncated title.
    """
    if not title:
        return ""

    # Strip leading/trailing whitespace
    cleaned = title.strip()

    # Remove surrounding quotes (only outermost pair)
    if len(cleaned) >= 2 and (
        (cleaned.startswith('"') and cleaned.endswith('"'))
        or (cleaned.startswith("'") and cleaned.endswith("'"))
    ):
        cleaned = cleaned[1:-1]

    # Apply truncation
    return truncate_at_word_boundary(cleaned, max_length)
