"""Tests for blog journal reader (markdown parsing, no LLM)."""

from datetime import date
from pathlib import Path

from distill.blog.reader import (
    JournalReader,
    _extract_prose,
    _parse_frontmatter,
)

SAMPLE_JOURNAL = """\
---
date: 2026-02-05
type: journal
style: dev-journal
sessions_count: 5
duration_minutes: 120
tags:
  - journal
  - python
  - refactoring
projects:
  - distill
  - session-insights
created: 2026-02-05T10:00:00
---

# Dev Journal: February 05, 2026

Today I worked on the multi-agent orchestration system. The branch merge
logic needed a complete rethink after three consecutive failures.

I spent the morning debugging the worktree cleanup issue. By afternoon,
the pattern was clear: we needed to remove worktrees after merge, not before.

---

*5 sessions | 120 minutes
| Projects: distill, session-insights*

## Related

- [[daily/daily-2026-02-05|Daily Summary]]
"""


class TestParseFrontmatter:
    def test_basic_parsing(self):
        fm = _parse_frontmatter(SAMPLE_JOURNAL)
        assert fm["date"] == "2026-02-05"
        assert fm["type"] == "journal"
        assert fm["style"] == "dev-journal"
        assert fm["sessions_count"] == "5"

    def test_list_fields(self):
        fm = _parse_frontmatter(SAMPLE_JOURNAL)
        assert isinstance(fm["tags"], list)
        assert "journal" in fm["tags"]
        assert "python" in fm["tags"]

    def test_projects_list(self):
        fm = _parse_frontmatter(SAMPLE_JOURNAL)
        assert isinstance(fm["projects"], list)
        assert "distill" in fm["projects"]

    def test_no_frontmatter(self):
        fm = _parse_frontmatter("Just some text with no frontmatter")
        assert fm == {}

    def test_empty_frontmatter(self):
        fm = _parse_frontmatter("---\n---\nBody text")
        assert fm == {}


class TestExtractProse:
    def test_extracts_body(self):
        prose = _extract_prose(SAMPLE_JOURNAL)
        assert "multi-agent orchestration" in prose
        assert "worktree cleanup" in prose

    def test_strips_title(self):
        prose = _extract_prose(SAMPLE_JOURNAL)
        assert "# Dev Journal" not in prose

    def test_strips_related_section(self):
        prose = _extract_prose(SAMPLE_JOURNAL)
        assert "## Related" not in prose
        assert "Daily Summary" not in prose

    def test_strips_metrics_footer(self):
        prose = _extract_prose(SAMPLE_JOURNAL)
        assert "5 sessions | 120 minutes" not in prose


class TestJournalReader:
    def test_read_all(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir()

        (journal_dir / "journal-2026-02-05-dev-journal.md").write_text(
            SAMPLE_JOURNAL, encoding="utf-8"
        )
        (journal_dir / "journal-2026-02-04-dev-journal.md").write_text(
            SAMPLE_JOURNAL.replace("2026-02-05", "2026-02-04"),
            encoding="utf-8",
        )

        reader = JournalReader()
        entries = reader.read_all(journal_dir)

        assert len(entries) == 2
        assert entries[0].date == date(2026, 2, 4)
        assert entries[1].date == date(2026, 2, 5)

    def test_read_week(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir()

        # W06 2026 starts on Feb 2
        (journal_dir / "journal-2026-02-03-dev-journal.md").write_text(
            SAMPLE_JOURNAL.replace("2026-02-05", "2026-02-03"),
            encoding="utf-8",
        )
        (journal_dir / "journal-2026-02-05-dev-journal.md").write_text(
            SAMPLE_JOURNAL, encoding="utf-8"
        )
        # W07
        (journal_dir / "journal-2026-02-10-dev-journal.md").write_text(
            SAMPLE_JOURNAL.replace("2026-02-05", "2026-02-10"),
            encoding="utf-8",
        )

        reader = JournalReader()
        entries = reader.read_week(journal_dir, 2026, 6)

        assert len(entries) == 2
        assert all(e.date.isocalendar().week == 6 for e in entries)

    def test_read_date_range(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir()

        for day in (3, 4, 5, 6, 7):
            (journal_dir / f"journal-2026-02-{day:02d}-dev-journal.md").write_text(
                SAMPLE_JOURNAL.replace("2026-02-05", f"2026-02-{day:02d}"),
                encoding="utf-8",
            )

        reader = JournalReader()
        entries = reader.read_date_range(
            journal_dir, date(2026, 2, 4), date(2026, 2, 6)
        )

        assert len(entries) == 3
        assert entries[0].date == date(2026, 2, 4)
        assert entries[-1].date == date(2026, 2, 6)

    def test_empty_directory(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir()

        reader = JournalReader()
        assert reader.read_all(journal_dir) == []

    def test_nonexistent_directory(self, tmp_path: Path):
        reader = JournalReader()
        assert reader.read_all(tmp_path / "nonexistent") == []

    def test_parses_metadata(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir()

        (journal_dir / "journal-2026-02-05-dev-journal.md").write_text(
            SAMPLE_JOURNAL, encoding="utf-8"
        )

        reader = JournalReader()
        entries = reader.read_all(journal_dir)

        entry = entries[0]
        assert entry.date == date(2026, 2, 5)
        assert entry.style == "dev-journal"
        assert entry.sessions_count == 5
        assert entry.duration_minutes == 120.0
        assert "python" in entry.tags
        assert "distill" in entry.projects
        assert entry.prose != ""

    def test_date_from_filename_fallback(self, tmp_path: Path):
        journal_dir = tmp_path / "journal"
        journal_dir.mkdir()

        # Journal with no date in frontmatter
        no_date = "---\ntype: journal\nstyle: dev-journal\n---\n\n# Title\n\nSome prose."
        (journal_dir / "journal-2026-02-05-dev-journal.md").write_text(
            no_date, encoding="utf-8"
        )

        reader = JournalReader()
        entries = reader.read_all(journal_dir)

        assert len(entries) == 1
        assert entries[0].date == date(2026, 2, 5)
