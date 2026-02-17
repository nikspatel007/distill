"""Source fetchers for the content brainstorm pipeline."""

from __future__ import annotations

import json
import logging
import urllib.request
import xml.etree.ElementTree as ET

from distill.brainstorm.models import ResearchItem, SourceTier

logger = logging.getLogger(__name__)

try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    feedparser = None  # type: ignore[assignment]
    _HAS_FEEDPARSER = False

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


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
    url = f"{ARXIV_API_URL}?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

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
            authors = [
                a.find(f"{ATOM_NS}name").text
                for a in entry.findall(f"{ATOM_NS}author")
                if a.find(f"{ATOM_NS}name") is not None
                and a.find(f"{ATOM_NS}name").text
            ]
            items.append(
                ResearchItem(
                    title=(title_el.text or "").strip() if title_el is not None else "",
                    url=link_el.get("href", "") if link_el is not None else "",
                    summary=(summary_el.text or "").strip()[:300] if summary_el is not None else "",
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
