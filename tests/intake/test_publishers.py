"""Tests for intake publishers."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers import create_intake_publisher
from distill.intake.publishers.markdown import MarkdownIntakePublisher
from distill.intake.publishers.obsidian import (
    ObsidianIntakePublisher,
    _extract_int,
    _extract_list,
    _strip_frontmatter,
)


def _ctx(**overrides) -> DailyIntakeContext:
    defaults = dict(
        date=date(2026, 2, 7),
        total_items=5,
        total_word_count=1500,
        sources=["rss"],
        sites=["Blog A", "Blog B"],
        all_tags=["python", "ai"],
        combined_text="Combined text here.",
    )
    defaults.update(overrides)
    return DailyIntakeContext(**defaults)


class TestObsidianIntakePublisher:
    def test_format_daily(self):
        pub = ObsidianIntakePublisher()
        with patch("distill.intake.publishers.obsidian.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "08:00"
            result = pub.format_daily(_ctx(), "Daily digest prose.")
        assert "---" in result
        assert "date: 2026-02-07" in result
        assert "type: intake-digest" in result
        assert "items: 5" in result
        assert "## Update — 08:00" in result
        assert "Daily digest prose." in result

    def test_format_daily_includes_timestamp(self):
        pub = ObsidianIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert "## Update —" in result

    def test_daily_output_path(self):
        pub = ObsidianIntakePublisher()
        from pathlib import Path

        path = pub.daily_output_path(Path("/out"), date(2026, 2, 7))
        assert path == Path("/out/intake/intake-2026-02-07.md")

    def test_tags_in_frontmatter(self):
        pub = ObsidianIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        assert "python" in result
        assert "ai" in result

    def test_merge_daily_appends_content(self):
        pub = ObsidianIntakePublisher()
        existing = (
            "---\ndate: 2026-02-07\ntype: intake-digest\n"
            "items: 5\nword_count: 1500\nsources: [rss]\ntags: [python, ai]\n---\n"
            "## Update — 08:00\n\nMorning prose.\n"
        )
        evening_ctx = _ctx(total_items=3, total_word_count=800, sources=["rss", "email"], all_tags=["ai", "llm"])
        with patch("distill.intake.publishers.obsidian.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "18:00"
            result = pub.merge_daily(existing, evening_ctx, "Evening prose.")

        # Frontmatter has cumulative stats
        assert "items: 8" in result
        assert "word_count: 2300" in result
        # Sources are unioned
        assert "rss" in result
        assert "email" in result
        # Tags are unioned
        assert "python" in result
        assert "ai" in result
        assert "llm" in result
        # Both sections present
        assert "Morning prose." in result
        assert "## Update — 18:00" in result
        assert "Evening prose." in result
        # Divider between sections
        assert "---\n\n## Update — 18:00" in result

    def test_merge_daily_preserves_multiple_runs(self):
        """Three runs in a day should all be preserved."""
        pub = ObsidianIntakePublisher()
        # First run
        with patch("distill.intake.publishers.obsidian.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "06:00"
            first = pub.format_daily(_ctx(total_items=2, total_word_count=500), "Morning.")
        # Second run
        with patch("distill.intake.publishers.obsidian.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "12:00"
            second = pub.merge_daily(first, _ctx(total_items=3, total_word_count=700), "Midday.")
        # Third run
        with patch("distill.intake.publishers.obsidian.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "18:00"
            third = pub.merge_daily(second, _ctx(total_items=4, total_word_count=900), "Evening.")

        assert "items: 9" in third  # 2 + 3 + 4
        assert "word_count: 2100" in third  # 500 + 700 + 900
        assert "Morning." in third
        assert "Midday." in third
        assert "Evening." in third
        assert "## Update — 06:00" in third
        assert "## Update — 12:00" in third
        assert "## Update — 18:00" in third


class TestFrontmatterHelpers:
    def test_extract_int(self):
        content = "---\nitems: 42\nword_count: 1500\n---\n"
        assert _extract_int(content, "items") == 42
        assert _extract_int(content, "word_count") == 1500

    def test_extract_int_missing(self):
        assert _extract_int("no frontmatter", "items") == 0

    def test_extract_list(self):
        content = "---\nsources: [rss, email]\ntags: [python, ai, llm]\n---\n"
        assert _extract_list(content, "sources") == ["rss", "email"]
        assert _extract_list(content, "tags") == ["python", "ai", "llm"]

    def test_extract_list_missing(self):
        assert _extract_list("no frontmatter", "sources") == []

    def test_extract_list_empty(self):
        assert _extract_list("---\nsources: []\n---\n", "sources") == []

    def test_strip_frontmatter(self):
        content = "---\ndate: 2026-02-07\n---\nBody here."
        assert _strip_frontmatter(content) == "Body here."

    def test_strip_frontmatter_no_frontmatter(self):
        assert _strip_frontmatter("Just text.") == "Just text."


class TestMarkdownIntakePublisher:
    def test_format_daily(self):
        pub = MarkdownIntakePublisher()
        result = pub.format_daily(_ctx(), "Daily digest.")
        assert "# Intake Digest" in result
        assert "2026-02-07" in result
        assert "5 items" in result
        assert "Daily digest." in result

    def test_daily_output_path(self):
        pub = MarkdownIntakePublisher()
        from pathlib import Path

        path = pub.daily_output_path(Path("/out"), date(2026, 2, 7))
        assert path == Path("/out/intake/markdown/intake-2026-02-07.md")


class TestPublisherFactory:
    def test_create_obsidian(self):
        pub = create_intake_publisher("obsidian")
        assert isinstance(pub, ObsidianIntakePublisher)

    def test_create_markdown(self):
        pub = create_intake_publisher("markdown")
        assert isinstance(pub, MarkdownIntakePublisher)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown intake publisher"):
            create_intake_publisher("nonexistent")
