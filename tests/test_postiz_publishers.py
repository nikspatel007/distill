"""Tests for Postiz blog and intake publishers."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from distill.blog.publishers.postiz import PostizBlogPublisher
from distill.intake.publishers.postiz import PostizIntakePublisher
from distill.integrations.postiz import PostizConfig, PostizIntegration


class TestPostizBlogPublisher:
    def test_requires_llm(self):
        pub = PostizBlogPublisher()
        assert pub.requires_llm is True

    def test_weekly_output_path(self):
        pub = PostizBlogPublisher()
        path = pub.weekly_output_path(Path("/out"), 2026, 6)
        assert path == Path("/out/blog/postiz/weekly-2026-W06.md")

    def test_thematic_output_path(self):
        pub = PostizBlogPublisher()
        path = pub.thematic_output_path(Path("/out"), "content-pipeline")
        assert path == Path("/out/blog/postiz/content-pipeline.md")

    def test_index_path(self):
        pub = PostizBlogPublisher()
        path = pub.index_path(Path("/out"))
        assert path == Path("/out/blog/postiz/index.md")

    def test_format_index_returns_empty(self):
        pub = PostizBlogPublisher()
        result = pub.format_index(Path("/out"), MagicMock())
        assert result == ""

    def test_format_weekly_not_configured(self):
        """When Postiz is not configured, returns raw prose."""
        config = PostizConfig(url="", api_key="")
        pub = PostizBlogPublisher(postiz_config=config)
        result = pub.format_weekly(MagicMock(), "My weekly post")
        assert result == "My weekly post"

    def test_format_thematic_not_configured(self):
        config = PostizConfig(url="", api_key="")
        pub = PostizBlogPublisher(postiz_config=config)
        result = pub.format_thematic(MagicMock(), "My thematic post")
        assert result == "My thematic post"

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_format_weekly_pushes_draft(self, mock_client_cls, mock_resolve):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_resolve.return_value = {"twitter": ["int-1"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        synthesizer = MagicMock()
        synthesizer.adapt_for_platform.return_value = "Adapted tweet"

        pub = PostizBlogPublisher(
            synthesizer=synthesizer,
            postiz_config=config,
            target_platforms=["twitter"],
        )
        context = MagicMock()
        context.editorial_notes = ""
        result = pub.format_weekly(context, "Weekly prose")

        synthesizer.adapt_for_platform.assert_called_once_with(
            "Weekly prose", "twitter", "weekly", editorial_hint=""
        )
        mock_client.create_post.assert_called_once_with(
            "Adapted tweet", ["int-1"], post_type="draft", scheduled_at=None, images=[]
        )
        assert "twitter" in result
        assert "Adapted tweet" in result

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_format_thematic_pushes_draft(self, mock_client_cls, mock_resolve):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"linkedin": ["int-2"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["linkedin"])
        result = pub.format_thematic(MagicMock(), "Thematic prose")

        mock_client.create_post.assert_called_once()
        assert "linkedin" in result

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_adapt_fallback_on_error(self, mock_client_cls, mock_resolve):
        """When adapt_for_platform fails, raw prose is used."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"twitter": ["int-1"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        synthesizer = MagicMock()
        synthesizer.adapt_for_platform.side_effect = RuntimeError("LLM failure")

        pub = PostizBlogPublisher(
            synthesizer=synthesizer,
            postiz_config=config,
            target_platforms=["twitter"],
        )
        result = pub.format_weekly(MagicMock(), "Raw prose")

        # Should still push the raw prose
        mock_client.create_post.assert_called_once()
        assert "Raw prose" in result

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_create_post_failure_marked(self, mock_client_cls, mock_resolve):
        """When create_post fails, result marks the platform as FAILED."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.side_effect = RuntimeError("API down")
        mock_resolve.return_value = {"twitter": ["int-1"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["twitter"])
        result = pub.format_weekly(MagicMock(), "Post text")

        assert "FAILED" in result

    @patch("distill.integrations.postiz.PostizClient")
    def test_connection_failure_returns_prose(self, mock_client_cls):
        """When Postiz connection fails entirely, returns raw prose."""
        mock_client_cls.side_effect = RuntimeError("Connection refused")

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizBlogPublisher(postiz_config=config)
        result = pub.format_weekly(MagicMock(), "My prose")

        assert result == "My prose"

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_no_synthesizer_uses_raw_prose(self, mock_client_cls, mock_resolve):
        """Without a synthesizer, raw prose is pushed directly."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"twitter": ["int-1"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["twitter"])
        result = pub.format_weekly(MagicMock(), "Direct prose")

        # create_post should receive the raw prose
        call_args = mock_client.create_post.call_args
        assert call_args[0][0] == "Direct prose"

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_schedule_mode_weekly(self, mock_client_cls, mock_resolve):
        """When schedule_enabled, create_post uses 'schedule' with scheduled_at."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"slack": ["int-1"]}

        config = PostizConfig(
            url="https://postiz.test",
            api_key="key",
            schedule_enabled=True,
        )
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["slack"])
        result = pub.format_weekly(MagicMock(), "Scheduled weekly")

        call_args = mock_client.create_post.call_args
        assert call_args[1]["post_type"] == "schedule"
        assert call_args[1]["scheduled_at"] is not None
        assert "Scheduled for" in result

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_schedule_mode_thematic(self, mock_client_cls, mock_resolve):
        """Thematic posts get scheduled on thematic days."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"slack": ["int-1"]}

        config = PostizConfig(
            url="https://postiz.test",
            api_key="key",
            schedule_enabled=True,
        )
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["slack"])
        result = pub.format_thematic(MagicMock(), "Scheduled thematic")

        call_args = mock_client.create_post.call_args
        assert call_args[1]["post_type"] == "schedule"
        assert call_args[1]["scheduled_at"] is not None

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_draft_mode_no_scheduled_at(self, mock_client_cls, mock_resolve):
        """When schedule_enabled=False, no scheduled_at is passed."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"slack": ["int-1"]}

        config = PostizConfig(
            url="https://postiz.test",
            api_key="key",
            schedule_enabled=False,
        )
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["slack"])
        pub.format_weekly(MagicMock(), "Draft post")

        call_args = mock_client.create_post.call_args
        assert call_args[1]["post_type"] == "draft"
        assert call_args[1]["scheduled_at"] is None


class TestAppendBlogLink:
    """Tests for PostizBlogPublisher._append_blog_link static method."""

    def test_appends_read_more_for_linkedin(self):
        result = PostizBlogPublisher._append_blog_link(
            "My LinkedIn post", "linkedin", "https://blog.example.com/post"
        )
        assert result.endswith("\n\nRead the full post: https://blog.example.com/post")

    def test_appends_url_to_last_tweet_in_thread(self):
        thread = "First tweet\n---\nSecond tweet\n---\nLast tweet"
        result = PostizBlogPublisher._append_blog_link(
            thread, "x", "https://blog.example.com/post"
        )
        assert "https://blog.example.com/post" in result
        # URL should be in the last segment
        parts = result.rsplit("\n---\n", 1)
        assert "blog.example.com" in parts[-1]

    def test_appends_url_for_single_tweet(self):
        result = PostizBlogPublisher._append_blog_link(
            "Single tweet", "twitter", "https://blog.example.com/post"
        )
        assert result == "Single tweet\n\nhttps://blog.example.com/post"

    def test_no_url_returns_original(self):
        result = PostizBlogPublisher._append_blog_link("Content", "linkedin", None)
        assert result == "Content"

    def test_empty_url_returns_original(self):
        result = PostizBlogPublisher._append_blog_link("Content", "linkedin", "")
        assert result == "Content"

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_blog_url_included_in_push(self, mock_client_cls, mock_resolve):
        """When blog_url is provided, it's included in the adapted content."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_resolve.return_value = {"linkedin": ["int-1"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["linkedin"])
        result = pub.format_weekly(
            MagicMock(), "Weekly prose", blog_url="https://blog.example.com/w07"
        )

        # The blog URL should appear in the result
        assert "https://blog.example.com/w07" in result
        # The content pushed to create_post should contain the URL
        call_content = mock_client.create_post.call_args[0][0]
        assert "blog.example.com" in call_content

    @patch("distill.integrations.mapping.resolve_integration_ids")
    @patch("distill.integrations.postiz.PostizClient")
    def test_feature_image_passed_to_api(self, mock_client_cls, mock_resolve):
        """When feature_image_url is provided, it's passed as images to create_post."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_resolve.return_value = {"linkedin": ["int-1"]}

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizBlogPublisher(postiz_config=config, target_platforms=["linkedin"])
        pub.format_weekly(
            MagicMock(),
            "Weekly prose",
            feature_image_url="https://ghost.example.com/image.png",
        )

        call_kwargs = mock_client.create_post.call_args[1]
        assert call_kwargs["images"] == ["https://ghost.example.com/image.png"]


class TestPostizIntakePublisher:
    def test_daily_output_path(self):
        pub = PostizIntakePublisher()
        path = pub.daily_output_path(Path("/out"), date(2026, 2, 8))
        assert path == Path("/out/intake/postiz/digest-2026-02-08.md")

    def test_format_daily_not_configured(self):
        """When Postiz is not configured, returns raw prose."""
        config = PostizConfig(url="", api_key="")
        pub = PostizIntakePublisher(postiz_config=config)
        result = pub.format_daily(MagicMock(), "Daily digest")
        assert result == "Daily digest"

    @patch("distill.integrations.postiz.PostizClient")
    def test_format_daily_pushes_draft(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.list_integrations.return_value = [
            PostizIntegration(id="int-1", name="Slack", provider="slack"),
        ]

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizIntakePublisher(postiz_config=config)
        result = pub.format_daily(MagicMock(), "Digest content")

        mock_client.create_post.assert_called_once()
        call_args = mock_client.create_post.call_args
        assert call_args[0][0] == "Digest content"
        assert call_args[1]["post_type"] == "draft"
        assert call_args[1]["scheduled_at"] is None
        assert result == "Digest content"

    @patch("distill.integrations.postiz.PostizClient")
    def test_format_daily_no_integrations(self, mock_client_cls):
        """When no integrations found, doesn't call create_post."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_integrations.return_value = []

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizIntakePublisher(postiz_config=config)
        result = pub.format_daily(MagicMock(), "Digest content")

        mock_client.create_post.assert_not_called()
        assert result == "Digest content"

    @patch("distill.integrations.postiz.PostizClient")
    def test_format_daily_api_error(self, mock_client_cls):
        """When the API fails, returns prose without raising."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_integrations.return_value = [
            PostizIntegration(id="int-1", name="Slack", provider="slack"),
        ]
        mock_client.create_post.side_effect = RuntimeError("API error")

        config = PostizConfig(url="https://postiz.test", api_key="key")
        pub = PostizIntakePublisher(postiz_config=config)
        result = pub.format_daily(MagicMock(), "Digest content")

        assert result == "Digest content"

    @patch("distill.integrations.postiz.PostizClient")
    def test_format_daily_schedule_mode(self, mock_client_cls):
        """When schedule_enabled, intake uses next_intake_slot."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_post.return_value = {}
        mock_client.list_integrations.return_value = [
            PostizIntegration(id="int-1", name="Slack", provider="slack"),
        ]

        config = PostizConfig(
            url="https://postiz.test",
            api_key="key",
            schedule_enabled=True,
        )
        pub = PostizIntakePublisher(postiz_config=config)
        result = pub.format_daily(MagicMock(), "Digest")

        call_args = mock_client.create_post.call_args
        assert call_args[1]["post_type"] == "schedule"
        assert call_args[1]["scheduled_at"] is not None
        assert result == "Digest"

    def test_format_daily_uses_env_config(self, monkeypatch):
        """When no config passed, falls back to PostizConfig.from_env()."""
        monkeypatch.delenv("POSTIZ_URL", raising=False)
        monkeypatch.delenv("POSTIZ_API_KEY", raising=False)
        pub = PostizIntakePublisher()
        result = pub.format_daily(MagicMock(), "Content")
        assert result == "Content"  # Not configured, returns as-is


class TestPublisherFactoryIntegration:
    def test_create_blog_publisher_postiz(self):
        from distill.blog.publishers import create_publisher

        config = PostizConfig(url="https://postiz.test", api_key="key", schedule_enabled=True)
        pub = create_publisher("postiz", postiz_config=config)
        assert isinstance(pub, PostizBlogPublisher)
        assert pub._postiz_config is config

    def test_create_blog_publisher_postiz_no_config(self):
        from distill.blog.publishers import create_publisher

        pub = create_publisher("postiz")
        assert isinstance(pub, PostizBlogPublisher)

    def test_create_intake_publisher_postiz(self):
        from distill.intake.publishers import create_intake_publisher

        pub = create_intake_publisher("postiz")
        assert isinstance(pub, PostizIntakePublisher)
