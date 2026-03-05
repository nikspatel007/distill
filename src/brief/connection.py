"""Connection engine — links today's reading to your past."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from distill.memory.models import UnifiedMemory
from distill.memory.services import load_unified_memory

if TYPE_CHECKING:
    from distill.brief.models import ReadingHighlight

logger = logging.getLogger(__name__)


class ConnectionInsight(BaseModel):
    """A connection between today's reading and something from your past."""
    today: str  # highlight title
    past: str  # what it connects to
    connection_type: str  # "thread", "entity", "theme", "published"
    explanation: str  # 1-2 sentence explanation
    strength: float = 0.0  # 0-1 score


def find_connection(
    highlights: list[ReadingHighlight],
    output_dir: Path,
) -> ConnectionInsight | None:
    """Find the strongest connection between today's reading and past activity.

    Uses text matching on tags, titles, and themes to find overlaps.
    No LLM calls — pure algorithmic matching.
    """
    memory = load_unified_memory(output_dir)
    if not memory.entries and not memory.threads and not memory.entities:
        return None
    if not highlights:
        return None

    candidates: list[ConnectionInsight] = []

    # Collect all highlight keywords (tags + title words)
    for highlight in highlights:
        h_keywords = set(t.lower() for t in highlight.tags)
        h_keywords.update(
            w.lower() for w in highlight.title.split()
            if len(w) > 3  # skip short words
        )
        h_title = highlight.title

        # Check against memory threads
        for thread in memory.threads:
            if thread.status != "active":
                continue
            thread_words = set(w.lower() for w in thread.name.split() if len(w) > 3)
            thread_words.update(w.lower() for w in thread.summary.split() if len(w) > 3)
            overlap = h_keywords & thread_words
            if overlap:
                score = len(overlap) / max(len(h_keywords), 1)
                candidates.append(ConnectionInsight(
                    today=h_title,
                    past=f"ongoing thread: {thread.name}",
                    connection_type="thread",
                    explanation=(
                        f"Your reading about '{h_title}' connects to "
                        f"'{thread.name}' — a thread you've been tracking "
                        f"since {thread.first_seen.isoformat()} "
                        f"({thread.mention_count} mentions). "
                        f"Shared concepts: {', '.join(sorted(overlap)[:3])}."
                    ),
                    strength=min(score * 1.5, 1.0),  # boost threads
                ))

        # Check against entities
        for _key, entity in memory.entities.items():
            entity_words = set(w.lower() for w in entity.name.split() if len(w) > 2)
            # Direct name match in highlight title or tags
            if entity.name.lower() in h_title.lower() or entity_words & h_keywords:
                days_tracked = (entity.last_seen - entity.first_seen).days + 1
                score = min(entity.mention_count / 10.0, 1.0)
                candidates.append(ConnectionInsight(
                    today=h_title,
                    past=f"{entity.entity_type}: {entity.name}",
                    connection_type="entity",
                    explanation=(
                        f"'{h_title}' mentions {entity.name}, "
                        f"a {entity.entity_type} you've tracked "
                        f"{entity.mention_count} times over {days_tracked} days."
                    ),
                    strength=score,
                ))

        # Check against recent themes in daily entries
        for entry in sorted(memory.entries, key=lambda e: e.date, reverse=True)[:14]:
            entry_themes = set(t.lower() for t in entry.themes)
            overlap = h_keywords & entry_themes
            if overlap:
                score = len(overlap) / max(len(h_keywords), 1) * 0.8
                candidates.append(ConnectionInsight(
                    today=h_title,
                    past=f"themes from {entry.date.isoformat()}",
                    connection_type="theme",
                    explanation=(
                        f"Your reading about '{h_title}' echoes themes "
                        f"from {entry.date.isoformat()}: "
                        f"{', '.join(sorted(overlap)[:3])}."
                    ),
                    strength=min(score, 1.0),
                ))

    if not candidates:
        return None

    # Return strongest connection
    candidates.sort(key=lambda c: c.strength, reverse=True)
    return candidates[0]
