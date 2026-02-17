"""Publisher — outputs content ideas to seeds, Ghost, and calendar files."""

from __future__ import annotations

import logging
from pathlib import Path

from distill.brainstorm.models import (
    ContentCalendar,
    ContentIdea,
    save_calendar,
)

logger = logging.getLogger(__name__)


def _render_markdown(ideas: list[ContentIdea], date: str) -> str:
    """Render content ideas as a human-readable markdown file."""
    lines = [f"# Content Calendar — {date}", ""]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"## {i}. {idea.title}")
        lines.append("")
        lines.append(f"**Angle:** {idea.angle}")
        lines.append(f"**Platform:** {idea.platform}")
        lines.append(f"**Pillars:** {', '.join(idea.pillars)}")
        lines.append(f"**Source:** {idea.source_url}")
        lines.append(f"**Why:** {idea.rationale}")
        if idea.tags:
            lines.append(f"**Tags:** {', '.join(idea.tags)}")
        lines.append("")
    return "\n".join(lines)


def publish_calendar(
    ideas: list[ContentIdea],
    date: str,
    output_dir: Path,
    create_seeds: bool = True,
    create_ghost_drafts: bool = True,
) -> ContentCalendar:
    """Publish content ideas to all destinations."""
    calendar = ContentCalendar(date=date, ideas=ideas)

    # 1. Save JSON calendar
    save_calendar(calendar, output_dir)

    # 2. Save markdown calendar
    cal_dir = output_dir / "content-calendar"
    cal_dir.mkdir(parents=True, exist_ok=True)
    md_path = cal_dir / f"{date}.md"
    md_path.write_text(_render_markdown(ideas, date), encoding="utf-8")

    # 3. Create seeds
    if create_seeds:
        try:
            from distill.intake.seeds import SeedStore

            store = SeedStore(output_dir)
            for idea in ideas:
                store.add(
                    text=f"{idea.title}: {idea.angle}",
                    tags=idea.tags,
                )
            logger.info("Created %d seeds from content ideas", len(ideas))
        except Exception:
            logger.warning("Failed to create seeds", exc_info=True)

    # 4. Create Ghost drafts
    if create_ghost_drafts:
        try:
            from distill.integrations.ghost import GhostAPIClient, GhostConfig

            config = GhostConfig.from_env()
            if config.is_configured:
                client = GhostAPIClient(config)
                for idea in ideas:
                    if idea.platform not in ("blog", "both"):
                        continue
                    outline = (
                        f"## {idea.title}\n\n"
                        f"{idea.angle}\n\n"
                        f"**Source:** {idea.source_url}\n\n"
                        f"{idea.rationale}"
                    )
                    result = client.create_post(
                        title=idea.title,
                        markdown=outline,
                        tags=idea.pillars + idea.tags,
                        status="draft",
                    )
                    idea.ghost_post_id = result.get("id")
                    logger.info("Created Ghost draft: %s", idea.title)
            else:
                logger.info("Ghost not configured, skipping drafts")
        except Exception:
            logger.warning("Failed to create Ghost drafts", exc_info=True)

    # Re-save calendar with ghost_post_ids
    save_calendar(calendar, output_dir)

    return calendar
