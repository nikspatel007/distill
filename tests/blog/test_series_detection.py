"""Tests for series detection in themes.py."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from distill.blog.state import BlogState
from distill.blog.themes import detect_series_candidates
from distill.memory import EntityRecord, MemoryThread, UnifiedMemory


@pytest.fixture
def entries():
    """Create mock journal entries."""
    entry = MagicMock()
    entry.date = date.today()
    entry.prose = "Working on distill content pipeline with vector search"
    entry.tags = ["distill", "pipeline"]
    return [entry]


class TestDetectSeriesCandidates:
    def test_returns_empty_for_wrong_types(self, entries):
        result = detect_series_candidates(entries, "not_memory", "not_state")
        assert result == []

    def test_detects_thread_with_high_count(self, entries):
        memory = UnifiedMemory(
            threads=[
                MemoryThread(
                    name="content pipeline",
                    summary="Building a content pipeline",
                    first_seen=date.today() - timedelta(days=10),
                    last_seen=date.today(),
                    mention_count=5,
                    status="active",
                ),
            ]
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) >= 1
        assert any("series-" in c.slug for c in candidates)

    def test_skips_thread_with_low_count(self, entries):
        memory = UnifiedMemory(
            threads=[
                MemoryThread(
                    name="one-off",
                    summary="Brief topic",
                    first_seen=date.today(),
                    last_seen=date.today(),
                    mention_count=1,
                    status="active",
                ),
            ]
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) == 0

    def test_skips_resolved_threads(self, entries):
        memory = UnifiedMemory(
            threads=[
                MemoryThread(
                    name="done topic",
                    summary="Finished",
                    first_seen=date.today() - timedelta(days=10),
                    last_seen=date.today(),
                    mention_count=5,
                    status="resolved",
                ),
            ]
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) == 0

    def test_detects_entity_with_high_count(self, entries):
        memory = UnifiedMemory(
            entities={
                "concept:agent coordination": EntityRecord(
                    name="agent coordination",
                    entity_type="concept",
                    first_seen=date.today() - timedelta(days=20),
                    last_seen=date.today(),
                    mention_count=12,
                ),
            }
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) >= 1
        assert any("agent-coordination" in c.slug for c in candidates)

    def test_skips_already_generated(self, entries):
        memory = UnifiedMemory(
            threads=[
                MemoryThread(
                    name="content pipeline",
                    summary="Building a pipeline",
                    first_seen=date.today() - timedelta(days=10),
                    last_seen=date.today(),
                    mention_count=6,
                    status="active",
                ),
            ]
        )
        state = BlogState()
        # Mark the slug as generated
        from distill.blog.state import BlogPostRecord
        from datetime import datetime

        state.mark_generated(
            BlogPostRecord(
                slug="series-content-pipeline",
                post_type="thematic",
                generated_at=datetime.now(),
                source_dates=[date.today()],
                file_path="/fake",
            )
        )
        candidates = detect_series_candidates(entries, memory, state)
        assert not any(c.slug == "series-content-pipeline" for c in candidates)

    def test_entity_below_threshold_excluded(self, entries):
        memory = UnifiedMemory(
            entities={
                "project:minor": EntityRecord(
                    name="minor project",
                    entity_type="project",
                    first_seen=date.today(),
                    last_seen=date.today(),
                    mention_count=3,
                ),
            }
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) == 0

    def test_skips_single_word_entity_names(self, entries):
        """Generic single-word names like 'edit', 'python' are too vague."""
        memory = UnifiedMemory(
            entities={
                "tool:edit": EntityRecord(
                    name="edit",
                    entity_type="tool",
                    first_seen=date.today() - timedelta(days=20),
                    last_seen=date.today(),
                    mention_count=50,
                ),
            }
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) == 0

    def test_skips_blocklisted_names(self, entries):
        """Names in the blocklist are skipped even if multi-word."""
        memory = UnifiedMemory(
            entities={
                "concept:code review": EntityRecord(
                    name="code review",
                    entity_type="concept",
                    first_seen=date.today() - timedelta(days=20),
                    last_seen=date.today(),
                    mention_count=15,
                ),
            }
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) == 0

    def test_skips_generic_single_word_threads(self, entries):
        """Single-word thread names are too generic."""
        memory = UnifiedMemory(
            threads=[
                MemoryThread(
                    name="debugging",
                    summary="Various debugging",
                    first_seen=date.today() - timedelta(days=10),
                    last_seen=date.today(),
                    mention_count=10,
                    status="active",
                ),
            ]
        )
        state = BlogState()
        candidates = detect_series_candidates(entries, memory, state)
        assert len(candidates) == 0
