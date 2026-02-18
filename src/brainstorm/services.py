"""Service functions for the content brainstorm pipeline.

Consolidates analyst, source-fetching, and publishing logic.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from distill.brainstorm.models import (
    ContentCalendar,
    ContentIdea,
    ResearchItem,
    SourceTier,
    save_calendar,
)
from distill.brainstorm.prompts import get_analyst_prompt

logger = logging.getLogger(__name__)

try:
    import feedparser

    _HAS_FEEDPARSER = True
except ImportError:
    feedparser = None  # type: ignore[assignment]
    _HAS_FEEDPARSER = False

# ---------------------------------------------------------------------------
# Source constants
# ---------------------------------------------------------------------------

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

# ---------------------------------------------------------------------------
# Source fetchers (from sources.py)
# ---------------------------------------------------------------------------


def fetch_hacker_news(min_points: int = 50) -> list[ResearchItem]:
    """Fetch front-page HN stories above a point threshold."""
    try:
        req = urllib.request.Request(HN_ALGOLIA_URL)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.warning("Failed to fetch Hacker News", exc_info=True)
        return []

    items: list[ResearchItem] = []
    for hit in data.get("hits", []):
        points = hit.get("points", 0) or 0
        if points < min_points:
            continue
        url = hit.get("url", "")
        if not url:
            url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        items.append(
            ResearchItem(
                title=hit.get("title", ""),
                url=url,
                summary=f"{points} points, {hit.get('num_comments', 0)} comments on HN",
                source_tier=SourceTier.HN,
                points=points,
            )
        )
    return items


def fetch_arxiv(
    categories: list[str] | None = None,
    max_results: int = 20,
) -> list[ResearchItem]:
    """Fetch recent arXiv papers for given categories."""
    cats = categories or ["cs.AI"]
    query = "+OR+".join(f"cat:{c}" for c in cats)
    url = (
        f"{ARXIV_API_URL}?search_query={query}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_results}"
    )

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception:
        logger.warning("Failed to fetch arXiv", exc_info=True)
        return []

    items: list[ResearchItem] = []
    try:
        root = ET.fromstring(xml_data)
        for entry in root.findall(f"{ATOM_NS}entry"):
            title_el = entry.find(f"{ATOM_NS}title")
            summary_el = entry.find(f"{ATOM_NS}summary")
            link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
            authors = []
            for a in entry.findall(f"{ATOM_NS}author"):
                name_el = a.find(f"{ATOM_NS}name")
                if name_el is not None and name_el.text:
                    authors.append(name_el.text)
            items.append(
                ResearchItem(
                    title=(title_el.text or "").strip() if title_el is not None else "",
                    url=link_el.get("href", "") if link_el is not None else "",
                    summary=(
                        (summary_el.text or "").strip()[:300] if summary_el is not None else ""
                    ),
                    source_tier=SourceTier.ARXIV,
                    authors=authors,
                )
            )
    except ET.ParseError:
        logger.warning("Failed to parse arXiv XML", exc_info=True)

    return items


def _fetch_feed_items(feed_url: str) -> list[ResearchItem]:
    """Fetch items from a single RSS/Atom feed."""
    if not _HAS_FEEDPARSER:
        logger.warning("feedparser not installed, skipping feed: %s", feed_url)
        return []
    try:
        feed = feedparser.parse(feed_url)
        items: list[ResearchItem] = []
        for entry in feed.entries[:10]:
            items.append(
                ResearchItem(
                    title=getattr(entry, "title", ""),
                    url=getattr(entry, "link", ""),
                    summary=getattr(entry, "summary", "")[:300],
                    source_tier=SourceTier.FOLLOWED,
                )
            )
        return items
    except Exception:
        logger.warning("Failed to fetch feed: %s", feed_url, exc_info=True)
        return []


def fetch_followed_feeds(feed_urls: list[str]) -> list[ResearchItem]:
    """Fetch items from all followed feed URLs."""
    items: list[ResearchItem] = []
    for url in feed_urls:
        items.extend(_fetch_feed_items(url))
    return items


def _fetch_url_item(url: str) -> ResearchItem:
    """Fetch a single URL and extract title + summary."""
    req = urllib.request.Request(url, headers={"User-Agent": "distill/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")[:10000]

    # Simple title extraction
    title = url
    if "<title>" in html.lower():
        start = html.lower().index("<title>") + 7
        end = html.lower().index("</title>", start)
        title = html[start:end].strip()

    return ResearchItem(
        title=title,
        url=url,
        summary="",
        source_tier=SourceTier.MANUAL,
    )


def fetch_manual_links(urls: list[str]) -> list[ResearchItem]:
    """Fetch and extract info from manual link URLs."""
    items: list[ResearchItem] = []
    for url in urls:
        try:
            items.append(_fetch_url_item(url))
        except Exception:
            logger.warning("Failed to fetch manual link: %s", url, exc_info=True)
    return items


# ---------------------------------------------------------------------------
# Analyst logic (from analyst.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Publisher logic (from publisher.py)
# ---------------------------------------------------------------------------


def _render_markdown(ideas: list[ContentIdea], date: str) -> str:
    """Render content ideas as a human-readable markdown file."""
    lines = [f"# Content Calendar — {date}", ""]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"## {i}. {idea.title}")
        lines.append("")
        lines.append(f"**Angle:** {idea.angle}")
        lines.append(f"**Platform:** {idea.platform}")
        lines.append(f"**Pillars:** {', '.join(idea.pillars)}")
        lines.append(f"**Source:** {idea.source_url}")
        lines.append(f"**Why:** {idea.rationale}")
        if idea.tags:
            lines.append(f"**Tags:** {', '.join(idea.tags)}")
        lines.append("")
    return "\n".join(lines)


def publish_calendar(
    ideas: list[ContentIdea],
    date: str,
    output_dir: Path,
    create_seeds: bool = True,
    create_ghost_drafts: bool = True,
) -> ContentCalendar:
    """Publish content ideas to all destinations."""
    calendar = ContentCalendar(date=date, ideas=ideas)

    # 1. Save JSON calendar
    save_calendar(calendar, output_dir)

    # 2. Save markdown calendar
    cal_dir = output_dir / "content-calendar"
    cal_dir.mkdir(parents=True, exist_ok=True)
    md_path = cal_dir / f"{date}.md"
    md_path.write_text(_render_markdown(ideas, date), encoding="utf-8")

    # 3. Create seeds
    if create_seeds:
        try:
            from distill.intake.seeds import SeedStore

            store = SeedStore(output_dir)
            for idea in ideas:
                store.add(
                    text=f"{idea.title}: {idea.angle}",
                    tags=idea.tags,
                )
            logger.info("Created %d seeds from content ideas", len(ideas))
        except Exception:
            logger.warning("Failed to create seeds", exc_info=True)

    # 4. Create Ghost drafts
    if create_ghost_drafts:
        try:
            from distill.integrations.ghost import GhostAPIClient, GhostConfig

            config = GhostConfig.from_env()
            if config.is_configured:
                client = GhostAPIClient(config)
                for idea in ideas:
                    if idea.platform not in ("blog", "both"):
                        continue
                    outline = (
                        f"## {idea.title}\n\n"
                        f"{idea.angle}\n\n"
                        f"**Source:** {idea.source_url}\n\n"
                        f"{idea.rationale}"
                    )
                    result = client.create_post(
                        title=idea.title,
                        markdown=outline,
                        tags=idea.pillars + idea.tags,
                        status="draft",
                    )
                    idea.ghost_post_id = result.get("id")
                    logger.info("Created Ghost draft: %s", idea.title)
            else:
                logger.info("Ghost not configured, skipping drafts")
        except Exception:
            logger.warning("Failed to create Ghost drafts", exc_info=True)

    # Re-save calendar with ghost_post_ids
    save_calendar(calendar, output_dir)

    return calendar
