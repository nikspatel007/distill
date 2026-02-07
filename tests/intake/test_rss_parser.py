"""Tests for RSS feed parser."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.intake.config import IntakeConfig, RSSConfig
from distill.intake.models import ContentSource, ContentType
from distill.intake.parsers.rss import RSSParser, _strip_html


# ── HTML stripping ──────────────────────────────────────────────────────

class TestStripHtml:
    def test_strips_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self):
        assert _strip_html("&amp; &lt; &gt; &quot; &#39;") == '& < > " \''

    def test_nbsp(self):
        assert _strip_html("foo&nbsp;bar") == "foo bar"

    def test_collapses_newlines(self):
        assert _strip_html("a\n\n\n\nb") == "a\n\nb"

    def test_empty(self):
        assert _strip_html("") == ""


# ── Feed URL resolution ────────────────────────────────────────────────

class TestResolveFeeds:
    def test_direct_feeds(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://a.com/feed", "https://b.com/feed"])
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == ["https://a.com/feed", "https://b.com/feed"]

    def test_deduplicates(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://a.com/feed", "https://a.com/feed"])
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == ["https://a.com/feed"]

    def test_strips_whitespace(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["  https://a.com/feed  "])
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == ["https://a.com/feed"]

    def test_reads_feeds_file(self, tmp_path):
        feeds_file = tmp_path / "feeds.txt"
        feeds_file.write_text(
            "# comment\nhttps://a.com/feed\n\nhttps://b.com/feed\n"
        )
        config = IntakeConfig(
            rss=RSSConfig(feeds_file=str(feeds_file))
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == ["https://a.com/feed", "https://b.com/feed"]

    def test_reads_opml(self, tmp_path):
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(
            '<?xml version="1.0"?>'
            "<opml><body>"
            '<outline xmlUrl="https://a.com/feed" />'
            '<outline xmlUrl="https://b.com/feed" />'
            "</body></opml>"
        )
        config = IntakeConfig(
            rss=RSSConfig(opml_file=str(opml_file))
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == ["https://a.com/feed", "https://b.com/feed"]

    def test_missing_feeds_file(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds_file="/nonexistent/feeds.txt")
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == []

    def test_missing_opml_file(self):
        config = IntakeConfig(
            rss=RSSConfig(opml_file="/nonexistent/feeds.opml")
        )
        parser = RSSParser(config=config)
        urls = parser._resolve_feed_urls()
        assert urls == []


# ── Entry conversion ───────────────────────────────────────────────────

def _make_feed_entry(**overrides):
    """Create a mock feedparser entry."""
    entry = {
        "title": "Test Article",
        "link": "https://example.com/article",
        "summary": "This is a test article about Python programming and stuff.",
        "author": "Test Author",
        "id": "guid-123",
        "published_parsed": time.gmtime(1707300000),
        "tags": [{"term": "python"}, {"term": "ai"}],
    }
    entry.update(overrides)

    class FeedEntry(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    return FeedEntry(entry)


class TestEntryConversion:
    def _make_parser(self, min_word_count=0):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://example.com/feed"]),
            min_word_count=min_word_count,
        )
        return RSSParser(config=config)

    def test_basic_conversion(self):
        parser = self._make_parser()
        entry = _make_feed_entry()
        item = parser._entry_to_item(entry, site_name="Example Blog")

        assert item is not None
        assert item.title == "Test Article"
        assert item.url == "https://example.com/article"
        assert item.author == "Test Author"
        assert item.site_name == "Example Blog"
        assert item.source == ContentSource.RSS
        assert item.content_type == ContentType.ARTICLE
        assert "python" in item.tags
        assert "ai" in item.tags
        assert item.source_id == "guid-123"

    def test_content_over_summary(self):
        parser = self._make_parser()
        entry = _make_feed_entry(
            content=[{"value": "<p>Full article content here with lots of words.</p>"}],
            summary="Short summary.",
        )
        item = parser._entry_to_item(entry)
        assert item is not None
        assert "Full article content" in item.body
        assert item.excerpt == "Short summary."

    def test_no_link_no_title_returns_none(self):
        parser = self._make_parser()
        entry = _make_feed_entry(title="", link="")
        item = parser._entry_to_item(entry)
        assert item is None

    def test_word_count(self):
        parser = self._make_parser()
        entry = _make_feed_entry(
            summary="one two three four five"
        )
        item = parser._entry_to_item(entry)
        assert item is not None
        assert item.word_count == 5

    def test_id_is_hash(self):
        parser = self._make_parser()
        entry = _make_feed_entry()
        item = parser._entry_to_item(entry)
        assert item is not None
        assert len(item.id) == 16  # sha256[:16]

    def test_stable_id(self):
        parser = self._make_parser()
        entry = _make_feed_entry()
        item1 = parser._entry_to_item(entry)
        item2 = parser._entry_to_item(entry)
        assert item1.id == item2.id

    def test_published_at_parsed(self):
        parser = self._make_parser()
        entry = _make_feed_entry()
        item = parser._entry_to_item(entry)
        assert item is not None
        assert item.published_at is not None
        assert item.published_at.tzinfo == timezone.utc

    def test_no_date(self):
        parser = self._make_parser()
        entry = _make_feed_entry()
        del entry["published_parsed"]
        item = parser._entry_to_item(entry)
        assert item is not None
        assert item.published_at is None

    def test_feed_url_in_metadata(self):
        parser = self._make_parser()
        entry = _make_feed_entry()
        item = parser._entry_to_item(entry, feed_url="https://example.com/feed")
        assert item is not None
        assert item.metadata["feed_url"] == "https://example.com/feed"


# ── Feed parsing ───────────────────────────────────────────────────────

class TestParseFeed:
    def test_parse_with_mock_feed(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://example.com/feed"]),
            min_word_count=0,
        )
        parser = RSSParser(config=config)

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Test Blog"}
        mock_feed.entries = [_make_feed_entry()]

        with patch("distill.intake.parsers.rss.feedparser.parse", return_value=mock_feed):
            items = parser.parse()

        assert len(items) == 1
        assert items[0].site_name == "Test Blog"

    def test_since_filter(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://example.com/feed"]),
            min_word_count=0,
        )
        parser = RSSParser(config=config)

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Blog"}
        mock_feed.entries = [
            _make_feed_entry(published_parsed=time.gmtime(1707300000)),  # old
        ]

        future = datetime(2030, 1, 1, tzinfo=timezone.utc)
        with patch("distill.intake.parsers.rss.feedparser.parse", return_value=mock_feed):
            items = parser.parse(since=future)

        assert len(items) == 0

    def test_word_count_filter(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://example.com/feed"]),
            min_word_count=100,
        )
        parser = RSSParser(config=config)

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Blog"}
        mock_feed.entries = [
            _make_feed_entry(summary="short"),  # only 1 word
        ]

        with patch("distill.intake.parsers.rss.feedparser.parse", return_value=mock_feed):
            items = parser.parse()

        assert len(items) == 0

    def test_bozo_feed_without_entries(self):
        config = IntakeConfig(
            rss=RSSConfig(feeds=["https://example.com/feed"]),
            min_word_count=0,
        )
        parser = RSSParser(config=config)

        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("parse error")
        mock_feed.entries = []
        mock_feed.feed = {}

        with patch("distill.intake.parsers.rss.feedparser.parse", return_value=mock_feed):
            items = parser.parse()

        assert len(items) == 0

    def test_not_configured(self):
        config = IntakeConfig(rss=RSSConfig())
        parser = RSSParser(config=config)
        assert parser.is_configured is False

    def test_source_property(self):
        config = IntakeConfig(rss=RSSConfig(feeds=["https://a.com/feed"]))
        parser = RSSParser(config=config)
        assert parser.source == ContentSource.RSS


# ── Parser factory ─────────────────────────────────────────────────────

class TestParserFactory:
    def test_create_rss_parser(self):
        from distill.intake.parsers import create_parser

        config = IntakeConfig(rss=RSSConfig(feeds=["https://a.com/feed"]))
        parser = create_parser("rss", config=config)
        assert isinstance(parser, RSSParser)
        assert parser.is_configured is True

    def test_unknown_source(self):
        from distill.intake.parsers import create_parser

        config = IntakeConfig()
        with pytest.raises(ValueError):
            create_parser("unknown_source_xyz", config=config)

    def test_get_configured_parsers(self):
        from distill.intake.parsers import get_configured_parsers

        config = IntakeConfig(rss=RSSConfig(feeds=["https://a.com/feed"]))
        parsers = get_configured_parsers(config)
        assert len(parsers) >= 1
        assert any(p.source == ContentSource.RSS for p in parsers)

    def test_get_configured_parsers_none(self):
        from distill.intake.parsers import get_configured_parsers

        config = IntakeConfig(rss=RSSConfig())
        parsers = get_configured_parsers(config)
        rss_parsers = [p for p in parsers if p.source == ContentSource.RSS]
        assert len(rss_parsers) == 0
