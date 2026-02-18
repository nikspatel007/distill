"""Social pipeline — journal → daily social posts."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from distill.core import _atomic_write
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DAILY_SOCIAL_STATE_FILENAME = ".daily-social-state.json"


class DailySocialState(BaseModel):
    """Tracks the day counter for the daily social series."""

    day_number: int = 0
    last_posted_date: str = ""  # YYYY-MM-DD
    series_name: str = "100 days of building in public"


def _load_daily_social_state(output_dir: Path) -> DailySocialState:
    state_path = output_dir / "blog" / DAILY_SOCIAL_STATE_FILENAME
    if not state_path.exists():
        return DailySocialState()
    try:
        import json

        data = json.loads(state_path.read_text(encoding="utf-8"))
        return DailySocialState.model_validate(data)
    except Exception:
        return DailySocialState()


def _save_daily_social_state(state: DailySocialState, output_dir: Path) -> None:
    state_path = output_dir / "blog" / DAILY_SOCIAL_STATE_FILENAME
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def _build_daily_social_context(
    entry: Any,
    output_dir: Path,
    postiz_config: Any,
    recent_entries: list[Any] | None = None,
) -> str:
    """Build curated source context for daily social post generation.

    1. Filter journal prose to paragraphs mentioning the focus project.
       If today's entry has no relevant content, pull from recent entries.
    2. Append relevant unused seed ideas.
    3. Append active editorial notes targeting "daily".

    Falls back to the full journal prose if no project-specific content found.
    """
    focus_project = getattr(postiz_config, "daily_social_project", "")
    prose = entry.prose

    # --- 1. Project-filter the journal prose ---
    aliases: list[str] = []
    if focus_project:
        aliases = [focus_project.lower()]
        # Also match common aliases and related keywords
        try:
            from distill.shared.config import load_config

            cfg = load_config()
            for proj in cfg.projects:
                if proj.name.lower() == focus_project.lower():
                    aliases.extend(a.lower() for a in (proj.aliases or []))
                    # Extract key terms from project description
                    desc = (proj.description or "").lower()
                    for term in ["agent", "orchestrat", "blackboard", "roster",
                                 "squad", "spawn", "workflow", "temporal"]:
                        if term in desc:
                            aliases.append(term)
        except Exception:
            pass

        # Collect project-relevant paragraphs from today
        paragraphs = prose.split("\n\n")
        relevant = [
            p for p in paragraphs
            if any(alias in p.lower() for alias in aliases)
        ]

        # If today is thin, pull from recent entries too
        if len(relevant) < 2 and recent_entries:
            for older in recent_entries:
                if older.date == entry.date:
                    continue
                older_paras = older.prose.split("\n\n")
                older_relevant = [
                    p for p in older_paras
                    if any(alias in p.lower() for alias in aliases)
                ]
                if older_relevant:
                    relevant.extend(older_relevant)
                if len(relevant) >= 4:
                    break

        if relevant:
            prose = "\n\n".join(relevant)

    # --- 2. Append unused seed ideas ---
    seeds_section = ""
    try:
        from distill.intake import SeedStore

        store = SeedStore(output_dir)
        unused = [s for s in store.list_active() if not s.used]
        # Pick seeds relevant to the focus project or general ones
        if focus_project and unused:
            project_seeds = [
                s
                for s in unused
                if any(
                    alias in s.text.lower() or alias in " ".join(s.tags).lower()
                    for alias in aliases
                )
            ]
            if project_seeds:
                unused = project_seeds
        if unused:
            seed_texts = [s.text for s in unused[:3]]  # Cap at 3
            seeds_section = (
                "\n\n## Seed ideas (angles you can riff on):\n"
                + "\n".join(f"- {t}" for t in seed_texts)
            )
    except Exception:
        pass

    # --- 3. Append editorial notes targeting "daily" ---
    editorial_section = ""
    try:
        from distill.shared.editorial import EditorialStore

        store = EditorialStore(output_dir)
        rendered = store.render_for_prompt(target="daily")
        if rendered:
            editorial_section = "\n\n" + rendered
    except Exception:
        pass

    return prose + seeds_section + editorial_section


def _generate_daily_social_image(
    post_content: str,
    output_dir: Path,
    slug: str,
    postiz_config: Any,
) -> str | None:
    """Generate a hero image for a daily social post and return its URL.

    Uses the existing ImageGenerator (Google Gemini) to create the image,
    then uploads to Ghost to get a CDN URL that Postiz can reference.
    Returns None if image generation or upload is not configured.
    """
    if not post_content:
        return None

    try:
        from distill.shared.images import ImageGenerator

        generator = ImageGenerator()
        if not generator.is_configured():
            return None

        # Extract a short image prompt from the post content.
        from distill.intake.images import extract_image_prompts

        prompts = extract_image_prompts(post_content)
        if not prompts:
            # Fallback: generate directly from the first sentence
            first_line = post_content.strip().split("\n")[0][:200]
            from distill.intake.images import ImagePrompt

            prompts = [
                ImagePrompt(
                    role="hero",
                    prompt=first_line,
                    alt="Daily social hero image",
                    after_heading=None,
                    mood="energetic",
                )
            ]

        hero_prompt = prompts[0]
        images_dir = output_dir / "blog" / "daily-social" / "images"
        hero_path = images_dir / f"{slug}-hero.png"

        result = generator.generate(
            hero_prompt.prompt,
            output_path=hero_path,
            aspect_ratio="16:9",
            mood=hero_prompt.mood,
        )
        if result is None:
            return None

        # Upload to Ghost to get a CDN URL (Postiz needs a URL, not a file path)
        try:
            from distill.integrations.ghost import GhostAPIClient
            from distill.shared.config import load_config

            cfg = load_config()
            ghost_config = cfg.to_ghost_config()
            if ghost_config.is_configured:
                api = GhostAPIClient(ghost_config)
                url = api.upload_image(hero_path)
                if url:
                    logger.info("Daily social image uploaded to Ghost: %s", url)
                    return url
        except Exception:
            logger.debug("Ghost upload unavailable for daily social image", exc_info=True)

        logger.info("Generated daily social image at %s (no CDN URL)", hero_path)
        return None

    except Exception:
        logger.warning("Daily social image generation failed", exc_info=True)
        return None


def generate_daily_social(
    output_dir: Path,
    *,
    postiz_config: Any | None = None,
    model: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    target_date: date | None = None,
) -> list[Path]:
    """Generate a daily social post from today's journal entry.

    Reads the most recent journal entry and adapts it into a short LinkedIn
    post using the DAILY_SOCIAL_PROMPT. Pushes to Postiz as a scheduled post
    for the next morning.

    The day counter persists across runs via .daily-social-state.json.

    Args:
        output_dir: Root output directory (contains journal/ and blog/).
        postiz_config: PostizConfig for scheduling. If None, daily social is skipped.
        model: Optional Claude model override.
        dry_run: Preview without calling LLM or Postiz.
        force: Regenerate even if already posted today.
        target_date: Specific date to generate for (defaults to today).

    Returns:
        List of written file paths.
    """
    from distill.blog import BlogConfig, BlogSynthesizer, JournalReader

    if postiz_config is None:
        return []

    if not getattr(postiz_config, "daily_social_enabled", False):
        return []

    today = target_date or date.today()
    state = _load_daily_social_state(output_dir)

    # Skip if already posted today (unless forced)
    if not force and state.last_posted_date == today.isoformat():
        logger.debug("Daily social already posted for %s", today)
        return []

    series_length = getattr(postiz_config, "daily_social_series_length", 100)
    if state.day_number >= series_length:
        logger.info("Daily social series complete (%d days)", series_length)
        return []

    # Read today's journal entry
    reader = JournalReader()
    journal_dir = output_dir / "journal"
    entries = reader.read_all(journal_dir)
    if not entries:
        logger.warning("No journal entries found for daily social")
        return []

    # Find entry for target date, or the most recent one
    today_entry = None
    for entry in reversed(entries):
        if entry.date == today:
            today_entry = entry
            break
    if today_entry is None:
        # Fall back to most recent entry
        today_entry = entries[-1]
        if (today - today_entry.date).days > 2:
            logger.warning(
                "No recent journal entry for daily social (latest: %s)",
                today_entry.date,
            )
            return []

    # When forcing a re-run for the same date, reuse the existing day number
    if force and state.last_posted_date == today.isoformat():
        day_number = state.day_number
    else:
        day_number = state.day_number + 1

    if dry_run:
        print(f"[DRY RUN] Would generate daily social post: Day {day_number}/{series_length}")
        print(f"  Journal entry: {today_entry.date}")
        return []

    # Build curated source context (project-filtered + seeds + editorial notes)
    # Pass recent entries so we can pull from the last few days if today is thin
    recent = [e for e in entries if (today - e.date).days <= 3]
    source_text = _build_daily_social_context(
        today_entry, output_dir, postiz_config, recent_entries=recent
    )

    # Synthesize per-platform content
    from distill.blog import get_daily_social_prompt
    from distill.shared.config import load_config as _load_cfg

    _cfg = _load_cfg()
    _focus_project = getattr(postiz_config, "daily_social_project", "")
    _proj_desc = ""
    for _p in _cfg.projects:
        if _p.name.lower() == _focus_project.lower():
            _proj_desc = _p.description
            break
    _hashtags = " ".join(_cfg.social.brand_hashtags) if _cfg.social.brand_hashtags else ""

    config = BlogConfig(model=model)
    synthesizer = BlogSynthesizer(config)
    platforms = getattr(postiz_config, "daily_social_platforms", ["linkedin"])

    day_prefix = f"Day {day_number}/{series_length} of the series.\n\n"
    platform_content: dict[str, str] = {}
    for platform in platforms:
        # Map Postiz provider names to prompt keys
        prompt_key = {"x": "twitter"}.get(platform, platform)
        prompt = get_daily_social_prompt(
            prompt_key,
            project_name=_focus_project,
            project_description=_proj_desc,
            hashtags=_hashtags,
        )
        system_prompt = day_prefix + prompt
        platform_content[platform] = synthesizer._call_claude(
            system_prompt, source_text, f"daily-social-{platform}-{today.isoformat()}"
        )

    written: list[Path] = []

    # Write files per platform
    slug = f"daily-social-{today.isoformat()}"
    out_dir = output_dir / "blog" / "daily-social"
    out_dir.mkdir(parents=True, exist_ok=True)
    for platform, content in platform_content.items():
        suffix = f"-{platform}" if len(platforms) > 1 else ""
        out_path = out_dir / f"{slug}{suffix}.md"
        _atomic_write(out_path, content)
        written.append(out_path)

    # Generate hero image for social posts
    image_url = _generate_daily_social_image(
        platform_content.get("linkedin", ""),
        output_dir,
        slug,
        postiz_config,
    )

    # Push to Postiz per platform (separate calls so each gets its own content)
    if postiz_config.is_configured and postiz_config.schedule_enabled:
        try:
            from distill.integrations.mapping import resolve_integration_ids
            from distill.integrations.postiz import PostizClient
            from distill.integrations.scheduling import next_daily_social_slot

            client = PostizClient(postiz_config)
            integration_map = resolve_integration_ids(client, platforms)
            scheduled_at = next_daily_social_slot(postiz_config)

            for platform in platforms:
                ids = integration_map.get(platform, [])
                if not ids:
                    logger.warning("No Postiz integration for %s, skipping", platform)
                    continue
                content = platform_content.get(platform, "")
                if not content:
                    continue
                # Attach image to LinkedIn and X posts (not Slack)
                imgs = [image_url] if image_url and platform != "slack" else None
                client.create_post(
                    content,
                    ids,
                    post_type="schedule",
                    scheduled_at=scheduled_at,
                    images=imgs,
                )
                logger.info(
                    "Daily social Day %d (%s) scheduled for %s%s",
                    day_number,
                    platform,
                    scheduled_at,
                    " (with image)" if imgs else "",
                )
        except Exception:
            logger.warning("Failed to push daily social to Postiz", exc_info=True)

    # Update state
    state.day_number = day_number
    state.last_posted_date = today.isoformat()
    _save_daily_social_state(state, output_dir)

    return written
