import json
from unittest.mock import patch, MagicMock

from distill.brainstorm.models import ResearchItem, SourceTier
from distill.brainstorm.sources import (
    fetch_hacker_news,
    fetch_arxiv,
    fetch_followed_feeds,
    fetch_manual_links,
)


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
            "url": "",
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


def test_fetch_followed_feeds():
    mock_items = [
        ResearchItem(
            title="Simon's Post",
            url="https://simonwillison.net/post1",
            summary="A post about LLMs",
            source_tier=SourceTier.FOLLOWED,
        )
    ]
    with patch("distill.brainstorm.services._fetch_feed_items", return_value=mock_items):
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
    with patch("distill.brainstorm.services._fetch_url_item", side_effect=mock_items):
        items = fetch_manual_links(["https://example.com/article"])

    assert len(items) == 1
    assert items[0].source_tier == SourceTier.MANUAL


def test_fetch_manual_links_skips_failures():
    with patch("distill.brainstorm.services._fetch_url_item", side_effect=Exception("fail")):
        items = fetch_manual_links(["https://example.com/bad"])
    assert items == []
