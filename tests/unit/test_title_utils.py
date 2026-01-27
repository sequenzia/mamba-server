"""Tests for title utility functions."""

import pytest

from mamba.core.title_utils import clean_title, truncate_at_word_boundary


class TestTruncateAtWordBoundary:
    """Tests for truncate_at_word_boundary function."""

    def test_short_text_unchanged(self):
        """Test short text is returned unchanged."""
        text = "Short title"
        result = truncate_at_word_boundary(text, 50)
        assert result == "Short title"

    def test_exact_max_length_unchanged(self):
        """Test text at exact max_length is unchanged."""
        text = "Exactly twenty chars"
        result = truncate_at_word_boundary(text, 20)
        assert result == text

    def test_truncate_at_word_boundary(self):
        """Test truncation occurs at word boundary."""
        text = "This is a longer title that needs truncation at word boundary"
        result = truncate_at_word_boundary(text, 30)
        # Should truncate at word boundary and add "..."
        assert result.endswith("...")
        assert len(result) <= 33  # 30 + 3 for "..."
        assert " " not in result[-4:]  # No space before "..."

    def test_truncate_uses_word_boundary_in_last_40_percent(self):
        """Test truncation uses word boundary if in last 40% of text."""
        # With max_length=50, last 40% starts at position 30
        # So word boundary must be after position 30 to be used
        text = "This is a test string with spaces evenly distributed here"
        result = truncate_at_word_boundary(text, 50)
        assert result.endswith("...")
        # Should end at a word boundary
        without_ellipsis = result[:-3]
        assert without_ellipsis == without_ellipsis.rstrip()

    def test_hard_truncate_no_good_boundary(self):
        """Test hard truncate when no good word boundary found."""
        # Single long word - no spaces to break on
        text = "Thisisaverylongwordwithoutanyspacesinit"
        result = truncate_at_word_boundary(text, 20)
        assert result == "Thisisaverylongwo..."
        assert len(result) == 20

    def test_empty_string_returned_for_empty_input(self):
        """Test empty string is returned unchanged."""
        result = truncate_at_word_boundary("", 50)
        assert result == ""

    def test_single_character_unchanged_when_under_limit(self):
        """Test single character is unchanged when under limit."""
        result = truncate_at_word_boundary("a", 50)
        assert result == "a"

    def test_max_length_zero_returns_empty(self):
        """Test max_length of 0 returns empty string."""
        result = truncate_at_word_boundary("Some text", 0)
        assert result == ""

    def test_negative_max_length_returns_empty(self):
        """Test negative max_length returns empty string."""
        result = truncate_at_word_boundary("Some text", -5)
        assert result == ""

    def test_truncation_preserves_leading_content(self):
        """Test truncation preserves content from the start."""
        text = "The quick brown fox jumps over the lazy dog"
        result = truncate_at_word_boundary(text, 20)
        assert result.startswith("The quick")


class TestCleanTitle:
    """Tests for clean_title function."""

    def test_strips_whitespace(self):
        """Test leading and trailing whitespace is stripped."""
        result = clean_title("  Hello World  ", 50)
        assert result == "Hello World"

    def test_removes_double_quotes(self):
        """Test surrounding double quotes are removed."""
        result = clean_title('"Hello World"', 50)
        assert result == "Hello World"

    def test_removes_single_quotes(self):
        """Test surrounding single quotes are removed."""
        result = clean_title("'Hello World'", 50)
        assert result == "Hello World"

    def test_only_removes_outermost_quotes(self):
        """Test only outermost quotes are removed."""
        result = clean_title('"\'Hello World\'"', 50)
        assert result == "'Hello World'"

    def test_handles_whitespace_and_quotes(self):
        """Test whitespace is stripped before quote removal."""
        result = clean_title('  "Hello World"  ', 50)
        assert result == "Hello World"

    def test_applies_truncation(self):
        """Test truncation is applied after cleaning."""
        long_title = '"This is a very long title that exceeds the maximum length allowed"'
        result = clean_title(long_title, 30)
        assert len(result) <= 33  # Account for "..."
        assert result.endswith("...")

    def test_empty_string_returns_empty(self):
        """Test empty string returns empty."""
        result = clean_title("", 50)
        assert result == ""

    def test_whitespace_only_returns_empty(self):
        """Test whitespace-only string returns empty after strip."""
        result = clean_title("   ", 50)
        assert result == ""

    def test_single_char_unchanged(self):
        """Test single character is unchanged."""
        result = clean_title("a", 50)
        assert result == "a"

    def test_mismatched_quotes_not_removed(self):
        """Test mismatched quotes are not removed."""
        result = clean_title('"Hello World\'', 50)
        assert result == '"Hello World\''

    def test_quotes_only_returns_empty(self):
        """Test quotes-only string returns empty after cleaning."""
        result = clean_title('""', 50)
        assert result == ""

    def test_single_quote_pair_returns_empty(self):
        """Test single quote pair returns empty after cleaning."""
        result = clean_title("''", 50)
        assert result == ""

    def test_internal_quotes_preserved(self):
        """Test internal quotes are preserved."""
        result = clean_title('Hello "World"', 50)
        assert result == 'Hello "World"'

    def test_unicode_content_preserved(self):
        """Test unicode content is preserved."""
        result = clean_title('"こんにちは世界"', 50)
        assert result == "こんにちは世界"

    def test_combines_all_cleaning_steps(self):
        """Test all cleaning steps work together."""
        # Whitespace, quotes, and truncation
        title = '  "This is a really long title that should be truncated properly"  '
        result = clean_title(title, 30)
        # Should strip whitespace, remove quotes, and truncate
        assert not result.startswith('"')
        assert not result.startswith(" ")
        assert len(result) <= 33
