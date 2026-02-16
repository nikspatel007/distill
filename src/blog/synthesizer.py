"""Claude CLI integration for blog synthesis.

Calls ``claude -p`` to transform assembled blog context into publishable
prose. Follows the same subprocess pattern as journal/synthesizer.py.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from distill.blog.blog_memory import BlogPostSummary
from distill.blog.config import BlogConfig, BlogPostType
from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.prompts import MEMORY_EXTRACTION_PROMPT, get_blog_prompt, get_social_prompt

logger = logging.getLogger(__name__)


class BlogSynthesisError(Exception):
    """Raised when blog LLM synthesis fails."""


class BlogSynthesizer:
    """Synthesizes blog posts via Claude CLI."""

    def __init__(self, config: BlogConfig) -> None:
        self._config = config

    def synthesize_weekly(self, context: WeeklyBlogContext, blog_memory: str = "") -> str:
        """Transform weekly context into blog prose.

        Args:
            context: Assembled weekly blog context.
            blog_memory: Optional rendered blog memory for cross-referencing.

        Returns:
            Raw prose string from Claude including Mermaid blocks.

        Raises:
            BlogSynthesisError: If the CLI call fails.
        """
        system_prompt = get_blog_prompt(
            BlogPostType.WEEKLY,
            self._config.target_word_count,
            blog_memory=blog_memory,
        )
        user_prompt = _render_weekly_prompt(context)
        return self._call_claude(system_prompt, user_prompt, f"weekly W{context.week}")

    def synthesize_thematic(self, context: ThematicBlogContext, blog_memory: str = "") -> str:
        """Transform thematic context into blog prose.

        Args:
            context: Assembled thematic blog context.
            blog_memory: Optional rendered blog memory for cross-referencing.

        Returns:
            Raw prose string from Claude including Mermaid blocks.

        Raises:
            BlogSynthesisError: If the CLI call fails.
        """
        system_prompt = get_blog_prompt(
            BlogPostType.THEMATIC,
            self._config.target_word_count,
            theme_title=context.theme.title,
            blog_memory=blog_memory,
            intake_context=context.intake_context,
            seed_angle=context.seed_angle,
        )
        user_prompt = _render_thematic_prompt(context)
        return self._call_claude(system_prompt, user_prompt, context.theme.slug)

    def synthesize_raw(self, system_prompt: str, user_prompt: str) -> str:
        """Synthesize content from raw system and user prompts."""
        return self._call_claude(system_prompt, user_prompt, "raw-synthesis")

    def adapt_for_platform(
        self,
        prose: str,
        platform: str,
        slug: str,
        editorial_hint: str = "",
        hashtags: str = "",
    ) -> str:
        """Adapt blog prose for a specific platform.

        Args:
            prose: Canonical blog post prose.
            platform: Target platform key (e.g., "twitter", "linkedin", "reddit").
            slug: Post slug for logging.
            editorial_hint: Optional editorial direction to prepend.
            hashtags: Space-separated hashtags for the closing line.

        Returns:
            Platform-adapted text.

        Raises:
            BlogSynthesisError: If the CLI call fails.
            KeyError: If platform is not a known social prompt key.
        """
        # Map Postiz provider names to prompt keys (e.g. "x" → "twitter")
        prompt_key = {"x": "twitter"}.get(platform, platform)
        system_prompt = get_social_prompt(prompt_key, hashtags=hashtags)
        input_text = prose
        if editorial_hint:
            input_text = f"EDITORIAL DIRECTION: {editorial_hint}\n\n{prose}"
        return self._call_claude(system_prompt, input_text, f"adapt-{platform}-{slug}")

    def extract_blog_memory(
        self, prose: str, slug: str, title: str, post_type: str
    ) -> BlogPostSummary:
        """Extract structured memory from blog prose.

        Args:
            prose: Blog post prose to extract from.
            slug: Post slug.
            title: Post title.
            post_type: Post type ("weekly" or "thematic").

        Returns:
            BlogPostSummary with extracted key_points and themes_covered.
        """
        try:
            raw = self._call_claude(MEMORY_EXTRACTION_PROMPT, prose, f"memory-{slug}")
            data = json.loads(_strip_json_fences(raw))
            key_points = data.get("key_points", [])
            themes_covered = data.get("themes_covered", [])
            examples_used = data.get("examples_used", [])
        except (BlogSynthesisError, json.JSONDecodeError, ValueError):
            logger.warning("Failed to extract blog memory for %s", slug)
            key_points = []
            themes_covered = []
            examples_used = []

        return BlogPostSummary(
            slug=slug,
            title=title,
            post_type=post_type,
            date=date.today(),
            key_points=key_points,
            themes_covered=themes_covered,
            examples_used=examples_used,
            platforms_published=[],
        )

    def _call_claude(self, system_prompt: str, user_prompt: str, label: str) -> str:
        """Call Claude CLI with combined prompt."""
        from distill.llm import LLMError, call_claude

        try:
            return call_claude(
                system_prompt,
                user_prompt,
                model=self._config.model,
                timeout=self._config.claude_timeout,
                label=label,
            )
        except LLMError as exc:
            raise BlogSynthesisError(str(exc)) from exc


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences and preamble from LLM JSON output."""
    from distill.llm import strip_json_fences

    return strip_json_fences(text)


def _render_weekly_prompt(context: WeeklyBlogContext) -> str:
    """Render the user prompt for weekly synthesis."""
    lines: list[str] = []
    lines.append(f"# Week {context.year}-W{context.week:02d}")
    lines.append(f"({context.week_start.isoformat()} to {context.week_end.isoformat()})")
    lines.append(f"Total sessions: {context.total_sessions}")
    lines.append(f"Total duration: {context.total_duration_minutes:.0f} minutes")

    if context.projects:
        lines.append(f"Projects: {', '.join(context.projects)}")
    lines.append("")

    if context.working_memory:
        lines.append(context.working_memory)
        lines.append("")

    if context.project_context:
        lines.append(context.project_context)
        lines.append("")

    if context.editorial_notes:
        lines.append(context.editorial_notes)
        lines.append("")

    lines.append("# Daily Journal Entries")
    lines.append("")
    lines.append(context.combined_prose)

    return "\n".join(lines)


def _render_thematic_prompt(context: ThematicBlogContext) -> str:
    """Render the user prompt for thematic synthesis."""
    lines: list[str] = []
    lines.append(f"# Theme: {context.theme.title}")
    lines.append(f"Description: {context.theme.description}")
    lines.append(
        f"Evidence from {context.evidence_count} journal entries "
        f"({context.date_range[0].isoformat()} to {context.date_range[1].isoformat()})"
    )
    lines.append("")

    if context.relevant_threads:
        lines.append("## Relevant Ongoing Threads")
        for thread in context.relevant_threads:
            lines.append(f"- {thread.name} ({thread.status}): {thread.summary}")
        lines.append("")

    if context.project_context:
        lines.append(context.project_context)
        lines.append("")

    if context.editorial_notes:
        lines.append(context.editorial_notes)
        lines.append("")

    lines.append("# Evidence from Journal Entries")
    lines.append("")
    lines.append(context.combined_evidence)

    return "\n".join(lines)
