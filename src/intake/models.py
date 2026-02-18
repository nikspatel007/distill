"""Pure data models for the intake pipeline.

All Pydantic models and enums live here. No I/O, no business logic,
no subprocess calls. Services import from this module; this module
only imports from stdlib, third-party packages, and distill.shared.*.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Content enums
# ---------------------------------------------------------------------------


class ContentSource(StrEnum):
    """Supported content sources."""

    RSS = "rss"
    GMAIL = "gmail"
    SUBSTACK = "substack"
    BROWSER = "browser"
    LINKEDIN = "linkedin"
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    SESSION = "session"
    SEEDS = "seeds"
    MANUAL = "manual"


class ContentType(StrEnum):
    """Content format categories."""

    ARTICLE = "article"
    NEWSLETTER = "newsletter"
    POST = "post"
    COMMENT = "comment"
    VIDEO = "video"
    THREAD = "thread"
    WEBPAGE = "webpage"


# ---------------------------------------------------------------------------
# Core content models
# ---------------------------------------------------------------------------


class Highlight(BaseModel):
    """A highlighted passage from a content item."""

    text: str
    note: str = ""
    position: int = 0


class ContentItem(BaseModel):
    """Source-agnostic content item — the canonical model.

    Every source parser produces these. The core pipeline operates
    entirely on ``ContentItem[]`` and never knows which source
    produced an item. Analogous to ``BaseSession`` in the session
    parsing pipeline.
    """

    id: str
    url: str = ""
    title: str = ""
    body: str = ""
    excerpt: str = ""
    word_count: int = 0
    author: str = ""
    site_name: str = ""
    source: ContentSource
    source_id: str = ""
    content_type: ContentType = ContentType.ARTICLE
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    saved_at: datetime = Field(default_factory=datetime.now)
    consumed_at: datetime | None = None
    is_starred: bool = False
    highlights: list[Highlight] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Per-source configuration models  (from config.py)
# ---------------------------------------------------------------------------


class RSSConfig(BaseModel):
    """RSS feed configuration."""

    feeds: list[str] = Field(default_factory=list)
    opml_file: str = ""
    feeds_file: str = ""
    fetch_timeout: int = 30
    max_items_per_feed: int = 50
    max_age_days: int = 7
    extract_full_text: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.feeds or self.opml_file or self.feeds_file)


class GmailIntakeConfig(BaseModel):
    """Gmail intake configuration."""

    credentials_file: str = ""
    token_file: str = ""
    query: str = "category:promotions OR label:newsletters"

    @property
    def is_configured(self) -> bool:
        return bool(self.credentials_file)


class RedditIntakeConfig(BaseModel):
    """Reddit intake configuration."""

    client_id: str = ""
    client_secret: str = ""
    username: str = ""
    password: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @classmethod
    def from_env(cls) -> RedditIntakeConfig:
        return cls(
            client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
            username=os.environ.get("REDDIT_USERNAME", ""),
            password=os.environ.get("REDDIT_PASSWORD", ""),
        )


class BrowserIntakeConfig(BaseModel):
    """Browser history intake configuration."""

    browsers: list[str] = Field(default_factory=lambda: ["chrome"])
    min_visit_duration_seconds: int = 30
    domain_allowlist: list[str] = Field(default_factory=list)
    domain_blocklist: list[str] = Field(
        default_factory=lambda: [
            "google.com",
            "localhost",
            "github.com",
            "stackoverflow.com",
        ]
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.browsers)


class LinkedInIntakeConfig(BaseModel):
    """LinkedIn GDPR export configuration."""

    export_path: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.export_path)


class SubstackIntakeConfig(BaseModel):
    """Substack newsletter configuration."""

    blog_urls: list[str] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return bool(self.blog_urls)


class YouTubeIntakeConfig(BaseModel):
    """YouTube intake configuration."""

    api_key: str = ""
    credentials_file: str = ""
    token_file: str = ""
    fetch_transcripts: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key or self.credentials_file)

    @classmethod
    def from_env(cls) -> YouTubeIntakeConfig:
        return cls(
            api_key=os.environ.get("YOUTUBE_API_KEY", ""),
        )


class TwitterIntakeConfig(BaseModel):
    """Twitter/X intake configuration."""

    export_path: str = ""
    nitter_feeds: list[str] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return bool(self.export_path or self.nitter_feeds)


class SessionIntakeConfig(BaseModel):
    """Session intake configuration."""

    session_dirs: list[str] = Field(default_factory=list)
    include_global: bool = False
    sources: list[str] = Field(default_factory=lambda: ["claude", "codex"])

    @property
    def is_configured(self) -> bool:
        return True  # sessions are always available locally


class IntakeConfig(BaseModel):
    """Top-level intake configuration."""

    rss: RSSConfig = Field(default_factory=RSSConfig)
    gmail: GmailIntakeConfig = Field(default_factory=GmailIntakeConfig)
    reddit: RedditIntakeConfig = Field(default_factory=RedditIntakeConfig)
    browser: BrowserIntakeConfig = Field(default_factory=BrowserIntakeConfig)
    linkedin: LinkedInIntakeConfig = Field(default_factory=LinkedInIntakeConfig)
    substack: SubstackIntakeConfig = Field(default_factory=SubstackIntakeConfig)
    youtube: YouTubeIntakeConfig = Field(default_factory=YouTubeIntakeConfig)
    twitter: TwitterIntakeConfig = Field(default_factory=TwitterIntakeConfig)
    session: SessionIntakeConfig = Field(default_factory=SessionIntakeConfig)

    model: str | None = None
    claude_timeout: int = 180
    target_word_count: int = 800
    user_name: str = ""
    user_role: str = "software engineer"

    domain_blocklist: list[str] = Field(default_factory=lambda: ["google.com", "localhost"])
    min_word_count: int = 50
    max_items_per_source: int = 50


# ---------------------------------------------------------------------------
# Intake memory models  (from memory.py)
# ---------------------------------------------------------------------------


class IntakeThread(BaseModel):
    """A recurring topic across intake sessions."""

    name: str
    summary: str
    first_seen: date
    last_seen: date
    mention_count: int = 1
    status: str = "active"


class DailyIntakeEntry(BaseModel):
    """Extracted memory from a single day's intake."""

    date: date
    themes: list[str] = Field(default_factory=list)
    key_items: list[str] = Field(default_factory=list)
    emerging_interests: list[str] = Field(default_factory=list)
    item_count: int = 0


class IntakeMemory(BaseModel):
    """Rolling memory across intake sessions."""

    entries: list[DailyIntakeEntry] = Field(default_factory=list)
    threads: list[IntakeThread] = Field(default_factory=list)

    def render_for_prompt(self) -> str:
        """Render memory as text for LLM context injection."""
        if not self.entries and not self.threads:
            return ""

        lines: list[str] = ["# Recent Reading Context", ""]

        recent = sorted(self.entries, key=lambda e: e.date, reverse=True)[:7]
        for entry in recent:
            lines.append(f"## {entry.date.isoformat()} ({entry.item_count} items)")
            if entry.themes:
                lines.append(f"Themes: {', '.join(entry.themes)}")
            if entry.key_items:
                for item in entry.key_items[:5]:
                    lines.append(f"- {item}")
            lines.append("")

        active_threads = [t for t in self.threads if t.status == "active"]
        if active_threads:
            lines.append("## Ongoing Interests")
            for thread in active_threads:
                lines.append(
                    f"- **{thread.name}** ({thread.mention_count}x since "
                    f"{thread.first_seen.isoformat()}): {thread.summary}"
                )
            lines.append("")

        return "\n".join(lines)

    def add_entry(self, entry: DailyIntakeEntry) -> None:
        """Add a daily entry, replacing any existing entry for the same date."""
        self.entries = [e for e in self.entries if e.date != entry.date]
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.date)

    def prune(self, keep_days: int = 30) -> None:
        """Remove entries older than ``keep_days``."""
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=keep_days)
        self.entries = [e for e in self.entries if e.date >= cutoff]


# ---------------------------------------------------------------------------
# Intake state models  (from state.py)
# ---------------------------------------------------------------------------


class IntakeRecord(BaseModel):
    """Record of a processed content item."""

    item_id: str
    url: str = ""
    title: str = ""
    source: str = ""
    processed_at: datetime = Field(default_factory=datetime.now)


class IntakeState(BaseModel):
    """Tracks which content items have been processed."""

    records: list[IntakeRecord] = Field(default_factory=list)
    last_run: datetime | None = None

    def is_processed(self, item_id: str) -> bool:
        return any(r.item_id == item_id for r in self.records)

    def mark_processed(self, record: IntakeRecord) -> None:
        self.records = [r for r in self.records if r.item_id != record.item_id]
        self.records.append(record)

    def prune(self, keep_days: int = 30) -> None:
        """Remove records older than ``keep_days``."""
        cutoff = datetime.now().timestamp() - keep_days * 86400
        self.records = [r for r in self.records if r.processed_at.timestamp() > cutoff]


# ---------------------------------------------------------------------------
# Seed models  (from seeds.py)
# ---------------------------------------------------------------------------


class SeedIdea(BaseModel):
    """A raw thought, headline, or topic seed."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    used: bool = False
    used_in: str | None = None


# ---------------------------------------------------------------------------
# Clustering models  (from clustering.py)
# ---------------------------------------------------------------------------


class TopicCluster(BaseModel):
    """A group of content items sharing a common topic."""

    label: str
    items: list[ContentItem]
    keywords: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Context models  (from context.py)
# ---------------------------------------------------------------------------


class DailyIntakeContext(BaseModel):
    """Context for a daily intake synthesis."""

    date: date
    items: list[ContentItem] = Field(default_factory=list)
    total_items: int = 0
    total_word_count: int = 0
    sources: list[str] = Field(default_factory=list)
    sites: list[str] = Field(default_factory=list)
    all_tags: list[str] = Field(default_factory=list)
    combined_text: str = ""

    # Partitioned item lists for unified synthesis
    session_items: list[ContentItem] = Field(default_factory=list)
    seed_items: list[ContentItem] = Field(default_factory=list)
    content_items: list[ContentItem] = Field(default_factory=list)

    # Aggregated from session metadata
    projects_worked_on: list[str] = Field(default_factory=list)
    tools_used_today: list[str] = Field(default_factory=list)

    @property
    def has_sessions(self) -> bool:
        return len(self.session_items) > 0

    @property
    def has_seeds(self) -> bool:
        return len(self.seed_items) > 0


# ---------------------------------------------------------------------------
# Fulltext models  (from fulltext.py)
# ---------------------------------------------------------------------------


class FullTextResult(BaseModel):
    """Result of a full-text extraction attempt."""

    body: str = ""
    author: str = ""
    title: str = ""
    word_count: int = 0
    success: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Synthesis error  (from synthesizer.py)
# ---------------------------------------------------------------------------


class IntakeSynthesisError(Exception):
    """Raised when intake LLM synthesis fails."""
