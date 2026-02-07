"""Tests for journal working memory."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from distill.journal.config import JournalConfig
from distill.journal.context import DailyContext
from distill.journal.memory import (
    MEMORY_FILENAME,
    DailyMemoryEntry,
    MemoryThread,
    WorkingMemory,
    load_memory,
    save_memory,
)
from distill.journal.synthesizer import JournalSynthesizer, SynthesisError


def _make_entry(day: int = 5, **kwargs) -> DailyMemoryEntry:
    defaults = dict(
        date=date(2026, 2, day),
        themes=["debugging", "refactoring"],
        key_insights=["Cache invalidation is hard"],
        decisions_made=["Use direct-to-main merges"],
        open_questions=["Rate limiting strategy?"],
        tomorrow_intentions=["Start recovery plan"],
    )
    defaults.update(kwargs)
    return DailyMemoryEntry(**defaults)


def _make_thread(**kwargs) -> MemoryThread:
    defaults = dict(
        name="merge-drops-source",
        summary="Branch merges lost code",
        first_mentioned=date(2026, 2, 1),
        last_mentioned=date(2026, 2, 5),
        status="open",
    )
    defaults.update(kwargs)
    return MemoryThread(**defaults)


class TestWorkingMemoryRoundTrip:
    """Save/load round-trip tests."""

    def test_save_and_load(self, tmp_path):
        memory = WorkingMemory(
            entries=[_make_entry()],
            threads=[_make_thread()],
        )
        save_memory(memory, tmp_path)
        loaded = load_memory(tmp_path)

        assert len(loaded.entries) == 1
        assert loaded.entries[0].date == date(2026, 2, 5)
        assert len(loaded.threads) == 1
        assert loaded.threads[0].name == "merge-drops-source"

    def test_load_missing_file(self, tmp_path):
        memory = load_memory(tmp_path)
        assert memory.entries == []
        assert memory.threads == []

    def test_load_corrupt_file(self, tmp_path):
        memory_path = tmp_path / "journal" / MEMORY_FILENAME
        memory_path.parent.mkdir(parents=True)
        memory_path.write_text("not valid json", encoding="utf-8")

        memory = load_memory(tmp_path)
        assert memory.entries == []

    def test_creates_directory(self, tmp_path):
        memory = WorkingMemory(entries=[_make_entry()])
        save_memory(memory, tmp_path)

        assert (tmp_path / "journal" / MEMORY_FILENAME).exists()


class TestRenderForPrompt:
    """Tests for WorkingMemory.render_for_prompt()."""

    def test_empty_memory_renders_empty(self):
        memory = WorkingMemory()
        assert memory.render_for_prompt() == ""

    def test_renders_entry(self):
        memory = WorkingMemory(entries=[_make_entry()])
        text = memory.render_for_prompt()

        assert "# Previous Context" in text
        assert "2026-02-05" in text
        assert "debugging" in text
        assert "Cache invalidation is hard" in text
        assert "Use direct-to-main merges" in text
        assert "Rate limiting strategy?" in text
        assert "Start recovery plan" in text

    def test_renders_multiple_entries_in_order(self):
        memory = WorkingMemory(
            entries=[_make_entry(day=4), _make_entry(day=5)]
        )
        text = memory.render_for_prompt()
        pos_4 = text.index("2026-02-04")
        pos_5 = text.index("2026-02-05")
        assert pos_4 < pos_5

    def test_renders_open_threads_only(self):
        memory = WorkingMemory(
            threads=[
                _make_thread(name="open-thread", status="open"),
                _make_thread(name="resolved-thread", status="resolved"),
            ]
        )
        text = memory.render_for_prompt()
        assert "open-thread" in text
        assert "resolved-thread" not in text

    def test_renders_thread_details(self):
        memory = WorkingMemory(
            threads=[_make_thread()],
        )
        text = memory.render_for_prompt()
        assert "Ongoing Threads" in text
        assert "merge-drops-source" in text
        assert "2026-02-01" in text
        assert "Branch merges lost code" in text


class TestAddEntry:
    """Tests for WorkingMemory.add_entry()."""

    def test_appends_new_entry(self):
        memory = WorkingMemory()
        memory.add_entry(_make_entry(day=5))
        assert len(memory.entries) == 1

    def test_replaces_same_date(self):
        memory = WorkingMemory()
        memory.add_entry(_make_entry(day=5, themes=["old"]))
        memory.add_entry(_make_entry(day=5, themes=["new"]))
        assert len(memory.entries) == 1
        assert memory.entries[0].themes == ["new"]

    def test_sorts_by_date(self):
        memory = WorkingMemory()
        memory.add_entry(_make_entry(day=7))
        memory.add_entry(_make_entry(day=3))
        memory.add_entry(_make_entry(day=5))
        dates = [e.date.day for e in memory.entries]
        assert dates == [3, 5, 7]


class TestPrune:
    """Tests for WorkingMemory.prune()."""

    def test_removes_old_entries(self):
        memory = WorkingMemory(
            entries=[
                _make_entry(day=1),
                _make_entry(day=3),
                _make_entry(day=5),
            ]
        )
        memory.prune(window_days=3)
        dates = [e.date.day for e in memory.entries]
        assert 1 not in dates
        assert 5 in dates

    def test_keeps_recent_entries(self):
        memory = WorkingMemory(
            entries=[_make_entry(day=4), _make_entry(day=5)]
        )
        memory.prune(window_days=7)
        assert len(memory.entries) == 2

    def test_empty_prune_no_error(self):
        memory = WorkingMemory()
        memory.prune(window_days=7)
        assert memory.entries == []

    def test_removes_old_resolved_threads(self):
        memory = WorkingMemory(
            entries=[_make_entry(day=10)],
            threads=[
                _make_thread(
                    name="old-resolved",
                    status="resolved",
                    last_mentioned=date(2026, 2, 1),
                ),
                _make_thread(
                    name="recent-resolved",
                    status="resolved",
                    last_mentioned=date(2026, 2, 9),
                ),
                _make_thread(
                    name="old-open",
                    status="open",
                    last_mentioned=date(2026, 2, 1),
                ),
            ],
        )
        memory.prune(window_days=3)
        names = [t.name for t in memory.threads]
        assert "old-resolved" not in names
        assert "recent-resolved" in names
        assert "old-open" in names  # Open threads kept regardless


class TestUpdateThreads:
    """Tests for WorkingMemory.update_threads()."""

    def test_adds_new_thread(self):
        memory = WorkingMemory()
        memory.update_threads([_make_thread(name="new-thread")])
        assert len(memory.threads) == 1
        assert memory.threads[0].name == "new-thread"

    def test_updates_existing_thread(self):
        memory = WorkingMemory(
            threads=[_make_thread(name="existing", summary="old state")]
        )
        memory.update_threads([
            _make_thread(
                name="existing",
                summary="new state",
                last_mentioned=date(2026, 2, 6),
            )
        ])
        assert len(memory.threads) == 1
        assert memory.threads[0].summary == "new state"
        assert memory.threads[0].last_mentioned == date(2026, 2, 6)

    def test_resolves_thread(self):
        memory = WorkingMemory(
            threads=[_make_thread(name="fix-bug", status="open")]
        )
        memory.update_threads([
            _make_thread(name="fix-bug", status="resolved")
        ])
        assert memory.threads[0].status == "resolved"


class TestContextInjection:
    """Tests for previous_context in DailyContext.render_text()."""

    def test_renders_without_previous_context(self):
        ctx = DailyContext(
            date=date(2026, 2, 5),
            total_sessions=1,
            total_duration_minutes=30.0,
        )
        text = ctx.render_text()
        assert "Previous Context" not in text

    def test_renders_with_previous_context(self):
        ctx = DailyContext(
            date=date(2026, 2, 5),
            total_sessions=1,
            total_duration_minutes=30.0,
            previous_context="# Previous Context\n\nYesterday was productive.",
        )
        text = ctx.render_text()
        assert "Previous Context" in text
        assert "Yesterday was productive" in text


class TestExtractMemory:
    """Tests for JournalSynthesizer.extract_memory()."""

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_extracts_valid_memory(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "themes": ["debugging", "recovery"],
                "key_insights": ["Direct merges are safer"],
                "decisions_made": ["Switch to direct-to-main"],
                "open_questions": ["Rate limiting?"],
                "tomorrow_intentions": ["Start recovery"],
                "threads": [
                    {
                        "name": "merge-issue",
                        "summary": "Merges drop code",
                        "status": "open",
                    }
                ],
            }),
            stderr="",
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        entry, threads = synthesizer.extract_memory(
            "Today I debugged merge issues...", date(2026, 2, 5)
        )

        assert entry.date == date(2026, 2, 5)
        assert "debugging" in entry.themes
        assert "Direct merges are safer" in entry.key_insights
        assert len(threads) == 1
        assert threads[0].name == "merge-issue"
        assert threads[0].first_mentioned == date(2026, 2, 5)

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_strips_markdown_fences(self, mock_run):
        fenced = '```json\n{"themes": ["test"], "key_insights": [], "decisions_made": [], "open_questions": [], "tomorrow_intentions": [], "threads": []}\n```'
        mock_run.return_value = MagicMock(
            returncode=0, stdout=fenced, stderr=""
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        entry, threads = synthesizer.extract_memory("prose", date(2026, 2, 5))
        assert entry.themes == ["test"]

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_invalid_json_raises(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="not json at all", stderr=""
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        with pytest.raises(SynthesisError, match="invalid JSON"):
            synthesizer.extract_memory("prose", date(2026, 2, 5))

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_cli_failure_raises(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error"
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        with pytest.raises(SynthesisError, match="exited 1"):
            synthesizer.extract_memory("prose", date(2026, 2, 5))

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_empty_threads(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "themes": ["testing"],
                "key_insights": [],
                "decisions_made": [],
                "open_questions": [],
                "tomorrow_intentions": [],
                "threads": [],
            }),
            stderr="",
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        entry, threads = synthesizer.extract_memory("prose", date(2026, 2, 5))
        assert entry.themes == ["testing"]
        assert threads == []

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_passes_model_flag(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "themes": [], "key_insights": [], "decisions_made": [],
                "open_questions": [], "tomorrow_intentions": [], "threads": [],
            }),
            stderr="",
        )
        config = JournalConfig(model="claude-haiku-4-5-20251001")
        synthesizer = JournalSynthesizer(config)
        synthesizer.extract_memory("prose", date(2026, 2, 5))

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-haiku-4-5-20251001" in cmd
