"""Reddit discussion post publisher for intake digests."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.base import IntakePublisher

logger = logging.getLogger(__name__)

REDDIT_SYSTEM_PROMPT = (
    "Adapt this daily research digest for a Reddit discussion post "
    "(r/programming or r/technology).\n"
    "Structure:\n"
    "- **TL;DR** (2-3 sentences capturing the day's most important finding)\n"
    "- **What I Read Today** (3-5 bullet points with links)\n"
    "- Brief narrative (2-3 paragraphs, casual but informed tone, ~400-600 words)\n"
    "- **Discussion question** (engaging, open-ended, invites debate)\n"
    "Output ONLY the post, no commentary."
)


class RedditIntakePublisher(IntakePublisher):
    """Adapts intake digests into Reddit discussion posts via Claude CLI."""

    requires_llm = True

    def format_daily(self, context: DailyIntakeContext, prose: str) -> str:
        """Format a daily intake digest as a Reddit discussion post.

        Calls Claude CLI to adapt the prose for Reddit. Returns empty
        string on failure so the pipeline can continue.
        """
        from distill.llm import LLMError, call_claude

        try:
            return call_claude(
                REDDIT_SYSTEM_PROMPT,
                prose,
                timeout=120,
                label="reddit-intake",
            )
        except LLMError as exc:
            logger.warning("Claude CLI failed for Reddit adaptation: %s", exc)
            return ""

    def daily_output_path(self, output_dir: Path, target_date: date) -> Path:
        """Compute the output file path for a Reddit daily digest."""
        return output_dir / "intake" / "social" / "reddit" / f"reddit-{target_date}.md"
