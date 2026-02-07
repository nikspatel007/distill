"""Tests for journal cache."""

import json
from datetime import date
from pathlib import Path

from distill.journal.cache import JournalCache
from distill.journal.config import JournalStyle


class TestJournalCache:
    """Tests for JournalCache."""

    def test_not_generated_initially(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        assert not cache.is_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

    def test_mark_and_check(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        cache.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        assert cache.is_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

    def test_different_count_invalidates(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        cache.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        # Same date/style but different session count -> stale
        assert not cache.is_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 5)

    def test_different_style_separate(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        cache.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        assert not cache.is_generated(date(2026, 2, 5), JournalStyle.TECH_BLOG, 3)

    def test_different_date_separate(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        cache.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        assert not cache.is_generated(date(2026, 2, 6), JournalStyle.DEV_JOURNAL, 3)

    def test_persists_to_disk(self, tmp_path: Path):
        cache1 = JournalCache(tmp_path)
        cache1.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        # New cache instance should load from disk
        cache2 = JournalCache(tmp_path)
        assert cache2.is_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

    def test_creates_directory(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        cache.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        cache_file = tmp_path / "journal" / ".journal-cache.json"
        assert cache_file.exists()

    def test_cache_file_is_valid_json(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        cache.mark_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

        cache_file = tmp_path / "journal" / ".journal-cache.json"
        data = json.loads(cache_file.read_text())
        assert "2026-02-05:dev-journal" in data

    def test_handles_corrupt_cache(self, tmp_path: Path):
        # Write invalid JSON
        cache_dir = tmp_path / "journal"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".journal-cache.json").write_text("not json")

        # Should not raise, just start fresh
        cache = JournalCache(tmp_path)
        assert not cache.is_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)

    def test_handles_missing_cache_file(self, tmp_path: Path):
        cache = JournalCache(tmp_path)
        assert not cache.is_generated(date(2026, 2, 5), JournalStyle.DEV_JOURNAL, 3)
