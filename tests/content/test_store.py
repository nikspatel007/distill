"""Tests for ContentStore — JSON-backed content lifecycle store."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from distill.content.models import (
    ContentRecord,
    ContentStatus,
    ContentType,
    ImageRecord,
    PlatformContent,
)
from distill.content.store import STORE_FILENAME, ContentStore


def _make_record(
    slug: str = "test-post",
    content_type: ContentType = ContentType.WEEKLY,
    title: str = "Test Post",
    body: str = "Test body",
    status: ContentStatus = ContentStatus.DRAFT,
    **kwargs: object,
) -> ContentRecord:
    """Helper to build a ContentRecord with sensible defaults."""
    return ContentRecord(
        slug=slug,
        content_type=content_type,
        title=title,
        body=body,
        status=status,
        created_at=datetime.now(tz=UTC),
        **kwargs,  # type: ignore[arg-type]
    )


class TestUpsert:
    def test_creates_record(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        record = _make_record()
        store.upsert(record)

        fetched = store.get("test-post")
        assert fetched is not None
        assert fetched.slug == "test-post"
        assert fetched.title == "Test Post"

    def test_overwrites_existing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(title="Version 1"))
        store.upsert(_make_record(title="Version 2"))

        fetched = store.get("test-post")
        assert fetched is not None
        assert fetched.title == "Version 2"

    def test_persists_to_disk(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record())

        store_path = tmp_path / STORE_FILENAME
        assert store_path.exists()
        data = json.loads(store_path.read_text(encoding="utf-8"))
        assert len(data["records"]) == 1
        assert data["records"][0]["slug"] == "test-post"


class TestGet:
    def test_returns_none_for_missing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        assert store.get("nonexistent") is None

    def test_returns_record_for_existing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="my-post", title="My Post"))

        result = store.get("my-post")
        assert result is not None
        assert result.title == "My Post"


class TestExists:
    def test_false_when_missing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        assert store.exists("nope") is False

    def test_true_when_present(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="present"))
        assert store.exists("present") is True


class TestList:
    def test_empty_store(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        assert store.list() == []

    def test_list_all(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="a"))
        store.upsert(_make_record(slug="b"))
        store.upsert(_make_record(slug="c"))

        results = store.list()
        assert len(results) == 3
        slugs = {r.slug for r in results}
        assert slugs == {"a", "b", "c"}

    def test_filter_by_content_type(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="w1", content_type=ContentType.WEEKLY))
        store.upsert(_make_record(slug="t1", content_type=ContentType.THEMATIC))
        store.upsert(_make_record(slug="w2", content_type=ContentType.WEEKLY))

        results = store.list(content_type=ContentType.WEEKLY)
        assert len(results) == 2
        assert all(r.content_type == ContentType.WEEKLY for r in results)

    def test_filter_by_status(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="draft1", status=ContentStatus.DRAFT))
        store.upsert(_make_record(slug="review1", status=ContentStatus.REVIEW))
        store.upsert(_make_record(slug="draft2", status=ContentStatus.DRAFT))

        results = store.list(status=ContentStatus.DRAFT)
        assert len(results) == 2
        assert all(r.status == ContentStatus.DRAFT for r in results)

    def test_filter_by_both(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(
            _make_record(
                slug="w-draft", content_type=ContentType.WEEKLY, status=ContentStatus.DRAFT
            )
        )
        store.upsert(
            _make_record(
                slug="w-review", content_type=ContentType.WEEKLY, status=ContentStatus.REVIEW
            )
        )
        store.upsert(
            _make_record(
                slug="t-draft", content_type=ContentType.THEMATIC, status=ContentStatus.DRAFT
            )
        )

        results = store.list(content_type=ContentType.WEEKLY, status=ContentStatus.DRAFT)
        assert len(results) == 1
        assert results[0].slug == "w-draft"


class TestUpdateStatus:
    def test_updates_status(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1", status=ContentStatus.DRAFT))

        store.update_status("post1", ContentStatus.REVIEW)

        record = store.get("post1")
        assert record is not None
        assert record.status == ContentStatus.REVIEW

    def test_raises_for_missing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        with pytest.raises(KeyError):
            store.update_status("ghost", ContentStatus.REVIEW)


class TestSavePlatformContent:
    def test_saves_platform_content(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1"))

        pc = PlatformContent(platform="ghost", content="Ghost version of the post")
        store.save_platform_content("post1", "ghost", pc)

        record = store.get("post1")
        assert record is not None
        assert "ghost" in record.platforms
        assert record.platforms["ghost"].content == "Ghost version of the post"

    def test_raises_for_missing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        pc = PlatformContent(platform="ghost", content="Content")
        with pytest.raises(KeyError):
            store.save_platform_content("missing", "ghost", pc)


class TestImages:
    def test_add_image(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1"))

        img = ImageRecord(filename="hero.png", role="hero")
        store.add_image("post1", img)

        record = store.get("post1")
        assert record is not None
        assert len(record.images) == 1
        assert record.images[0].filename == "hero.png"

    def test_add_image_appends(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1"))

        store.add_image("post1", ImageRecord(filename="hero.png", role="hero"))
        store.add_image("post1", ImageRecord(filename="inline.png", role="inline"))

        record = store.get("post1")
        assert record is not None
        assert len(record.images) == 2
        assert record.images[0].filename == "hero.png"
        assert record.images[1].filename == "inline.png"

    def test_add_image_raises_for_missing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        with pytest.raises(KeyError):
            store.add_image("missing", ImageRecord(filename="x.png", role="hero"))

    def test_get_images_returns_empty_for_missing(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        assert store.get_images("nonexistent") == []

    def test_get_images_returns_images(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1"))
        store.add_image("post1", ImageRecord(filename="hero.png", role="hero"))

        images = store.get_images("post1")
        assert len(images) == 1
        assert images[0].filename == "hero.png"


class TestMarkPublished:
    def test_marks_published(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1"))
        pc = PlatformContent(platform="ghost", content="Ghost content")
        store.save_platform_content("post1", "ghost", pc)

        store.mark_published("post1", "ghost", "ext-123")

        record = store.get("post1")
        assert record is not None
        assert record.status == ContentStatus.PUBLISHED
        ghost = record.platforms["ghost"]
        assert ghost.published is True
        assert ghost.published_at is not None
        assert ghost.external_id == "ext-123"

    def test_raises_for_missing_slug(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        with pytest.raises(KeyError, match="missing"):
            store.mark_published("missing", "ghost", "ext-123")

    def test_raises_for_missing_platform(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        store.upsert(_make_record(slug="post1"))

        with pytest.raises(KeyError, match="ghost"):
            store.mark_published("post1", "ghost", "ext-123")


class TestPersistence:
    def test_new_store_reads_existing_file(self, tmp_path: Path):
        # Create and populate first store
        store1 = ContentStore(tmp_path)
        store1.upsert(
            _make_record(
                slug="persisted-post",
                title="Persisted",
                source_dates=[date(2026, 2, 10)],
                tags=["agents"],
            )
        )

        # Create a second store instance from same directory
        store2 = ContentStore(tmp_path)
        record = store2.get("persisted-post")
        assert record is not None
        assert record.title == "Persisted"
        assert record.source_dates == [date(2026, 2, 10)]
        assert record.tags == ["agents"]

    def test_corrupt_file_starts_empty(self, tmp_path: Path):
        store_path = tmp_path / STORE_FILENAME
        store_path.write_text("not valid json", encoding="utf-8")

        store = ContentStore(tmp_path)
        assert store.list() == []

    def test_empty_dir_no_crash(self, tmp_path: Path):
        store = ContentStore(tmp_path)
        assert store.list() == []
        assert store.get("anything") is None
