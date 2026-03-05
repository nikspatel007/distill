"""Tests for reading brief models."""
from distill.brief.models import DraftPost, ReadingBrief, ReadingHighlight


class TestReadingHighlight:
    def test_create_highlight(self):
        h = ReadingHighlight(
            title="Anthropic traces model reasoning",
            source="Anthropic Research",
            url="https://example.com/paper",
            summary="They mapped internal circuits. This matters because X.",
            tags=["interpretability", "ai"],
        )
        assert h.title == "Anthropic traces model reasoning"
        assert h.source == "Anthropic Research"
        assert len(h.tags) == 2

    def test_highlight_defaults(self):
        h = ReadingHighlight(
            title="Test", source="Test", summary="Test summary."
        )
        assert h.url == ""
        assert h.tags == []


class TestDraftPost:
    def test_create_draft(self):
        d = DraftPost(
            platform="linkedin",
            content="Post content here.",
            char_count=19,
            source_highlights=["Highlight 1"],
        )
        assert d.platform == "linkedin"
        assert d.char_count == 19

    def test_draft_defaults(self):
        d = DraftPost(platform="x", content="Tweet.")
        assert d.char_count == 0
        assert d.source_highlights == []


class TestReadingBrief:
    def test_create_brief(self):
        b = ReadingBrief(
            date="2026-03-05",
            highlights=[
                ReadingHighlight(
                    title="Test", source="Test", summary="Summary."
                )
            ],
        )
        assert b.date == "2026-03-05"
        assert len(b.highlights) == 1
        assert b.drafts == []

    def test_empty_brief(self):
        b = ReadingBrief(date="2026-03-05")
        assert b.highlights == []
        assert b.drafts == []
