"""Blog generation pipeline for thought leadership content.

Transforms journal entries and working memory into publishable weekly
synthesis posts and thematic deep-dive articles with Mermaid diagrams.
Reads existing journal markdown files as input -- a layer on top of
the journal system.
"""

from distill.blog.models import (
    BlogConfig,
    BlogMemory,
    BlogPostRecord,
    BlogPostSummary,
    BlogPostType,
    BlogState,
    JournalEntry,
    Platform,
    ReadingListContext,
    ThematicBlogContext,
    ThemeDefinition,
    WeeklyBlogContext,
)
from distill.blog.prompts import get_blog_prompt, get_daily_social_prompt
from distill.blog.services import (
    BlogSynthesizer,
    JournalReader,
    THEMES,
    clean_diagrams,
    detect_series_candidates,
    gather_evidence,
    get_ready_themes,
    load_blog_memory,
    load_blog_state,
    prepare_reading_list_context,
    prepare_thematic_context,
    prepare_weekly_context,
    render_reading_list_prompt,
    save_blog_memory,
    save_blog_state,
    themes_from_seeds,
)

__all__ = [
    "BlogConfig",
    "BlogMemory",
    "BlogPostRecord",
    "BlogPostSummary",
    "BlogPostType",
    "BlogState",
    "BlogSynthesizer",
    "JournalEntry",
    "JournalReader",
    "Platform",
    "ReadingListContext",
    "THEMES",
    "ThematicBlogContext",
    "ThemeDefinition",
    "WeeklyBlogContext",
    "clean_diagrams",
    "detect_series_candidates",
    "gather_evidence",
    "get_blog_prompt",
    "get_daily_social_prompt",
    "get_ready_themes",
    "load_blog_memory",
    "load_blog_state",
    "prepare_reading_list_context",
    "prepare_thematic_context",
    "prepare_weekly_context",
    "render_reading_list_prompt",
    "save_blog_memory",
    "save_blog_state",
    "themes_from_seeds",
]
