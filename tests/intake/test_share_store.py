"""Tests for ShareStore — URL sharing for intake pipeline."""

import json
from pathlib import Path

import pytest

from distill.intake.models import ContentSource, ShareItem
from distill.intake.services import SHARES_FILENAME, ShareStore


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path


class TestShareStore:
    def test_add_creates_item(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        share = store.add("https://example.com/article", note="good read")
        assert share.url == "https://example.com/article"
        assert share.note == "good read"
        assert share.used is False
        assert len(share.id) == 12

    def test_add_with_tags(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        share = store.add("https://example.com", tags=["ai", "ml"])
        assert share.tags == ["ai", "ml"]

    def test_list_pending(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        store.add("https://a.com")
        store.add("https://b.com")
        store.mark_used(store.list_all()[0].id, "intake-2026-03-01")
        assert len(store.list_pending()) == 1
        assert store.list_pending()[0].url == "https://b.com"

    def test_list_all(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        store.add("https://a.com")
        store.add("https://b.com")
        assert len(store.list_all()) == 2

    def test_mark_used(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        share = store.add("https://example.com")
        store.mark_used(share.id, "intake-2026-03-01")
        reloaded = ShareStore(tmp_output)
        found = [s for s in reloaded.list_all() if s.id == share.id][0]
        assert found.used is True
        assert found.used_in == "intake-2026-03-01"

    def test_remove(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        share = store.add("https://example.com")
        store.remove(share.id)
        assert len(store.list_all()) == 0

    def test_to_content_items(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        store.add("https://example.com/article", note="test note")
        items = store.to_content_items()
        assert len(items) == 1
        item = items[0]
        assert item.source == ContentSource.MANUAL
        assert item.url == "https://example.com/article"
        assert item.body == ""
        assert item.metadata["share_id"] == store.list_all()[0].id
        assert item.metadata["note"] == "test note"

    def test_to_content_items_skips_used(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        share = store.add("https://example.com")
        store.mark_used(share.id, "intake-2026-03-01")
        assert len(store.to_content_items()) == 0

    def test_corrupt_file_handled(self, tmp_output: Path) -> None:
        (tmp_output / SHARES_FILENAME).write_text("not json", encoding="utf-8")
        store = ShareStore(tmp_output)
        assert len(store.list_all()) == 0

    def test_missing_file_returns_empty(self, tmp_output: Path) -> None:
        store = ShareStore(tmp_output)
        assert len(store.list_all()) == 0

    def test_persistence(self, tmp_output: Path) -> None:
        store1 = ShareStore(tmp_output)
        store1.add("https://example.com")
        store2 = ShareStore(tmp_output)
        assert len(store2.list_all()) == 1
        assert store2.list_all()[0].url == "https://example.com"
