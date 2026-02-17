"""Data models for the content brainstorm pipeline."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class SourceTier(str, Enum):
    MANUAL = "manual"
    FOLLOWED = "followed"
    HN = "hacker_news"
    ARXIV = "arxiv"


class ResearchItem(BaseModel):
    """A single item gathered from a research source."""
    title: str
    url: str
    summary: str
    source_tier: SourceTier
    points: int | None = None
    authors: list[str] = Field(default_factory=list)


class ContentIdea(BaseModel):
    """A content idea produced by the analyst."""
    title: str
    angle: str
    source_url: str
    platform: str  # "blog", "social", "both"
    rationale: str
    pillars: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "pending"  # "pending", "approved", "rejected"
    ghost_post_id: str | None = None


class ContentCalendar(BaseModel):
    """A day's content calendar with brainstormed ideas."""
    date: str  # YYYY-MM-DD
    ideas: list[ContentIdea] = Field(default_factory=list)


CALENDAR_DIR = "content-calendar"


def save_calendar(calendar: ContentCalendar, output_dir: Path) -> Path:
    """Save a content calendar to JSON file."""
    cal_dir = output_dir / CALENDAR_DIR
    cal_dir.mkdir(parents=True, exist_ok=True)
    path = cal_dir / f"{calendar.date}.json"
    path.write_text(calendar.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_calendar(date: str, output_dir: Path) -> ContentCalendar | None:
    """Load a content calendar for a specific date."""
    path = output_dir / CALENDAR_DIR / f"{date}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ContentCalendar.model_validate(data)
    except Exception:
        return None
