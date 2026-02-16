"""Tests for blog synthesizer (mocked LLM)."""

import subprocess
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from distill.blog.config import BlogConfig
from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.reader import JournalEntry
from distill.blog.synthesizer import BlogSynthesisError, BlogSynthesizer
from distill.blog.themes import ThemeDefinition


def _make_weekly_context() -> WeeklyBlogContext:
    return WeeklyBlogContext(
        year=2026,
        week=6,
        week_start=date(2026, 2, 2),
        week_end=date(2026, 2, 8),
        entries=[
            JournalEntry(date=date(2026, 2, 3), prose="Monday work."),
            JournalEntry(date=date(2026, 2, 5), prose="Wednesday work."),
        ],
        total_sessions=10,
        total_duration_minutes=200,
        projects=["distill"],
        combined_prose="Combined prose here.",
    )


def _make_thematic_context() -> ThematicBlogContext:
    return ThematicBlogContext(
        theme=ThemeDefinition(
            slug="test-theme",
            title="Test Theme Title",
            keywords=["test"],
            thread_patterns=[],
        ),
        evidence_entries=[
            JournalEntry(date=date(2026, 2, 3), prose="Evidence."),
        ],
        date_range=(date(2026, 2, 1), date(2026, 2, 5)),
        evidence_count=1,
        combined_evidence="Combined evidence here.",
    )


class TestBlogSynthesizer:
    @patch("distill.llm.call_claude")
    def test_weekly_synthesis(self, mock_call: MagicMock):
        mock_call.return_value = "# Week in Review\n\nGreat week of progress..."
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        result = synthesizer.synthesize_weekly(_make_weekly_context())

        assert "Week in Review" in result
        mock_call.assert_called_once()

    @patch("distill.llm.call_claude")
    def test_thematic_synthesis(self, mock_call: MagicMock):
        mock_call.return_value = "# Deep Dive\n\nExploring the theme..."
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        result = synthesizer.synthesize_thematic(_make_thematic_context())

        assert "Deep Dive" in result
        mock_call.assert_called_once()

    @patch("distill.llm.call_claude")
    def test_passes_model_flag(self, mock_call: MagicMock):
        mock_call.return_value = "Prose"
        config = BlogConfig(model="claude-sonnet-4-5-20250929")
        synthesizer = BlogSynthesizer(config)
        synthesizer.synthesize_weekly(_make_weekly_context())

        _, kwargs = mock_call.call_args
        assert kwargs["model"] == "claude-sonnet-4-5-20250929"

    @patch("distill.llm.call_claude")
    def test_no_model_flag_by_default(self, mock_call: MagicMock):
        mock_call.return_value = "Prose"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        synthesizer.synthesize_weekly(_make_weekly_context())

        _, kwargs = mock_call.call_args
        assert kwargs["model"] is None

    @patch("distill.llm.call_claude")
    def test_cli_not_found(self, mock_call: MagicMock):
        from distill.llm import LLMError

        mock_call.side_effect = LLMError("Claude CLI not found")
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)

        with pytest.raises(BlogSynthesisError, match="not found"):
            synthesizer.synthesize_weekly(_make_weekly_context())

    @patch("distill.llm.call_claude")
    def test_cli_timeout(self, mock_call: MagicMock):
        from distill.llm import LLMError

        mock_call.side_effect = LLMError("Claude CLI timed out after 360s")
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)

        with pytest.raises(BlogSynthesisError, match="timed out"):
            synthesizer.synthesize_weekly(_make_weekly_context())

    @patch("distill.llm.call_claude")
    def test_cli_nonzero_exit(self, mock_call: MagicMock):
        from distill.llm import LLMError

        mock_call.side_effect = LLMError("Claude CLI failed (exit 1, label=test): API error")
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)

        with pytest.raises(BlogSynthesisError, match="exit 1"):
            synthesizer.synthesize_thematic(_make_thematic_context())

    @patch("distill.llm.call_claude")
    def test_uses_configured_timeout(self, mock_call: MagicMock):
        mock_call.return_value = "prose"
        config = BlogConfig(claude_timeout=300)
        synthesizer = BlogSynthesizer(config)
        synthesizer.synthesize_weekly(_make_weekly_context())

        _, kwargs = mock_call.call_args
        assert kwargs["timeout"] == 300

    @patch("distill.llm.call_claude")
    def test_adapt_for_platform_calls_claude_with_social_prompt(self, mock_call: MagicMock):
        mock_call.return_value = "1/ Great thread hook..."
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        synthesizer.adapt_for_platform("Blog prose here", "twitter", "weekly-W06")

        mock_call.assert_called_once()
        args = mock_call.call_args[0]
        system_prompt = args[0]
        assert "Twitter/X thread" in system_prompt

    @patch("distill.llm.call_claude")
    def test_adapt_for_platform_returns_output(self, mock_call: MagicMock):
        mock_call.return_value = "1/ Hook tweet\n2/ Detail tweet"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        result = synthesizer.adapt_for_platform("Blog prose", "twitter", "weekly-W06")

        assert "1/ Hook tweet" in result

    @patch("distill.llm.call_claude")
    def test_extract_blog_memory_parses_json(self, mock_call: MagicMock):
        mock_call.return_value = '{"key_points": ["point 1", "point 2"], "themes_covered": ["agents"]}'
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        summary = synthesizer.extract_blog_memory(
            "Blog prose", "weekly-W06", "Week 6 Post", "weekly"
        )

        assert summary.slug == "weekly-W06"
        assert summary.title == "Week 6 Post"
        assert summary.post_type == "weekly"
        assert summary.key_points == ["point 1", "point 2"]
        assert summary.themes_covered == ["agents"]
        assert summary.platforms_published == []

    @patch("distill.llm.call_claude")
    def test_extract_blog_memory_handles_bad_json(self, mock_call: MagicMock):
        mock_call.return_value = "not valid json at all"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        summary = synthesizer.extract_blog_memory(
            "Blog prose", "weekly-W06", "Week 6 Post", "weekly"
        )

        assert summary.slug == "weekly-W06"
        assert summary.key_points == []
        assert summary.themes_covered == []

    @patch("distill.llm.call_claude")
    def test_synthesize_weekly_with_blog_memory(self, mock_call: MagicMock):
        mock_call.return_value = "# Post with memory"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        memory_text = "## Previous Blog Posts\n\n- Some older post"
        result = synthesizer.synthesize_weekly(
            _make_weekly_context(), blog_memory=memory_text
        )

        assert "Post with memory" in result
        args = mock_call.call_args[0]
        system_prompt = args[0]
        assert "Previous Blog Posts" in system_prompt

    @patch("distill.llm.call_claude")
    def test_weekly_prompt_includes_project_context(self, mock_call: MagicMock):
        mock_call.return_value = "# Post"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        ctx = _make_weekly_context()
        ctx.project_context = "## Project Context\n\n**Distill**: Content pipeline"
        synthesizer.synthesize_weekly(ctx)

        args = mock_call.call_args[0]
        user_prompt = args[1]
        assert "**Distill**: Content pipeline" in user_prompt

    @patch("distill.llm.call_claude")
    def test_weekly_prompt_includes_editorial_notes(self, mock_call: MagicMock):
        mock_call.return_value = "# Post"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        ctx = _make_weekly_context()
        ctx.editorial_notes = "## Editorial Direction\n\n- Focus on fan-in pattern"
        synthesizer.synthesize_weekly(ctx)

        args = mock_call.call_args[0]
        user_prompt = args[1]
        assert "Focus on fan-in pattern" in user_prompt

    @patch("distill.llm.call_claude")
    def test_thematic_prompt_includes_project_context(self, mock_call: MagicMock):
        mock_call.return_value = "# Post"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        ctx = _make_thematic_context()
        ctx.project_context = "## Project Context\n\n**Distill**: Content pipeline"
        synthesizer.synthesize_thematic(ctx)

        args = mock_call.call_args[0]
        user_prompt = args[1]
        assert "**Distill**: Content pipeline" in user_prompt

    @patch("distill.llm.call_claude")
    def test_adapt_for_platform_with_editorial_hint(self, mock_call: MagicMock):
        mock_call.return_value = "1/ Adapted thread"
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        synthesizer.adapt_for_platform(
            "Blog prose", "twitter", "weekly-W06",
            editorial_hint="Emphasize the fan-in pattern"
        )

        args = mock_call.call_args[0]
        user_prompt = args[1]
        assert "EDITORIAL DIRECTION: Emphasize the fan-in pattern" in user_prompt
