"""LinkedIn post publisher for blog posts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.publishers.base import BlogPublisher
from distill.blog.state import BlogState

if TYPE_CHECKING:
    from distill.blog.synthesizer import BlogSynthesizer


class LinkedInPublisher(BlogPublisher):
    """Adapts blog posts into LinkedIn posts via LLM re-synthesis."""

    requires_llm = True

    def __init__(self, *, synthesizer: BlogSynthesizer) -> None:
        self._synthesizer = synthesizer

    def format_weekly(self, context: WeeklyBlogContext, prose: str) -> str:
        slug = f"weekly-{context.year}-W{context.week:02d}"
        return self._synthesizer.adapt_for_platform(prose, "linkedin", slug)

    def format_thematic(self, context: ThematicBlogContext, prose: str) -> str:
        return self._synthesizer.adapt_for_platform(prose, "linkedin", context.theme.slug)

    def weekly_output_path(self, output_dir: Path, year: int, week: int) -> Path:
        return output_dir / "blog" / "social" / "linkedin" / f"weekly-{year}-W{week:02d}.md"

    def thematic_output_path(self, output_dir: Path, slug: str) -> Path:
        return output_dir / "blog" / "social" / "linkedin" / f"{slug}.md"

    def format_index(self, output_dir: Path, state: BlogState) -> str:
        return ""

    def index_path(self, output_dir: Path) -> Path:
        return output_dir / "blog" / "social" / "linkedin" / "index.md"
