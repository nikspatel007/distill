"""Tests for the discovery engine."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from distill.brief.discovery import (
    DiscoveryItem,
    DiscoveryResult,
    _extract_active_topics,
    _get_read_urls,
    _save_discoveries,
    discover_content,
    load_discoveries,
)


def _create_archive(tmp_path: Path, d: date, items: list[dict]) -> None:
    archive_dir = tmp_path / "intake" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"{d.isoformat()}.json"
    path.write_text(json.dumps({"date": d.isoformat(), "items": items}))


def _make_item(
    tags: list[str],
    url: str = "https://example.com",
    source: str = "rss",
) -> dict:
    return {"id": "test", "title": "Test", "source": source, "tags": tags, "url": url}


MOCK_DISCOVERY_RESPONSE = json.dumps({
    "items": [
        {
            "title": "New Research on Agents",
            "url": "https://new-article.com/agents",
            "source": "AI Blog",
            "summary": "Relevant because you read about agents.",
            "topic": "agents",
            "content_type": "article",
        },
        {
            "title": "LLM Interpretability Video",
            "url": "https://youtube.com/watch?v=123",
            "source": "ML Channel",
            "summary": "Deep dive into interpretability.",
            "topic": "interpretability",
            "content_type": "video",
        },
    ]
})


class TestExtractActiveTopics:
    def test_extracts_from_archives(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai", "agents"]),
            _make_item(["ai", "llms"]),
            _make_item(["agents"]),
        ])
        topics = _extract_active_topics(tmp_path, days=7, top_n=3)
        assert "ai" in topics or "agents" in topics

    def test_skips_sessions(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["session-only"], source="session"),
            _make_item(["reading-tag"], source="rss"),
            _make_item(["reading-tag"], source="rss"),
        ])
        topics = _extract_active_topics(tmp_path)
        assert "session-only" not in topics

    def test_empty_archive_dir(self, tmp_path: Path):
        assert _extract_active_topics(tmp_path) == []


class TestGetReadUrls:
    def test_collects_urls(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai"], url="https://example.com/1"),
            _make_item(["ai"], url="https://example.com/2"),
        ])
        urls = _get_read_urls(tmp_path)
        assert "https://example.com/1" in urls
        assert "https://example.com/2" in urls

    def test_empty(self, tmp_path: Path):
        assert _get_read_urls(tmp_path) == set()


class TestDiscoverContent:
    @patch("distill.brief.discovery._call_claude")
    def test_discovers_items(self, mock_claude, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai", "agents"]),
            _make_item(["ai", "agents"]),
        ])
        mock_claude.return_value = MOCK_DISCOVERY_RESPONSE
        result = discover_content(tmp_path, today.isoformat())
        assert len(result.items) == 2
        assert result.items[0].title == "New Research on Agents"

    @patch("distill.brief.discovery._call_claude")
    def test_deduplicates_read_urls(self, mock_claude, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai"], url="https://new-article.com/agents"),
            _make_item(["ai"], url="https://example.com/old"),
        ])
        mock_claude.return_value = MOCK_DISCOVERY_RESPONSE
        result = discover_content(tmp_path, today.isoformat())
        urls = [i.url for i in result.items]
        assert "https://new-article.com/agents" not in urls

    def test_no_topics_returns_empty(self, tmp_path: Path):
        result = discover_content(tmp_path, date.today().isoformat())
        assert result.items == []

    @patch("distill.brief.discovery._call_claude")
    def test_saves_to_disk(self, mock_claude, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai", "agents"]),
            _make_item(["ai", "agents"]),
        ])
        mock_claude.return_value = MOCK_DISCOVERY_RESPONSE
        discover_content(tmp_path, today.isoformat())
        loaded = load_discoveries(tmp_path, today.isoformat())
        assert loaded is not None
        assert len(loaded.items) >= 1


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path: Path):
        result = DiscoveryResult(
            date="2026-03-05",
            items=[
                DiscoveryItem(title="Test", url="https://test.com", summary="Good.")
            ],
            topics_searched=["ai"],
        )
        _save_discoveries(result, tmp_path)
        loaded = load_discoveries(tmp_path, "2026-03-05")
        assert loaded is not None
        assert len(loaded.items) == 1

    def test_load_missing(self, tmp_path: Path):
        assert load_discoveries(tmp_path, "2026-03-05") is None

    def test_multiple_dates(self, tmp_path: Path):
        r1 = DiscoveryResult(date="2026-03-04", topics_searched=["ai"])
        r2 = DiscoveryResult(date="2026-03-05", topics_searched=["ml"])
        _save_discoveries(r1, tmp_path)
        _save_discoveries(r2, tmp_path)
        assert load_discoveries(tmp_path, "2026-03-04") is not None
        assert load_discoveries(tmp_path, "2026-03-05") is not None
