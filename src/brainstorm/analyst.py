"""Analyst logic -- scores research and generates content ideas."""

from __future__ import annotations

import json
import logging

from distill.brainstorm.models import ContentIdea, ResearchItem
from distill.brainstorm.prompts import get_analyst_prompt

logger = logging.getLogger(__name__)


def score_against_pillars(
    items: list[ResearchItem],
    pillars: list[str],
) -> list[ResearchItem]:
    """Filter research items that likely relate to content pillars.

    Uses keyword matching as a fast pre-filter before the LLM call.
    """
    pillar_keywords: list[set[str]] = []
    for p in pillars:
        words = {w.lower() for w in p.split() if len(w) > 3}
        pillar_keywords.append(words)

    scored: list[ResearchItem] = []
    for item in items:
        text = f"{item.title} {item.summary}".lower()
        for kw_set in pillar_keywords:
            if any(kw in text for kw in kw_set):
                scored.append(item)
                break
    return scored


def _call_llm(prompt: str) -> str:
    """Call Claude via the shared LLM module."""
    from distill.llm import call_claude

    return call_claude(
        system_prompt="You are a content strategist.",
        user_prompt=prompt,
        timeout=120,
        label="brainstorm-analyst",
    )


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from JSON response."""
    from distill.llm import strip_json_fences

    return strip_json_fences(text)


def analyze_research(
    items: list[ResearchItem],
    pillars: list[str],
    journal_context: str,
    existing_seeds: list[str],
    published_titles: list[str],
) -> list[ContentIdea]:
    """Analyze research items and generate content ideas via LLM."""
    if not items:
        return []

    research_json = json.dumps(
        [item.model_dump() for item in items],
        indent=2,
        default=str,
    )

    prompt = get_analyst_prompt(
        research_json=research_json,
        pillars=pillars,
        journal_context=journal_context,
        existing_seeds=existing_seeds,
        published_titles=published_titles,
    )

    try:
        raw = _call_llm(prompt)
        cleaned = _strip_json_fences(raw)
        ideas_data = json.loads(cleaned)
    except (json.JSONDecodeError, Exception):
        logger.warning("Failed to parse analyst LLM response", exc_info=True)
        return []

    ideas: list[ContentIdea] = []
    for idea_dict in ideas_data:
        try:
            ideas.append(ContentIdea.model_validate(idea_dict))
        except Exception:
            logger.warning("Failed to parse content idea: %s", idea_dict)
    return ideas
