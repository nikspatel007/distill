"""Tests for the Reddit intake publisher."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.base import IntakePublisher
from distill.intake.publishers.reddit import REDDIT_SYSTEM_PROMPT, RedditIntakePublisher
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


class TestRedditIntakePublisher:
    def test_requires_llm_attribute(self):
        assert RedditIntakePublisher.requires_llm is True

    def test_is_intake_publisher(self):
        assert issubclass(RedditIntakePublisher, IntakePublisher)

    def test_daily_output_path(self):
        pub = RedditIntakePublisher()
        path = pub.daily_output_path(Path("/output"), date(2026, 2, 7))
        assert path == Path("/output/intake/social/reddit/reddit-2026-02-07.md")

    def test_daily_output_path_different_date(self):
        pub = RedditIntakePublisher()
        path = pub.daily_output_path(Path("/out"), date(2025, 12, 31))
        assert path == Path("/out/intake/social/reddit/reddit-2025-12-31.md")

    @patch("distill.llm.call_claude")
    def test_format_daily_calls_claude(self, mock_call: MagicMock):
        mock_call.return_value = "**TL;DR** Great stuff\n\nReddit post body."
        pub = RedditIntakePublisher()
        result = pub.format_daily(_ctx(), "Daily digest prose.")

        mock_call.assert_called_once()
        args = mock_call.call_args[0]
        assert REDDIT_SYSTEM_PROMPT in args[0]
        assert "Daily digest prose." in args[1]
        assert result == "**TL;DR** Great stuff\n\nReddit post body."

    @patch("distill.llm.call_claude")
    def test_format_daily_returns_output(self, mock_call: MagicMock):
        mock_call.return_value = "Reddit post with whitespace"
        pub = RedditIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == "Reddit post with whitespace"

    @patch("distill.llm.call_claude")
    def test_format_daily_llm_error_returns_empty(self, mock_call: MagicMock):
        mock_call.side_effect = LLMError("Claude CLI failed (exit 1): Error")
        pub = RedditIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_file_not_found_returns_empty(self, mock_call: MagicMock):
        mock_call.side_effect = LLMError("Claude CLI not found")
        pub = RedditIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == ""

    @patch("distill.llm.call_claude")
    def test_format_daily_timeout_returns_empty(self, mock_call: MagicMock):
        mock_call.side_effect = LLMError("Claude CLI timed out after 120s")
        pub = RedditIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert result == ""

    def test_system_prompt_contains_structure(self):
        assert "TL;DR" in REDDIT_SYSTEM_PROMPT
        assert "What I Read Today" in REDDIT_SYSTEM_PROMPT
        assert "Discussion question" in REDDIT_SYSTEM_PROMPT
        assert "r/programming" in REDDIT_SYSTEM_PROMPT
