"""Blog generation pipeline for thought leadership content.

Transforms journal entries and working memory into publishable weekly
synthesis posts and thematic deep-dive articles with Mermaid diagrams.
Reads existing journal markdown files as input -- a layer on top of
the journal system.
"""

from session_insights.blog.config import BlogConfig, BlogPostType
from session_insights.blog.context import ThematicBlogContext, WeeklyBlogContext
from session_insights.blog.reader import JournalEntry, JournalReader
from session_insights.blog.state import BlogState, load_blog_state, save_blog_state
from session_insights.blog.themes import ThemeDefinition

__all__ = [
    "BlogConfig",
    "BlogPostType",
    "BlogState",
    "JournalEntry",
    "JournalReader",
    "ThematicBlogContext",
    "ThemeDefinition",
    "WeeklyBlogContext",
    "load_blog_state",
    "save_blog_state",
]
