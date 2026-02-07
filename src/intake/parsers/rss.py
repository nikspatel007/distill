"""RSS/Atom feed parser."""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from calendar import timegm
from datetime import datetime, timezone
from pathlib import Path

import feedparser

from distill.intake.config import IntakeConfig
from distill.intake.models import ContentItem, ContentSource, ContentType
from distill.intake.parsers.base import ContentParser

logger = logging.getLogger(__name__)


class RSSParser(ContentParser):
    """Parses RSS and Atom feeds into ContentItem objects."""

    @property
    def source(self) -> ContentSource:
        return ContentSource.RSS

    @property
    def is_configured(self) -> bool:
        return self._config.rss.is_configured

    def parse(self, since: datetime | None = None) -> list[ContentItem]:
        """Fetch and parse all configured RSS feeds.

        Args:
            since: Only return entries published after this time.

        Returns:
            List of ContentItem objects from all feeds.
        """
        feed_urls = self._resolve_feed_urls()
        if not feed_urls:
            logger.warning("No RSS feed URLs configured")
            return []

        items: list[ContentItem] = []
        for url in feed_urls:
            try:
                feed_items = self._parse_feed(url, since=since)
                items.extend(feed_items)
            except Exception:
                logger.warning("Failed to parse feed: %s", url, exc_info=True)

        logger.info("Parsed %d items from %d RSS feeds", len(items), len(feed_urls))
        return items

    def _resolve_feed_urls(self) -> list[str]:
        """Collect feed URLs from all configured sources."""
        urls: list[str] = list(self._config.rss.feeds)

        if self._config.rss.feeds_file:
            urls.extend(self._read_feeds_file(self._config.rss.feeds_file))

        if self._config.rss.opml_file:
            urls.extend(self._read_opml(self._config.rss.opml_file))

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for url in urls:
            normalized = url.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)

        return unique

    def _parse_feed(
        self, url: str, *, since: datetime | None = None
    ) -> list[ContentItem]:
        """Parse a single RSS/Atom feed URL."""
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("Feed error for %s: %s", url, feed.bozo_exception)
            return []

        site_name = feed.feed.get("title", "")
        items: list[ContentItem] = []
        max_items = self._config.rss.max_items_per_feed

        for entry in feed.entries[:max_items]:
            item = self._entry_to_item(entry, site_name=site_name, feed_url=url)
            if item is None:
                continue
            if since and item.published_at and item.published_at < since:
                continue
            if item.word_count < self._config.min_word_count:
                continue
            items.append(item)

        return items

    def _entry_to_item(
        self,
        entry: feedparser.FeedParserDict,
        *,
        site_name: str = "",
        feed_url: str = "",
    ) -> ContentItem | None:
        """Convert a feedparser entry to a ContentItem."""
        link = entry.get("link", "")
        title = entry.get("title", "")

        if not link and not title:
            return None

        # Extract body from content or summary
        body = self._extract_body(entry)
        excerpt = entry.get("summary", "")
        if excerpt == body:
            excerpt = body[:300] + "..." if len(body) > 300 else body

        # Parse published date
        published_at = self._parse_date(entry)

        # Generate stable ID from URL or title
        id_source = link or title
        item_id = hashlib.sha256(id_source.encode()).hexdigest()[:16]

        author = entry.get("author", "")
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        word_count = len(body.split()) if body else 0

        return ContentItem(
            id=item_id,
            url=link,
            title=title,
            body=body,
            excerpt=excerpt,
            word_count=word_count,
            author=author,
            site_name=site_name,
            source=ContentSource.RSS,
            source_id=entry.get("id", link),
            content_type=ContentType.ARTICLE,
            tags=tags,
            published_at=published_at,
            metadata={"feed_url": feed_url},
        )

    @staticmethod
    def _extract_body(entry: feedparser.FeedParserDict) -> str:
        """Extract the best available body text from a feed entry."""
        # Prefer full content over summary
        content_list = entry.get("content", [])
        if content_list:
            # Pick the longest content block (often HTML)
            best = max(content_list, key=lambda c: len(c.get("value", "")))
            return _strip_html(best.get("value", ""))

        summary = entry.get("summary", "")
        if summary:
            return _strip_html(summary)

        return ""

    @staticmethod
    def _parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
        """Parse the published date from a feed entry."""
        for field in ("published_parsed", "updated_parsed"):
            time_struct = entry.get(field)
            if time_struct:
                try:
                    return datetime.fromtimestamp(
                        timegm(time_struct), tz=timezone.utc
                    )
                except (ValueError, OverflowError):
                    continue
        return None

    @staticmethod
    def _read_feeds_file(path: str) -> list[str]:
        """Read feed URLs from a newline-delimited text file."""
        feeds_path = Path(path).expanduser()
        if not feeds_path.exists():
            logger.warning("Feeds file not found: %s", path)
            return []

        lines = feeds_path.read_text(encoding="utf-8").splitlines()
        return [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

    @staticmethod
    def _read_opml(path: str) -> list[str]:
        """Extract feed URLs from an OPML file."""
        opml_path = Path(path).expanduser()
        if not opml_path.exists():
            logger.warning("OPML file not found: %s", path)
            return []

        try:
            tree = ET.parse(opml_path)  # noqa: S314
        except ET.ParseError:
            logger.warning("Failed to parse OPML file: %s", path, exc_info=True)
            return []

        urls: list[str] = []
        for outline in tree.iter("outline"):
            xml_url = outline.get("xmlUrl", "")
            if xml_url:
                urls.append(xml_url)

        return urls


def _strip_html(html: str) -> str:
    """Rough HTML tag stripping for feed content."""
    import re

    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
