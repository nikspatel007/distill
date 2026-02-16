"""Configuration models for blog generation."""

from enum import StrEnum

from pydantic import BaseModel, Field

from distill.integrations.ghost import GhostConfig  # noqa: F401 — re-export


class BlogPostType(StrEnum):
    """Available blog post types."""

    WEEKLY = "weekly"
    THEMATIC = "thematic"
    READING_LIST = "reading-list"


class Platform(StrEnum):
    """Available publishing platforms."""

    OBSIDIAN = "obsidian"
    GHOST = "ghost"
    MARKDOWN = "markdown"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    REDDIT = "reddit"
    POSTIZ = "postiz"


class BlogConfig(BaseModel):
    """Configuration for blog post generation."""

    target_word_count: int = 1200
    include_diagrams: bool = True
    model: str | None = None
    claude_timeout: int = 360
    max_thematic_posts: int = 2
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.OBSIDIAN])
    ghost: GhostConfig = Field(default_factory=GhostConfig)
