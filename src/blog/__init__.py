"""Blog generation pipeline for thought leadership content.

Transforms journal entries and working memory into publishable weekly
synthesis posts and thematic deep-dive articles with Mermaid diagrams.
Reads existing journal markdown files as input -- a layer on top of
the journal system.
"""

from distill.blog.models import (
    BlogConfig,
    BlogMemory,
    BlogPostSummary,
    BlogPostType,
    BlogState,
    JournalEntry,
    Platform,
    ThematicBlogContext,
    ThemeDefinition,
    WeeklyBlogContext,
)
from distill.blog.services import (
    JournalReader,
    load_blog_memory,
    load_blog_state,
    save_blog_memory,
    save_blog_state,
)

__all__ = [
    "BlogConfig",
    "BlogMemory",
    "BlogPostSummary",
    "BlogPostType",
    "BlogState",
    "JournalEntry",
    "JournalReader",
    "Platform",
    "ThematicBlogContext",
    "ThemeDefinition",
    "WeeklyBlogContext",
    "load_blog_memory",
    "load_blog_state",
    "save_blog_memory",
    "save_blog_state",
]
