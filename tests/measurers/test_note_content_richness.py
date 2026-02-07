"""Tests for note_content_richness KPI measurer."""

import json
import tempfile
from pathlib import Path

import pytest

from distill.measurers.base import KPIResult
from distill.measurers.note_content_richness import (
    NoteContentRichnessMeasurer,
    score_note_file,
)


def _write_note(path: Path, content: str) -> Path:
    """Write a note file and return the path."""
    path.write_text(content, encoding="utf-8")
    return path


class TestScoreNoteFile:
    """Tests for the file-based note scoring function."""

    def test_score_empty_note(self, tmp_path: Path) -> None:
        """Empty note file should have all fields false."""
        note = _write_note(tmp_path / "session-empty.md", "")
        source, scores = score_note_file(note)
        assert all(not v for v in scores.values())

    def test_score_rich_claude_note(self, tmp_path: Path) -> None:
        """Note file with all expected sections should score all true."""
        content = """\
---
id: test-123
date: 2024-01-15
time: "10:30:00"
source: claude
duration_minutes: 30
tags:
  - "#ai-session"
---
# Session 2024-01-15 10:30

## Summary

Fixed auth bug

## Timeline

- **Started:** 2024-01-15 10:30:00
- **Ended:** 2024-01-15 11:00:00
- **Duration:** 30 minutes

## Tools Used

- **Read**: 5 calls

## Outcomes

- [done] Fixed authentication

## Conversation

> **User** _10:30:00_
> Help me fix the bug

## Related Notes

- [[daily-2024-01-15]]
"""
        note = _write_note(tmp_path / "session-2024-01-15-1030-test1234.md", content)
        source, scores = score_note_file(note)
        assert source == "claude"
        assert scores["has_timestamps"]
        assert scores["has_duration"]
        assert scores["has_tool_list"]
        assert scores["has_outcomes"]
        assert scores["has_conversation_summary"]

    def test_score_vermas_note(self, tmp_path: Path) -> None:
        """VerMAS note file should check for vermas-specific sections."""
        content = """\
---
source: vermas
---
# Session

## Timeline

- **Started:** 2024-01-15 10:00:00
- **Duration:** 15 minutes

## Tools Used

- **Bash**: 3 calls

## Outcomes

- [done] Task completed

## Task Details

- **Task:** implement-feature
- **Cycle:** 1

## Agent Signals

| Time | Agent | Role | Signal |

## Learnings

### Agent: general
"""
        note = _write_note(tmp_path / "vermas-2024-01-15-impl.md", content)
        source, scores = score_note_file(note)
        assert source == "vermas"
        assert scores["has_timestamps"]
        assert scores["has_duration"]
        assert scores["has_tool_list"]
        assert scores["has_outcomes"]
        assert scores["has_vermas_task_details"]
        assert scores["has_vermas_signals"]
        assert scores["has_vermas_learnings"]

    def test_score_partial_note(self, tmp_path: Path) -> None:
        """Partially complete note should have mixed scores."""
        content = """\
---
source: claude
---
# Session

## Timeline

- **Started:** 2024-01-15 10:00:00

## Outcomes

- [done] Fixed
"""
        note = _write_note(tmp_path / "session-2024-01-15-partial.md", content)
        source, scores = score_note_file(note)
        assert scores["has_timestamps"]
        assert not scores["has_duration"]
        assert not scores["has_tool_list"]
        assert scores["has_outcomes"]

    def test_detect_source_from_filename(self, tmp_path: Path) -> None:
        """Source detection works from filename prefix."""
        note = _write_note(tmp_path / "vermas-2024-01-15-task.md", "no frontmatter")
        source, _ = score_note_file(note)
        assert source == "vermas"

    def test_detect_source_from_frontmatter(self, tmp_path: Path) -> None:
        """Source detection works from frontmatter source field."""
        content = "---\nsource: codex\n---\n# Note"
        note = _write_note(tmp_path / "session-something.md", content)
        source, _ = score_note_file(note)
        assert source == "codex"


class TestNoteContentRichnessMeasurer:
    """Tests for the note_content_richness measurer."""

    def test_result_is_kpi_result(self) -> None:
        """Measurer returns a KPIResult with correct KPI name."""
        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure()
        assert isinstance(result, KPIResult)
        assert result.kpi == "note_content_richness"
        assert result.target == 90.0

    def test_value_in_range(self) -> None:
        """Measured value is between 0 and 100."""
        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure()
        assert 0.0 <= result.value <= 100.0

    def test_details_contain_note_info(self) -> None:
        """Details include per-note scores."""
        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure()
        assert "total_notes" in result.details

    def test_json_serialization(self) -> None:
        """Result serializes to valid JSON."""
        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure()
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["kpi"] == "note_content_richness"
        assert isinstance(parsed["value"], float)

    def test_measure_from_note_files(self, tmp_path: Path) -> None:
        """measure_from_note_files scores files on disk."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        rich = """\
---
source: claude
---
# Session

## Timeline
- **Started:** 2024-01-15 10:00:00
- **Duration:** 30 min

## Tools Used
- **Read**: 5 calls

## Outcomes
- [done] Fixed

## Conversation
> User: help
"""
        (sessions_dir / "session-2024-01-15-rich.md").write_text(rich)

        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure_from_note_files(tmp_path)
        assert result.value > 0.0
        assert result.details["total_notes"] == 1
        per_note = result.details["per_note"]
        assert len(per_note) == 1
        assert per_note[0]["source"] == "claude"

    def test_measure_from_empty_dir(self, tmp_path: Path) -> None:
        """Empty note dir gives 0 total notes."""
        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure_from_note_files(tmp_path)
        assert result.details["total_notes"] == 0

    def test_excludes_index_and_daily(self, tmp_path: Path) -> None:
        """index.md and daily-*.md are excluded from scoring."""
        (tmp_path / "index.md").write_text("# Index")
        (tmp_path / "daily-2024-01-15.md").write_text("# Daily")
        (tmp_path / "session-foo.md").write_text("---\nsource: claude\n---\n# Real note")

        measurer = NoteContentRichnessMeasurer()
        result = measurer.measure_from_note_files(tmp_path)
        assert result.details["total_notes"] == 1
