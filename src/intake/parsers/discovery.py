"""Discovery parser — active web search for topics & people.

Uses the Anthropic API with server-side web_search tool.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from distill.intake.models import ContentItem, ContentSource, ContentType
from distill.intake.parsers.base import ContentParser
from distill.shared.llm import (
    _HAS_ANTHROPIC,
    LLMError,
    call_claude_with_tools,
    strip_json_fences,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a research assistant that searches the web for recent, high-quality content.

For each query, use WebSearch to find recent articles, blog posts, and announcements.
Then use WebFetch on the most promising URLs to get details.

Return ONLY a JSON array (no markdown fences, no explanation) with up to {max_results} items:
[
  {{
    "title": "Article title",
    "url": "https://...",
    "author": "Author name or empty string",
    "summary": "2-3 sentence summary of the content",
    "published_date": "YYYY-MM-DD or empty string",
    "tags": ["tag1", "tag2"]
  }}
]

Rules:
- Only include content from the last {max_age_days} days
- Prefer primary sources over aggregators
- Skip paywalled content, social media posts, and press releases
- Each item must have a valid URL
- Return an empty array [] if nothing relevant is found
"""


class DiscoveryParser(ContentParser):
    """Searches the web for configured topics and people using the Agent SDK."""

    @property
    def source(self) -> ContentSource:
        return ContentSource.DISCOVERY

    @property
    def is_configured(self) -> bool:
        return _HAS_ANTHROPIC and self._config.discovery.is_configured

    def _build_queries(self) -> list[tuple[str, str]]:
        """Build (query_text, category) pairs from config."""
        queries: list[tuple[str, str]] = []
        for topic in self._config.discovery.topics:
            queries.append((f"latest news and articles about: {topic}", "topic"))
        for person in self._config.discovery.people:
            queries.append(
                (f"recent blog posts, talks, or articles by or about: {person}", "person")
            )
        return queries

    def parse(self, since: datetime | None = None) -> list[ContentItem]:
        """Search the web for each configured topic/person.

        Args:
            since: Only return items published after this time.
                   Defaults to max_age_days from config.

        Returns:
            Deduplicated list of ContentItem objects.
        """
        cfg = self._config.discovery
        if not self.is_configured:
            return []

        if since is None:
            since = datetime.now(tz=UTC) - timedelta(days=cfg.max_age_days)
        elif since.tzinfo is None:
            since = since.replace(tzinfo=UTC)

        system = _SYSTEM_PROMPT.format(
            max_results=cfg.max_results_per_query,
            max_age_days=cfg.max_age_days,
        )

        seen_urls: set[str] = set()
        items: list[ContentItem] = []

        for query_text, category in self._build_queries():
            try:
                raw = call_claude_with_tools(
                    system,
                    query_text,
                    allowed_tools=["WebSearch", "WebFetch"],
                    model="haiku",
                    label=f"discovery-{category}",
                )
                parsed = json.loads(strip_json_fences(raw))
                if not isinstance(parsed, list):
                    logger.warning("Discovery query returned non-list: %s", query_text)
                    continue

                for entry in parsed:
                    url = entry.get("url", "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    item_id = hashlib.sha256(url.encode()).hexdigest()[:16]
                    pub_date = self._parse_date(entry.get("published_date", ""))

                    if pub_date and pub_date < since:
                        continue

                    items.append(
                        ContentItem(
                            id=item_id,
                            url=url,
                            title=entry.get("title", ""),
                            excerpt=entry.get("summary", ""),
                            author=entry.get("author", ""),
                            source=ContentSource.DISCOVERY,
                            content_type=ContentType.ARTICLE,
                            tags=entry.get("tags", []),
                            published_at=pub_date,
                            metadata={"discovery_query": query_text, "category": category},
                        )
                    )

            except (LLMError, json.JSONDecodeError) as exc:
                logger.warning("Discovery query failed (%s): %s", query_text, exc)
                continue
            except Exception as exc:
                logger.warning("Unexpected error in discovery query (%s): %s", query_text, exc)
                continue

        logger.info("Discovery parser found %d items from %d queries", len(items), len(seen_urls))
        return items

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Try to parse a YYYY-MM-DD date string."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
