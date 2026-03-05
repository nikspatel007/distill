"""Test that connection + learning are wired into the brief."""
import json
from datetime import datetime
from unittest.mock import patch

import pytest

from distill.brief.connection import ConnectionInsight
from distill.brief.learning import TopicTrend
from distill.brief.models import ReadingBrief
from distill.brief.store import load_reading_brief, save_reading_brief


def test_reading_brief_includes_connection():
    conn = ConnectionInsight(
        today="Test Article",
        past="ongoing thread: AI safety",
        connection_type="thread",
        explanation="Test connection explanation",
        strength=0.8,
    )
    brief = ReadingBrief(
        date="2026-03-05",
        generated_at=datetime.now().isoformat(),
        connection=conn,
    )
    assert brief.connection is not None
    assert brief.connection.today == "Test Article"


def test_reading_brief_includes_learning_pulse():
    trends = [
        TopicTrend(topic="ai", status="trending", count=10, recent_count=5),
        TopicTrend(topic="rust", status="emerging", count=3, recent_count=3),
    ]
    brief = ReadingBrief(
        date="2026-03-05",
        generated_at=datetime.now().isoformat(),
        learning_pulse=trends,
    )
    assert len(brief.learning_pulse) == 2
    assert brief.learning_pulse[0].topic == "ai"


def test_reading_brief_defaults_none_connection():
    brief = ReadingBrief(date="2026-03-05")
    assert brief.connection is None
    assert brief.learning_pulse == []


def test_reading_brief_roundtrip_with_connection(tmp_path):
    conn = ConnectionInsight(
        today="Test",
        past="thread: X",
        connection_type="thread",
        explanation="Links together",
        strength=0.9,
    )
    trends = [TopicTrend(topic="ai", status="trending", count=5, recent_count=3)]
    brief = ReadingBrief(
        date="2026-03-05",
        generated_at=datetime.now().isoformat(),
        connection=conn,
        learning_pulse=trends,
    )
    save_reading_brief(brief, tmp_path)
    loaded = load_reading_brief(tmp_path, "2026-03-05")
    assert loaded is not None
    assert loaded.connection is not None
    assert loaded.connection.strength == 0.9
    assert len(loaded.learning_pulse) == 1


@patch("distill.brief.services._call_claude")
def test_generate_brief_calls_connection_and_learning(mock_claude, tmp_path):
    from distill.intake.models import ContentItem, ContentSource, ContentType

    mock_claude.return_value = json.dumps({
        "highlights": [
            {"title": "Test Article", "source": "Test", "url": "https://test.com", "summary": "A test", "tags": ["ai"]}
        ]
    })

    items = [ContentItem(
        id="1", title="Test Article", url="https://test.com",
        source=ContentSource.RSS, content_type=ContentType.ARTICLE,
        word_count=100, excerpt="Test excerpt",
    )]

    with patch("distill.brief.services.find_connection") as mock_conn, \
         patch("distill.brief.services.compute_learning_pulse") as mock_pulse:
        mock_conn.return_value = ConnectionInsight(
            today="Test Article", past="thread: X",
            connection_type="thread", explanation="Connected",
            strength=0.7,
        )
        mock_pulse.return_value = [
            TopicTrend(topic="ai", status="trending", count=5, recent_count=3),
        ]

        from distill.brief.services import generate_reading_brief
        brief = generate_reading_brief(items, "2026-03-05", tmp_path, generate_drafts=False)

        assert brief.connection is not None
        assert len(brief.learning_pulse) == 1
        mock_conn.assert_called_once()
        mock_pulse.assert_called_once()
