"""Tests for the Twitter/X intake publisher."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.base import IntakePublisher
from distill.intake.publishers.twitter import (
    TWITTER_SYSTEM_PROMPT,
    TwitterIntakePublisher,
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


class TestTwitterIntakePublisher:
    def test_requires_llm_is_true(self):
        assert TwitterIntakePublisher.requires_llm is True

    def test_is_intake_publisher(self):
        assert issubclass(TwitterIntakePublisher, IntakePublisher)

    def test_daily_output_path(self):
        pub = TwitterIntakePublisher()
        path = pub.daily_output_path(Path("/out"), date(2026, 2, 7))
        assert path == Path("/out/intake/social/twitter/twitter-2026-02-07.md")

    def test_daily_output_path_different_date(self):
        pub = TwitterIntakePublisher()
        path = pub.daily_output_path(Path("/output"), date(2025, 12, 31))
        assert path == Path("/output/intake/social/twitter/twitter-2025-12-31.md")

    @patch("distill.llm.call_claude")
    def test_format_daily_calls_claude(self, mock_call: MagicMock):
        mock_call.return_value = "1/ Hook tweet\n\n2/ Second tweet\n\n3/ Final tweet with CTA"
        pub = TwitterIntakePublisher()
        result = pub.format_daily(_ctx(), "Some digest prose.")

        mock_call.assert_called_once()
        args = mock_call.call_args[0]
        assert TWITTER_SYSTEM_PROMPT in args[0]
        assert "Some digest prose." in args[1]
        assert result == "1/ Hook tweet\n\n2/ Second tweet\n\n3/ Final tweet with CTA"

    @patch("distill.llm.call_claude")
    def test_format_daily_returns_output(self, mock_call: MagicMock):
        mock_call.return_value = "1/ Thread content"
        pub = TwitterIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == "1/ Thread content"

    @patch("distill.llm.call_claude")
    def test_format_daily_returns_empty_on_llm_error(self, mock_call: MagicMock):
        mock_call.side_effect = LLMError("Claude CLI failed (exit 1): Error")
        pub = TwitterIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_returns_empty_on_file_not_found(self, mock_call: MagicMock):
        mock_call.side_effect = LLMError("Claude CLI not found")
        pub = TwitterIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_returns_empty_on_timeout(self, mock_call: MagicMock):
        mock_call.side_effect = LLMError("Claude CLI timed out after 120s")
        pub = TwitterIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_prompt_contains_system_and_prose(self, mock_call: MagicMock):
        mock_call.return_value = "1/ Thread"
        pub = TwitterIntakePublisher()
        pub.format_daily(_ctx(), "My digest content here.")

        args = mock_call.call_args[0]
        system_prompt = args[0]
        user_prompt = args[1]
        assert "Convert this daily research digest" in system_prompt
        assert "280 characters" in system_prompt
        assert "My digest content here." in user_prompt
