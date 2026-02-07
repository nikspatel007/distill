"""Blog generation pipeline for thought leadership content.

Transforms journal entries and working memory into publishable weekly
synthesis posts and thematic deep-dive articles with Mermaid diagrams.
Reads existing journal markdown files as input -- a layer on top of
the journal system.
"""

from distill.blog.blog_memory import BlogMemory, BlogPostSummary, load_blog_memory, save_blog_memory
from distill.blog.config import BlogConfig, BlogPostType, Platform
from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.reader import JournalEntry, JournalReader
from distill.blog.state import BlogState, load_blog_state, save_blog_state
from distill.blog.themes import ThemeDefinition

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
