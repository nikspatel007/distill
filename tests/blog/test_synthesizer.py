"""Tests for blog synthesizer (mocked subprocess)."""

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
        projects=["vermas"],
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
    @patch("distill.blog.synthesizer.subprocess.run")
    def test_weekly_synthesis(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="# Week in Review\n\nGreat week of progress...",
            stderr="",
        )
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        result = synthesizer.synthesize_weekly(_make_weekly_context())

        assert "Week in Review" in result
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_thematic_synthesis(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="# Deep Dive\n\nExploring the theme...",
            stderr="",
        )
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        result = synthesizer.synthesize_thematic(_make_thematic_context())

        assert "Deep Dive" in result
        mock_run.assert_called_once()

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_passes_model_flag(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Prose", stderr=""
        )
        config = BlogConfig(model="claude-sonnet-4-5-20250929")
        synthesizer = BlogSynthesizer(config)
        synthesizer.synthesize_weekly(_make_weekly_context())

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-sonnet-4-5-20250929" in cmd

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_no_model_flag_by_default(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Prose", stderr=""
        )
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)
        synthesizer.synthesize_weekly(_make_weekly_context())

        cmd = mock_run.call_args[0][0]
        assert "--model" not in cmd

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_cli_not_found(self, mock_run: MagicMock):
        mock_run.side_effect = FileNotFoundError()
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)

        with pytest.raises(BlogSynthesisError, match="not found"):
            synthesizer.synthesize_weekly(_make_weekly_context())

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_cli_timeout(self, mock_run: MagicMock):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=180)
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)

        with pytest.raises(BlogSynthesisError, match="timed out"):
            synthesizer.synthesize_weekly(_make_weekly_context())

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_cli_nonzero_exit(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="API error"
        )
        config = BlogConfig()
        synthesizer = BlogSynthesizer(config)

        with pytest.raises(BlogSynthesisError, match="exited 1"):
            synthesizer.synthesize_thematic(_make_thematic_context())

    @patch("distill.blog.synthesizer.subprocess.run")
    def test_uses_configured_timeout(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="prose", stderr=""
        )
        config = BlogConfig(claude_timeout=300)
        synthesizer = BlogSynthesizer(config)
        synthesizer.synthesize_weekly(_make_weekly_context())

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 300
