"""Tests for intake publishers."""

from __future__ import annotations

from datetime import date

import pytest

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers import create_intake_publisher
from distill.intake.publishers.markdown import MarkdownIntakePublisher
from distill.intake.publishers.obsidian import ObsidianIntakePublisher


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


class TestObsidianIntakePublisher:
    def test_format_daily(self):
        pub = ObsidianIntakePublisher()
        result = pub.format_daily(_ctx(), "Daily digest prose.")
        assert "---" in result
        assert "date: 2026-02-07" in result
        assert "type: intake-digest" in result
        assert "items: 5" in result
        assert "Daily digest prose." in result

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


class TestExtractHighlights:
    def test_parses_highlights(self):
        from distill.intake.publishers.obsidian import _extract_highlights

        text = (
            "HIGHLIGHTS:\n"
            "- Agent memory speeds up orientation\n"
            "- RSS feeds beat social media for signal\n"
            "- Parsers need generosity\n"
            "\n"
            "# The Good Parser\n"
            "\n"
            "Full essay here."
        )
        highlights, prose = _extract_highlights(text)
        assert highlights == [
            "Agent memory speeds up orientation",
            "RSS feeds beat social media for signal",
            "Parsers need generosity",
        ]
        assert prose.startswith("# The Good Parser")

    def test_no_highlights_block(self):
        from distill.intake.publishers.obsidian import _extract_highlights

        text = "# Just an Essay\n\nNo highlights block here."
        highlights, prose = _extract_highlights(text)
        assert highlights == []
        assert prose == text

    def test_highlights_with_leading_whitespace(self):
        from distill.intake.publishers.obsidian import _extract_highlights

        text = "\n\nHIGHLIGHTS:\n- Item one\n- Item two\n\nEssay body."
        highlights, prose = _extract_highlights(text)
        assert len(highlights) == 2


class TestObsidianHighlights:
    def test_frontmatter_includes_highlights(self):
        pub = ObsidianIntakePublisher()
        prose = (
            "HIGHLIGHTS:\n"
            "- Key insight A\n"
            "- Key insight B\n"
            "\n"
            "# Essay Title\n"
            "\n"
            "Full essay here."
        )
        result = pub.format_daily(_ctx(), prose)
        assert "highlights:" in result
        assert '  - "Key insight A"' in result
        assert '  - "Key insight B"' in result
        # HIGHLIGHTS block should be stripped from body
        assert "HIGHLIGHTS:" not in result.split("---", 2)[2]

    def test_no_highlights_when_absent(self):
        pub = ObsidianIntakePublisher()
        result = pub.format_daily(_ctx(), "# Just Prose\n\nBody here.")
        frontmatter = result.split("---")[1]
        assert "highlights:" not in frontmatter


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
