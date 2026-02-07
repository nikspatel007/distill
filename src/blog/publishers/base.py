"""Base class for platform-specific blog publishing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.state import BlogState


class BlogPublisher(ABC):
    """Base class for platform-specific blog publishing."""

    requires_llm: bool = False

    @abstractmethod
    def format_weekly(self, context: WeeklyBlogContext, prose: str) -> str:
        """Format/adapt a weekly post for this platform."""

    @abstractmethod
    def format_thematic(self, context: ThematicBlogContext, prose: str) -> str:
        """Format/adapt a thematic post for this platform."""

    @abstractmethod
    def weekly_output_path(self, output_dir: Path, year: int, week: int) -> Path:
        """Compute the output file path for a weekly blog post."""

    @abstractmethod
    def thematic_output_path(self, output_dir: Path, slug: str) -> Path:
        """Compute the output file path for a thematic blog post."""

    @abstractmethod
    def format_index(self, output_dir: Path, state: BlogState) -> str:
        """Generate an index page listing all blog posts."""

    @abstractmethod
    def index_path(self, output_dir: Path) -> Path:
        """Compute the output file path for the blog index."""
