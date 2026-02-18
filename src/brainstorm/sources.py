"""Backward-compat shim -- re-exports source fetchers from services."""
from distill.brainstorm.services import (  # noqa: F401
    _fetch_feed_items,
    _fetch_url_item,
    fetch_arxiv,
    fetch_followed_feeds,
    fetch_hacker_news,
    fetch_manual_links,
)
