"""Pure data models for blog generation.

All Pydantic models and enums live here. No I/O, no business logic,
no subprocess calls. Services import from this module; this module
only imports from stdlib, third-party packages, and distill.shared.*.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from distill.integrations.ghost import GhostConfig  # noqa: F401 -- re-export
from distill.journal.models import MemoryThread  # noqa: F401 -- used by ThematicBlogContext
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Reader models (parsed from markdown files)
# ---------------------------------------------------------------------------


class JournalEntry(BaseModel):
    """Parsed journal entry from a markdown file."""

    date: date
    style: str = ""
    sessions_count: int = 0
    duration_minutes: float = 0.0
    tags: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    prose: str = ""
    file_path: Path = Path(".")


class IntakeDigestEntry(BaseModel):
    """Parsed intake digest entry from a markdown file."""

    date: date
    themes: list[str] = Field(default_factory=list)
    key_items: list[str] = Field(default_factory=list)
    prose: str = ""
    file_path: Path = Path(".")


# ---------------------------------------------------------------------------
# Blog state
# ---------------------------------------------------------------------------


class BlogPostRecord(BaseModel):
    """Record of a generated blog post."""

    slug: str
    post_type: str
    generated_at: datetime
    source_dates: list[date] = Field(default_factory=list)
    file_path: str = ""


class BlogState(BaseModel):
    """Tracks what blog posts have been generated."""

    posts: list[BlogPostRecord] = Field(default_factory=list)

    def is_generated(self, slug: str) -> bool:
        """Check if a blog post with this slug has already been generated."""
        return any(p.slug == slug for p in self.posts)

    def mark_generated(self, record: BlogPostRecord) -> None:
        """Record that a blog post was generated.

        Replaces any existing record with the same slug.
        """
        self.posts = [p for p in self.posts if p.slug != record.slug]
        self.posts.append(record)


# ---------------------------------------------------------------------------
# Blog memory
# ---------------------------------------------------------------------------


class BlogPostSummary(BaseModel):
    """Summary of a published blog post for cross-referencing."""

    slug: str
    title: str
    post_type: str  # "weekly" or "thematic"
    date: date
    key_points: list[str] = Field(default_factory=list)
    themes_covered: list[str] = Field(default_factory=list)
    examples_used: list[str] = Field(default_factory=list)
    platforms_published: list[str] = Field(default_factory=list)
    postiz_ids: list[str] = Field(default_factory=list)


class BlogMemory(BaseModel):
    """Rolling memory of published blog content."""

    posts: list[BlogPostSummary] = Field(default_factory=list)

    def render_for_prompt(self) -> str:
        """Render as context for LLM injection.

        Returns empty string if no posts exist. Includes dedup section
        listing examples/anecdotes already used across previous posts.
        """
        if not self.posts:
            return ""

        lines: list[str] = ["## Previous Blog Posts", ""]
        for post in sorted(self.posts, key=lambda p: p.date, reverse=True):
            points = "; ".join(post.key_points) if post.key_points else "no summary"
            lines.append(f'- "{post.title}" ({post.date.isoformat()}): {points}')
        lines.append("")

        # Collect all examples used across posts for dedup
        all_examples: list[str] = []
        for post in self.posts:
            all_examples.extend(post.examples_used)
        if all_examples:
            lines.append("## DO NOT REUSE These Examples")
            lines.append(
                "The following specific examples, anecdotes, bugs, and statistics"
                " have already been used in previous posts. Find DIFFERENT"
                " evidence from the journal entries. Never recycle these:"
            )
            lines.append("")
            for ex in sorted(set(all_examples)):
                lines.append(f"- {ex}")
            lines.append("")

        return "\n".join(lines)

    def add_post(self, summary: BlogPostSummary) -> None:
        """Add or replace a post summary by slug."""
        self.posts = [p for p in self.posts if p.slug != summary.slug]
        self.posts.append(summary)

    def is_published_to(self, slug: str, platform: str) -> bool:
        """Check if a post has been published to a platform."""
        for post in self.posts:
            if post.slug == slug and platform in post.platforms_published:
                return True
        return False

    def mark_published(self, slug: str, platform: str) -> None:
        """Add platform to a post's platforms_published list."""
        for post in self.posts:
            if post.slug == slug and platform not in post.platforms_published:
                post.platforms_published.append(platform)
                return


# ---------------------------------------------------------------------------
# Theme models
# ---------------------------------------------------------------------------


class ThemeDefinition(BaseModel):
    """A blog-worthy theme with detection criteria."""

    slug: str
    title: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    thread_patterns: list[str] = Field(default_factory=list)
    min_evidence_days: int = 3


# ---------------------------------------------------------------------------
# Context models
# ---------------------------------------------------------------------------


class WeeklyBlogContext(BaseModel):
    """Context for a weekly synthesis blog post."""

    year: int
    week: int
    week_start: date
    week_end: date
    entries: list[JournalEntry] = Field(default_factory=list)
    total_sessions: int = 0
    total_duration_minutes: float = 0.0
    projects: list[str] = Field(default_factory=list)
    all_tags: list[str] = Field(default_factory=list)
    working_memory: str = ""
    combined_prose: str = ""
    intake_context: str = ""
    reading_themes: list[str] = Field(default_factory=list)
    project_context: str = ""
    editorial_notes: str = ""


class ThematicBlogContext(BaseModel):
    """Context for a thematic deep-dive blog post."""

    theme: ThemeDefinition
    evidence_entries: list[JournalEntry] = Field(default_factory=list)
    date_range: tuple[date, date] = (date.min, date.min)
    evidence_count: int = 0
    relevant_threads: list[MemoryThread] = Field(default_factory=list)
    combined_evidence: str = ""
    intake_context: str = ""
    seed_angle: str = ""
    project_context: str = ""
    editorial_notes: str = ""


# ---------------------------------------------------------------------------
# Reading list models
# ---------------------------------------------------------------------------


class ReadingListContext(BaseModel):
    """Context for a reading list blog post."""

    week_start: date
    week_end: date
    items: list[dict[str, object]] = Field(default_factory=list)
    total_items_read: int = 0
    themes: list[str] = Field(default_factory=list)

    @property
    def year(self) -> int:
        return self.week_start.isocalendar().year

    @property
    def week(self) -> int:
        return self.week_start.isocalendar().week
