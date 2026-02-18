# Content Brainstorm Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a TroopX 3-agent workflow that daily gathers research from HN, arXiv, and followed feeds, then brainstorms 2-3 content ideas filtered through content pillars, outputting to seeds, Ghost drafts, and a dashboard page.

**Architecture:** New `src/brainstorm/` module with config, source fetchers, analyst logic, and publisher. TroopX workflow YAML defines 3 agents (researcher→analyst→editor) coordinating via agent-router blackboard. Web dashboard gets a new `/calendar` route.

**Tech Stack:** Python 3.11+, Pydantic v2, feedparser (existing), urllib (HN/arXiv APIs), TroopX agent-router MCP, Hono + React + TanStack Router (dashboard).

---

### Task 1: BrainstormConfig model + TOML integration

**Files:**
- Create: `src/brainstorm/__init__.py`
- Create: `src/brainstorm/config.py`
- Modify: `src/config.py:166-183` (add brainstorm field to DistillConfig)
- Modify: `.distill.toml` (add [brainstorm] section)
- Test: `tests/brainstorm/test_config.py`

**Step 1: Write the failing test**

```python
# tests/brainstorm/__init__.py — empty

# tests/brainstorm/test_config.py
from distill.brainstorm.config import BrainstormConfig


def test_default_config():
    cfg = BrainstormConfig()
    assert cfg.pillars == []
    assert cfg.followed_people == []
    assert cfg.manual_links == []
    assert cfg.arxiv_categories == ["cs.AI", "cs.SE", "cs.MA"]
    assert cfg.hacker_news is True
    assert cfg.hn_min_points == 50


def test_is_configured_empty():
    cfg = BrainstormConfig()
    assert cfg.is_configured is False


def test_is_configured_with_pillars():
    cfg = BrainstormConfig(pillars=["Multi-agent systems"])
    assert cfg.is_configured is True


def test_distill_config_has_brainstorm():
    from distill.config import DistillConfig

    dc = DistillConfig()
    assert hasattr(dc, "brainstorm")
    assert isinstance(dc.brainstorm, BrainstormConfig)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_config.py -x -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.brainstorm'`

**Step 3: Write minimal implementation**

```python
# src/brainstorm/__init__.py
"""Content brainstorm pipeline — daily content ideation from research sources."""

# src/brainstorm/config.py
"""Configuration for the brainstorm pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrainstormConfig(BaseModel):
    """Configuration for the content brainstorm pipeline."""

    pillars: list[str] = Field(default_factory=list)
    followed_people: list[str] = Field(default_factory=list)
    manual_links: list[str] = Field(default_factory=list)
    arxiv_categories: list[str] = Field(
        default_factory=lambda: ["cs.AI", "cs.SE", "cs.MA"]
    )
    hacker_news: bool = True
    hn_min_points: int = 50

    @property
    def is_configured(self) -> bool:
        return bool(self.pillars)
```

Then add to `src/config.py`:
- Import: `from distill.brainstorm.config import BrainstormConfig`
- Add field to `DistillConfig`: `brainstorm: BrainstormConfig = Field(default_factory=BrainstormConfig)`

Add to `pyproject.toml` packages list: `"distill.brainstorm"`

Add to `.distill.toml`:
```toml
[brainstorm]
pillars = [
  "Building multi-agent systems",
  "AI architecture patterns",
  "Human-AI collaboration",
  "Evals and verification",
  "Running an autonomous company",
]
followed_people = [
  "https://simonwillison.net/atom/everything/",
  "https://martinfowler.com/feed.atom",
]
manual_links = []
arxiv_categories = ["cs.AI", "cs.SE", "cs.MA"]
hacker_news = true
hn_min_points = 50
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_config.py -x -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/ tests/brainstorm/ src/config.py pyproject.toml .distill.toml
git commit -m "feat(brainstorm): add BrainstormConfig model and TOML integration"
```

---

### Task 2: Content calendar data models

**Files:**
- Create: `src/brainstorm/models.py`
- Test: `tests/brainstorm/test_models.py`

**Step 1: Write the failing test**

```python
# tests/brainstorm/test_models.py
import json
from datetime import datetime, timezone

from distill.brainstorm.models import (
    ContentIdea,
    ContentCalendar,
    ResearchItem,
    SourceTier,
)


def test_source_tier_values():
    assert SourceTier.MANUAL == "manual"
    assert SourceTier.HN == "hacker_news"
    assert SourceTier.ARXIV == "arxiv"
    assert SourceTier.FOLLOWED == "followed"


def test_research_item_creation():
    item = ResearchItem(
        title="Test Paper",
        url="https://example.com/paper",
        summary="A test paper about agents.",
        source_tier=SourceTier.ARXIV,
    )
    assert item.title == "Test Paper"
    assert item.source_tier == SourceTier.ARXIV
    assert item.points is None


def test_content_idea_creation():
    idea = ContentIdea(
        title="Building Reliable Agent Swarms",
        angle="How evals catch coordination failures before production",
        source_url="https://arxiv.org/abs/2026.12345",
        platform="both",
        rationale="Bridges multi-agent and evals pillars",
        pillars=["Building multi-agent systems", "Evals and verification"],
        tags=["agents", "evals"],
    )
    assert idea.platform == "both"
    assert len(idea.pillars) == 2
    assert idea.status == "pending"


def test_content_calendar_serialization():
    cal = ContentCalendar(
        date="2026-02-17",
        ideas=[
            ContentIdea(
                title="Test",
                angle="Test angle",
                source_url="https://example.com",
                platform="blog",
                rationale="Test",
                pillars=["AI architecture patterns"],
            )
        ],
    )
    data = json.loads(cal.model_dump_json())
    assert data["date"] == "2026-02-17"
    assert len(data["ideas"]) == 1
    assert data["ideas"][0]["status"] == "pending"


def test_content_calendar_load_save(tmp_path):
    from distill.brainstorm.models import load_calendar, save_calendar

    cal = ContentCalendar(
        date="2026-02-17",
        ideas=[
            ContentIdea(
                title="Test",
                angle="Angle",
                source_url="https://example.com",
                platform="social",
                rationale="Reason",
                pillars=["Human-AI collaboration"],
            )
        ],
    )
    save_calendar(cal, tmp_path)
    loaded = load_calendar("2026-02-17", tmp_path)
    assert loaded is not None
    assert len(loaded.ideas) == 1
    assert loaded.ideas[0].title == "Test"


def test_load_calendar_missing(tmp_path):
    from distill.brainstorm.models import load_calendar

    loaded = load_calendar("2099-01-01", tmp_path)
    assert loaded is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_models.py -x -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/brainstorm/models.py
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_models.py -x -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/models.py tests/brainstorm/test_models.py
git commit -m "feat(brainstorm): add ContentIdea, ContentCalendar, ResearchItem models"
```

---

### Task 3: HN source fetcher

**Files:**
- Create: `src/brainstorm/sources.py`
- Test: `tests/brainstorm/test_sources.py`

**Step 1: Write the failing test**

```python
# tests/brainstorm/test_sources.py
import json
from unittest.mock import patch, MagicMock

from distill.brainstorm.models import SourceTier
from distill.brainstorm.sources import fetch_hacker_news


HN_RESPONSE = {
    "hits": [
        {
            "title": "Show HN: An agent framework",
            "url": "https://example.com/agent",
            "points": 120,
            "num_comments": 45,
            "objectID": "123",
        },
        {
            "title": "Low quality post",
            "url": "https://example.com/low",
            "points": 10,
            "num_comments": 2,
            "objectID": "456",
        },
        {
            "title": "Another good post",
            "url": "",  # Ask HN style, no URL
            "points": 200,
            "num_comments": 80,
            "objectID": "789",
        },
    ]
}


def test_fetch_hacker_news_filters_by_points():
    response = MagicMock()
    response.read.return_value = json.dumps(HN_RESPONSE).encode()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=response):
        items = fetch_hacker_news(min_points=50)

    assert len(items) == 2
    assert items[0].title == "Show HN: An agent framework"
    assert items[0].source_tier == SourceTier.HN
    assert items[0].points == 120


def test_fetch_hacker_news_handles_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        items = fetch_hacker_news()

    assert items == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_sources.py::test_fetch_hacker_news_filters_by_points -x -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/brainstorm/sources.py
"""Source fetchers for the content brainstorm pipeline."""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone

from distill.brainstorm.models import ResearchItem, SourceTier

logger = logging.getLogger(__name__)

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"


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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_sources.py -x -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/sources.py tests/brainstorm/test_sources.py
git commit -m "feat(brainstorm): add HN source fetcher"
```

---

### Task 4: arXiv source fetcher

**Files:**
- Modify: `src/brainstorm/sources.py`
- Test: `tests/brainstorm/test_sources.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/brainstorm/test_sources.py
from distill.brainstorm.sources import fetch_arxiv

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Multi-Agent Coordination via Shared Memory</title>
    <id>http://arxiv.org/abs/2026.12345v1</id>
    <summary>We propose a novel approach to multi-agent coordination.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link href="http://arxiv.org/abs/2026.12345v1" rel="alternate" type="text/html"/>
  </entry>
  <entry>
    <title>Unrelated Biology Paper</title>
    <id>http://arxiv.org/abs/2026.99999v1</id>
    <summary>A study on cell division.</summary>
    <author><name>Carol Bio</name></author>
    <link href="http://arxiv.org/abs/2026.99999v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""


def test_fetch_arxiv_parses_entries():
    response = MagicMock()
    response.read.return_value = ARXIV_XML.encode()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=response):
        items = fetch_arxiv(categories=["cs.AI"])

    assert len(items) == 2
    assert items[0].title == "Multi-Agent Coordination via Shared Memory"
    assert items[0].source_tier == SourceTier.ARXIV
    assert "Alice Smith" in items[0].authors


def test_fetch_arxiv_handles_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        items = fetch_arxiv(categories=["cs.AI"])

    assert items == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_sources.py::test_fetch_arxiv_parses_entries -x -v`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

Add to `src/brainstorm/sources.py`:

```python
import xml.etree.ElementTree as ET

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_sources.py -x -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/sources.py tests/brainstorm/test_sources.py
git commit -m "feat(brainstorm): add arXiv source fetcher"
```

---

### Task 5: Feed + manual link fetchers

**Files:**
- Modify: `src/brainstorm/sources.py`
- Test: `tests/brainstorm/test_sources.py` (append)

**Step 1: Write the failing test**

```python
# Append to tests/brainstorm/test_sources.py
from distill.brainstorm.sources import fetch_followed_feeds, fetch_manual_links


def test_fetch_followed_feeds(tmp_path):
    """Test feed fetching reuses RSSParser logic."""
    from unittest.mock import patch, MagicMock
    from distill.brainstorm.models import SourceTier

    mock_items = [
        ResearchItem(
            title="Simon's Post",
            url="https://simonwillison.net/post1",
            summary="A post about LLMs",
            source_tier=SourceTier.FOLLOWED,
        )
    ]
    with patch("distill.brainstorm.sources._fetch_feed_items", return_value=mock_items):
        items = fetch_followed_feeds(["https://simonwillison.net/atom/everything/"])

    assert len(items) == 1
    assert items[0].source_tier == SourceTier.FOLLOWED


def test_fetch_manual_links():
    mock_items = [
        ResearchItem(
            title="Interesting Article",
            url="https://example.com/article",
            summary="An article summary",
            source_tier=SourceTier.MANUAL,
        )
    ]
    with patch("distill.brainstorm.sources._fetch_url_item", side_effect=mock_items):
        items = fetch_manual_links(["https://example.com/article"])

    assert len(items) == 1
    assert items[0].source_tier == SourceTier.MANUAL


def test_fetch_manual_links_skips_failures():
    with patch("distill.brainstorm.sources._fetch_url_item", side_effect=Exception("fail")):
        items = fetch_manual_links(["https://example.com/bad"])

    assert items == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_sources.py::test_fetch_followed_feeds -x -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `src/brainstorm/sources.py`:

```python
try:
    import feedparser

    _HAS_FEEDPARSER = True
except ImportError:
    feedparser = None  # type: ignore[assignment]
    _HAS_FEEDPARSER = False


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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_sources.py -x -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/sources.py tests/brainstorm/test_sources.py
git commit -m "feat(brainstorm): add feed and manual link fetchers"
```

---

### Task 6: Analyst — pillar scoring + idea generation prompts

**Files:**
- Create: `src/brainstorm/prompts.py`
- Create: `src/brainstorm/analyst.py`
- Test: `tests/brainstorm/test_analyst.py`

**Step 1: Write the failing test**

```python
# tests/brainstorm/test_analyst.py
import json
from unittest.mock import patch

from distill.brainstorm.analyst import analyze_research, score_against_pillars
from distill.brainstorm.models import ContentIdea, ResearchItem, SourceTier


PILLARS = [
    "Building multi-agent systems",
    "AI architecture patterns",
    "Evals and verification",
]


def test_score_against_pillars_matches():
    items = [
        ResearchItem(
            title="Multi-Agent Coordination Framework",
            url="https://example.com/1",
            summary="A framework for coordinating multiple AI agents in production.",
            source_tier=SourceTier.ARXIV,
        ),
        ResearchItem(
            title="Best Pizza in NYC",
            url="https://example.com/2",
            summary="A review of pizza restaurants.",
            source_tier=SourceTier.HN,
        ),
    ]
    scored = score_against_pillars(items, PILLARS)
    # The agent framework clearly matches pillars; pizza does not
    assert len(scored) >= 1
    assert any("agent" in item.title.lower() for item in scored)


def test_analyze_research_returns_ideas():
    """Test full analyst pipeline with mocked LLM call."""
    items = [
        ResearchItem(
            title="New Eval Framework for LLM Agents",
            url="https://arxiv.org/abs/2026.55555",
            summary="A comprehensive evaluation framework.",
            source_tier=SourceTier.ARXIV,
        ),
    ]

    llm_response = json.dumps([
        {
            "title": "Why Your Agent Evals Are Lying to You",
            "angle": "Most eval frameworks test the wrong thing",
            "source_url": "https://arxiv.org/abs/2026.55555",
            "platform": "both",
            "rationale": "Bridges evals and multi-agent pillars",
            "pillars": ["Evals and verification"],
            "tags": ["evals", "agents"],
        }
    ])

    with patch("distill.brainstorm.analyst._call_llm", return_value=llm_response):
        ideas = analyze_research(
            items=items,
            pillars=PILLARS,
            journal_context="Today I worked on agent evaluation.",
            existing_seeds=[],
            published_titles=[],
        )

    assert len(ideas) == 1
    assert ideas[0].title == "Why Your Agent Evals Are Lying to You"
    assert ideas[0].status == "pending"


def test_analyze_research_handles_bad_llm_response():
    items = [
        ResearchItem(
            title="Test",
            url="https://example.com",
            summary="Test",
            source_tier=SourceTier.HN,
        ),
    ]

    with patch("distill.brainstorm.analyst._call_llm", return_value="not json"):
        ideas = analyze_research(
            items=items,
            pillars=PILLARS,
            journal_context="",
            existing_seeds=[],
            published_titles=[],
        )

    assert ideas == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_analyst.py -x -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/brainstorm/prompts.py
"""LLM prompts for the brainstorm analyst."""

from __future__ import annotations


def get_analyst_prompt(
    research_json: str,
    pillars: list[str],
    journal_context: str,
    existing_seeds: list[str],
    published_titles: list[str],
) -> str:
    pillar_list = "\n".join(f"- {p}" for p in pillars)
    seed_list = "\n".join(f"- {s}" for s in existing_seeds[:10]) if existing_seeds else "(none)"
    published_list = "\n".join(f"- {t}" for t in published_titles[:20]) if published_titles else "(none)"

    return f"""You are a content strategist. Given today's research findings and the creator's context, propose 2-3 content ideas.

## Content Pillars (ALL ideas must connect to at least one)
{pillar_list}

## Today's Research Findings
{research_json}

## Creator's Recent Journal
{journal_context[:2000]}

## Existing Seed Ideas (DO NOT duplicate)
{seed_list}

## Already Published (DO NOT re-cover)
{published_list}

## Output Format
Return a JSON array of 2-3 content ideas. Each object:
{{
  "title": "Working title",
  "angle": "The specific hook or argument (1-2 sentences)",
  "source_url": "URL that inspired this idea",
  "platform": "blog" | "social" | "both",
  "rationale": "Why this matters to the audience (1 sentence)",
  "pillars": ["Which content pillar(s) this serves"],
  "tags": ["relevant", "topic", "tags"]
}}

Rules:
- Every idea MUST connect to at least one content pillar
- Prefer ideas that bridge multiple pillars
- Titles should be provocative, not generic
- Angles should be specific and opinionated
- Return ONLY the JSON array, no other text"""
```

```python
# src/brainstorm/analyst.py
"""Analyst logic — scores research and generates content ideas."""

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

    return call_claude(prompt, timeout=120)


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from JSON response."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_analyst.py -x -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/prompts.py src/brainstorm/analyst.py tests/brainstorm/test_analyst.py
git commit -m "feat(brainstorm): add analyst with pillar scoring and LLM idea generation"
```

---

### Task 7: Editor — publish to seeds + Ghost + calendar file

**Files:**
- Create: `src/brainstorm/publisher.py`
- Test: `tests/brainstorm/test_publisher.py`

**Step 1: Write the failing test**

```python
# tests/brainstorm/test_publisher.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from distill.brainstorm.models import ContentIdea, ContentCalendar
from distill.brainstorm.publisher import publish_calendar


def _make_ideas() -> list[ContentIdea]:
    return [
        ContentIdea(
            title="Why Your Agent Evals Are Lying",
            angle="Most eval frameworks test the wrong thing",
            source_url="https://arxiv.org/abs/2026.55555",
            platform="both",
            rationale="Bridges evals and agents",
            pillars=["Evals and verification"],
            tags=["evals", "agents"],
        ),
        ContentIdea(
            title="The 3 Patterns Every AI Architect Needs",
            angle="Lessons from building production agent systems",
            source_url="https://example.com/patterns",
            platform="social",
            rationale="Architecture content",
            pillars=["AI architecture patterns"],
            tags=["architecture"],
        ),
    ]


def test_publish_saves_calendar_json(tmp_path):
    ideas = _make_ideas()
    publish_calendar(
        ideas=ideas,
        date="2026-02-17",
        output_dir=tmp_path,
        create_seeds=False,
        create_ghost_drafts=False,
    )
    cal_path = tmp_path / "content-calendar" / "2026-02-17.json"
    assert cal_path.exists()
    data = json.loads(cal_path.read_text())
    assert len(data["ideas"]) == 2


def test_publish_saves_calendar_markdown(tmp_path):
    ideas = _make_ideas()
    publish_calendar(
        ideas=ideas,
        date="2026-02-17",
        output_dir=tmp_path,
        create_seeds=False,
        create_ghost_drafts=False,
    )
    md_path = tmp_path / "content-calendar" / "2026-02-17.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "Agent Evals" in content
    assert "AI Architect" in content


def test_publish_creates_seeds(tmp_path):
    ideas = _make_ideas()
    seeds_path = tmp_path / ".distill-seeds.json"
    seeds_path.write_text('{"seeds": []}')

    with patch("distill.brainstorm.publisher.SeedStore") as MockStore:
        mock_instance = MagicMock()
        MockStore.return_value = mock_instance

        publish_calendar(
            ideas=ideas,
            date="2026-02-17",
            output_dir=tmp_path,
            create_seeds=True,
            create_ghost_drafts=False,
        )

    assert mock_instance.add.call_count == 2


def test_publish_creates_ghost_drafts(tmp_path):
    ideas = _make_ideas()
    # Only "both" and "blog" platform ideas go to Ghost
    blog_ideas = [i for i in ideas if i.platform in ("blog", "both")]

    with patch("distill.brainstorm.publisher.GhostAPIClient") as MockGhost:
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "ghost-123"}
        MockGhost.return_value = mock_client

        with patch("distill.brainstorm.publisher.GhostConfig.from_env") as mock_env:
            mock_env.return_value = MagicMock(is_configured=True)

            publish_calendar(
                ideas=ideas,
                date="2026-02-17",
                output_dir=tmp_path,
                create_seeds=False,
                create_ghost_drafts=True,
            )

    # Only 1 idea has platform "both" (blog-eligible)
    assert mock_client.create_post.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/brainstorm/test_publisher.py -x -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/brainstorm/publisher.py
"""Publisher — outputs content ideas to seeds, Ghost, and calendar files."""

from __future__ import annotations

import logging
from pathlib import Path

from distill.brainstorm.models import (
    ContentCalendar,
    ContentIdea,
    save_calendar,
)

logger = logging.getLogger(__name__)


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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/brainstorm/test_publisher.py -x -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/brainstorm/publisher.py tests/brainstorm/test_publisher.py
git commit -m "feat(brainstorm): add publisher for seeds, Ghost drafts, and calendar files"
```

---

### Task 8: TroopX workflow definition + agent descriptions

**Files:**
- Create: `.troopx/workflows/content-brainstorm.yaml`
- Create: `.troopx/agents/researcher.yaml`
- Create: `.troopx/agents/analyst.yaml`
- Create: `.troopx/agents/editor.yaml`

**Step 1: Create workflow and agent definitions**

Use `mcp__agent-router__create_agent` and `mcp__agent-router__create_workflow` to register:

```yaml
# Researcher agent
name: brainstorm-researcher
description: |
  You are a research agent for the distill content pipeline.

  Your job: Fetch content from 3 source tiers and write findings to the blackboard.

  Steps:
  1. Read .distill.toml for brainstorm config (followed_people, manual_links, arxiv_categories, hn_min_points)
  2. Call fetch_hacker_news() from distill.brainstorm.sources
  3. Call fetch_arxiv() from distill.brainstorm.sources
  4. Call fetch_followed_feeds() from distill.brainstorm.sources
  5. Call fetch_manual_links() from distill.brainstorm.sources
  6. Write each result set to blackboard (namespace=research, keys: hn-findings, arxiv-findings, followed-findings, manual-findings)
  7. Signal 'done'
capabilities: [research]

# Analyst agent
name: brainstorm-analyst
description: |
  You are a content analyst for the distill content pipeline.

  Your job: Read research findings from the blackboard, cross-reference with journal and existing content, and propose 2-3 content ideas.

  Steps:
  1. Read blackboard namespace=research (all findings from researcher)
  2. Read recent journal entries from insights/journal/ (last 3 days)
  3. Read unused seeds from .distill-seeds.json
  4. Read content pillars from .distill.toml [brainstorm] pillars
  5. Check BlogMemory for already-published titles
  6. Call analyze_research() from distill.brainstorm.analyst
  7. Write ideas to blackboard (namespace=content-ideas, key=daily-calendar)
  8. Signal 'done'
capabilities: [research, code]

# Editor agent
name: brainstorm-editor
description: |
  You are a content editor for the distill content pipeline.

  Your job: Take content ideas from the blackboard and publish to seeds, Ghost drafts, and calendar files.

  Steps:
  1. Read blackboard namespace=content-ideas, key=daily-calendar
  2. Call publish_calendar() from distill.brainstorm.publisher
  3. Write summary to blackboard (namespace=results, key=calendar-summary)
  4. Signal 'done'
capabilities: [code]
```

```yaml
# Workflow definition
workflow: content-brainstorm
agents:
  - name: brainstorm-researcher
    role: researcher
  - name: brainstorm-analyst
    role: analyst
  - name: brainstorm-editor
    role: editor
states:
  - name: research
    agent: brainstorm-researcher
    on_signal:
      done: analyze
      blocked: research
  - name: analyze
    agent: brainstorm-analyst
    on_signal:
      done: publish
      blocked: analyze
  - name: publish
    agent: brainstorm-editor
    on_signal:
      done: complete
```

**Step 2: Register via agent-router MCP**

Run the `mcp__agent-router__create_agent` and `mcp__agent-router__create_workflow` tools to register these definitions.

**Step 3: Commit**

```bash
git add .troopx/
git commit -m "feat(brainstorm): add TroopX workflow and agent definitions"
```

---

### Task 9: CLI command — `distill brainstorm`

**Files:**
- Modify: `src/cli.py` (add brainstorm command)
- Test: `tests/test_cli.py` (append brainstorm CLI test)

**Step 1: Write the failing test**

```python
# Append to tests/test_cli.py or create tests/test_cli_brainstorm.py
from click.testing import CliRunner
from unittest.mock import patch


def test_brainstorm_command_exists():
    from distill.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["brainstorm", "--help"])
    assert result.exit_code == 0
    assert "brainstorm" in result.output.lower()


def test_brainstorm_command_runs(tmp_path):
    from distill.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    with patch("distill.brainstorm.sources.fetch_hacker_news", return_value=[]), \
         patch("distill.brainstorm.sources.fetch_arxiv", return_value=[]), \
         patch("distill.brainstorm.sources.fetch_followed_feeds", return_value=[]), \
         patch("distill.brainstorm.sources.fetch_manual_links", return_value=[]):
        result = runner.invoke(app, ["brainstorm", "--output", str(tmp_path)])
    assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_brainstorm.py -x -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `src/cli.py`:

```python
@app.command()
def brainstorm(
    output: Path = typer.Option(Path("./insights"), help="Output directory"),
) -> None:
    """Brainstorm daily content ideas from research sources."""
    from datetime import datetime, timezone
    from distill.config import load_config
    from distill.brainstorm.sources import (
        fetch_hacker_news,
        fetch_arxiv,
        fetch_followed_feeds,
        fetch_manual_links,
    )
    from distill.brainstorm.analyst import analyze_research, score_against_pillars
    from distill.brainstorm.publisher import publish_calendar

    config = load_config()
    bc = config.brainstorm
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    typer.echo(f"Brainstorming content ideas for {today}...")

    # Gather
    items = []
    items.extend(fetch_hacker_news(min_points=bc.hn_min_points))
    items.extend(fetch_arxiv(categories=bc.arxiv_categories))
    items.extend(fetch_followed_feeds(bc.followed_people))
    items.extend(fetch_manual_links(bc.manual_links))

    typer.echo(f"Found {len(items)} research items")

    if not items:
        typer.echo("No research items found, skipping analysis.")
        return

    # Pre-filter
    relevant = score_against_pillars(items, bc.pillars) if bc.pillars else items
    typer.echo(f"{len(relevant)} items match content pillars")

    # Read journal context
    journal_context = ""
    journal_dir = output / "journal"
    if journal_dir.exists():
        recent = sorted(journal_dir.glob("*.md"), reverse=True)[:3]
        journal_context = "\n---\n".join(
            f.read_text(encoding="utf-8")[:1000] for f in recent
        )

    # Analyze
    ideas = analyze_research(
        items=relevant,
        pillars=bc.pillars,
        journal_context=journal_context,
        existing_seeds=[],
        published_titles=[],
    )

    if not ideas:
        typer.echo("No content ideas generated.")
        return

    # Publish
    calendar = publish_calendar(
        ideas=ideas,
        date=today,
        output_dir=output,
    )

    typer.echo(f"Published {len(calendar.ideas)} content ideas:")
    for idea in calendar.ideas:
        typer.echo(f"  - {idea.title} ({idea.platform})")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_brainstorm.py -x -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/cli.py tests/test_cli_brainstorm.py
git commit -m "feat(brainstorm): add 'distill brainstorm' CLI command"
```

---

### Task 10: Dashboard — content calendar API route

**Files:**
- Create: `web/server/routes/calendar.ts`
- Modify: `web/server/index.ts` (register route)
- Test: `web/server/__tests__/calendar.test.ts`

**Step 1: Write the failing test**

```typescript
// web/server/__tests__/calendar.test.ts
import { describe, test, expect, beforeAll } from "bun:test";
import { Hono } from "hono";
import calendarApp from "../routes/calendar";
import { setConfig } from "../lib/config";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const FIXTURE_DIR = join(import.meta.dir, "fixtures", "calendar-test");

beforeAll(async () => {
  setConfig({ OUTPUT_DIR: FIXTURE_DIR, PORT: 3001 });
  const calDir = join(FIXTURE_DIR, "content-calendar");
  await mkdir(calDir, { recursive: true });
  await writeFile(
    join(calDir, "2026-02-17.json"),
    JSON.stringify({
      date: "2026-02-17",
      ideas: [
        {
          title: "Test Idea",
          angle: "Test angle",
          source_url: "https://example.com",
          platform: "blog",
          rationale: "Test reason",
          pillars: ["AI architecture patterns"],
          tags: ["test"],
          status: "pending",
          ghost_post_id: null,
        },
      ],
    }),
  );
});

const app = new Hono().route("/", calendarApp);

describe("GET /api/calendar", () => {
  test("returns calendar list", async () => {
    const res = await app.request("/api/calendar");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.calendars.length).toBeGreaterThanOrEqual(1);
  });
});

describe("GET /api/calendar/:date", () => {
  test("returns specific calendar", async () => {
    const res = await app.request("/api/calendar/2026-02-17");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.date).toBe("2026-02-17");
    expect(data.ideas.length).toBe(1);
  });

  test("returns 404 for missing date", async () => {
    const res = await app.request("/api/calendar/2099-01-01");
    expect(res.status).toBe(404);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd web && bun test server/__tests__/calendar.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```typescript
// web/server/routes/calendar.ts
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import { getConfig } from "../lib/config";

const app = new Hono();

app.get("/api/calendar", async (c) => {
  const { OUTPUT_DIR } = getConfig();
  const calDir = join(OUTPUT_DIR, "content-calendar");

  try {
    const files = await readdir(calDir);
    const calendars = files
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(".json", ""))
      .sort()
      .reverse();
    return c.json({ calendars });
  } catch {
    return c.json({ calendars: [] });
  }
});

app.get("/api/calendar/:date", async (c) => {
  const { OUTPUT_DIR } = getConfig();
  const date = c.req.param("date");
  const filePath = join(OUTPUT_DIR, "content-calendar", `${date}.json`);

  try {
    const content = await readFile(filePath, "utf-8");
    return c.json(JSON.parse(content));
  } catch {
    return c.json({ error: "Calendar not found" }, 404);
  }
});

export default app;
```

Register in `web/server/index.ts`:
```typescript
import calendarRoutes from "./routes/calendar";
// ... existing route registrations ...
app.route("/", calendarRoutes);
```

**Step 4: Run test to verify it passes**

Run: `cd web && bun test server/__tests__/calendar.test.ts`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add web/server/routes/calendar.ts web/server/__tests__/calendar.test.ts web/server/index.ts
git commit -m "feat(brainstorm): add content calendar API route"
```

---

### Task 11: Dashboard — content calendar frontend page

**Files:**
- Create: `web/src/routes/calendar.tsx`
- Modify: `web/src/components/layout/Sidebar.tsx` (add nav link)
- Modify: `web/shared/schemas.ts` (add Zod schemas)

**Step 1: Add Zod schemas**

```typescript
// Append to web/shared/schemas.ts
export const ContentIdeaSchema = z.object({
  title: z.string(),
  angle: z.string(),
  source_url: z.string(),
  platform: z.string(),
  rationale: z.string(),
  pillars: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  status: z.string().default("pending"),
  ghost_post_id: z.string().nullable().default(null),
});

export const ContentCalendarSchema = z.object({
  date: z.string(),
  ideas: z.array(ContentIdeaSchema).default([]),
});

export type ContentIdea = z.infer<typeof ContentIdeaSchema>;
export type ContentCalendar = z.infer<typeof ContentCalendarSchema>;
```

**Step 2: Create the page component**

```typescript
// web/src/routes/calendar.tsx
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import type { ContentCalendar, ContentIdea } from "../../shared/schemas";

export const Route = createFileRoute("/calendar")({
  component: CalendarPage,
  loader: async () => {
    const res = await fetch("/api/calendar");
    const data = await res.json();
    return data as { calendars: string[] };
  },
});

function CalendarPage() {
  const { calendars } = Route.useLoaderData();
  const [selectedDate, setSelectedDate] = useState<string>(calendars[0] ?? "");
  const [calendar, setCalendar] = useState<ContentCalendar | null>(null);

  const loadCalendar = async (date: string) => {
    setSelectedDate(date);
    const res = await fetch(`/api/calendar/${date}`);
    if (res.ok) {
      setCalendar(await res.json());
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Content Calendar</h1>

      <div className="flex gap-2 mb-6 flex-wrap">
        {calendars.map((date) => (
          <button
            key={date}
            onClick={() => loadCalendar(date)}
            className={`px-3 py-1 rounded text-sm ${
              selectedDate === date
                ? "bg-blue-600 text-white"
                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }`}
          >
            {date}
          </button>
        ))}
      </div>

      {calendar && (
        <div className="space-y-4">
          {calendar.ideas.map((idea, i) => (
            <IdeaCard key={i} idea={idea} />
          ))}
        </div>
      )}
    </div>
  );
}

function IdeaCard({ idea }: { idea: ContentIdea }) {
  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold">{idea.title}</h2>
        <span
          className={`text-xs px-2 py-1 rounded ${
            idea.platform === "blog"
              ? "bg-purple-100 text-purple-700"
              : idea.platform === "social"
                ? "bg-green-100 text-green-700"
                : "bg-blue-100 text-blue-700"
          }`}
        >
          {idea.platform}
        </span>
      </div>
      <p className="text-gray-700 mb-2">{idea.angle}</p>
      <p className="text-sm text-gray-500 mb-3">{idea.rationale}</p>
      <div className="flex gap-2 flex-wrap">
        {idea.pillars.map((p) => (
          <span key={p} className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded">
            {p}
          </span>
        ))}
        {idea.tags.map((t) => (
          <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
            {t}
          </span>
        ))}
      </div>
      <a
        href={idea.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-blue-500 hover:underline mt-2 block"
      >
        Source
      </a>
    </div>
  );
}
```

**Step 3: Add sidebar nav link**

Add to `Sidebar.tsx` nav items:
```typescript
{ to: "/calendar", label: "Calendar", icon: "📅" },
```

**Step 4: Build and verify**

Run: `cd web && bun run build`
Expected: Build succeeds with 0 TypeScript errors

**Step 5: Commit**

```bash
git add web/src/routes/calendar.tsx web/shared/schemas.ts web/src/components/layout/Sidebar.tsx
git commit -m "feat(brainstorm): add content calendar dashboard page"
```

---

### Task 12: Integration test — full brainstorm pipeline

**Files:**
- Create: `tests/brainstorm/test_integration.py`

**Step 1: Write integration test**

```python
# tests/brainstorm/test_integration.py
"""Integration test: full brainstorm pipeline with mocked sources."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from distill.brainstorm.models import ResearchItem, SourceTier, load_calendar
from distill.brainstorm.sources import fetch_hacker_news
from distill.brainstorm.analyst import analyze_research
from distill.brainstorm.publisher import publish_calendar


def test_full_pipeline(tmp_path):
    """End-to-end: gather → analyze → publish."""
    # 1. Mock research items
    items = [
        ResearchItem(
            title="Multi-Agent Eval Framework",
            url="https://arxiv.org/abs/2026.12345",
            summary="A framework for evaluating multi-agent systems",
            source_tier=SourceTier.ARXIV,
            authors=["Alice"],
        ),
        ResearchItem(
            title="Building AI Teams That Actually Work",
            url="https://simonwillison.net/2026/teams",
            summary="Lessons from deploying agent teams",
            source_tier=SourceTier.FOLLOWED,
        ),
    ]

    pillars = [
        "Building multi-agent systems",
        "Evals and verification",
    ]

    # 2. Mock LLM response
    llm_response = json.dumps([
        {
            "title": "Your Agent Team Is Only as Good as Your Evals",
            "angle": "Why eval-first development matters for multi-agent systems",
            "source_url": "https://arxiv.org/abs/2026.12345",
            "platform": "both",
            "rationale": "Bridges the two most important pillars",
            "pillars": ["Building multi-agent systems", "Evals and verification"],
            "tags": ["agents", "evals", "testing"],
        },
    ])

    # 3. Analyze
    with patch("distill.brainstorm.analyst._call_llm", return_value=llm_response):
        ideas = analyze_research(
            items=items,
            pillars=pillars,
            journal_context="Today I worked on agent coordination.",
            existing_seeds=[],
            published_titles=[],
        )

    assert len(ideas) == 1

    # 4. Publish (no Ghost, no seeds — just calendar files)
    calendar = publish_calendar(
        ideas=ideas,
        date="2026-02-17",
        output_dir=tmp_path,
        create_seeds=False,
        create_ghost_drafts=False,
    )

    # 5. Verify outputs
    assert (tmp_path / "content-calendar" / "2026-02-17.json").exists()
    assert (tmp_path / "content-calendar" / "2026-02-17.md").exists()

    loaded = load_calendar("2026-02-17", tmp_path)
    assert loaded is not None
    assert len(loaded.ideas) == 1
    assert loaded.ideas[0].title == "Your Agent Team Is Only as Good as Your Evals"
    assert "Evals and verification" in loaded.ideas[0].pillars
```

**Step 2: Run test**

Run: `uv run pytest tests/brainstorm/test_integration.py -x -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -x -q --ignore=tests/test_verify_all_kpis.py`
Expected: All tests pass, 92%+ coverage

**Step 4: Commit**

```bash
git add tests/brainstorm/test_integration.py
git commit -m "feat(brainstorm): add integration test for full pipeline"
```

---

## Summary

| Task | Component | New Tests |
|------|-----------|-----------|
| 1 | BrainstormConfig + TOML | 4 |
| 2 | Data models (ContentIdea, ContentCalendar) | 6 |
| 3 | HN source fetcher | 2 |
| 4 | arXiv source fetcher | 2 |
| 5 | Feed + manual link fetchers | 3 |
| 6 | Analyst (pillar scoring + LLM ideas) | 3 |
| 7 | Publisher (seeds + Ghost + calendar) | 4 |
| 8 | TroopX workflow + agent definitions | 0 (config) |
| 9 | CLI `distill brainstorm` command | 2 |
| 10 | Dashboard API route | 3 |
| 11 | Dashboard frontend page | 0 (build check) |
| 12 | Integration test | 1 |
| **Total** | | **~30 tests** |
