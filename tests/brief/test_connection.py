"""Tests for the connection engine."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from distill.brief.connection import ConnectionInsight, find_connection
from distill.brief.models import ReadingHighlight
from distill.memory.models import (
    DailyEntry,
    EntityRecord,
    MemoryThread,
    UnifiedMemory,
)


def _make_highlight(title: str = "Test", tags: list[str] | None = None) -> ReadingHighlight:
    return ReadingHighlight(
        title=title,
        source="Test Source",
        summary="Test summary.",
        tags=tags or [],
    )


def _make_memory(
    threads: list[MemoryThread] | None = None,
    entities: dict[str, EntityRecord] | None = None,
    entries: list[DailyEntry] | None = None,
) -> UnifiedMemory:
    return UnifiedMemory(
        threads=threads or [],
        entities=entities or {},
        entries=entries or [],
    )


class TestFindConnection:
    @patch("distill.brief.connection.load_unified_memory")
    def test_no_highlights_returns_none(self, mock_load, tmp_path: Path):
        mock_load.return_value = _make_memory()
        assert find_connection([], tmp_path) is None

    @patch("distill.brief.connection.load_unified_memory")
    def test_empty_memory_returns_none(self, mock_load, tmp_path: Path):
        mock_load.return_value = _make_memory()
        h = _make_highlight("Interpretability Research", ["ai", "interpretability"])
        assert find_connection([h], tmp_path) is None

    @patch("distill.brief.connection.load_unified_memory")
    def test_matches_thread(self, mock_load, tmp_path: Path):
        thread = MemoryThread(
            name="interpretability research",
            summary="Tracking work on model interpretability",
            first_seen=date(2026, 2, 20),
            last_seen=date(2026, 3, 4),
            mention_count=5,
            status="active",
        )
        mock_load.return_value = _make_memory(threads=[thread])
        h = _make_highlight("Anthropic Interpretability Paper", ["interpretability", "ai"])
        result = find_connection([h], tmp_path)
        assert result is not None
        assert result.connection_type == "thread"
        assert "interpretability" in result.explanation.lower()

    @patch("distill.brief.connection.load_unified_memory")
    def test_matches_entity(self, mock_load, tmp_path: Path):
        entities = {
            "project:qwen": EntityRecord(
                name="Qwen",
                entity_type="project",
                first_seen=date(2026, 2, 15),
                last_seen=date(2026, 3, 4),
                mention_count=8,
            )
        }
        mock_load.return_value = _make_memory(entities=entities)
        h = _make_highlight("Qwen 3.5 Release", ["qwen", "open-models"])
        result = find_connection([h], tmp_path)
        assert result is not None
        assert result.connection_type == "entity"
        assert "Qwen" in result.explanation

    @patch("distill.brief.connection.load_unified_memory")
    def test_matches_theme(self, mock_load, tmp_path: Path):
        entry = DailyEntry(
            date=date(2026, 3, 3),
            themes=["agents", "agentic"],
        )
        mock_load.return_value = _make_memory(entries=[entry])
        h = _make_highlight("Ambient Agents Pattern", ["agents", "ux-patterns"])
        result = find_connection([h], tmp_path)
        assert result is not None
        assert result.connection_type == "theme"

    @patch("distill.brief.connection.load_unified_memory")
    def test_strongest_wins(self, mock_load, tmp_path: Path):
        thread = MemoryThread(
            name="interpretability deep dive",
            summary="Deep research on interpretability",
            first_seen=date(2026, 2, 1),
            last_seen=date(2026, 3, 4),
            mention_count=10,
            status="active",
        )
        entry = DailyEntry(
            date=date(2026, 3, 3),
            themes=["interpretability"],
        )
        mock_load.return_value = _make_memory(threads=[thread], entries=[entry])
        h = _make_highlight(
            "Anthropic Interpretability Research",
            ["interpretability", "deep", "research"],
        )
        result = find_connection([h], tmp_path)
        assert result is not None
        # Thread should win due to the 1.5x boost and more keyword overlap
        assert result.connection_type == "thread"

    @patch("distill.brief.connection.load_unified_memory")
    def test_skips_inactive_threads(self, mock_load, tmp_path: Path):
        thread = MemoryThread(
            name="old interpretability work",
            summary="Old stuff",
            first_seen=date(2026, 1, 1),
            last_seen=date(2026, 1, 15),
            mention_count=3,
            status="resolved",
        )
        mock_load.return_value = _make_memory(threads=[thread])
        h = _make_highlight("Interpretability Paper", ["interpretability"])
        result = find_connection([h], tmp_path)
        assert result is None
