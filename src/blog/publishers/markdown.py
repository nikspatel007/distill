"""Plain markdown publisher for GitHub Pages and repositories."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.publishers.base import BlogPublisher
from distill.blog.state import BlogState


class MarkdownPublisher(BlogPublisher):
    """Formats blog posts as plain markdown with minimal frontmatter."""

    def format_weekly(self, context: WeeklyBlogContext, prose: str) -> str:
        fm = self._weekly_frontmatter(context)
        body = self._weekly_body(context, prose)
        return fm + body

    def format_thematic(self, context: ThematicBlogContext, prose: str) -> str:
        fm = self._thematic_frontmatter(context)
        body = self._thematic_body(context, prose)
        return fm + body

    def weekly_output_path(self, output_dir: Path, year: int, week: int) -> Path:
        return output_dir / "blog" / "markdown" / "weekly" / f"weekly-{year}-W{week:02d}.md"

    def thematic_output_path(self, output_dir: Path, slug: str) -> Path:
        return output_dir / "blog" / "markdown" / "themes" / f"{slug}.md"

    def format_index(self, output_dir: Path, state: BlogState) -> str:
        lines: list[str] = [
            "# Blog",
            "",
        ]

        weekly = sorted(
            [p for p in state.posts if p.post_type == "weekly"],
            key=lambda p: p.slug,
            reverse=True,
        )
        if weekly:
            lines.append("## Weekly Synthesis")
            lines.append("")
            for post in weekly:
                date_str = post.generated_at.strftime("%Y-%m-%d")
                lines.append(f"- [{post.slug}](weekly/{post.slug}.md) (generated {date_str})")
            lines.append("")

        thematic = sorted(
            [p for p in state.posts if p.post_type == "thematic"],
            key=lambda p: p.slug,
        )
        if thematic:
            lines.append("## Thematic Deep-Dives")
            lines.append("")
            for post in thematic:
                date_str = post.generated_at.strftime("%Y-%m-%d")
                lines.append(f"- [{post.slug}](themes/{post.slug}.md) (generated {date_str})")
            lines.append("")

        return "\n".join(lines)

    def index_path(self, output_dir: Path) -> Path:
        return output_dir / "blog" / "markdown" / "README.md"

    def _weekly_frontmatter(self, context: WeeklyBlogContext) -> str:
        lines: list[str] = ["---"]
        lines.append(f'title: "Week {context.year}-W{context.week:02d} Synthesis"')
        lines.append(f"date: {context.week_start.isoformat()}")
        lines.append("tags:")
        lines.append("  - blog")
        lines.append("  - weekly")
        for tag in context.all_tags[:10]:
            if tag not in ("blog", "weekly"):
                lines.append(f"  - {tag}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def _weekly_body(self, context: WeeklyBlogContext, prose: str) -> str:
        lines: list[str] = [prose, ""]
        lines.append("---")
        lines.append("")
        lines.append("## Sources")
        lines.append("")
        for entry in sorted(context.entries, key=lambda e: e.date):
            stem = entry.file_path.stem
            date_label = entry.date.strftime("%b %d")
            lines.append(f"- [{date_label} Journal](../journal/{stem}.md)")
        lines.append("")
        return "\n".join(lines)

    def _thematic_frontmatter(self, context: ThematicBlogContext) -> str:
        lines: list[str] = ["---"]
        lines.append(f'title: "{context.theme.title}"')
        lines.append(f"date: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("tags:")
        lines.append("  - blog")
        lines.append("  - thematic")
        for part in context.theme.slug.split("-"):
            lines.append(f"  - {part}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def _thematic_body(self, context: ThematicBlogContext, prose: str) -> str:
        lines: list[str] = [prose, ""]
        lines.append("---")
        lines.append("")
        lines.append("## Sources")
        lines.append("")
        for entry in sorted(context.evidence_entries, key=lambda e: e.date):
            stem = entry.file_path.stem
            date_label = entry.date.strftime("%b %d")
            lines.append(f"- [{date_label} Journal](../journal/{stem}.md)")
        lines.append("")
        return "\n".join(lines)
