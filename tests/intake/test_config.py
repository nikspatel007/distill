"""Tests for intake configuration."""

from __future__ import annotations

from distill.intake.config import (
    BrowserIntakeConfig,
    GmailIntakeConfig,
    IntakeConfig,
    LinkedInIntakeConfig,
    RedditIntakeConfig,
    RSSConfig,
)


class TestRSSConfig:
    def test_not_configured_empty(self):
        cfg = RSSConfig()
        assert cfg.is_configured is False

    def test_configured_with_feeds(self):
        cfg = RSSConfig(feeds=["https://example.com/feed"])
        assert cfg.is_configured is True

    def test_configured_with_opml(self):
        cfg = RSSConfig(opml_file="~/feeds.opml")
        assert cfg.is_configured is True

    def test_configured_with_feeds_file(self):
        cfg = RSSConfig(feeds_file="~/feeds.txt")
        assert cfg.is_configured is True

    def test_defaults(self):
        cfg = RSSConfig()
        assert cfg.fetch_timeout == 30
        assert cfg.max_items_per_feed == 50
        assert cfg.extract_full_text is False


class TestRedditIntakeConfig:
    def test_not_configured(self):
        cfg = RedditIntakeConfig()
        assert cfg.is_configured is False

    def test_configured(self):
        cfg = RedditIntakeConfig(client_id="id", client_secret="secret")
        assert cfg.is_configured is True

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "rid")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "rsec")
        monkeypatch.setenv("REDDIT_USERNAME", "user")
        monkeypatch.setenv("REDDIT_PASSWORD", "pass")
        cfg = RedditIntakeConfig.from_env()
        assert cfg.client_id == "rid"
        assert cfg.client_secret == "rsec"
        assert cfg.is_configured is True

    def test_from_env_empty(self, monkeypatch):
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        cfg = RedditIntakeConfig.from_env()
        assert cfg.is_configured is False


class TestGmailIntakeConfig:
    def test_not_configured(self):
        assert GmailIntakeConfig().is_configured is False

    def test_configured(self):
        cfg = GmailIntakeConfig(credentials_file="creds.json")
        assert cfg.is_configured is True


class TestBrowserIntakeConfig:
    def test_always_configured(self):
        assert BrowserIntakeConfig().is_configured is True


class TestLinkedInIntakeConfig:
    def test_not_configured(self):
        assert LinkedInIntakeConfig().is_configured is False

    def test_configured(self):
        cfg = LinkedInIntakeConfig(export_path="/tmp/linkedin.zip")
        assert cfg.is_configured is True


class TestIntakeConfig:
    def test_defaults(self):
        cfg = IntakeConfig()
        assert cfg.model is None
        assert cfg.claude_timeout == 180
        assert cfg.target_word_count == 800
        assert cfg.min_word_count == 50

    def test_nested_configs(self):
        cfg = IntakeConfig(
            rss=RSSConfig(feeds=["https://example.com/feed"]),
            model="claude-haiku-4-5-20251001",
        )
        assert cfg.rss.is_configured is True
        assert cfg.model == "claude-haiku-4-5-20251001"
