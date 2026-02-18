"""Content domain models — pure Pydantic v2 data types.

These models represent the canonical content lifecycle: from draft
through review, ready, published, and archived states.  Every piece
of generated content (blog posts, digests, social posts, seeds) is
tracked as a ContentRecord with optional per-platform variants and
image attachments.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ContentStatus(StrEnum):
    """Lifecycle status of a content record."""

    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentType(StrEnum):
    """Category of generated content."""

    WEEKLY = "weekly"
    THEMATIC = "thematic"
    READING_LIST = "reading_list"
    DIGEST = "digest"
    DAILY_SOCIAL = "daily_social"
    SEED = "seed"


class ImageRecord(BaseModel):
    """An image attached to a content record."""

    filename: str
    role: str  # "hero", "inline", "social"
    prompt: str = ""
    relative_path: str = ""


class PlatformContent(BaseModel):
    """Platform-specific variant of a content record."""

    platform: str
    content: str
    published: bool = False
    published_at: datetime | None = None
    external_id: str = ""


class ChatMessage(BaseModel):
    """A single message in a content editing chat history."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str


class ContentRecord(BaseModel):
    """Canonical content record — the spine of the content lifecycle.

    Tracks a piece of generated content from initial draft through
    publication, including per-platform variants, image attachments,
    and an optional chat editing history.
    """

    slug: str
    content_type: ContentType
    title: str
    body: str
    status: ContentStatus = ContentStatus.DRAFT
    created_at: datetime
    source_dates: list[date] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    images: list[ImageRecord] = Field(default_factory=list)
    platforms: dict[str, PlatformContent] = Field(default_factory=dict)
    chat_history: list[ChatMessage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    file_path: str = ""
