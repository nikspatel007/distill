"""Tests for reading brief store."""
from pathlib import Path

from distill.brief.models import ReadingBrief, ReadingHighlight
from distill.brief.store import BRIEF_FILENAME, load_reading_brief, save_reading_brief


class TestStore:
    def test_save_and_load(self, tmp_path: Path):
        brief = ReadingBrief(
            date="2026-03-05",
            highlights=[
                ReadingHighlight(
                    title="Test", source="Blog", summary="Summary."
                )
            ],
        )
        save_reading_brief(brief, tmp_path)
        loaded = load_reading_brief(tmp_path, "2026-03-05")
        assert loaded is not None
        assert loaded.date == "2026-03-05"
        assert len(loaded.highlights) == 1

    def test_load_missing(self, tmp_path: Path):
        assert load_reading_brief(tmp_path, "2026-03-05") is None

    def test_load_wrong_date(self, tmp_path: Path):
        brief = ReadingBrief(date="2026-03-04")
        save_reading_brief(brief, tmp_path)
        assert load_reading_brief(tmp_path, "2026-03-05") is None

    def test_overwrite_same_date(self, tmp_path: Path):
        brief1 = ReadingBrief(date="2026-03-05")
        save_reading_brief(brief1, tmp_path)
        brief2 = ReadingBrief(
            date="2026-03-05",
            highlights=[
                ReadingHighlight(title="New", source="X", summary="Y.")
            ],
        )
        save_reading_brief(brief2, tmp_path)
        loaded = load_reading_brief(tmp_path, "2026-03-05")
        assert loaded is not None
        assert len(loaded.highlights) == 1
        assert loaded.highlights[0].title == "New"

    def test_multiple_dates(self, tmp_path: Path):
        save_reading_brief(ReadingBrief(date="2026-03-04"), tmp_path)
        save_reading_brief(ReadingBrief(date="2026-03-05"), tmp_path)
        assert load_reading_brief(tmp_path, "2026-03-04") is not None
        assert load_reading_brief(tmp_path, "2026-03-05") is not None
