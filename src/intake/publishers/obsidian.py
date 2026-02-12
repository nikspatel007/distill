"""Obsidian-formatted intake publisher."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.base import IntakePublisher


class ObsidianIntakePublisher(IntakePublisher):
    """Formats intake digests as Obsidian-compatible markdown."""

    def format_daily(self, context: DailyIntakeContext, prose: str) -> str:
        frontmatter = self._build_frontmatter(context)
        timestamp = datetime.now().strftime("%H:%M")
        return f"{frontmatter}\n## Update — {timestamp}\n\n{prose}\n"

    def merge_daily(
        self, existing_content: str, context: DailyIntakeContext, prose: str
    ) -> str:
        """Append new prose to an existing daily digest, updating frontmatter."""
        prev_items = _extract_int(existing_content, "items")
        prev_words = _extract_int(existing_content, "word_count")
        prev_sources = _extract_list(existing_content, "sources")
        prev_tags = _extract_list(existing_content, "tags")

        merged_sources = list(dict.fromkeys(prev_sources + context.sources))
        merged_tags = list(dict.fromkeys(prev_tags + list(context.all_tags[:10])))

        frontmatter = _build_frontmatter_raw(
            context.date,
            prev_items + context.total_items,
            prev_words + context.total_word_count,
            merged_sources,
            merged_tags,
        )

        body = _strip_frontmatter(existing_content)
        timestamp = datetime.now().strftime("%H:%M")
        return f"{frontmatter}\n{body}\n---\n\n## Update — {timestamp}\n\n{prose}\n"

    def daily_output_path(self, output_dir: Path, target_date: date) -> Path:
        return output_dir / "intake" / f"intake-{target_date.isoformat()}.md"

    def _build_frontmatter(self, context: DailyIntakeContext) -> str:
        return _build_frontmatter_raw(
            context.date,
            context.total_items,
            context.total_word_count,
            context.sources,
            list(context.all_tags[:10]),
        )


def _build_frontmatter_raw(
    target_date: date,
    items: int,
    word_count: int,
    sources: list[str],
    tags: list[str],
) -> str:
    lines = [
        "---",
        f"date: {target_date.isoformat()}",
        "type: intake-digest",
        f"items: {items}",
        f"word_count: {word_count}",
    ]
    if sources:
        lines.append(f"sources: [{', '.join(sources)}]")
    if tags:
        lines.append(f"tags: [{', '.join(tags[:10])}]")
    lines.append("---")
    return "\n".join(lines)


def _extract_int(content: str, field: str) -> int:
    m = re.search(rf"^{field}:\s*(\d+)", content, re.MULTILINE)
    return int(m.group(1)) if m else 0


def _extract_list(content: str, field: str) -> list[str]:
    m = re.search(rf"^{field}:\s*\[([^\]]*)\]", content, re.MULTILINE)
    if not m:
        return []
    return [s.strip() for s in m.group(1).split(",") if s.strip()]


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from markdown content."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].lstrip("\n")
    return content
