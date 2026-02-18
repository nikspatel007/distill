"""Tests for LinkedIn intake publisher."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.linkedin import (
    LINKEDIN_SYSTEM_PROMPT,
    LinkedInIntakePublisher,
)
from distill.llm import LLMError


def _ctx() -> DailyIntakeContext:
    return DailyIntakeContext(
        date=date(2026, 2, 7),
        total_items=5,
        total_word_count=1500,
        sources=["rss"],
        sites=["Blog A", "Blog B"],
        all_tags=["python", "ai"],
        combined_text="Combined text here.",
    )


class TestLinkedInIntakePublisher:
    def test_requires_llm_attribute(self):
        pub = LinkedInIntakePublisher()
        assert pub.requires_llm is True

    def test_daily_output_path(self):
        pub = LinkedInIntakePublisher()
        path = pub.daily_output_path(Path("/out"), date(2026, 2, 7))
        assert path == Path("/out/intake/social/linkedin/linkedin-2026-02-07.md")

    def test_daily_output_path_different_date(self):
        pub = LinkedInIntakePublisher()
        path = pub.daily_output_path(Path("/output"), date(2025, 12, 31))
        assert path == Path("/output/intake/social/linkedin/linkedin-2025-12-31.md")

    @patch("distill.llm.call_claude")
    def test_format_daily_calls_claude(self, mock_call):
        mock_call.return_value = "LinkedIn post content here"
        pub = LinkedInIntakePublisher()
        result = pub.format_daily(_ctx(), "Daily digest prose.")

        assert result == "LinkedIn post content here"
        mock_call.assert_called_once()

        args = mock_call.call_args[0]
        assert LINKEDIN_SYSTEM_PROMPT in args[0]
        assert "Daily digest prose." in args[1]

    @patch("distill.llm.call_claude")
    def test_format_daily_prompt_structure(self, mock_call):
        mock_call.return_value = "Post output"
        pub = LinkedInIntakePublisher()
        pub.format_daily(_ctx(), "Some digest prose.")

        args = mock_call.call_args[0]
        assert LINKEDIN_SYSTEM_PROMPT in args[0]
        assert "Some digest prose." in args[1]

    @patch("distill.llm.call_claude")
    def test_format_daily_llm_error(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI failed (exit 1): Error")
        pub = LinkedInIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")

        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_file_not_found(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI not found")
        pub = LinkedInIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")

        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_timeout(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI timed out after 120s")
        pub = LinkedInIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")

        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_returns_output(self, mock_call):
        mock_call.return_value = "LinkedIn post"
        pub = LinkedInIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")

        assert result == "LinkedIn post"
