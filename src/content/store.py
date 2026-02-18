"""JSON-backed content lifecycle store.

Persists all ContentRecords in a single JSON file, loaded on init
and saved after every write operation.  Provides CRUD, filtering,
image management, and publication lifecycle tracking.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from distill.content.models import (
    ContentRecord,
    ContentStatus,
    ContentType,
    ImageRecord,
    PlatformContent,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

STORE_FILENAME = ".distill-content-store.json"

# Alias to avoid shadowing by ContentStore.list method
_list = list


class _StoreData(BaseModel):
    """Internal wrapper for JSON serialization."""

    records: list[ContentRecord] = Field(default_factory=list)


class ContentStore:
    """JSON-backed CRUD store for content records.

    Loads the store file on init and saves after every mutation.
    """

    def __init__(self, output_dir: Path) -> None:
        self._path = output_dir / STORE_FILENAME
        self._data = self._load()

    # ── Private helpers ──────────────────────────────────────────

    def _load(self) -> _StoreData:
        if not self._path.exists():
            return _StoreData()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return _StoreData.model_validate(raw)
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Corrupt content store at %s, starting fresh", self._path)
            return _StoreData()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            self._data.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _find(self, slug: str) -> ContentRecord | None:
        for record in self._data.records:
            if record.slug == slug:
                return record
        return None

    def _require(self, slug: str) -> ContentRecord:
        record = self._find(slug)
        if record is None:
            raise KeyError(slug)
        return record

    # ── Write operations ─────────────────────────────────────────

    def upsert(self, record: ContentRecord) -> None:
        """Insert or replace a content record by slug."""
        self._data.records = [r for r in self._data.records if r.slug != record.slug]
        self._data.records.append(record)
        self._save()

    def update_status(self, slug: str, status: ContentStatus) -> None:
        """Update the lifecycle status of a record.

        Raises KeyError if the slug does not exist.
        """
        record = self._require(slug)
        record.status = status
        self._save()

    def save_platform_content(self, slug: str, platform: str, content: PlatformContent) -> None:
        """Save platform-specific content for a record.

        Raises KeyError if the slug does not exist.
        """
        record = self._require(slug)
        record.platforms[platform] = content
        self._save()

    # ── Read operations ──────────────────────────────────────────

    def get(self, slug: str) -> ContentRecord | None:
        """Return a record by slug, or None if not found."""
        return self._find(slug)

    def list(
        self,
        content_type: ContentType | None = None,
        status: ContentStatus | None = None,
    ) -> _list[ContentRecord]:
        """Return records, optionally filtered by type and/or status."""
        results = self._data.records
        if content_type is not None:
            results = [r for r in results if r.content_type == content_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        return _list(results)

    def exists(self, slug: str) -> bool:
        """Check whether a record with this slug exists."""
        return self._find(slug) is not None

    # ── Image operations ─────────────────────────────────────────

    def add_image(self, slug: str, image: ImageRecord) -> None:
        """Append an image to a record.

        Raises KeyError if the slug does not exist.
        """
        record = self._require(slug)
        record.images.append(image)
        self._save()

    def get_images(self, slug: str) -> _list[ImageRecord]:
        """Return images for a record, or empty list if slug not found."""
        record = self._find(slug)
        if record is None:
            return []
        return _list(record.images)

    # ── Lifecycle operations ─────────────────────────────────────

    def mark_published(self, slug: str, platform: str, external_id: str) -> None:
        """Mark a record as published on a specific platform.

        Sets the platform's published flag, timestamp, and external ID.
        Also promotes the record status to PUBLISHED.

        Raises KeyError if the slug or platform does not exist.
        """
        record = self._require(slug)
        if platform not in record.platforms:
            raise KeyError(platform)
        pc = record.platforms[platform]
        pc.published = True
        pc.published_at = datetime.now(tz=UTC)
        pc.external_id = external_id
        record.status = ContentStatus.PUBLISHED
        self._save()
