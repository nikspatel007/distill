"""Unified configuration loaded from .distill.toml, env vars, and CLI flags.

Loading order: defaults → TOML file → env vars → CLI flags.
"""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path
from typing import Any

from distill.brainstorm.config import BrainstormConfig
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

CONFIG_FILENAME = ".distill.toml"
CONFIG_SEARCH_PATHS = [
    Path("."),
    Path.home() / ".config" / "distill",
]


class ProjectConfig(BaseModel):
    """Single project description for LLM context injection."""

    name: str
    description: str
    url: str = ""
    tags: list[str] = Field(default_factory=list)


class OutputConfig(BaseModel):
    """[output] section."""

    directory: str = "./insights"


class SessionsConfig(BaseModel):
    """[sessions] section."""

    sources: list[str] = Field(default_factory=lambda: ["claude", "codex"])
    include_global: bool = False
    since_days: int = 2


class JournalSectionConfig(BaseModel):
    """[journal] section."""

    style: str = "dev-journal"
    target_word_count: int = 600
    model: str | None = None
    memory_window_days: int = 7
    claude_timeout: int = 120


class BlogSectionConfig(BaseModel):
    """[blog] section."""

    target_word_count: int = 1200
    include_diagrams: bool = True
    model: str | None = None
    claude_timeout: int = 360
    platforms: list[str] = Field(default_factory=lambda: ["obsidian"])


class IntakeSectionConfig(BaseModel):
    """[intake] section."""

    feeds_file: str = ""
    opml_file: str = ""
    use_defaults: bool = True
    browser_history: bool = False
    substack_blogs: list[str] = Field(default_factory=list)
    rss_feeds: list[str] = Field(default_factory=list)
    target_word_count: int = 800
    model: str | None = None
    publishers: list[str] = Field(default_factory=lambda: ["obsidian"])


class GraphSectionConfig(BaseModel):
    """[graph] section."""

    agent_prompt_patterns: list[str] = Field(default_factory=list)


class GhostTargetConfig(BaseModel):
    """A single named Ghost target (e.g. [ghost.personal])."""

    url: str = ""
    admin_api_key: str = ""
    newsletter_slug: str = ""
    auto_publish: bool | None = None
    blog_as_draft: bool | None = None


class GhostSectionConfig(BaseModel):
    """[ghost] section with optional named targets.

    Supports two formats:

    Legacy flat (single target)::

        [ghost]
        url = "https://ghost.example"
        admin_api_key = "id:secret"

    Named targets::

        [ghost]
        default = "troopx"
        auto_publish = true

        [ghost.troopx]
        url = "https://troopx-ghost.example"

        [ghost.personal]
        url = "https://blog.nik-patel.com"
    """

    default: str = ""
    url: str = ""
    admin_api_key: str = ""
    newsletter_slug: str = ""
    auto_publish: bool = True
    blog_as_draft: bool = False
    targets: dict[str, GhostTargetConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _extract_targets(cls, data: Any) -> Any:
        """Extract named sub-dicts as targets before validation."""
        if not isinstance(data, dict):
            return data
        data = dict(data)  # shallow copy
        known = {
            "default", "url", "admin_api_key", "newsletter_slug",
            "auto_publish", "blog_as_draft", "targets",
        }
        targets: dict[str, object] = {}
        for key in list(data.keys()):
            if key not in known and isinstance(data[key], dict):
                targets[key] = data.pop(key)
        if targets:
            existing = data.get("targets", {})
            if isinstance(existing, dict):
                existing.update(targets)
                data["targets"] = existing
            else:
                data["targets"] = targets
        return data

    def get_target(self, name: str | None = None) -> GhostTargetConfig:
        """Resolve a named target, falling back to top-level config.

        Args:
            name: Target name (e.g. "personal", "troopx").
                  If None, uses ``self.default``. If no default,
                  returns the top-level flat config.

        Returns:
            Resolved GhostTargetConfig with inherited defaults.
        """
        target_name = name or self.default
        if target_name and target_name in self.targets:
            t = self.targets[target_name]
            return GhostTargetConfig(
                url=t.url or self.url,
                admin_api_key=t.admin_api_key or self.admin_api_key,
                newsletter_slug=t.newsletter_slug or self.newsletter_slug,
                auto_publish=t.auto_publish if t.auto_publish is not None else self.auto_publish,
                blog_as_draft=(
                    t.blog_as_draft
                    if t.blog_as_draft is not None
                    else self.blog_as_draft
                ),
            )
        return GhostTargetConfig(
            url=self.url,
            admin_api_key=self.admin_api_key,
            newsletter_slug=self.newsletter_slug,
            auto_publish=self.auto_publish,
            blog_as_draft=self.blog_as_draft,
        )

    @property
    def target_names(self) -> list[str]:
        """List all named targets."""
        return list(self.targets.keys())


class RedditSectionConfig(BaseModel):
    """[reddit] section."""

    client_id: str = ""
    client_secret: str = ""
    username: str = ""


class YouTubeSectionConfig(BaseModel):
    """[youtube] section."""

    api_key: str = ""


class PostizSectionConfig(BaseModel):
    """[postiz] section."""

    url: str = ""
    api_key: str = ""
    default_type: str = "draft"
    schedule_enabled: bool = False
    timezone: str = "America/Chicago"
    weekly_time: str = "09:00"
    weekly_day: int = 0
    thematic_time: str = "09:00"
    thematic_days: list[int] = Field(default_factory=lambda: [1, 2, 3])
    intake_time: str = "17:00"
    daily_social_time: str = "08:00"
    daily_social_platforms: list[str] = Field(default_factory=lambda: ["linkedin"])
    daily_social_enabled: bool = False
    daily_social_series_length: int = 100
    daily_social_project: str = ""  # Focus on this project (filters journal content)
    slack_channel: str = ""


class NotificationConfig(BaseModel):
    """[notifications] section."""

    slack_webhook: str = ""
    ntfy_url: str = ""
    ntfy_topic: str = "distill"
    enabled: bool = True

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.slack_webhook or self.ntfy_url)


class UserConfig(BaseModel):
    """[user] section — identity for LLM prompts."""

    name: str = ""
    role: str = "software engineer"
    bio: str = ""


class SocialConfig(BaseModel):
    """[social] section — branding for social posts."""

    brand_hashtags: list[str] = Field(default_factory=list)
    secondary_hashtags: list[str] = Field(default_factory=list)


class IntelligenceConfig(BaseModel):
    """[intelligence] section."""

    model: str = "claude-haiku-4-5-20251001"


class DistillConfig(BaseModel):
    """Top-level configuration model for the entire distill pipeline."""

    output: OutputConfig = Field(default_factory=OutputConfig)
    sessions: SessionsConfig = Field(default_factory=SessionsConfig)
    journal: JournalSectionConfig = Field(default_factory=JournalSectionConfig)
    blog: BlogSectionConfig = Field(default_factory=BlogSectionConfig)
    intake: IntakeSectionConfig = Field(default_factory=IntakeSectionConfig)
    graph: GraphSectionConfig = Field(default_factory=GraphSectionConfig)
    ghost: GhostSectionConfig = Field(default_factory=GhostSectionConfig)
    reddit: RedditSectionConfig = Field(default_factory=RedditSectionConfig)
    youtube: YouTubeSectionConfig = Field(default_factory=YouTubeSectionConfig)
    postiz: PostizSectionConfig = Field(default_factory=PostizSectionConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    projects: list[ProjectConfig] = Field(default_factory=list)
    user: UserConfig = Field(default_factory=UserConfig)
    social: SocialConfig = Field(default_factory=SocialConfig)
    brainstorm: BrainstormConfig = Field(default_factory=BrainstormConfig)

    def render_project_context(self) -> str:
        """Render project descriptions for LLM prompt injection."""
        if not self.projects:
            return ""
        lines = ["## Project Context", ""]
        for p in self.projects:
            lines.append(f"**{p.name}**: {p.description}")
            if p.url:
                lines.append(f"  URL: {p.url}")
        return "\n".join(lines)

    def to_journal_config(self) -> object:
        """Convert to JournalConfig for the journal pipeline."""
        from distill.journal.config import JournalConfig, JournalStyle

        return JournalConfig(
            style=JournalStyle(self.journal.style),
            target_word_count=self.journal.target_word_count,
            model=self.journal.model,
            memory_window_days=self.journal.memory_window_days,
            claude_timeout=self.journal.claude_timeout,
        )

    def to_blog_config(self) -> object:
        """Convert to BlogConfig for the blog pipeline."""
        from distill.blog.config import BlogConfig

        return BlogConfig(
            target_word_count=self.blog.target_word_count,
            include_diagrams=self.blog.include_diagrams,
            model=self.blog.model,
            claude_timeout=self.blog.claude_timeout,
        )

    def to_intake_config(self) -> object:
        """Convert to IntakeConfig for the intake pipeline."""
        from distill.intake.config import IntakeConfig, RSSConfig

        return IntakeConfig(
            rss=RSSConfig(
                feeds_file=self.intake.feeds_file,
                opml_file=self.intake.opml_file,
            ),
            model=self.intake.model,
            target_word_count=self.intake.target_word_count,
            user_name=self.user.name,
            user_role=self.user.role,
        )

    def to_ghost_config(self, target: str | None = None) -> object:
        """Convert to GhostConfig for Ghost CMS publishing.

        Args:
            target: Named Ghost target (e.g. "personal", "troopx").
                    If None, uses the default target from config.
        """
        from distill.integrations.ghost import GhostConfig

        t = self.ghost.get_target(target)
        return GhostConfig(
            url=t.url,
            admin_api_key=t.admin_api_key,
            newsletter_slug=t.newsletter_slug,
            auto_publish=t.auto_publish if t.auto_publish is not None else True,
            blog_as_draft=t.blog_as_draft if t.blog_as_draft is not None else False,
        )

    def to_postiz_config(self) -> object:
        """Convert to PostizConfig for the Postiz integration."""
        from distill.integrations.postiz import PostizConfig

        return PostizConfig(
            url=self.postiz.url,
            api_key=self.postiz.api_key,
            default_type=self.postiz.default_type,
            schedule_enabled=self.postiz.schedule_enabled,
            timezone=self.postiz.timezone,
            weekly_time=self.postiz.weekly_time,
            weekly_day=self.postiz.weekly_day,
            thematic_time=self.postiz.thematic_time,
            thematic_days=list(self.postiz.thematic_days),
            intake_time=self.postiz.intake_time,
            daily_social_time=self.postiz.daily_social_time,
            daily_social_platforms=list(self.postiz.daily_social_platforms),
            daily_social_enabled=self.postiz.daily_social_enabled,
            daily_social_series_length=self.postiz.daily_social_series_length,
            daily_social_project=self.postiz.daily_social_project,
            slack_channel=self.postiz.slack_channel,
        )

    def to_notification_config(self) -> NotificationConfig:
        """Return the notification config section."""
        return self.notifications


def load_config(path: str | Path | None = None) -> DistillConfig:
    """Load configuration from a TOML file.

    Search order:
    1. Explicit path (if provided)
    2. .distill.toml in CWD
    3. ~/.config/distill/config.toml

    Then overlay environment variables.

    Args:
        path: Explicit path to a TOML file.

    Returns:
        Merged DistillConfig.
    """
    data: dict[str, object] = {}

    if path is not None:
        toml_path = Path(path)
        if toml_path.exists():
            data = _load_toml(toml_path)
        else:
            logger.warning("Config file not found: %s", toml_path)
    else:
        for search_dir in CONFIG_SEARCH_PATHS:
            candidate = search_dir / CONFIG_FILENAME
            if candidate.exists():
                data = _load_toml(candidate)
                logger.info("Loaded config from %s", candidate)
                break
        # Also check ~/.config/distill/config.toml
        global_config = Path.home() / ".config" / "distill" / "config.toml"
        if not data and global_config.exists():
            data = _load_toml(global_config)
            logger.info("Loaded config from %s", global_config)

    config = DistillConfig.model_validate(data) if data else DistillConfig()

    # Overlay environment variables
    config = _apply_env_vars(config)

    return config


def merge_cli_overrides(config: DistillConfig, **cli_kwargs: object) -> DistillConfig:
    """Overlay explicitly-set CLI flags onto the config.

    Only overrides values where the CLI flag was explicitly provided
    (i.e., not None).

    Args:
        config: Base config.
        **cli_kwargs: CLI flag values. Keys use dot notation flattened
            with underscores (e.g., ``output_directory``, ``journal_style``).

    Returns:
        Updated config with CLI overrides applied.
    """
    data = config.model_dump()

    mapping: dict[str, tuple[str, str]] = {
        "output_directory": ("output", "directory"),
        "journal_style": ("journal", "style"),
        "journal_words": ("journal", "target_word_count"),
        "journal_model": ("journal", "model"),
        "blog_words": ("blog", "target_word_count"),
        "blog_model": ("blog", "model"),
        "blog_platforms": ("blog", "platforms"),
        "intake_words": ("intake", "target_word_count"),
        "intake_model": ("intake", "model"),
        "intake_feeds_file": ("intake", "feeds_file"),
        "ghost_url": ("ghost", "url"),
        "ghost_key": ("ghost", "admin_api_key"),
        "ghost_newsletter": ("ghost", "newsletter_slug"),
        "postiz_url": ("postiz", "url"),
        "postiz_key": ("postiz", "api_key"),
        "model": ("journal", "model"),  # global --model override
    }

    for key, value in cli_kwargs.items():
        if value is None:
            continue
        if key in mapping:
            section, field = mapping[key]
            data[section][field] = value
        # Global model overrides all sections
        if key == "model" and value is not None:
            for section in ("journal", "blog", "intake"):
                data[section]["model"] = value

    return DistillConfig.model_validate(data)


def _load_toml(path: Path) -> dict[str, object]:
    """Load a TOML file and return the data dict."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}


def _apply_env_vars(config: DistillConfig) -> DistillConfig:
    """Apply environment variable overrides to config."""
    data = config.model_dump()

    env_mapping: dict[str, tuple[str, str]] = {
        "DISTILL_OUTPUT_DIR": ("output", "directory"),
        "DISTILL_MODEL": ("journal", "model"),
        "GHOST_URL": ("ghost", "url"),
        "GHOST_ADMIN_API_KEY": ("ghost", "admin_api_key"),
        "GHOST_NEWSLETTER_SLUG": ("ghost", "newsletter_slug"),
        "REDDIT_CLIENT_ID": ("reddit", "client_id"),
        "REDDIT_CLIENT_SECRET": ("reddit", "client_secret"),
        "REDDIT_USERNAME": ("reddit", "username"),
        "YOUTUBE_API_KEY": ("youtube", "api_key"),
        "DISTILL_SLACK_WEBHOOK": ("notifications", "slack_webhook"),
        "DISTILL_NTFY_URL": ("notifications", "ntfy_url"),
        "DISTILL_NTFY_TOPIC": ("notifications", "ntfy_topic"),
        "POSTIZ_URL": ("postiz", "url"),
        "POSTIZ_API_KEY": ("postiz", "api_key"),
        "POSTIZ_SLACK_CHANNEL": ("postiz", "slack_channel"),
    }

    for env_var, (section, field) in env_mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            data[section][field] = value

    # Per-target Ghost env vars: GHOST_<TARGET>_URL, GHOST_<TARGET>_ADMIN_API_KEY
    ghost_targets = data.get("ghost", {}).get("targets", {})
    for target_name in list(ghost_targets.keys()):
        prefix = f"GHOST_{target_name.upper()}_"
        for env_suffix, field in [("URL", "url"), ("ADMIN_API_KEY", "admin_api_key")]:
            val = os.environ.get(f"{prefix}{env_suffix}")
            if val is not None:
                ghost_targets[target_name][field] = val

    # Postiz scheduling env vars (non-string types)
    sched_raw = os.environ.get("POSTIZ_SCHEDULE_ENABLED")
    if sched_raw is not None:
        data["postiz"]["schedule_enabled"] = sched_raw.lower() in ("true", "1", "yes")
    tz_raw = os.environ.get("POSTIZ_TIMEZONE")
    if tz_raw is not None:
        data["postiz"]["timezone"] = tz_raw
    for key, field in [
        ("POSTIZ_WEEKLY_TIME", "weekly_time"),
        ("POSTIZ_THEMATIC_TIME", "thematic_time"),
        ("POSTIZ_INTAKE_TIME", "intake_time"),
        ("POSTIZ_DAILY_SOCIAL_TIME", "daily_social_time"),
    ]:
        val = os.environ.get(key)
        if val is not None:
            data["postiz"][field] = val
    day_raw = os.environ.get("POSTIZ_WEEKLY_DAY")
    if day_raw is not None:
        data["postiz"]["weekly_day"] = int(day_raw)
    tdays_raw = os.environ.get("POSTIZ_THEMATIC_DAYS")
    if tdays_raw is not None:
        data["postiz"]["thematic_days"] = [
            int(d.strip()) for d in tdays_raw.split(",") if d.strip()
        ]

    daily_enabled_raw = os.environ.get("POSTIZ_DAILY_SOCIAL_ENABLED")
    if daily_enabled_raw is not None:
        data["postiz"]["daily_social_enabled"] = daily_enabled_raw.lower() in ("true", "1", "yes")
    daily_platforms_raw = os.environ.get("POSTIZ_DAILY_SOCIAL_PLATFORMS")
    if daily_platforms_raw is not None:
        data["postiz"]["daily_social_platforms"] = [
            p.strip() for p in daily_platforms_raw.split(",") if p.strip()
        ]
    daily_length_raw = os.environ.get("POSTIZ_DAILY_SOCIAL_SERIES_LENGTH")
    if daily_length_raw is not None:
        data["postiz"]["daily_social_series_length"] = int(daily_length_raw)

    # Global model env var overrides all sections
    global_model = os.environ.get("DISTILL_MODEL")
    if global_model:
        for section in ("journal", "blog", "intake"):
            data[section]["model"] = global_model

    return DistillConfig.model_validate(data)
