"""Tests for Ghost CMS API client and live publishing."""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest

from distill.blog.config import GhostConfig
from distill.blog.context import WeeklyBlogContext
from distill.blog.publishers import create_publisher
from distill.blog.publishers.ghost import GhostAPIClient, GhostPublisher
from distill.blog.reader import JournalEntry


# ── GhostConfig ──────────────────────────────────────────────────────────

class TestGhostConfig:
    def test_is_configured_when_both_set(self):
        cfg = GhostConfig(url="https://blog.example.com", admin_api_key="abc:def123")
        assert cfg.is_configured is True

    def test_not_configured_when_url_missing(self):
        cfg = GhostConfig(admin_api_key="abc:def123")
        assert cfg.is_configured is False

    def test_not_configured_when_key_missing(self):
        cfg = GhostConfig(url="https://blog.example.com")
        assert cfg.is_configured is False

    def test_not_configured_default(self):
        cfg = GhostConfig()
        assert cfg.is_configured is False

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("GHOST_URL", "https://env.ghost.io")
        monkeypatch.setenv("GHOST_ADMIN_API_KEY", "id1:aabbcc")
        monkeypatch.setenv("GHOST_NEWSLETTER_SLUG", "weekly-digest")
        cfg = GhostConfig.from_env()
        assert cfg.url == "https://env.ghost.io"
        assert cfg.admin_api_key == "id1:aabbcc"
        assert cfg.newsletter_slug == "weekly-digest"
        assert cfg.is_configured is True

    def test_from_env_empty(self, monkeypatch):
        monkeypatch.delenv("GHOST_URL", raising=False)
        monkeypatch.delenv("GHOST_ADMIN_API_KEY", raising=False)
        monkeypatch.delenv("GHOST_NEWSLETTER_SLUG", raising=False)
        cfg = GhostConfig.from_env()
        assert cfg.is_configured is False


# ── GhostAPIClient ──────────────────────────────────────────────────────

# Use a known hex secret for deterministic JWT testing
_TEST_KEY_ID = "testkey123"
_TEST_SECRET_HEX = "aabbccdd" * 4  # 16 bytes hex
_TEST_CONFIG = GhostConfig(
    url="https://blog.example.com",
    admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
)


class TestGhostAPIClientJWT:
    def test_generate_token_is_valid_jwt(self):
        client = GhostAPIClient(_TEST_CONFIG)
        token = client._generate_token()
        # Decode and verify
        decoded = jwt.decode(
            token,
            bytes.fromhex(_TEST_SECRET_HEX),
            algorithms=["HS256"],
            audience="/admin/",
        )
        assert decoded["aud"] == "/admin/"
        assert "iat" in decoded
        assert "exp" in decoded
        assert decoded["exp"] - decoded["iat"] == 300  # 5 minutes

    def test_generate_token_has_kid_header(self):
        client = GhostAPIClient(_TEST_CONFIG)
        token = client._generate_token()
        header = jwt.get_unverified_header(token)
        assert header["kid"] == _TEST_KEY_ID
        assert header["alg"] == "HS256"

    def test_generate_token_deterministic_with_fixed_time(self):
        client = GhostAPIClient(_TEST_CONFIG)
        fixed_time = 1700000000
        with patch("distill.blog.publishers.ghost.time") as mock_time:
            mock_time.time.return_value = fixed_time
            token = client._generate_token()

        decoded = jwt.decode(
            token,
            bytes.fromhex(_TEST_SECRET_HEX),
            algorithms=["HS256"],
            audience="/admin/",
            options={"verify_exp": False},
        )
        assert decoded["iat"] == fixed_time
        assert decoded["exp"] == fixed_time + 300


class TestGhostAPIClientRequests:
    def test_create_post_request_format(self):
        client = GhostAPIClient(_TEST_CONFIG)
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "posts": [{"id": "post-1", "title": "Test", "status": "draft"}]
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = client.create_post("Test Post", "# Hello", ["blog", "test"], "draft")

        assert result["id"] == "post-1"
        # Verify the request was made correctly
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://blog.example.com/ghost/api/admin/posts/"
        assert req.method == "POST"
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("Authorization").startswith("Ghost ")
        body = json.loads(req.data)
        assert body["posts"][0]["title"] == "Test Post"
        # Content should be in mobiledoc format with markdown card
        mobiledoc = json.loads(body["posts"][0]["mobiledoc"])
        assert mobiledoc["cards"][0][0] == "markdown"
        assert mobiledoc["cards"][0][1]["markdown"] == "# Hello"
        assert body["posts"][0]["status"] == "draft"
        assert body["posts"][0]["tags"] == [{"name": "blog"}, {"name": "test"}]

    def test_create_post_without_tags(self):
        client = GhostAPIClient(_TEST_CONFIG)
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "posts": [{"id": "post-2", "title": "No Tags"}]
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = client.create_post("No Tags Post", "Content")

        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert "tags" not in body["posts"][0]
        # Should use mobiledoc, not html
        assert "mobiledoc" in body["posts"][0]
        assert "html" not in body["posts"][0]

    def test_publish_with_newsletter(self):
        client = GhostAPIClient(_TEST_CONFIG)
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "posts": [{"id": "post-1", "status": "published"}]
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = client.publish_with_newsletter("post-1", "default-newsletter")

        assert result["status"] == "published"
        req = mock_urlopen.call_args[0][0]
        assert "/posts/post-1/?newsletter=default-newsletter" in req.full_url
        assert req.method == "PUT"
        body = json.loads(req.data)
        assert body["posts"][0]["status"] == "published"


# ── GhostPublisher integration ──────────────────────────────────────────

def _make_weekly_context() -> WeeklyBlogContext:
    return WeeklyBlogContext(
        year=2026,
        week=6,
        week_start=date(2026, 2, 2),
        week_end=date(2026, 2, 8),
        entries=[
            JournalEntry(
                date=date(2026, 2, 3),
                prose="Monday.",
                file_path=Path("journal/journal-2026-02-03-dev-journal.md"),
            ),
        ],
        total_sessions=5,
        total_duration_minutes=100,
        projects=["distill"],
        all_tags=["python", "ghost"],
        combined_prose="All prose.",
    )


class TestGhostPublisherFileOnly:
    """Tests for file-only mode (no API credentials)."""

    def test_format_weekly_without_config(self):
        pub = GhostPublisher()
        result = pub.format_weekly(_make_weekly_context(), "Blog prose.")
        assert "<!-- ghost-meta:" in result
        assert "Blog prose." in result

    def test_format_weekly_with_unconfigured_config(self):
        cfg = GhostConfig()  # empty, not configured
        pub = GhostPublisher(ghost_config=cfg)
        result = pub.format_weekly(_make_weekly_context(), "Prose.")
        assert "<!-- ghost-meta:" in result
        # No API call should happen

    def test_no_api_client_when_unconfigured(self):
        pub = GhostPublisher()
        assert pub._api is None

    def test_no_api_client_with_empty_config(self):
        pub = GhostPublisher(ghost_config=GhostConfig())
        assert pub._api is None


class TestGhostPublisherWithAPI:
    """Tests for live API publishing."""

    def test_api_client_created_when_configured(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
        )
        pub = GhostPublisher(ghost_config=cfg)
        assert pub._api is not None

    def test_format_weekly_publishes_to_api(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
        )
        pub = GhostPublisher(ghost_config=cfg)

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "posts": [{"id": "post-1", "title": "Test", "status": "published"}]
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = pub.format_weekly(_make_weekly_context(), "Blog prose.")

        assert "<!-- ghost-meta:" in result
        assert "Blog prose." in result

    def test_newsletter_two_step_flow(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
            newsletter_slug="my-newsletter",
        )
        pub = GhostPublisher(ghost_config=cfg)

        # Mock create_post and publish_with_newsletter
        pub._api = MagicMock()
        pub._api.create_post.return_value = {"id": "post-1", "status": "draft"}
        pub._api.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}

        result = pub.format_weekly(_make_weekly_context(), "Blog prose.")

        pub._api.create_post.assert_called_once()
        # Verify draft status: check positional or keyword args
        args, kwargs = pub._api.create_post.call_args
        status = kwargs.get("status", args[3] if len(args) > 3 else None)
        assert status == "draft"

        pub._api.publish_with_newsletter.assert_called_once_with("post-1", "my-newsletter")

    def test_auto_publish_without_newsletter(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
            auto_publish=True,
        )
        pub = GhostPublisher(ghost_config=cfg)
        pub._api = MagicMock()
        pub._api.create_post.return_value = {"id": "post-1", "status": "published"}

        pub.format_weekly(_make_weekly_context(), "Prose.")

        args, kwargs = pub._api.create_post.call_args
        status = kwargs.get("status", args[3] if len(args) > 3 else None)
        assert status == "published"

    def test_draft_without_newsletter(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
            auto_publish=False,
        )
        pub = GhostPublisher(ghost_config=cfg)
        pub._api = MagicMock()
        pub._api.create_post.return_value = {"id": "post-1", "status": "draft"}

        pub.format_weekly(_make_weekly_context(), "Prose.")

        args, kwargs = pub._api.create_post.call_args
        status = kwargs.get("status", args[3] if len(args) > 3 else None)
        assert status == "draft"

    def test_api_failure_still_returns_content(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
        )
        pub = GhostPublisher(ghost_config=cfg)
        pub._api = MagicMock()
        pub._api.create_post.side_effect = Exception("Connection refused")

        # Should not raise, just log warning and return content
        result = pub.format_weekly(_make_weekly_context(), "Blog prose.")
        assert "Blog prose." in result


class TestGhostPublisherMetaParsing:
    def test_parse_ghost_meta(self):
        pub = GhostPublisher()
        content = '<!-- ghost-meta: {"title": "Test", "tags": ["a"]} -->\n\nBody'
        meta = pub._parse_ghost_meta(content)
        assert meta["title"] == "Test"
        assert meta["tags"] == ["a"]

    def test_parse_ghost_meta_missing(self):
        pub = GhostPublisher()
        assert pub._parse_ghost_meta("No meta here") == {}


# ── Factory integration ─────────────────────────────────────────────────

class TestCreatePublisherWithGhostConfig:
    def test_ghost_publisher_gets_config(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
        )
        pub = create_publisher("ghost", ghost_config=cfg)
        assert isinstance(pub, GhostPublisher)
        assert pub._api is not None

    def test_ghost_publisher_without_config(self):
        pub = create_publisher("ghost")
        assert isinstance(pub, GhostPublisher)
        assert pub._api is None

    def test_non_ghost_ignores_config(self):
        cfg = GhostConfig(
            url="https://blog.example.com",
            admin_api_key=f"{_TEST_KEY_ID}:{_TEST_SECRET_HEX}",
        )
        pub = create_publisher("obsidian", ghost_config=cfg)
        # ObsidianPublisher should work fine, ghost_config is ignored
        assert not isinstance(pub, GhostPublisher)
