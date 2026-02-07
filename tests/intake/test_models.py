"""Tests for intake canonical models."""

from __future__ import annotations

from datetime import datetime

from distill.intake.models import (
    ContentItem,
    ContentSource,
    ContentType,
    Highlight,
)


class TestContentSource:
    def test_values(self):
        assert ContentSource.RSS == "rss"
        assert ContentSource.GMAIL == "gmail"
        assert ContentSource.REDDIT == "reddit"

    def test_from_string(self):
        assert ContentSource("rss") == ContentSource.RSS
        assert ContentSource("gmail") == ContentSource.GMAIL


class TestContentType:
    def test_values(self):
        assert ContentType.ARTICLE == "article"
        assert ContentType.NEWSLETTER == "newsletter"


class TestHighlight:
    def test_basic(self):
        h = Highlight(text="important passage")
        assert h.text == "important passage"
        assert h.note == ""
        assert h.position == 0


class TestContentItem:
    def test_minimal(self):
        item = ContentItem(id="abc123", source=ContentSource.RSS)
        assert item.id == "abc123"
        assert item.source == ContentSource.RSS
        assert item.content_type == ContentType.ARTICLE
        assert item.tags == []
        assert item.url == ""
        assert item.word_count == 0

    def test_full(self):
        item = ContentItem(
            id="test1",
            url="https://example.com/post",
            title="Test Post",
            body="This is the body.",
            excerpt="This is...",
            word_count=4,
            author="Author",
            site_name="Example Blog",
            source=ContentSource.RSS,
            source_id="guid123",
            content_type=ContentType.ARTICLE,
            tags=["python", "ai"],
            topics=["machine-learning"],
            published_at=datetime(2026, 2, 7, 12, 0),
            is_starred=True,
            metadata={"feed_url": "https://example.com/feed"},
        )
        assert item.title == "Test Post"
        assert item.author == "Author"
        assert item.tags == ["python", "ai"]
        assert item.is_starred is True
        assert item.metadata["feed_url"] == "https://example.com/feed"

    def test_saved_at_default(self):
        item = ContentItem(id="x", source=ContentSource.RSS)
        assert item.saved_at is not None

    def test_serialization(self):
        item = ContentItem(
            id="ser1",
            source=ContentSource.REDDIT,
            title="Serializable",
        )
        data = item.model_dump()
        assert data["source"] == "reddit"
        restored = ContentItem.model_validate(data)
        assert restored.id == "ser1"
        assert restored.source == ContentSource.REDDIT
