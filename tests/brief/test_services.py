"""Tests for reading brief generation service."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from distill.brief.models import ReadingBrief
from distill.brief.services import (
    READING_SOURCES,
    _filter_reading_items,
    _render_items_for_prompt,
    _strip_json_fences,
    generate_reading_brief,
)
from distill.brief.store import load_reading_brief
from distill.intake.models import ContentItem, ContentSource, ContentType


def _make_item(
    source: str = "rss",
    url: str = "https://example.com",
    word_count: int = 200,
    title: str = "Test Article",
) -> ContentItem:
    return ContentItem(
        id="test-id",
        url=url,
        title=title,
        body="Body text here. " * 10,
        excerpt="Excerpt here.",
        word_count=word_count,
        source=ContentSource(source),
        content_type=ContentType.ARTICLE,
        saved_at=datetime.now(),
        site_name="Test Site",
    )


MOCK_HIGHLIGHTS_RESPONSE = json.dumps({
    "highlights": [
        {
            "title": "Key Finding 1",
            "source": "Blog 0",
            "url": "https://example.com/article-0",
            "summary": "This matters because X.",
            "tags": ["ai"],
        },
        {
            "title": "Key Finding 2",
            "source": "Blog 1",
            "url": "https://example.com/article-1",
            "summary": "This matters because Y.",
            "tags": ["ml"],
        },
        {
            "title": "Key Finding 3",
            "source": "Blog 2",
            "url": "https://example.com/article-2",
            "summary": "This matters because Z.",
            "tags": ["ops"],
        },
    ]
})


class TestFilterReadingItems:
    def test_keeps_rss(self):
        items = [_make_item(source="rss")]
        assert len(_filter_reading_items(items)) == 1

    def test_keeps_browser(self):
        items = [_make_item(source="browser")]
        assert len(_filter_reading_items(items)) == 1

    def test_excludes_session(self):
        items = [_make_item(source="session")]
        assert len(_filter_reading_items(items)) == 0

    def test_excludes_seeds(self):
        items = [_make_item(source="seeds")]
        assert len(_filter_reading_items(items)) == 0

    def test_excludes_no_url(self):
        items = [_make_item(url="")]
        assert len(_filter_reading_items(items)) == 0

    def test_excludes_short_items(self):
        items = [_make_item(word_count=10)]
        assert len(_filter_reading_items(items)) == 0

    def test_excludes_troopx(self):
        items = [_make_item(source="troopx")]
        assert len(_filter_reading_items(items)) == 0


class TestStripJsonFences:
    def test_strips_json_fence(self):
        assert _strip_json_fences('```json\n{"a":1}\n```') == '{"a":1}'

    def test_strips_plain_fence(self):
        assert _strip_json_fences('```\n{"a":1}\n```') == '{"a":1}'

    def test_no_fence(self):
        assert _strip_json_fences('{"a":1}') == '{"a":1}'


class TestRenderItems:
    def test_renders_markdown(self):
        items = [_make_item(title="Great Article")]
        result = _render_items_for_prompt(items)
        assert "## Great Article" in result
        assert "Test Site" in result

    def test_limits_items(self):
        items = [_make_item(title=f"Article {i}") for i in range(20)]
        result = _render_items_for_prompt(items, max_items=5)
        assert "Article 0" in result
        assert "Article 4" in result
        assert "Article 5" not in result


class TestGenerateReadingBrief:
    @patch("distill.brief.services._call_claude")
    def test_generates_brief_with_highlights(self, mock_claude, tmp_path: Path):
        mock_claude.return_value = MOCK_HIGHLIGHTS_RESPONSE
        items = [_make_item(title=f"Article {i}") for i in range(5)]
        brief = generate_reading_brief(
            items, "2026-03-05", tmp_path, generate_drafts=False
        )
        assert brief.date == "2026-03-05"
        assert len(brief.highlights) == 3
        assert brief.highlights[0].title == "Key Finding 1"

    @patch("distill.brief.services._call_claude")
    def test_saves_to_disk(self, mock_claude, tmp_path: Path):
        mock_claude.return_value = MOCK_HIGHLIGHTS_RESPONSE
        items = [_make_item(title=f"Article {i}") for i in range(5)]
        generate_reading_brief(items, "2026-03-05", tmp_path, generate_drafts=False)
        loaded = load_reading_brief(tmp_path, "2026-03-05")
        assert loaded is not None
        assert len(loaded.highlights) == 3

    @patch("distill.brief.services._call_claude")
    def test_generates_drafts(self, mock_claude, tmp_path: Path):
        mock_claude.side_effect = [
            MOCK_HIGHLIGHTS_RESPONSE,
            "LinkedIn post content here.",
            "X post content.",
        ]
        items = [_make_item(title=f"Article {i}") for i in range(5)]
        brief = generate_reading_brief(
            items, "2026-03-05", tmp_path, generate_drafts=True
        )
        assert len(brief.drafts) == 2
        platforms = {d.platform for d in brief.drafts}
        assert "linkedin" in platforms
        assert "x" in platforms

    def test_empty_items_returns_empty_brief(self, tmp_path: Path):
        brief = generate_reading_brief([], "2026-03-05", tmp_path)
        assert brief.highlights == []
        assert brief.drafts == []

    @patch("distill.brief.services._call_claude")
    def test_filters_sessions(self, mock_claude, tmp_path: Path):
        mock_claude.return_value = MOCK_HIGHLIGHTS_RESPONSE
        session_item = ContentItem(
            id="session-1",
            url="",
            title="Coding Session",
            body="Built stuff.",
            word_count=500,
            source=ContentSource.SESSION,
            content_type=ContentType.ARTICLE,
            saved_at=datetime.now(),
        )
        rss_item = ContentItem(
            id="rss-1",
            url="https://example.com/article",
            title="Reading Item",
            body="Interesting article. " * 20,
            word_count=200,
            source=ContentSource.RSS,
            content_type=ContentType.ARTICLE,
            saved_at=datetime.now(),
            site_name="Blog",
        )
        brief = generate_reading_brief(
            [session_item, rss_item], "2026-03-05", tmp_path, generate_drafts=False
        )
        call_args = mock_claude.call_args_list[0]
        user_prompt = call_args[0][1]  # second positional arg
        assert "Reading Item" in user_prompt
        assert "Coding Session" not in user_prompt
