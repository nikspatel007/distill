"""Tests for intake context assembly."""

from __future__ import annotations

from datetime import date, datetime, timezone

from distill.intake.context import DailyIntakeContext, prepare_daily_context
from distill.intake.models import ContentItem, ContentSource


def _item(title: str, site: str = "Blog", **kw) -> ContentItem:
    return ContentItem(
        id=title[:8],
        title=title,
        body=f"Body of {title} with enough words to pass filters easily.",
        word_count=10,
        site_name=site,
        source=ContentSource.RSS,
        **kw,
    )


class TestPrepareDailyContext:
    def test_basic(self):
        items = [_item("Post A"), _item("Post B", site="Other Blog")]
        ctx = prepare_daily_context(items, target_date=date(2026, 2, 7))

        assert ctx.date == date(2026, 2, 7)
        assert ctx.total_items == 2
        assert ctx.total_word_count == 20
        assert "rss" in ctx.sources
        assert "Blog" in ctx.sites
        assert "Other Blog" in ctx.sites

    def test_defaults_to_today(self):
        ctx = prepare_daily_context([_item("X")])
        assert ctx.date == date.today()

    def test_combined_text_has_titles(self):
        items = [_item("Alpha Article"), _item("Beta Article")]
        ctx = prepare_daily_context(items)
        assert "Alpha Article" in ctx.combined_text
        assert "Beta Article" in ctx.combined_text

    def test_unique_sources(self):
        items = [_item("A"), _item("B"), _item("C")]
        ctx = prepare_daily_context(items)
        assert ctx.sources == ["rss"]

    def test_unique_sites(self):
        items = [_item("A", site="X"), _item("B", site="X")]
        ctx = prepare_daily_context(items)
        assert ctx.sites == ["X"]

    def test_tags_collected(self):
        items = [
            _item("A", tags=["python", "ai"]),
            _item("B", tags=["ai", "rust"]),
        ]
        ctx = prepare_daily_context(items)
        assert "python" in ctx.all_tags
        assert "ai" in ctx.all_tags
        assert "rust" in ctx.all_tags
        # No duplicates
        assert len([t for t in ctx.all_tags if t == "ai"]) == 1

    def test_empty(self):
        ctx = prepare_daily_context([])
        assert ctx.total_items == 0
        assert ctx.combined_text == ""

    def test_long_body_truncated(self):
        long_body = "word " * 1000  # 5000 chars
        items = [ContentItem(
            id="long",
            title="Long Article",
            body=long_body,
            word_count=1000,
            source=ContentSource.RSS,
        )]
        ctx = prepare_daily_context(items)
        assert "[... truncated]" in ctx.combined_text
