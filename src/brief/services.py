"""Reading brief generation service."""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from distill.brief.models import DraftPost, ReadingBrief, ReadingHighlight
from distill.brief.prompts import get_draft_post_prompt, get_reading_brief_prompt
from distill.brief.store import save_reading_brief
from distill.intake.models import ContentItem
from distill.voice.models import VoiceProfile

logger = logging.getLogger(__name__)

# Sources that count as "reading" (not coding sessions)
READING_SOURCES = frozenset({
    "rss", "browser", "substack", "reddit", "gmail",
    "manual", "discovery", "youtube",
})


def _filter_reading_items(items: list[ContentItem]) -> list[ContentItem]:
    """Keep only reading items, exclude sessions/seeds/troopx."""
    return [
        item for item in items
        if item.source.value.lower() in READING_SOURCES
        and item.url
        and item.word_count >= 50
    ]


def _render_items_for_prompt(items: list[ContentItem], max_items: int = 15) -> str:
    """Render reading items as markdown for the LLM prompt."""
    lines: list[str] = []
    for item in items[:max_items]:
        lines.append(f"## {item.title}")
        lines.append(f"*{item.site_name or item.author} | {item.url}*")
        if item.excerpt and item.excerpt != item.title:
            lines.append(f"\n{item.excerpt[:500]}")
        if item.body and item.body != item.excerpt:
            body_preview = item.body[:1000]
            lines.append(f"\n{body_preview}")
        lines.append("")
    return "\n".join(lines)


def _call_claude(system: str, user: str, tag: str = "brief") -> str:
    """Call Claude via subprocess."""
    result = subprocess.run(
        ["claude", "-p", "--output-format", "text"],
        input=f"<system>\n{system}\n</system>\n\n{user}",
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude call failed ({tag}): {result.stderr[:200]}")
    return result.stdout.strip()


def _strip_json_fences(text: str) -> str:
    """Remove ```json fences from Claude output."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def generate_reading_brief(
    items: list[ContentItem],
    target_date: str,
    output_dir: Path,
    *,
    voice_profile: VoiceProfile | None = None,
    generate_drafts: bool = True,
) -> ReadingBrief:
    """Generate a reading brief from intake items.

    1. Filter to reading-only sources
    2. Call LLM to extract 3 highlights
    3. Optionally generate LinkedIn + X drafts from highlights
    4. Save to output_dir
    """
    reading_items = _filter_reading_items(items)

    if not reading_items:
        brief = ReadingBrief(
            date=target_date,
            generated_at=datetime.now().isoformat(),
        )
        save_reading_brief(brief, output_dir)
        return brief

    voice_context = ""
    if voice_profile:
        voice_context = voice_profile.render_for_prompt(min_confidence=0.5)

    # Step 1: Extract highlights
    system_prompt = get_reading_brief_prompt(voice_context=voice_context)
    user_prompt = _render_items_for_prompt(reading_items)
    raw = _call_claude(system_prompt, user_prompt, "highlights")
    raw = _strip_json_fences(raw)

    try:
        data = json.loads(raw)
        highlights = [
            ReadingHighlight.model_validate(h)
            for h in data.get("highlights", [])[:3]
        ]
    except (json.JSONDecodeError, ValueError):
        highlights = []

    # Step 2: Generate drafts
    drafts: list[DraftPost] = []
    if generate_drafts and highlights:
        highlights_text = "\n\n".join(
            f"**{h.title}** ({h.source})\n{h.summary}"
            for h in highlights
        )
        for platform in ("linkedin", "x"):
            try:
                draft_prompt = get_draft_post_prompt(
                    platform, voice_context=voice_context,
                )
                draft_content = _call_claude(
                    draft_prompt, highlights_text, f"draft-{platform}",
                )
                drafts.append(DraftPost(
                    platform=platform,
                    content=draft_content,
                    char_count=len(draft_content),
                    source_highlights=[h.title for h in highlights],
                ))
            except Exception:
                pass  # Skip failed drafts, don't block the brief

    brief = ReadingBrief(
        date=target_date,
        generated_at=datetime.now().isoformat(),
        highlights=highlights,
        drafts=drafts,
    )
    save_reading_brief(brief, output_dir)
    return brief
