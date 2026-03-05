"""Discovery engine — find content based on reading patterns."""
from __future__ import annotations

import json
import logging
import subprocess
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DISCOVERY_FILENAME = ".distill-discoveries.json"


class DiscoveryItem(BaseModel):
    """A discovered content recommendation."""
    title: str
    url: str
    source: str = ""  # site/author name
    summary: str = ""  # why this is relevant
    topic: str = ""  # which user topic triggered this
    content_type: str = "article"  # article, video, paper, podcast


class DiscoveryResult(BaseModel):
    """Daily discovery results."""
    date: str
    generated_at: str = ""
    items: list[DiscoveryItem] = Field(default_factory=list)
    topics_searched: list[str] = Field(default_factory=list)


def _extract_active_topics(
    output_dir: Path,
    days: int = 7,
    top_n: int = 5,
) -> list[str]:
    """Extract the most active topics from recent intake archives."""
    archive_dir = output_dir / "intake" / "archive"
    if not archive_dir.exists():
        return []

    tag_counts: Counter[str] = Counter()
    today = date.today()

    for day_offset in range(days):
        d = today - timedelta(days=day_offset)
        path = archive_dir / f"{d.isoformat()}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.get("items", []) if isinstance(data, dict) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("source") in ("session", "seeds", "troopx"):
                    continue
                for tag in item.get("tags", []):
                    if tag and len(tag) > 2:
                        tag_counts[tag.lower()] += 1
                for topic in item.get("topics", []):
                    if topic and len(topic) > 2:
                        tag_counts[topic.lower()] += 1
        except (json.JSONDecodeError, OSError):
            continue

    # Filter out very generic tags
    generic = {"article", "blog", "post", "news", "update", "opinion", "reference"}
    return [
        tag for tag, _count in tag_counts.most_common(top_n + len(generic))
        if tag not in generic
    ][:top_n]


def _get_read_urls(output_dir: Path, days: int = 14) -> set[str]:
    """Collect URLs already read from recent archives."""
    archive_dir = output_dir / "intake" / "archive"
    if not archive_dir.exists():
        return set()

    urls: set[str] = set()
    today = date.today()

    for day_offset in range(days):
        d = today - timedelta(days=day_offset)
        path = archive_dir / f"{d.isoformat()}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.get("items", []) if isinstance(data, dict) else []
            for item in items:
                if isinstance(item, dict) and item.get("url"):
                    urls.add(item["url"])
        except (json.JSONDecodeError, OSError):
            continue

    return urls


def _call_claude(system: str, user: str, tag: str = "discovery") -> str:
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


def discover_content(
    output_dir: Path,
    target_date: str | None = None,
    max_items: int = 8,
) -> DiscoveryResult:
    """Discover new content based on recent reading patterns.

    1. Extract active topics from recent archives
    2. Ask Claude (with web search) to find fresh articles/videos
    3. Dedup against already-read URLs
    4. Save results
    """
    from datetime import datetime

    if target_date is None:
        target_date = date.today().isoformat()

    topics = _extract_active_topics(output_dir)
    if not topics:
        result = DiscoveryResult(
            date=target_date,
            generated_at=datetime.now().isoformat(),
        )
        _save_discoveries(result, output_dir)
        return result

    read_urls = _get_read_urls(output_dir)

    system_prompt = f"""You are a content curator. Based on the user's active reading topics, find fresh, high-quality content they should read next.

## Rules
- Find 6-8 specific articles, papers, YouTube videos, or podcast episodes
- Content must be substantive (no listicles, no SEO spam, no press releases)
- Prefer: original research, practitioner experience, deep analysis
- Each recommendation needs a concrete URL
- Include a mix of content types when possible (articles, videos, papers)
- For each item, explain in 1 sentence WHY it's relevant to the user's interests
- Do NOT recommend any of the URLs listed in the "Already Read" section

## Output Format
Return valid JSON:
```json
{{
  "items": [
    {{
      "title": "Article title",
      "url": "https://...",
      "source": "Author or site",
      "summary": "Why this is relevant",
      "topic": "which user topic this relates to",
      "content_type": "article|video|paper|podcast"
    }}
  ]
}}
```"""

    topics_text = "## Active Reading Topics\n" + "\n".join(f"- {t}" for t in topics)
    already_read = ""
    if read_urls:
        sample = list(read_urls)[:30]
        already_read = "\n\n## Already Read (do NOT recommend these)\n" + "\n".join(
            f"- {u}" for u in sample
        )

    user_prompt = f"{topics_text}{already_read}"

    try:
        raw = _call_claude(system_prompt, user_prompt, "discover")
        raw = _strip_json_fences(raw)
        data = json.loads(raw)
        items = [
            DiscoveryItem.model_validate(item)
            for item in data.get("items", [])[:max_items]
        ]
        # Final dedup against read URLs
        items = [item for item in items if item.url not in read_urls]
    except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
        logger.warning("Discovery generation failed: %s", exc)
        items = []

    result = DiscoveryResult(
        date=target_date,
        generated_at=datetime.now().isoformat(),
        items=items,
        topics_searched=topics,
    )
    _save_discoveries(result, output_dir)
    return result


def _save_discoveries(result: DiscoveryResult, output_dir: Path) -> None:
    """Save discovery results to disk."""
    path = output_dir / DISCOVERY_FILENAME
    output_dir.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = [e for e in data if e.get("date") != result.date]
        except (json.JSONDecodeError, OSError):
            pass
    existing.append(result.model_dump())
    existing = sorted(existing, key=lambda e: e.get("date", ""))[-14:]
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def load_discoveries(
    output_dir: Path,
    target_date: str,
) -> DiscoveryResult | None:
    """Load discoveries for a specific date."""
    path = output_dir / DISCOVERY_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and entry.get("date") == target_date:
                    return DiscoveryResult.model_validate(entry)
    except (json.JSONDecodeError, ValueError):
        pass
    return None
