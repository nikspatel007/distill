"""Tests for discovery parser — active web search for topics & people."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from distill.intake.models import (
    ContentSource,
    DiscoveryIntakeConfig,
    IntakeConfig,
)
from distill.intake.parsers.discovery import DiscoveryParser


def _make_config(
    topics: list[str] | None = None,
    people: list[str] | None = None,
    max_results: int = 5,
    max_age_days: int = 3,
) -> IntakeConfig:
    return IntakeConfig(
        discovery=DiscoveryIntakeConfig(
            topics=topics or [],
            people=people or [],
            max_results_per_query=max_results,
            max_age_days=max_age_days,
        ),
    )


def _sample_response(items: list[dict[str, object]] | None = None) -> str:
    """Build a JSON response string."""
    if items is None:
        items = [
            {
                "title": "Test Article",
                "url": "https://example.com/article-1",
                "author": "Alice",
                "summary": "An interesting article.",
                "published_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
                "tags": ["ai", "agents"],
            }
        ]
    return json.dumps(items)


# ── is_configured ──────────────────────────────────────────────────────


class TestIsConfigured:
    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    def test_configured_with_topics(self):
        parser = DiscoveryParser(config=_make_config(topics=["AI agents"]))
        assert parser.is_configured is True

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    def test_configured_with_people(self):
        parser = DiscoveryParser(config=_make_config(people=["Simon Willison"]))
        assert parser.is_configured is True

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    def test_not_configured_empty(self):
        parser = DiscoveryParser(config=_make_config())
        assert parser.is_configured is False

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", False)
    def test_not_configured_without_anthropic(self):
        parser = DiscoveryParser(config=_make_config(topics=["AI agents"]))
        assert parser.is_configured is False


# ── source property ────────────────────────────────────────────────────


class TestSource:
    def test_source_is_discovery(self):
        parser = DiscoveryParser(config=_make_config())
        assert parser.source == ContentSource.DISCOVERY


# ── _build_queries ─────────────────────────────────────────────────────


class TestBuildQueries:
    def test_topics_and_people(self):
        parser = DiscoveryParser(
            config=_make_config(topics=["AI agents"], people=["Karpathy"])
        )
        queries = parser._build_queries()
        assert len(queries) == 2
        assert queries[0][1] == "topic"
        assert queries[1][1] == "person"
        assert "AI agents" in queries[0][0]
        assert "Karpathy" in queries[1][0]

    def test_empty_config(self):
        parser = DiscoveryParser(config=_make_config())
        assert parser._build_queries() == []


# ── parse ──────────────────────────────────────────────────────────────


class TestParse:
    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_basic_parse(self, mock_call):
        mock_call.return_value = _sample_response()
        parser = DiscoveryParser(config=_make_config(topics=["AI agents"]))

        items = parser.parse()

        assert len(items) == 1
        assert items[0].title == "Test Article"
        assert items[0].url == "https://example.com/article-1"
        assert items[0].source == ContentSource.DISCOVERY
        assert items[0].author == "Alice"
        assert "ai" in items[0].tags
        mock_call.assert_called_once()

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_url_dedup_across_queries(self, mock_call):
        """Same URL from two different queries should only appear once."""
        response = _sample_response()
        mock_call.return_value = response

        parser = DiscoveryParser(
            config=_make_config(topics=["topic1", "topic2"])
        )
        items = parser.parse()

        assert mock_call.call_count == 2
        assert len(items) == 1  # deduped

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_distinct_urls_kept(self, mock_call):
        """Different URLs from different queries should all be kept."""
        responses = [
            _sample_response([{
                "title": "Article 1",
                "url": "https://example.com/a1",
                "author": "",
                "summary": "First.",
                "published_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
                "tags": [],
            }]),
            _sample_response([{
                "title": "Article 2",
                "url": "https://example.com/a2",
                "author": "",
                "summary": "Second.",
                "published_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
                "tags": [],
            }]),
        ]
        mock_call.side_effect = responses

        parser = DiscoveryParser(
            config=_make_config(topics=["topic1", "topic2"])
        )
        items = parser.parse()

        assert len(items) == 2

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_graceful_failure_per_query(self, mock_call):
        """One failing query should not kill the rest."""
        from distill.shared.llm import LLMError

        mock_call.side_effect = [
            LLMError("timeout"),
            _sample_response([{
                "title": "Good Article",
                "url": "https://example.com/good",
                "author": "",
                "summary": "OK.",
                "published_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
                "tags": [],
            }]),
        ]

        parser = DiscoveryParser(
            config=_make_config(topics=["fail-topic", "ok-topic"])
        )
        items = parser.parse()

        assert len(items) == 1
        assert items[0].title == "Good Article"

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_json_fence_stripping(self, mock_call):
        """Response wrapped in ```json fences should still parse."""
        raw = '```json\n' + _sample_response() + '\n```'
        mock_call.return_value = raw

        parser = DiscoveryParser(config=_make_config(topics=["AI"]))
        items = parser.parse()

        assert len(items) == 1

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_skips_empty_urls(self, mock_call):
        mock_call.return_value = _sample_response([{
            "title": "No URL",
            "url": "",
            "author": "",
            "summary": "Missing URL.",
            "published_date": "",
            "tags": [],
        }])

        parser = DiscoveryParser(config=_make_config(topics=["test"]))
        items = parser.parse()

        assert len(items) == 0

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_filters_old_articles(self, mock_call):
        """Articles older than max_age_days should be filtered out."""
        old_date = (datetime.now(tz=UTC) - timedelta(days=10)).strftime("%Y-%m-%d")
        mock_call.return_value = _sample_response([{
            "title": "Old Article",
            "url": "https://example.com/old",
            "author": "",
            "summary": "Ancient.",
            "published_date": old_date,
            "tags": [],
        }])

        parser = DiscoveryParser(config=_make_config(topics=["test"], max_age_days=3))
        items = parser.parse()

        assert len(items) == 0

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_keeps_items_without_date(self, mock_call):
        """Items with no published_date should be kept (can't filter)."""
        mock_call.return_value = _sample_response([{
            "title": "No Date",
            "url": "https://example.com/nodate",
            "author": "",
            "summary": "No date info.",
            "published_date": "",
            "tags": [],
        }])

        parser = DiscoveryParser(config=_make_config(topics=["test"]))
        items = parser.parse()

        assert len(items) == 1

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", False)
    def test_returns_empty_when_not_configured(self):
        parser = DiscoveryParser(config=_make_config(topics=["AI"]))
        assert parser.parse() == []

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_non_list_response_skipped(self, mock_call):
        """A non-list JSON response should be skipped gracefully."""
        mock_call.return_value = '{"error": "not a list"}'

        parser = DiscoveryParser(config=_make_config(topics=["test"]))
        items = parser.parse()

        assert len(items) == 0

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_metadata_includes_query_info(self, mock_call):
        mock_call.return_value = _sample_response()

        parser = DiscoveryParser(config=_make_config(topics=["AI agents"]))
        items = parser.parse()

        assert items[0].metadata["category"] == "topic"
        assert "AI agents" in items[0].metadata["discovery_query"]

    @patch("distill.intake.parsers.discovery._HAS_ANTHROPIC", True)
    @patch("distill.intake.parsers.discovery.call_claude_with_tools")
    def test_item_id_is_url_hash(self, mock_call):
        """Item ID should be derived from URL hash."""
        import hashlib

        mock_call.return_value = _sample_response()

        parser = DiscoveryParser(config=_make_config(topics=["test"]))
        items = parser.parse()

        expected = hashlib.sha256(b"https://example.com/article-1").hexdigest()[:16]
        assert items[0].id == expected


# ── _parse_date ────────────────────────────────────────────────────────


class TestParseDate:
    def test_valid_date(self):
        result = DiscoveryParser._parse_date("2026-03-01")
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1

    def test_empty_string(self):
        assert DiscoveryParser._parse_date("") is None

    def test_invalid_format(self):
        assert DiscoveryParser._parse_date("March 1, 2026") is None
