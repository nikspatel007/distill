"""Persistence for reading briefs."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from distill.brief.models import ReadingBrief

logger = logging.getLogger(__name__)

BRIEF_FILENAME = ".distill-reading-brief.json"


def load_reading_brief(output_dir: Path, target_date: str) -> ReadingBrief | None:
    """Load the reading brief for a specific date, or None if not found."""
    path = output_dir / BRIEF_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("date") == target_date:
            return ReadingBrief.model_validate(data)
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and entry.get("date") == target_date:
                    return ReadingBrief.model_validate(entry)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt reading brief at %s", path)
    return None


def save_reading_brief(brief: ReadingBrief, output_dir: Path) -> Path:
    """Save a reading brief. Stores as list to support multiple dates."""
    path = output_dir / BRIEF_FILENAME
    output_dir.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = [e for e in data if e.get("date") != brief.date]
            elif isinstance(data, dict):
                if data.get("date") != brief.date:
                    existing = [data]
        except (json.JSONDecodeError, ValueError):
            pass

    existing.append(brief.model_dump())
    # Keep last 14 days
    existing = sorted(existing, key=lambda e: e.get("date", ""))[-14:]
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return path
