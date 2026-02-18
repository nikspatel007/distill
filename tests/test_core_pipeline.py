"""Tests for pipeline functions in distill.core.

Covers generate_journal_notes, generate_blog_posts, _generate_weekly_posts,
_generate_thematic_posts, _generate_reading_list_posts, _generate_blog_images,
generate_images, and _atomic_write with mocked LLM calls and dependencies.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from distill.blog.blog_memory import BlogMemory, BlogPostSummary
from distill.blog.config import BlogConfig
from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.reader import JournalEntry
from distill.blog.state import BlogPostRecord, BlogState
from distill.blog.themes import ThemeDefinition
from distill.journal.context import DailyContext
from distill.journal.memory import DailyMemoryEntry, MemoryThread, WorkingMemory
from distill.memory import UnifiedMemory
from distill.parsers.models import BaseSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(dt: datetime | None = None, summary: str = "test session") -> BaseSession:
    """Create a minimal BaseSession for testing."""
    if dt is None:
        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
    return BaseSession(
        session_id="test-001",
        source="claude",
        start_time=dt,
        summary=summary,
        messages=[],
    )


def _make_journal_entry(d: date, prose: str = "Journal prose.") -> JournalEntry:
    """Create a minimal JournalEntry."""
    return JournalEntry(
        date=d,
        style="dev-journal",
        sessions_count=3,
        duration_minutes=120.0,
        tags=["testing"],
        projects=["distill"],
        prose=prose,
    )


def _make_daily_context(d: date) -> DailyContext:
    """Create a minimal DailyContext."""
    return DailyContext(
        date=d,
        total_sessions=2,
        total_duration_minutes=90.0,
        projects_worked=["distill"],
        tags=["testing"],
    )


def _make_weekly_context(year: int = 2026, week: int = 7) -> WeeklyBlogContext:
    """Create a minimal WeeklyBlogContext."""
    week_start = date.fromisocalendar(year, week, 1)
    return WeeklyBlogContext(
        year=year,
        week=week,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        entries=[_make_journal_entry(week_start)],
        total_sessions=5,
        total_duration_minutes=300.0,
        projects=["distill"],
        all_tags=["testing"],
        combined_prose="Weekly combined prose.",
    )


def _make_thematic_context(theme: ThemeDefinition) -> ThematicBlogContext:
    """Create a minimal ThematicBlogContext."""
    return ThematicBlogContext(
        theme=theme,
        evidence_entries=[_make_journal_entry(date(2026, 2, 10))],
        date_range=(date(2026, 2, 8), date(2026, 2, 14)),
        evidence_count=3,
        combined_evidence="Evidence prose.",
    )


# ---------------------------------------------------------------------------
# generate_journal_notes tests
# ---------------------------------------------------------------------------


class TestGenerateJournalNotes:
    """Tests for generate_journal_notes()."""

    def test_dry_run_prints_context_skips_llm(self, tmp_path, capsys):
        """dry_run=True should print context and skip LLM calls."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        ctx = _make_daily_context(date(2026, 2, 10))

        with (
            patch("distill.journal.prepare_daily_context", return_value=ctx),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
                dry_run=True,
            )

        assert result == []
        captured = capsys.readouterr()
        assert "2026-02-10" in captured.out

    def test_cache_hit_skips_generation(self, tmp_path):
        """Sessions already cached should be skipped."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        mock_cache = MagicMock()
        mock_cache.is_generated.return_value = True

        with (
            patch("distill.journal.JournalCache", return_value=mock_cache),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
            )

        assert result == []

    def test_no_sessions_for_date_continues(self, tmp_path):
        """If no sessions match the target date, nothing is generated."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 11, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        with (
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
            )

        assert result == []

    def test_synthesis_failure_logs_and_continues(self, tmp_path):
        """Synthesis failure should be logged but not crash."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        mock_synth = MagicMock()
        mock_synth.synthesize.side_effect = RuntimeError("LLM failed")

        with (
            patch("distill.journal.JournalCache") as mock_cache_cls,
            patch("distill.journal.JournalSynthesizer", return_value=mock_synth),
            patch("distill.journal.prepare_daily_context", return_value=_make_daily_context(date(2026, 2, 10))),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            mock_cache_cls.return_value.is_generated.return_value = False
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
            )

        assert result == []

    def test_memory_extraction_failure_continues(self, tmp_path):
        """Memory extraction failure should log and still write the entry."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        mock_synth = MagicMock()
        mock_synth.synthesize.return_value = "Generated journal prose."
        mock_synth.extract_memory.side_effect = RuntimeError("Memory extraction failed")

        out_file = tmp_path / "journal" / "journal-2026-02-10-dev-journal.md"
        mock_formatter = MagicMock()
        mock_formatter.format_entry.return_value = "---\ndate: 2026-02-10\n---\nProse."
        mock_formatter.output_path.return_value = out_file

        with (
            patch("distill.journal.JournalCache") as mock_cache_cls,
            patch("distill.journal.JournalSynthesizer", return_value=mock_synth),
            patch("distill.journal.JournalFormatter", return_value=mock_formatter),
            patch("distill.journal.prepare_daily_context", return_value=_make_daily_context(date(2026, 2, 10))),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.journal.save_memory"),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.memory.save_unified_memory"),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            mock_cache_cls.return_value.is_generated.return_value = False
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
            )

        assert len(result) == 1

    def test_normal_path_generates_entry(self, tmp_path):
        """Normal successful path writes journal entry and updates memory."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        daily_entry = DailyMemoryEntry(
            date=date(2026, 2, 10),
            themes=["testing"],
            key_insights=["insight1"],
        )
        thread = MemoryThread(
            name="test-thread",
            summary="A test thread",
            first_mentioned=date(2026, 2, 10),
            last_mentioned=date(2026, 2, 10),
        )

        mock_synth = MagicMock()
        mock_synth.synthesize.return_value = "Generated journal prose."
        mock_synth.extract_memory.return_value = (daily_entry, [thread])

        out_file = tmp_path / "journal" / "journal-2026-02-10-dev-journal.md"
        mock_formatter = MagicMock()
        mock_formatter.format_entry.return_value = "---\ndate: 2026-02-10\n---\nProse."
        mock_formatter.output_path.return_value = out_file

        with (
            patch("distill.journal.JournalCache") as mock_cache_cls,
            patch("distill.journal.JournalSynthesizer", return_value=mock_synth),
            patch("distill.journal.JournalFormatter", return_value=mock_formatter),
            patch("distill.journal.prepare_daily_context", return_value=_make_daily_context(date(2026, 2, 10))),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.journal.save_memory"),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.memory.save_unified_memory"),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            mock_cache_cls.return_value.is_generated.return_value = False
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
            )

        assert len(result) == 1
        assert result[0] == out_file
        mock_synth.synthesize.assert_called_once()
        mock_synth.extract_memory.assert_called_once()
        mock_cache_cls.return_value.mark_generated.assert_called_once()

    def test_auto_discovers_dates_from_sessions(self, tmp_path):
        """When target_dates is None, dates are discovered from sessions."""
        from distill.core import generate_journal_notes

        dt1 = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        dt2 = datetime(2026, 2, 11, 10, 0, tzinfo=UTC)
        sessions = [_make_session(dt1), _make_session(dt2)]

        mock_cache = MagicMock()
        mock_cache.is_generated.return_value = True

        with (
            patch("distill.journal.JournalCache", return_value=mock_cache),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            result = generate_journal_notes(
                sessions,
                tmp_path,
                target_dates=None,
            )

        assert result == []
        assert mock_cache.is_generated.call_count == 2

    def test_force_bypasses_cache(self, tmp_path):
        """force=True should bypass cache checks."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        mock_synth = MagicMock()
        mock_synth.synthesize.side_effect = RuntimeError("LLM failed")

        with (
            patch("distill.journal.JournalSynthesizer", return_value=mock_synth),
            patch("distill.journal.prepare_daily_context", return_value=_make_daily_context(date(2026, 2, 10))),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
                force=True,
            )

        assert result == []
        mock_synth.synthesize.assert_called_once()

    def test_report_records_synthesis_error(self, tmp_path):
        """When a report is provided, synthesis errors are recorded."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        mock_synth = MagicMock()
        mock_synth.synthesize.side_effect = RuntimeError("LLM failed")

        mock_report = MagicMock()

        with (
            patch("distill.journal.JournalCache") as mock_cache_cls,
            patch("distill.journal.JournalSynthesizer", return_value=mock_synth),
            patch("distill.journal.prepare_daily_context", return_value=_make_daily_context(date(2026, 2, 10))),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            mock_cache_cls.return_value.is_generated.return_value = False
            result = generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
                report=mock_report,
            )

        assert result == []
        mock_report.add_error.assert_called_once()

    def test_project_context_passed_to_daily_context(self, tmp_path):
        """project_context kwarg should be forwarded to the DailyContext."""
        from distill.core import generate_journal_notes

        dt = datetime(2026, 2, 10, 14, 0, tzinfo=UTC)
        session = _make_session(dt)

        ctx = _make_daily_context(date(2026, 2, 10))
        mock_synth = MagicMock()
        mock_synth.synthesize.side_effect = RuntimeError("stop early")

        with (
            patch("distill.journal.JournalCache") as mock_cache_cls,
            patch("distill.journal.JournalSynthesizer", return_value=mock_synth),
            patch("distill.journal.prepare_daily_context", return_value=ctx),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            mock_cache_cls.return_value.is_generated.return_value = False
            generate_journal_notes(
                [session],
                tmp_path,
                target_dates=[date(2026, 2, 10)],
                project_context="My project context",
            )

        assert ctx.project_context == "My project context"


# ---------------------------------------------------------------------------
# generate_blog_posts tests
# ---------------------------------------------------------------------------


class TestGenerateBlogPosts:
    """Tests for generate_blog_posts()."""

    def test_empty_journal_returns_empty(self, tmp_path):
        """No journal entries means no blog posts."""
        from distill.core import generate_blog_posts

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = []
        mock_reader.read_intake_digests.return_value = []

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg

            result = generate_blog_posts(tmp_path)

        assert result == []

    def test_dry_run_weekly(self, tmp_path, capsys):
        """dry_run for weekly posts prints context and skips LLM."""
        from distill.core import generate_blog_posts

        d = date(2026, 2, 10)
        entries = [
            _make_journal_entry(d),
            _make_journal_entry(d + timedelta(days=1)),
            _make_journal_entry(d + timedelta(days=2)),
        ]

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = entries
        mock_reader.read_intake_digests.return_value = []

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.blog.load_blog_state", return_value=BlogState()),
            patch("distill.blog.load_blog_memory", return_value=BlogMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
            patch("distill.shared.editorial.EditorialStore") as mock_es,
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg
            mock_es.return_value = MagicMock()

            result = generate_blog_posts(
                tmp_path,
                post_type="weekly",
                dry_run=True,
            )

        assert result == []
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out

    def test_normal_weekly_generation(self, tmp_path):
        """Normal weekly generation path with mocked synthesizer."""
        from distill.core import generate_blog_posts

        d = date(2026, 2, 10)
        entries = [
            _make_journal_entry(d),
            _make_journal_entry(d + timedelta(days=1)),
            _make_journal_entry(d + timedelta(days=2)),
        ]

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = entries
        mock_reader.read_intake_digests.return_value = []

        mock_synth = MagicMock()
        mock_synth.synthesize_weekly.return_value = "# Weekly Blog\n\nSome content."
        mock_synth.extract_blog_memory.return_value = BlogPostSummary(
            slug="weekly-2026-W07",
            title="Week 2026-W07",
            post_type="weekly",
            date=d,
        )

        mock_publisher = MagicMock()
        mock_publisher.requires_llm = False
        mock_publisher.format_weekly.return_value = "# Published Weekly\n\nContent."
        mock_publisher.weekly_output_path.return_value = tmp_path / "blog" / "weekly" / "2026-W07.md"
        mock_publisher.format_index.return_value = "index"
        mock_publisher.index_path.return_value = tmp_path / "blog" / "index.md"

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
            patch("distill.blog.BlogSynthesizer", return_value=mock_synth),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.blog.load_blog_state", return_value=BlogState()),
            patch("distill.blog.load_blog_memory", return_value=BlogMemory()),
            patch("distill.blog.save_blog_state"),
            patch("distill.blog.save_blog_memory"),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.memory.save_unified_memory"),
            patch("distill.trends.detect_trends", return_value=[]),
            patch("distill.shared.editorial.EditorialStore") as mock_es,
            patch("distill.blog.prepare_weekly_context", return_value=_make_weekly_context()),
            patch("distill.blog.clean_diagrams", side_effect=lambda x: x),
            patch("distill.pipeline.blog._generate_blog_images", return_value=None),
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg
            mock_es.return_value = MagicMock(render_for_prompt=MagicMock(return_value=""))

            result = generate_blog_posts(
                tmp_path,
                post_type="weekly",
                platforms=["obsidian"],
            )

        assert len(result) >= 1
        mock_synth.synthesize_weekly.assert_called_once()

    def test_saves_state_and_memory_when_not_dry_run(self, tmp_path):
        """When not dry_run, state and blog memory are saved."""
        from distill.core import generate_blog_posts

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = [_make_journal_entry(date(2026, 2, 10))]
        mock_reader.read_intake_digests.return_value = []

        mock_publisher = MagicMock()
        mock_publisher.requires_llm = False
        mock_publisher.format_index.return_value = ""

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
            patch("distill.blog.BlogSynthesizer"),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.blog.load_blog_state", return_value=BlogState()),
            patch("distill.blog.load_blog_memory", return_value=BlogMemory()),
            patch("distill.blog.save_blog_state") as mock_save_state,
            patch("distill.blog.save_blog_memory") as mock_save_memory,
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.memory.save_unified_memory") as mock_save_unified,
            patch("distill.trends.detect_trends", return_value=[]),
            patch("distill.shared.editorial.EditorialStore") as mock_es,
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg
            mock_es.return_value = MagicMock(render_for_prompt=MagicMock(return_value=""))

            generate_blog_posts(
                tmp_path,
                post_type="weekly",
                platforms=["obsidian"],
            )

        mock_save_state.assert_called_once()
        mock_save_memory.assert_called_once()
        mock_save_unified.assert_called_once()

    def test_dry_run_skips_saving(self, tmp_path):
        """When dry_run=True, state and memory are NOT saved."""
        from distill.core import generate_blog_posts

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = [_make_journal_entry(date(2026, 2, 10))]
        mock_reader.read_intake_digests.return_value = []

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.blog.load_blog_state", return_value=BlogState()),
            patch("distill.blog.load_blog_memory", return_value=BlogMemory()),
            patch("distill.blog.save_blog_state") as mock_save_state,
            patch("distill.blog.save_blog_memory") as mock_save_memory,
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.memory.save_unified_memory") as mock_save_unified,
            patch("distill.trends.detect_trends", return_value=[]),
            patch("distill.shared.editorial.EditorialStore") as mock_es,
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg
            mock_es.return_value = MagicMock()

            generate_blog_posts(
                tmp_path,
                post_type="weekly",
                dry_run=True,
            )

        mock_save_state.assert_not_called()
        mock_save_memory.assert_not_called()
        mock_save_unified.assert_not_called()

    def test_force_creates_fresh_state(self, tmp_path):
        """force=True should create a fresh BlogState (not load from disk)."""
        from distill.core import generate_blog_posts

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = []
        mock_reader.read_intake_digests.return_value = []

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
            patch("distill.blog.load_blog_state") as mock_load_state,
            patch("distill.blog.load_blog_memory", return_value=BlogMemory()),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.trends.detect_trends", return_value=[]),
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg

            generate_blog_posts(tmp_path, force=True)

        mock_load_state.assert_not_called()

    def test_all_post_types_dispatches(self, tmp_path):
        """post_type='all' calls weekly, thematic, and reading-list generators."""
        from distill.core import generate_blog_posts

        d = date(2026, 2, 10)
        entries = [
            _make_journal_entry(d),
            _make_journal_entry(d + timedelta(days=1)),
            _make_journal_entry(d + timedelta(days=2)),
        ]

        mock_reader = MagicMock()
        mock_reader.read_all.return_value = entries
        mock_reader.read_intake_digests.return_value = []

        mock_publisher = MagicMock()
        mock_publisher.requires_llm = False
        mock_publisher.format_index.return_value = ""

        with (
            patch("distill.shared.config.load_config") as mock_load_config,
            patch("distill.blog.JournalReader", return_value=mock_reader),
            patch("distill.journal.load_memory", return_value=WorkingMemory()),
            patch("distill.blog.load_blog_state", return_value=BlogState()),
            patch("distill.blog.load_blog_memory", return_value=BlogMemory()),
            patch("distill.blog.save_blog_state"),
            patch("distill.blog.save_blog_memory"),
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.memory.save_unified_memory"),
            patch("distill.trends.detect_trends", return_value=[]),
            patch("distill.shared.editorial.EditorialStore") as mock_es,
            patch("distill.pipeline.blog._generate_weekly_posts", return_value=[]) as mock_weekly,
            patch("distill.pipeline.blog._generate_thematic_posts", return_value=[]) as mock_thematic,
            patch("distill.pipeline.blog._generate_reading_list_posts", return_value=[]) as mock_reading,
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            mock_cfg = MagicMock()
            mock_cfg.render_project_context.return_value = ""
            mock_cfg.to_postiz_config.return_value = None
            mock_cfg.intake = MagicMock(rss_feeds=[])
            mock_load_config.return_value = mock_cfg
            mock_es.return_value = MagicMock()

            generate_blog_posts(tmp_path, post_type="all", platforms=["obsidian"])

        mock_weekly.assert_called_once()
        mock_thematic.assert_called_once()
        mock_reading.assert_called_once()


# ---------------------------------------------------------------------------
# _generate_weekly_posts tests
# ---------------------------------------------------------------------------


class TestGenerateWeeklyPosts:
    """Tests for _generate_weekly_posts()."""

    def test_dry_run_prints_and_skips(self, capsys):
        """dry_run prints slug and continues."""
        from distill.pipeline.blog import _generate_weekly_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d), _make_journal_entry(d + timedelta(days=1))]
        state = BlogState()

        result = _generate_weekly_posts(
            entries=entries,
            memory=WorkingMemory(),
            state=state,
            config=BlogConfig(),
            synthesizer=MagicMock(),
            output_dir=Path("/tmp/test"),
            target_week=None,
            force=False,
            dry_run=True,
            platforms=["obsidian"],
            blog_memory=BlogMemory(),
        )

        assert result == []
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "weekly-2026-W07" in captured.out

    def test_fewer_than_2_entries_skipped(self):
        """Weeks with fewer than 2 entries are skipped."""
        from distill.pipeline.blog import _generate_weekly_posts

        entries = [_make_journal_entry(date(2026, 2, 10))]
        state = BlogState()

        result = _generate_weekly_posts(
            entries=entries,
            memory=WorkingMemory(),
            state=state,
            config=BlogConfig(),
            synthesizer=MagicMock(),
            output_dir=Path("/tmp/test"),
            target_week=None,
            force=False,
            dry_run=False,
            platforms=["obsidian"],
            blog_memory=BlogMemory(),
        )

        assert result == []

    def test_already_generated_skipped(self):
        """Already-generated slugs are skipped."""
        from distill.pipeline.blog import _generate_weekly_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d), _make_journal_entry(d + timedelta(days=1))]

        state = BlogState()
        state.mark_generated(
            BlogPostRecord(
                slug="weekly-2026-W07",
                post_type="weekly",
                generated_at=datetime.now(),
            )
        )

        result = _generate_weekly_posts(
            entries=entries,
            memory=WorkingMemory(),
            state=state,
            config=BlogConfig(),
            synthesizer=MagicMock(),
            output_dir=Path("/tmp/test"),
            target_week=None,
            force=False,
            dry_run=False,
            platforms=["obsidian"],
            blog_memory=BlogMemory(),
        )

        assert result == []

    def test_target_week_filters_weeks(self, capsys):
        """target_week filters to only that week."""
        from distill.pipeline.blog import _generate_weekly_posts

        d1 = date(2026, 2, 10)  # W07
        d2 = date(2026, 2, 17)  # W08
        entries = [
            _make_journal_entry(d1),
            _make_journal_entry(d1 + timedelta(days=1)),
            _make_journal_entry(d2),
            _make_journal_entry(d2 + timedelta(days=1)),
        ]
        state = BlogState()

        result = _generate_weekly_posts(
            entries=entries,
            memory=WorkingMemory(),
            state=state,
            config=BlogConfig(),
            synthesizer=MagicMock(),
            output_dir=Path("/tmp/test"),
            target_week="2026-W08",
            force=False,
            dry_run=True,
            platforms=["obsidian"],
            blog_memory=BlogMemory(),
        )

        assert result == []
        captured = capsys.readouterr()
        assert "W08" in captured.out
        assert "W07" not in captured.out

    def test_normal_generation(self, tmp_path):
        """Normal weekly generation writes file and marks state."""
        from distill.pipeline.blog import _generate_weekly_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d), _make_journal_entry(d + timedelta(days=1))]

        state = BlogState()
        blog_memory = BlogMemory()

        mock_synth = MagicMock()
        mock_synth.synthesize_weekly.return_value = "# Weekly Post\n\nContent."
        mock_synth.extract_blog_memory.return_value = BlogPostSummary(
            slug="weekly-2026-W07",
            title="Week 2026-W07",
            post_type="weekly",
            date=d,
        )

        mock_publisher = MagicMock()
        mock_publisher.format_weekly.return_value = "# Published\n\nContent."
        mock_publisher.weekly_output_path.return_value = tmp_path / "blog" / "weekly" / "2026-W07.md"

        with (
            patch("distill.blog.prepare_weekly_context", return_value=_make_weekly_context()),
            patch("distill.blog.clean_diagrams", side_effect=lambda x: x),
            patch("distill.pipeline.blog._generate_blog_images", return_value=None),
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            result = _generate_weekly_posts(
                entries=entries,
                memory=WorkingMemory(),
                state=state,
                config=BlogConfig(),
                synthesizer=mock_synth,
                output_dir=tmp_path,
                target_week=None,
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=blog_memory,
                editorial_store=MagicMock(render_for_prompt=MagicMock(return_value="")),
            )

        assert len(result) == 1
        assert state.is_generated("weekly-2026-W07")
        mock_synth.synthesize_weekly.assert_called_once()

    def test_postiz_rate_limiting(self, tmp_path):
        """Postiz is skipped when limit is reached."""
        from distill.pipeline.blog import _generate_weekly_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d), _make_journal_entry(d + timedelta(days=1))]

        mock_synth = MagicMock()
        mock_synth.synthesize_weekly.return_value = "Content."
        mock_synth.extract_blog_memory.return_value = BlogPostSummary(
            slug="weekly-2026-W07",
            title="Week 2026-W07",
            post_type="weekly",
            date=d,
        )

        mock_publisher = MagicMock()
        mock_publisher.format_weekly.return_value = "Content."
        mock_publisher.weekly_output_path.return_value = tmp_path / "blog" / "weekly" / "2026-W07.md"

        postiz_counter = [5]

        with (
            patch("distill.blog.prepare_weekly_context", return_value=_make_weekly_context()),
            patch("distill.blog.clean_diagrams", side_effect=lambda x: x),
            patch("distill.pipeline.blog._generate_blog_images", return_value=None),
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            _generate_weekly_posts(
                entries=entries,
                memory=WorkingMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=mock_synth,
                output_dir=tmp_path,
                target_week=None,
                force=False,
                dry_run=False,
                platforms=["obsidian", "postiz"],
                blog_memory=BlogMemory(),
                postiz_limit=5,
                postiz_counter=postiz_counter,
                editorial_store=MagicMock(render_for_prompt=MagicMock(return_value="")),
            )

        assert postiz_counter[0] == 5

    def test_graph_context_appended(self, tmp_path, capsys):
        """graph_context is appended to working_memory."""
        from distill.pipeline.blog import _generate_weekly_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d), _make_journal_entry(d + timedelta(days=1))]

        ctx = _make_weekly_context()

        with patch("distill.blog.prepare_weekly_context", return_value=ctx):
            _generate_weekly_posts(
                entries=entries,
                memory=WorkingMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_week=None,
                force=False,
                dry_run=True,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
                graph_context="## Graph\n\nSome graph data.",
            )

        assert "Graph" in ctx.working_memory


# ---------------------------------------------------------------------------
# _generate_thematic_posts tests
# ---------------------------------------------------------------------------


class TestGenerateThematicPosts:
    """Tests for _generate_thematic_posts()."""

    def test_target_theme_not_found(self, tmp_path):
        """target_theme that doesn't exist returns empty."""
        from distill.pipeline.blog import _generate_thematic_posts

        with patch("distill.intake.SeedStore") as mock_ss:
            mock_ss.return_value.list_unused.return_value = []
            result = _generate_thematic_posts(
                entries=[_make_journal_entry(date(2026, 2, 10))],
                memory=WorkingMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_theme="nonexistent-theme",
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []

    def test_dry_run_prints_and_skips(self, tmp_path, capsys):
        """dry_run prints theme slug and skips LLM."""
        from distill.pipeline.blog import _generate_thematic_posts

        theme = ThemeDefinition(
            slug="test-theme",
            title="Test Theme",
            keywords=["test"],
            min_evidence_days=1,
        )

        d = date(2026, 2, 10)
        entry = _make_journal_entry(d, prose="test keyword here")

        with (
            patch("distill.blog.THEMES", [theme]),
            patch("distill.blog.gather_evidence", return_value=[entry]),
            patch("distill.blog.prepare_thematic_context", return_value=_make_thematic_context(theme)),
            patch("distill.intake.SeedStore") as mock_ss,
            patch("distill.blog.themes_from_seeds", return_value=[]),
        ):
            mock_ss.return_value.list_unused.return_value = []

            result = _generate_thematic_posts(
                entries=[entry],
                memory=WorkingMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_theme="test-theme",
                force=False,
                dry_run=True,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "test-theme" in captured.out

    def test_already_generated_skipped(self, tmp_path):
        """Already-generated themes are skipped."""
        from distill.pipeline.blog import _generate_thematic_posts

        theme = ThemeDefinition(
            slug="test-theme",
            title="Test Theme",
            keywords=["test"],
            min_evidence_days=1,
        )

        state = BlogState()
        state.mark_generated(
            BlogPostRecord(
                slug="test-theme",
                post_type="thematic",
                generated_at=datetime.now(),
            )
        )

        d = date(2026, 2, 10)
        entry = _make_journal_entry(d, prose="test keyword here")

        with (
            patch("distill.blog.THEMES", [theme]),
            patch("distill.blog.gather_evidence", return_value=[entry]),
            patch("distill.blog.prepare_thematic_context", return_value=_make_thematic_context(theme)),
            patch("distill.intake.SeedStore") as mock_ss,
            patch("distill.blog.themes_from_seeds", return_value=[]),
        ):
            mock_ss.return_value.list_unused.return_value = []

            result = _generate_thematic_posts(
                entries=[entry],
                memory=WorkingMemory(),
                state=state,
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_theme="test-theme",
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []

    def test_normal_thematic_generation(self, tmp_path):
        """Normal thematic generation writes file and marks state."""
        from distill.pipeline.blog import _generate_thematic_posts

        theme = ThemeDefinition(
            slug="test-theme",
            title="Test Theme",
            keywords=["test"],
            min_evidence_days=1,
        )

        d = date(2026, 2, 10)
        entry = _make_journal_entry(d, prose="test keyword here")

        mock_synth = MagicMock()
        mock_synth.synthesize_thematic.return_value = "# Thematic Post\n\nDeep dive content."
        mock_synth.extract_blog_memory.return_value = BlogPostSummary(
            slug="test-theme",
            title="Test Theme",
            post_type="thematic",
            date=d,
        )

        mock_publisher = MagicMock()
        mock_publisher.format_thematic.return_value = "# Published Thematic\n\nContent."
        mock_publisher.thematic_output_path.return_value = (
            tmp_path / "blog" / "thematic" / "test-theme.md"
        )

        state = BlogState()

        with (
            patch("distill.blog.THEMES", [theme]),
            patch("distill.blog.gather_evidence", return_value=[entry]),
            patch("distill.blog.prepare_thematic_context", return_value=_make_thematic_context(theme)),
            patch("distill.blog.clean_diagrams", side_effect=lambda x: x),
            patch("distill.pipeline.blog._generate_blog_images", return_value=None),
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
            patch("distill.intake.SeedStore") as mock_ss,
            patch("distill.blog.themes_from_seeds", return_value=[]),
        ):
            mock_ss.return_value.list_unused.return_value = []

            result = _generate_thematic_posts(
                entries=[entry],
                memory=WorkingMemory(),
                state=state,
                config=BlogConfig(),
                synthesizer=mock_synth,
                output_dir=tmp_path,
                target_theme="test-theme",
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
                editorial_store=MagicMock(render_for_prompt=MagicMock(return_value="")),
            )

        assert len(result) == 1
        assert state.is_generated("test-theme")
        mock_synth.synthesize_thematic.assert_called_once()

    def test_no_evidence_returns_empty(self, tmp_path):
        """Target theme with no evidence returns empty."""
        from distill.pipeline.blog import _generate_thematic_posts

        theme = ThemeDefinition(
            slug="test-theme",
            title="Test Theme",
            keywords=["test"],
            min_evidence_days=1,
        )

        with (
            patch("distill.blog.THEMES", [theme]),
            patch("distill.blog.gather_evidence", return_value=[]),
            patch("distill.intake.SeedStore") as mock_ss,
            patch("distill.blog.themes_from_seeds", return_value=[]),
        ):
            mock_ss.return_value.list_unused.return_value = []

            result = _generate_thematic_posts(
                entries=[_make_journal_entry(date(2026, 2, 10))],
                memory=WorkingMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_theme="test-theme",
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []

    def test_auto_discovery_with_cap(self, tmp_path, capsys):
        """Auto-discovery mode caps at max_thematic_posts."""
        from distill.pipeline.blog import _generate_thematic_posts

        d = date(2026, 2, 10)
        entries = [
            _make_journal_entry(d, prose="keyword1 testing stuff"),
            _make_journal_entry(d + timedelta(days=1), prose="keyword1 more testing"),
            _make_journal_entry(d + timedelta(days=2), prose="keyword1 final testing"),
        ]

        theme1 = ThemeDefinition(
            slug="theme-1", title="Theme 1", keywords=["keyword1"], min_evidence_days=1
        )
        theme2 = ThemeDefinition(
            slug="theme-2", title="Theme 2", keywords=["keyword1"], min_evidence_days=1
        )
        theme3 = ThemeDefinition(
            slug="theme-3", title="Theme 3", keywords=["keyword1"], min_evidence_days=1
        )

        config = MagicMock()
        config.include_diagrams = False
        config.max_thematic_posts = 2

        with (
            patch("distill.blog.get_ready_themes", return_value=[
                (theme1, entries),
                (theme2, entries),
                (theme3, entries),
            ]),
            patch("distill.blog.themes_from_seeds", return_value=[]),
            patch("distill.blog.prepare_thematic_context") as mock_prep,
            patch("distill.intake.SeedStore") as mock_ss,
            patch("distill.memory.load_unified_memory", return_value=UnifiedMemory()),
            patch("distill.blog.detect_series_candidates", return_value=[]),
        ):
            mock_ss.return_value.list_unused.return_value = []
            mock_prep.return_value = _make_thematic_context(theme1)

            _generate_thematic_posts(
                entries=entries,
                memory=WorkingMemory(),
                state=BlogState(),
                config=config,
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_theme=None,
                force=False,
                dry_run=True,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        captured = capsys.readouterr()
        assert captured.out.count("[DRY RUN]") == 2

    def test_editorial_notes_injected(self, tmp_path, capsys):
        """Editorial notes from the store are injected into context."""
        from distill.pipeline.blog import _generate_thematic_posts

        theme = ThemeDefinition(
            slug="test-theme",
            title="Test Theme",
            keywords=["test"],
            min_evidence_days=1,
        )

        d = date(2026, 2, 10)
        entry = _make_journal_entry(d, prose="test keyword here")
        ctx = _make_thematic_context(theme)

        mock_es = MagicMock()
        mock_es.render_for_prompt.return_value = "Focus on testing patterns."

        with (
            patch("distill.blog.THEMES", [theme]),
            patch("distill.blog.gather_evidence", return_value=[entry]),
            patch("distill.blog.prepare_thematic_context", return_value=ctx),
            patch("distill.intake.SeedStore") as mock_ss,
            patch("distill.blog.themes_from_seeds", return_value=[]),
        ):
            mock_ss.return_value.list_unused.return_value = []

            _generate_thematic_posts(
                entries=[entry],
                memory=WorkingMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                target_theme="test-theme",
                force=False,
                dry_run=True,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
                editorial_store=mock_es,
            )

        assert ctx.editorial_notes == "Focus on testing patterns."


# ---------------------------------------------------------------------------
# _generate_reading_list_posts tests
# ---------------------------------------------------------------------------


class TestGenerateReadingListPosts:
    """Tests for _generate_reading_list_posts()."""

    def test_dry_run_prints_and_skips(self, tmp_path, capsys):
        """dry_run prints slug and returns empty."""
        from distill.blog.reading_list import ReadingListContext
        from distill.pipeline.blog import _generate_reading_list_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d)]

        ctx = ReadingListContext(
            week_start=date.fromisocalendar(2026, 7, 1),
            week_end=date.fromisocalendar(2026, 7, 1) + timedelta(days=6),
            items=[{"title": "Article 1"}],
            total_items_read=5,
        )

        with (
            patch("distill.shared.store.create_store", return_value=MagicMock()),
            patch(
                "distill.blog.prepare_reading_list_context",
                return_value=ctx,
            ),
        ):
            result = _generate_reading_list_posts(
                entries=entries,
                unified=UnifiedMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                force=False,
                dry_run=True,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "reading-list-2026-W07" in captured.out

    def test_no_context_skips(self, tmp_path):
        """When prepare_reading_list_context returns None, skip."""
        from distill.pipeline.blog import _generate_reading_list_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d)]

        with (
            patch("distill.shared.store.create_store", return_value=MagicMock()),
            patch(
                "distill.blog.prepare_reading_list_context",
                return_value=None,
            ),
        ):
            result = _generate_reading_list_posts(
                entries=entries,
                unified=UnifiedMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []

    def test_already_generated_skipped(self, tmp_path):
        """Already-generated reading list slugs are skipped."""
        from distill.pipeline.blog import _generate_reading_list_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d)]

        state = BlogState()
        state.mark_generated(
            BlogPostRecord(
                slug="reading-list-2026-W07",
                post_type="reading-list",
                generated_at=datetime.now(),
            )
        )

        with patch("distill.shared.store.create_store", return_value=MagicMock()):
            result = _generate_reading_list_posts(
                entries=entries,
                unified=UnifiedMemory(),
                state=state,
                config=BlogConfig(),
                synthesizer=MagicMock(),
                output_dir=tmp_path,
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []

    def test_normal_generation(self, tmp_path):
        """Normal reading list generation writes file."""
        from distill.blog.reading_list import ReadingListContext
        from distill.pipeline.blog import _generate_reading_list_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d)]

        ctx = ReadingListContext(
            week_start=date.fromisocalendar(2026, 7, 1),
            week_end=date.fromisocalendar(2026, 7, 1) + timedelta(days=6),
            items=[{"title": "Article 1", "url": "https://example.com"}],
            total_items_read=5,
        )

        mock_synth = MagicMock()
        mock_synth.synthesize_raw.return_value = "# Reading List\n\nCurated picks."

        mock_publisher = MagicMock()
        mock_publisher.weekly_output_path.return_value = (
            tmp_path / "blog" / "weekly" / "2026-W07.md"
        )

        state = BlogState()

        with (
            patch("distill.shared.store.create_store", return_value=MagicMock()),
            patch(
                "distill.blog.prepare_reading_list_context",
                return_value=ctx,
            ),
            patch(
                "distill.blog.render_reading_list_prompt",
                return_value="prompt text",
            ),
            patch("distill.blog.get_blog_prompt", return_value="system prompt"),
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            result = _generate_reading_list_posts(
                entries=entries,
                unified=UnifiedMemory(),
                state=state,
                config=BlogConfig(),
                synthesizer=mock_synth,
                output_dir=tmp_path,
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert len(result) == 1
        assert state.is_generated("reading-list-2026-W07")
        mock_synth.synthesize_raw.assert_called_once()

    def test_postiz_rate_limiting(self, tmp_path):
        """Postiz is skipped when limit is reached in reading list."""
        from distill.blog.reading_list import ReadingListContext
        from distill.pipeline.blog import _generate_reading_list_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d)]

        ctx = ReadingListContext(
            week_start=date.fromisocalendar(2026, 7, 1),
            week_end=date.fromisocalendar(2026, 7, 1) + timedelta(days=6),
            items=[{"title": "Article 1"}],
            total_items_read=5,
        )

        mock_synth = MagicMock()
        mock_synth.synthesize_raw.return_value = "Content."

        mock_publisher = MagicMock()
        mock_publisher.weekly_output_path.return_value = (
            tmp_path / "blog" / "weekly" / "2026-W07.md"
        )

        postiz_counter = [3]

        with (
            patch("distill.shared.store.create_store", return_value=MagicMock()),
            patch(
                "distill.blog.prepare_reading_list_context",
                return_value=ctx,
            ),
            patch(
                "distill.blog.render_reading_list_prompt",
                return_value="prompt",
            ),
            patch("distill.blog.get_blog_prompt", return_value="system"),
            patch("distill.blog.publishers.create_publisher", return_value=mock_publisher),
        ):
            result = _generate_reading_list_posts(
                entries=entries,
                unified=UnifiedMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=mock_synth,
                output_dir=tmp_path,
                force=False,
                dry_run=False,
                platforms=["postiz"],
                blog_memory=BlogMemory(),
                postiz_limit=3,
                postiz_counter=postiz_counter,
            )

        assert result == []
        assert postiz_counter[0] == 3

    def test_publisher_failure_continues(self, tmp_path):
        """Publisher failure is caught and logged, not raised."""
        from distill.blog.reading_list import ReadingListContext
        from distill.pipeline.blog import _generate_reading_list_posts

        d = date(2026, 2, 10)
        entries = [_make_journal_entry(d)]

        ctx = ReadingListContext(
            week_start=date.fromisocalendar(2026, 7, 1),
            week_end=date.fromisocalendar(2026, 7, 1) + timedelta(days=6),
            items=[{"title": "Article 1"}],
            total_items_read=5,
        )

        mock_synth = MagicMock()
        mock_synth.synthesize_raw.return_value = "Content."

        with (
            patch("distill.shared.store.create_store", return_value=MagicMock()),
            patch(
                "distill.blog.prepare_reading_list_context",
                return_value=ctx,
            ),
            patch(
                "distill.blog.render_reading_list_prompt",
                return_value="prompt",
            ),
            patch("distill.blog.get_blog_prompt", return_value="system"),
            patch(
                "distill.blog.publishers.create_publisher",
                side_effect=ValueError("Unknown platform"),
            ),
        ):
            result = _generate_reading_list_posts(
                entries=entries,
                unified=UnifiedMemory(),
                state=BlogState(),
                config=BlogConfig(),
                synthesizer=mock_synth,
                output_dir=tmp_path,
                force=False,
                dry_run=False,
                platforms=["obsidian"],
                blog_memory=BlogMemory(),
            )

        assert result == []


# ---------------------------------------------------------------------------
# _generate_blog_images tests
# ---------------------------------------------------------------------------


class TestGenerateBlogImages:
    """Tests for _generate_blog_images()."""

    def test_not_configured_returns_none(self, tmp_path):
        """Returns None when image generator is not configured."""
        from distill.pipeline.blog import _generate_blog_images

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = False

        with patch("distill.shared.images.ImageGenerator", return_value=mock_gen):
            result = _generate_blog_images("Some prose.", tmp_path, "test-slug")

        assert result is None

    def test_no_prompts_returns_none(self, tmp_path):
        """Returns None when no image prompts are extracted."""
        from distill.pipeline.blog import _generate_blog_images

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True

        with (
            patch("distill.shared.images.ImageGenerator", return_value=mock_gen),
            patch("distill.intake.images.extract_image_prompts", return_value=[]),
        ):
            result = _generate_blog_images("Some prose.", tmp_path, "test-slug")

        assert result is None

    def test_exception_returns_none(self, tmp_path):
        """Returns None on any exception."""
        from distill.pipeline.blog import _generate_blog_images

        with patch("distill.shared.images.ImageGenerator", side_effect=RuntimeError("boom")):
            result = _generate_blog_images("Some prose.", tmp_path, "test-slug")

        assert result is None


# ---------------------------------------------------------------------------
# generate_images tests
# ---------------------------------------------------------------------------


class TestGenerateImages:
    """Tests for the generate_images() function."""

    def test_not_configured_returns_empty(self, tmp_path):
        """Returns empty when generator is not configured."""
        from distill.pipeline.intake import generate_images

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = False

        prompts, paths = generate_images("prose", tmp_path, "2026-02-10", generator=mock_gen)
        assert prompts == []
        assert paths == {}

    def test_no_prompts_returns_empty(self, tmp_path):
        """Returns empty when no image prompts are extracted."""
        from distill.pipeline.intake import generate_images

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True

        with patch("distill.intake.images.extract_image_prompts", return_value=[]):
            prompts, paths = generate_images(
                "prose", tmp_path, "2026-02-10", generator=mock_gen
            )

        assert prompts == []
        assert paths == {}


# ---------------------------------------------------------------------------
# _atomic_write tests
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """Tests for the _atomic_write helper."""

    def test_writes_content_atomically(self, tmp_path):
        """File content is written correctly."""
        from distill.core import _atomic_write

        out = tmp_path / "subdir" / "test.md"
        _atomic_write(out, "hello world")

        assert out.read_text() == "hello world"

    def test_creates_parent_dirs(self, tmp_path):
        """Parent directories are created if missing."""
        from distill.core import _atomic_write

        out = tmp_path / "deep" / "nested" / "dir" / "file.md"
        _atomic_write(out, "content")

        assert out.exists()
        assert out.read_text() == "content"

    def test_overwrites_existing_file(self, tmp_path):
        """Overwrites an existing file atomically."""
        from distill.core import _atomic_write

        out = tmp_path / "file.md"
        out.write_text("old content")
        _atomic_write(out, "new content")

        assert out.read_text() == "new content"


# ---------------------------------------------------------------------------
# DailySocialState tests
# ---------------------------------------------------------------------------


class TestDailySocialStateAdditional:
    """Extra tests for daily social state functions."""

    def test_load_daily_social_state_default(self, tmp_path):
        from distill.pipeline.social import _load_daily_social_state

        state = _load_daily_social_state(tmp_path)
        assert state.day_number == 0

    def test_save_and_load_daily_social_state(self, tmp_path):
        from distill.pipeline.social import (
            DailySocialState,
            _load_daily_social_state,
            _save_daily_social_state,
        )

        state = DailySocialState(day_number=10, last_posted_date="2026-02-15")
        _save_daily_social_state(state, tmp_path)

        loaded = _load_daily_social_state(tmp_path)
        assert loaded.day_number == 10
        assert loaded.last_posted_date == "2026-02-15"

    def test_daily_social_state_model(self):
        """DailySocialState has expected defaults."""
        from distill.core import DailySocialState

        state = DailySocialState()
        assert state.day_number == 0
        assert state.last_posted_date == ""
        assert state.series_name == "100 days of building in public"
