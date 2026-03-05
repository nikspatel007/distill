"""Learning pulse — topic attention tracking over time."""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TopicTrend(BaseModel):
    """A topic's attention trajectory."""
    topic: str
    status: str  # "trending", "cooling", "emerging", "stable"
    count: int = 0  # total mentions in window
    recent_count: int = 0  # mentions in last 3 days
    first_seen: str = ""  # ISO date
    last_seen: str = ""  # ISO date
    sparkline: list[int] = Field(default_factory=list)  # daily counts for visualization


def compute_learning_pulse(
    output_dir: Path,
    days: int = 14,
    recent_days: int = 3,
) -> list[TopicTrend]:
    """Compute topic attention trends from intake archives.

    Scans intake archives for the last `days` days, aggregates
    tags and topics, and classifies each as trending/cooling/emerging/stable.
    """
    today = date.today()
    archive_dir = output_dir / "intake" / "archive"

    if not archive_dir.exists():
        return []

    # Collect tag counts per day
    daily_tags: dict[str, Counter[str]] = {}
    all_tags: Counter[str] = Counter()
    recent_tags: Counter[str] = Counter()
    tag_first_seen: dict[str, str] = {}
    tag_last_seen: dict[str, str] = {}

    recent_cutoff = today - timedelta(days=recent_days)

    for day_offset in range(days):
        d = today - timedelta(days=day_offset)
        d_str = d.isoformat()
        archive_path = archive_dir / f"{d_str}.json"

        if not archive_path.exists():
            continue

        try:
            data = json.loads(archive_path.read_text(encoding="utf-8"))
            items = data.get("items", []) if isinstance(data, dict) else []
        except (json.JSONDecodeError, OSError):
            continue

        day_counter: Counter[str] = Counter()
        for item in items:
            if not isinstance(item, dict):
                continue
            # Skip session items
            source = item.get("source", "")
            if source in ("session", "seeds", "troopx"):
                continue

            tags = item.get("tags", [])
            topics = item.get("topics", [])
            combined = set(tags) | set(topics)

            for tag in combined:
                if not tag or len(tag) < 2:
                    continue
                tag_lower = tag.lower()
                day_counter[tag_lower] += 1
                all_tags[tag_lower] += 1

                if d >= recent_cutoff:
                    recent_tags[tag_lower] += 1

                if tag_lower not in tag_first_seen or d_str < tag_first_seen[tag_lower]:
                    tag_first_seen[tag_lower] = d_str
                if tag_lower not in tag_last_seen or d_str > tag_last_seen[tag_lower]:
                    tag_last_seen[tag_lower] = d_str

        daily_tags[d_str] = day_counter

    if not all_tags:
        return []

    # Build sparklines (daily counts for the window, oldest first)
    date_range = [
        (today - timedelta(days=i)).isoformat()
        for i in range(days - 1, -1, -1)
    ]

    # Classify each topic
    trends: list[TopicTrend] = []
    for topic, total in all_tags.most_common(20):  # top 20 topics
        if total < 2:
            continue

        recent = recent_tags.get(topic, 0)
        first = tag_first_seen.get(topic, "")
        last = tag_last_seen.get(topic, "")

        # Build sparkline
        sparkline = [
            daily_tags.get(d, Counter()).get(topic, 0)
            for d in date_range
        ]

        # Classify
        status = _classify_topic(total, recent, days, recent_days, first, today)

        trends.append(TopicTrend(
            topic=topic,
            status=status,
            count=total,
            recent_count=recent,
            first_seen=first,
            last_seen=last,
            sparkline=sparkline,
        ))

    # Sort: trending first, then by count
    status_order = {"trending": 0, "emerging": 1, "stable": 2, "cooling": 3}
    trends.sort(key=lambda t: (status_order.get(t.status, 4), -t.count))
    return trends


def _classify_topic(
    total: int,
    recent: int,
    days: int,
    recent_days: int,
    first_seen: str,
    today: date,
) -> str:
    """Classify a topic's trajectory."""
    # Emerging: first seen in the last 3 days
    if first_seen:
        try:
            fs = date.fromisoformat(first_seen)
            if (today - fs).days <= recent_days:
                return "emerging"
        except ValueError:
            pass

    # Expected recent count if evenly distributed
    expected_ratio = recent_days / days if days > 0 else 0
    expected = total * expected_ratio
    if expected < 1:
        expected = 1

    ratio = recent / expected if expected > 0 else 0

    if ratio >= 1.5:
        return "trending"
    elif ratio <= 0.3 and recent == 0:
        return "cooling"
    return "stable"
