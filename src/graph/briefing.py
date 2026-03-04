"""Executive briefing — LLM-synthesized personal intelligence from the knowledge graph."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BRIEFING_FILENAME = ".distill-briefing.json"


class BriefingArea(BaseModel):
    """A project or focus area with momentum tracking."""

    name: str
    status: str = "active"
    momentum: str = "steady"
    headline: str = ""
    sessions: int = 0
    reading_count: int = 0
    open_threads: list[str] = Field(default_factory=list)


class BriefingLearning(BaseModel):
    """A reading/learning topic and its connection to active work."""

    topic: str
    reading_count: int = 0
    connection: str = ""
    status: str = "emerging"


class BriefingRisk(BaseModel):
    """A risk with severity and plain-English description."""

    severity: str = "medium"
    headline: str
    detail: str = ""
    project: str = ""


class BriefingRecommendation(BaseModel):
    """A prioritized action recommendation."""

    priority: int = 1
    action: str
    rationale: str = ""


class Briefing(BaseModel):
    """Complete executive briefing for a given day."""

    date: str = Field(default_factory=lambda: datetime.now(tz=UTC).strftime("%Y-%m-%d"))
    generated_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    time_window_hours: int = 48
    summary: str = ""
    areas: list[BriefingArea] = Field(default_factory=list)
    learning: list[BriefingLearning] = Field(default_factory=list)
    risks: list[BriefingRisk] = Field(default_factory=list)
    recommendations: list[BriefingRecommendation] = Field(default_factory=list)


def load_briefing(output_dir: Path) -> Briefing | None:
    """Load the most recent briefing from disk."""
    path = output_dir / BRIEFING_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Briefing.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt briefing file at %s", path)
        return None


def save_briefing(briefing: Briefing, output_dir: Path) -> Path:
    """Save a briefing to disk. Returns the file path."""
    path = output_dir / BRIEFING_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(briefing.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return path
