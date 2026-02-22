"""Obsidian-formatted intake publisher."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.base import IntakePublisher


def _extract_highlights(text: str) -> tuple[list[str], str]:
    """Extract HIGHLIGHTS: block from LLM output.

    Returns (highlights_list, remaining_prose). If no HIGHLIGHTS block found,
    returns ([], original_text).
    """
    pattern = r"^\s*HIGHLIGHTS:\s*\n((?:\s*-\s+.+\n?)+)"
    match = re.match(pattern, text)
    if not match:
        return [], text
    block = match.group(1)
    highlights = [
        line.strip().lstrip("- ").strip()
        for line in block.strip().split("\n")
        if line.strip().startswith("-")
    ]
    remaining = text[match.end() :].strip()
    return highlights, remaining


class ObsidianIntakePublisher(IntakePublisher):
    """Formats intake digests as Obsidian-compatible markdown."""

    def format_daily(self, context: DailyIntakeContext, prose: str) -> str:
        highlights, clean_prose = _extract_highlights(prose)
        frontmatter = self._build_frontmatter(context, highlights=highlights)
        return f"{frontmatter}\n{clean_prose}\n"

    def daily_output_path(self, output_dir: Path, target_date: date) -> Path:
        return output_dir / "intake" / f"intake-{target_date.isoformat()}.md"

    def _build_frontmatter(
        self,
        context: DailyIntakeContext,
        highlights: list[str] | None = None,
    ) -> str:
        lines = [
            "---",
            f"date: {context.date.isoformat()}",
            "type: intake-digest",
            f"items: {context.total_items}",
            f"word_count: {context.total_word_count}",
        ]
        if context.sources:
            sources_str = ", ".join(context.sources)
            lines.append(f"sources: [{sources_str}]")
        if context.all_tags:
            tags_str = ", ".join(context.all_tags[:10])
            lines.append(f"tags: [{tags_str}]")
        if highlights:
            lines.append("highlights:")
            for h in highlights:
                lines.append(f'  - "{h}"')
        lines.append("---")
        return "\n".join(lines)
