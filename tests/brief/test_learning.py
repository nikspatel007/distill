"""Tests for learning pulse computation."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from distill.brief.learning import TopicTrend, compute_learning_pulse, _classify_topic


def _create_archive(tmp_path: Path, d: date, items: list[dict]) -> None:
    """Create a fake intake archive for a given date."""
    archive_dir = tmp_path / "intake" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"{d.isoformat()}.json"
    path.write_text(json.dumps({"date": d.isoformat(), "items": items}))


def _make_item(tags: list[str], source: str = "rss", topics: list[str] | None = None) -> dict:
    return {
        "id": "test",
        "title": "Test",
        "source": source,
        "tags": tags,
        "topics": topics or [],
    }


class TestComputeLearningPulse:
    def test_empty_dir(self, tmp_path: Path):
        result = compute_learning_pulse(tmp_path)
        assert result == []

    def test_single_day(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai", "llms"]),
            _make_item(["ai", "agents"]),
        ])
        result = compute_learning_pulse(tmp_path, days=14)
        topics = {t.topic for t in result}
        assert "ai" in topics

    def test_excludes_sessions(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai", "coding"], source="session"),
            _make_item(["ai", "reading"], source="rss"),
            _make_item(["ai", "reading"], source="rss"),
        ])
        result = compute_learning_pulse(tmp_path, days=14)
        topics = {t.topic for t in result}
        # "coding" only appears in session, should not be in results
        assert "coding" not in topics

    def test_trending_detection(self, tmp_path: Path):
        today = date.today()
        # Recent burst of "agents"
        for i in range(3):
            d = today - timedelta(days=i)
            _create_archive(tmp_path, d, [
                _make_item(["agents"]),
                _make_item(["agents"]),
            ])
        # Old data without agents
        for i in range(4, 10):
            d = today - timedelta(days=i)
            _create_archive(tmp_path, d, [
                _make_item(["other-topic"]),
            ])
        result = compute_learning_pulse(tmp_path, days=14, recent_days=3)
        agents = next((t for t in result if t.topic == "agents"), None)
        assert agents is not None
        assert agents.status in ("trending", "emerging")

    def test_sparkline_length(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai"]),
            _make_item(["ai"]),
        ])
        _create_archive(tmp_path, today - timedelta(days=1), [
            _make_item(["ai"]),
        ])
        result = compute_learning_pulse(tmp_path, days=7)
        ai = next((t for t in result if t.topic == "ai"), None)
        assert ai is not None
        assert len(ai.sparkline) == 7

    def test_topics_and_tags_merged(self, tmp_path: Path):
        today = date.today()
        _create_archive(tmp_path, today, [
            _make_item(["ai"], topics=["interpretability"]),
            _make_item(["ai"], topics=["interpretability"]),
        ])
        result = compute_learning_pulse(tmp_path, days=14)
        topics = {t.topic for t in result}
        assert "ai" in topics
        assert "interpretability" in topics


class TestClassifyTopic:
    def test_emerging(self):
        today = date.today()
        first = (today - timedelta(days=1)).isoformat()
        assert _classify_topic(2, 2, 14, 3, first, today) == "emerging"

    def test_trending(self):
        today = date.today()
        first = (today - timedelta(days=10)).isoformat()
        # 6 total, 5 recent out of 3-day window — very high ratio
        assert _classify_topic(6, 5, 14, 3, first, today) == "trending"

    def test_cooling(self):
        today = date.today()
        first = (today - timedelta(days=10)).isoformat()
        assert _classify_topic(8, 0, 14, 3, first, today) == "cooling"

    def test_stable(self):
        today = date.today()
        first = (today - timedelta(days=10)).isoformat()
        # 10 total, ~2 recent is roughly proportional for 3/14 ratio
        assert _classify_topic(10, 2, 14, 3, first, today) == "stable"
