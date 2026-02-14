"""Intelligence module — entity extraction, classification, and topic modeling.

Uses Claude CLI for LLM-based extraction. Applied uniformly to sessions
AND external content.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from distill.intake.models import ContentItem

logger = logging.getLogger(__name__)

# Batch size for LLM calls
_BATCH_SIZE = 8

# Structured-output tasks (entity extraction, classification) use Haiku for speed/cost.
# Can be overridden by passing model= to individual functions.
_INTELLIGENCE_MODEL = "claude-haiku-4-5-20251001"


def _call_claude(prompt: str, model: str | None = None, timeout: int = 120) -> str:
    """Call Claude CLI with a prompt. Returns stdout or empty string on failure."""
    cmd: list[str] = ["claude", "-p"]
    if model:
        cmd.extend(["--model", model])

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.warning(
            "Claude CLI returned exit code %d: %s",
            result.returncode,
            result.stderr.strip()[:200] if result.stderr else "(no stderr)",
        )
    except FileNotFoundError:
        logger.warning("Claude CLI not found on PATH")
    except subprocess.TimeoutExpired:
        logger.warning("Claude CLI timed out after %ds", timeout)
    except OSError as exc:
        logger.warning("Claude CLI OSError: %s", exc)
    return ""


def _parse_json_response(text: str) -> Any:
    """Extract JSON from LLM response, handling markdown code fences and preamble text."""
    text = text.strip()
    if not text:
        return None

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find a JSON array in the response (Claude sometimes adds preamble text)
    bracket_start = text.find("[")
    if bracket_start != -1:
        # Find the matching closing bracket by scanning from the end
        bracket_end = text.rfind("]")
        if bracket_end > bracket_start:
            candidate = text[bracket_start : bracket_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    # Fallback: find a JSON object in the response
    brace_start = text.find("{")
    if brace_start != -1:
        brace_end = text.rfind("}")
        if brace_end > brace_start:
            candidate = text[brace_start : brace_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    return None


def _build_entity_prompt(items: list[ContentItem]) -> str:
    """Build a prompt for entity extraction from a batch of items."""
    parts: list[str] = []
    for i, item in enumerate(items):
        text = item.title
        if item.body:
            text += "\n" + item.body[:500]
        parts.append(f"[ITEM {i}]\n{text}")

    items_text = "\n\n".join(parts)

    return f"""Extract named entities from each content item below.

Return ONLY valid JSON — an array of objects, one per item, in the same order.
Each object must have these fields:
- projects: list of project/product names mentioned
- technologies: list of technologies, frameworks, languages
- people: list of people mentioned
- concepts: list of abstract concepts or topics
- organizations: list of companies or organizations

Example: [{{"projects": ["distill"], "technologies": ["python", \
"pgvector"], "people": [], "concepts": ["content pipeline"], \
"organizations": ["Anthropic"]}}]

Content items:

{items_text}"""


def _build_classification_prompt(items: list[ContentItem]) -> str:
    """Build a prompt for content classification."""
    parts: list[str] = []
    for i, item in enumerate(items):
        text = item.title
        if item.body:
            text += "\n" + item.body[:300]
        parts.append(f"[ITEM {i}]\n{text}")

    items_text = "\n\n".join(parts)

    return f"""Classify each content item below.

Return ONLY valid JSON — an array of objects, one per item, in the same order.
Each object must have:
- category: one of "tutorial", "opinion", "news", "reference", \
"session-log", "announcement", "discussion"
- sentiment: one of "positive", "negative", "neutral", "mixed"
- relevance: integer 1-5 (how relevant to a software engineer's daily work)

Example: [{{"category": "tutorial", "sentiment": "positive", "relevance": 4}}]

Content items:

{items_text}"""


def _build_topic_prompt(items: list[ContentItem], existing_topics: list[str]) -> str:
    """Build a prompt for topic extraction across items."""
    titles = [item.title for item in items if item.title][:30]
    titles_text = "\n".join(f"- {t}" for t in titles)

    existing = ", ".join(existing_topics) if existing_topics else "(none)"

    return f"""Identify the main topics/themes across these content items.

Existing topics: {existing}

Content titles:
{titles_text}

Return ONLY valid JSON — a flat array of topic strings (3-8 topics).
Merge similar topics. Prefer existing topic names when they still apply.
Example: ["AI agents", "developer tools", "testing patterns"]"""


def extract_entities(
    items: list[ContentItem],
    *,
    model: str | None = None,
    timeout: int = 120,
) -> list[ContentItem]:
    """Extract named entities from content items via LLM.

    Populates item.metadata["entities"] with projects, technologies,
    people, concepts, and organizations.

    Args:
        items: Content items to process (modified in place).
        model: Optional Claude model override.
        timeout: LLM timeout in seconds.

    Returns:
        The same list with entities populated.
    """
    failed_empty = 0
    failed_parse = 0
    succeeded = 0

    for batch_start in range(0, len(items), _BATCH_SIZE):
        batch = items[batch_start : batch_start + _BATCH_SIZE]
        prompt = _build_entity_prompt(batch)
        response = _call_claude(prompt, model=model or _INTELLIGENCE_MODEL, timeout=timeout)

        if not response:
            failed_empty += 1
            continue

        parsed = _parse_json_response(response)
        if not isinstance(parsed, list):
            failed_parse += 1
            logger.debug(
                "Entity extraction non-list response (batch %d): %.200s",
                batch_start,
                response,
            )
            continue

        succeeded += 1
        for i, item in enumerate(batch):
            if i < len(parsed) and isinstance(parsed[i], dict):
                entities = parsed[i]
                item.metadata["entities"] = entities
                # Also populate topics from concepts
                concepts = entities.get("concepts", [])
                if concepts and not item.topics:
                    item.topics = concepts[:5]

    total = failed_empty + failed_parse + succeeded
    if failed_empty or failed_parse:
        logger.warning(
            "Entity extraction: %d/%d batches succeeded, %d empty responses, %d parse failures",
            succeeded,
            total,
            failed_empty,
            failed_parse,
        )

    return items


def classify_items(
    items: list[ContentItem],
    *,
    model: str | None = None,
    timeout: int = 120,
) -> list[ContentItem]:
    """Classify content items by type via LLM.

    Sets item.metadata["classification"] with category, sentiment,
    and relevance.

    Args:
        items: Content items to process (modified in place).
        model: Optional Claude model override.
        timeout: LLM timeout in seconds.

    Returns:
        The same list with classification populated.
    """
    failed_empty = 0
    failed_parse = 0
    succeeded = 0

    for batch_start in range(0, len(items), _BATCH_SIZE):
        batch = items[batch_start : batch_start + _BATCH_SIZE]
        prompt = _build_classification_prompt(batch)
        response = _call_claude(prompt, model=model or _INTELLIGENCE_MODEL, timeout=timeout)

        if not response:
            failed_empty += 1
            continue

        parsed = _parse_json_response(response)
        if not isinstance(parsed, list):
            failed_parse += 1
            logger.debug(
                "Classification non-list response (batch %d): %.200s",
                batch_start,
                response,
            )
            continue

        succeeded += 1
        for i, item in enumerate(batch):
            if i < len(parsed) and isinstance(parsed[i], dict):
                item.metadata["classification"] = parsed[i]

    total = failed_empty + failed_parse + succeeded
    if failed_empty or failed_parse:
        logger.warning(
            "Classification: %d/%d batches succeeded, %d empty responses, %d parse failures",
            succeeded,
            total,
            failed_empty,
            failed_parse,
        )

    return items


def extract_topics(
    items: list[ContentItem],
    existing_topics: list[str] | None = None,
    *,
    model: str | None = None,
    timeout: int = 120,
) -> list[str]:
    """Identify emergent topics across a batch of items.

    Args:
        items: Content items to analyze.
        existing_topics: Previously known topics for continuity.
        model: Optional Claude model override.
        timeout: LLM timeout in seconds.

    Returns:
        New/updated topic list.
    """
    if not items:
        return existing_topics or []

    prompt = _build_topic_prompt(items, existing_topics or [])
    response = _call_claude(prompt, model=model or _INTELLIGENCE_MODEL, timeout=timeout)

    if not response:
        return existing_topics or []

    parsed = _parse_json_response(response)
    if isinstance(parsed, list) and all(isinstance(t, str) for t in parsed):
        return parsed

    return existing_topics or []
