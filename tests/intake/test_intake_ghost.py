"""Tests for Ghost CMS intake publisher."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.blog.config import GhostConfig
from distill.intake.context import DailyIntakeContext
from distill.intake.publishers.ghost import GhostIntakePublisher


def _ctx(**overrides) -> DailyIntakeContext:
    defaults = dict(
        date=date(2026, 2, 7),
        total_items=5,
        total_word_count=1500,
        sources=["rss"],
        sites=["Blog A", "Blog B"],
        all_tags=["python", "ai", "llm", "tools", "rag"],
        combined_text="Combined text here.",
    )
    defaults.update(overrides)
    return DailyIntakeContext(**defaults)


def _configured_ghost() -> GhostConfig:
    return GhostConfig(
        url="https://ghost.example.com",
        admin_api_key="abc123:deadbeef",
        newsletter_slug="weekly-digest",
        auto_publish=True,
    )


def _unconfigured_ghost() -> GhostConfig:
    return GhostConfig(url="", admin_api_key="")


# ------------------------------------------------------------------
# Output path tests
# ------------------------------------------------------------------


class TestDailyOutputPath:
    def test_output_path_structure(self):
        pub = GhostIntakePublisher()
        path = pub.daily_output_path(Path("/out"), date(2026, 2, 7))
        assert path == Path("/out/intake/ghost/ghost-2026-02-07.md")

    def test_output_path_different_date(self):
        pub = GhostIntakePublisher()
        path = pub.daily_output_path(Path("/insights"), date(2025, 12, 31))
        assert path == Path("/insights/intake/ghost/ghost-2025-12-31.md")


# ------------------------------------------------------------------
# Ghost-meta comment generation
# ------------------------------------------------------------------


class TestFormatDailyMeta:
    def test_ghost_meta_comment_present(self):
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(), "Some prose.")
        assert "<!-- ghost-meta:" in result
        assert "-->" in result

    def test_ghost_meta_contains_title(self):
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        meta = _extract_meta(result)
        assert meta["title"] == "Daily Digest \u2014 February 7, 2026"

    def test_ghost_meta_contains_date(self):
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        meta = _extract_meta(result)
        assert meta["date"] == "2026-02-07"

    def test_ghost_meta_contains_tags(self):
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        meta = _extract_meta(result)
        assert meta["tags"] == ["python", "ai", "llm", "tools", "rag"]

    def test_ghost_meta_tags_limited_to_10(self):
        many_tags = [f"tag{i}" for i in range(20)]
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(all_tags=many_tags), "Prose.")
        meta = _extract_meta(result)
        assert len(meta["tags"]) == 10

    def test_ghost_meta_status_is_draft(self):
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(), "Prose.")
        meta = _extract_meta(result)
        assert meta["status"] == "draft"

    def test_prose_included_after_meta(self):
        pub = GhostIntakePublisher()
        result = pub.format_daily(_ctx(), "The actual digest content.")
        # Prose appears after the meta comment
        meta_end = result.index("-->")
        prose_start = result.index("The actual digest content.")
        assert prose_start > meta_end


# ------------------------------------------------------------------
# File-only mode
# ------------------------------------------------------------------


class TestFileOnlyMode:
    def test_none_config_produces_content(self):
        """When ghost_config is None, format_daily still returns content."""
        pub = GhostIntakePublisher(ghost_config=None)
        result = pub.format_daily(_ctx(), "Digest prose.")
        assert "<!-- ghost-meta:" in result
        assert "Digest prose." in result

    def test_unconfigured_config_produces_content(self):
        """When ghost_config is present but not configured, still returns content."""
        pub = GhostIntakePublisher(ghost_config=_unconfigured_ghost())
        result = pub.format_daily(_ctx(), "Digest prose.")
        assert "<!-- ghost-meta:" in result
        assert "Digest prose." in result

    def test_none_config_no_api_client(self):
        pub = GhostIntakePublisher(ghost_config=None)
        assert pub._api is None

    def test_unconfigured_config_no_api_client(self):
        pub = GhostIntakePublisher(ghost_config=_unconfigured_ghost())
        assert pub._api is None


# ------------------------------------------------------------------
# API publishing (mocked)
# ------------------------------------------------------------------


class TestAPIPublishing:
    @patch("distill.intake.publishers.ghost.GhostIntakePublisher._publish_to_api")
    def test_publish_called_when_configured(self, mock_publish):
        """When configured, _publish_to_api is called during format_daily."""
        pub = GhostIntakePublisher.__new__(GhostIntakePublisher)
        pub._config = _configured_ghost()
        pub._api = MagicMock()
        mock_publish.return_value = {"id": "post-1"}

        pub.format_daily(_ctx(), "Prose.")
        mock_publish.assert_called_once()

    @patch("distill.blog.publishers.ghost.GhostAPIClient")
    def test_api_create_post_called(self, MockClient):
        """API client's create_post is invoked with correct arguments."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "abc"}
        mock_client.publish_with_newsletter.return_value = {"id": "abc", "status": "published"}
        MockClient.return_value = mock_client

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config)
        pub._api = mock_client

        pub.format_daily(_ctx(), "Prose content.")

        mock_client.create_post.assert_called_once()
        call_args = mock_client.create_post.call_args
        assert "Daily Digest" in call_args[0][0] or "Daily Digest" in str(call_args)

    @patch("distill.blog.publishers.ghost.GhostAPIClient")
    def test_newsletter_publish_flow(self, MockClient):
        """With newsletter_slug, uses the two-step draft -> publish flow."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-99"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-99", "status": "published"}
        MockClient.return_value = mock_client

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config)
        pub._api = mock_client

        pub.format_daily(_ctx(), "Content.")

        mock_client.create_post.assert_called_once()
        mock_client.publish_with_newsletter.assert_called_once_with("post-99", "weekly-digest")

    @patch("distill.blog.publishers.ghost.GhostAPIClient")
    def test_auto_publish_without_newsletter(self, MockClient):
        """Without newsletter_slug, creates post directly with configured status."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        MockClient.return_value = mock_client

        config = GhostConfig(
            url="https://ghost.example.com",
            admin_api_key="abc123:deadbeef",
            newsletter_slug="",
            auto_publish=True,
        )
        pub = GhostIntakePublisher(ghost_config=config)
        pub._api = mock_client

        pub.format_daily(_ctx(), "Content.")

        mock_client.create_post.assert_called_once()
        call_kwargs = mock_client.create_post.call_args
        # status should be "published" since auto_publish=True
        assert call_kwargs[1]["status"] == "published" or call_kwargs[0][3] == "published"


# ------------------------------------------------------------------
# Graceful API error handling
# ------------------------------------------------------------------


class TestAPIErrorHandling:
    @patch("distill.blog.publishers.ghost.GhostAPIClient")
    def test_api_error_caught_gracefully(self, MockClient):
        """API exceptions are caught and logged; content is still returned."""
        mock_client = MagicMock()
        mock_client.create_post.side_effect = ConnectionError("Ghost unreachable")
        MockClient.return_value = mock_client

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config)
        pub._api = mock_client

        # Should NOT raise
        result = pub.format_daily(_ctx(), "My digest.")
        assert "<!-- ghost-meta:" in result
        assert "My digest." in result

    @patch("distill.blog.publishers.ghost.GhostAPIClient")
    def test_api_error_returns_none(self, MockClient):
        """_publish_to_api returns None on error."""
        mock_client = MagicMock()
        mock_client.create_post.side_effect = RuntimeError("boom")
        MockClient.return_value = mock_client

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config)
        pub._api = mock_client

        content = pub.format_daily(_ctx(), "Prose.")
        # Manually call _publish_to_api to verify return
        api_result = pub._publish_to_api(content)
        assert api_result is None


# ------------------------------------------------------------------
# Image upload and feature_image tests
# ------------------------------------------------------------------


class TestImageUpload:
    """Tests for uploading local images to Ghost and setting feature_image."""

    def test_images_uploaded_and_replaced_in_prose(self, tmp_path):
        """Image markdown refs are replaced with CDN URLs after upload."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}
        mock_client.upload_image.return_value = "https://cdn.ghost.io/images/hero.png"

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        # Create a local image file
        img_dir = tmp_path / "intake" / "images"
        img_dir.mkdir(parents=True)
        (img_dir / "2026-02-14-hero.png").write_bytes(b"fake-png")

        prose = "# My Digest\n\n![hero](images/2026-02-14-hero.png)\n\nSome text."
        pub.format_daily(_ctx(), prose)

        # upload_image should have been called with the local path
        mock_client.upload_image.assert_called_once_with(
            tmp_path / "intake" / "images" / "2026-02-14-hero.png"
        )

        # create_post should have the CDN URL in prose, not the local path
        call_args = mock_client.create_post.call_args
        sent_prose = call_args[0][1]
        assert "https://cdn.ghost.io/images/hero.png" in sent_prose
        assert "images/2026-02-14-hero.png" not in sent_prose

    def test_feature_image_set_from_first_image(self, tmp_path):
        """feature_image kwarg is set to the first uploaded image URL."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}
        mock_client.upload_image.side_effect = [
            "https://cdn.ghost.io/images/first.png",
            "https://cdn.ghost.io/images/second.png",
        ]

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        img_dir = tmp_path / "intake" / "images"
        img_dir.mkdir(parents=True)
        (img_dir / "first.png").write_bytes(b"fake")
        (img_dir / "second.png").write_bytes(b"fake")

        prose = "![a](images/first.png)\n![b](images/second.png)"
        pub.format_daily(_ctx(), prose)

        # feature_image should be the first image
        call_kwargs = mock_client.create_post.call_args[1]
        assert call_kwargs["feature_image"] == "https://cdn.ghost.io/images/first.png"

    def test_upload_failure_leaves_local_path(self, tmp_path):
        """When upload_image returns None, the local path stays in prose."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}
        mock_client.upload_image.return_value = None

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        img_dir = tmp_path / "intake" / "images"
        img_dir.mkdir(parents=True)
        (img_dir / "hero.png").write_bytes(b"fake")

        prose = "![alt](images/hero.png)\nMore text."
        pub.format_daily(_ctx(), prose)

        # The local path should remain since upload failed
        call_args = mock_client.create_post.call_args
        sent_prose = call_args[0][1]
        assert "images/hero.png" in sent_prose

        # feature_image should be None since upload failed
        call_kwargs = mock_client.create_post.call_args[1]
        assert call_kwargs["feature_image"] is None

    def test_no_images_behaves_as_before(self):
        """When prose has no image refs, behavior is unchanged."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config)
        pub._api = mock_client

        prose = "Just text, no images."
        pub.format_daily(_ctx(), prose)

        # upload_image should not have been called
        mock_client.upload_image.assert_not_called()

        # feature_image should be None
        call_kwargs = mock_client.create_post.call_args[1]
        assert call_kwargs["feature_image"] is None

    def test_missing_image_file_skipped(self, tmp_path):
        """When the local image file doesn't exist, it's skipped gracefully."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        # Don't create the image file — it won't exist
        prose = "![alt](images/missing.png)\nSome text."
        pub.format_daily(_ctx(), prose)

        # upload_image should NOT be called since file doesn't exist
        mock_client.upload_image.assert_not_called()

        # local path stays in prose
        call_args = mock_client.create_post.call_args
        sent_prose = call_args[0][1]
        assert "images/missing.png" in sent_prose

    def test_no_output_dir_skips_upload(self):
        """When output_dir is not set, image upload is skipped entirely."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=None)
        pub._api = mock_client

        prose = "![alt](images/hero.png)"
        pub.format_daily(_ctx(), prose)

        # Should not attempt upload without output_dir
        mock_client.upload_image.assert_not_called()

    def test_multiple_images_all_uploaded(self, tmp_path):
        """All image references in prose are processed."""
        cdn_urls = [
            "https://cdn.ghost.io/images/a.png",
            "https://cdn.ghost.io/images/b.png",
            "https://cdn.ghost.io/images/c.png",
        ]
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}
        mock_client.upload_image.side_effect = cdn_urls

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        img_dir = tmp_path / "intake" / "images"
        img_dir.mkdir(parents=True)
        for name in ["a.png", "b.png", "c.png"]:
            (img_dir / name).write_bytes(b"fake")

        prose = "![x](images/a.png)\n![y](images/b.png)\n![z](images/c.png)"
        pub.format_daily(_ctx(), prose)

        assert mock_client.upload_image.call_count == 3

        call_args = mock_client.create_post.call_args
        sent_prose = call_args[0][1]
        for url in cdn_urls:
            assert url in sent_prose

    def test_partial_upload_failure(self, tmp_path):
        """When some uploads fail, successful ones are replaced; failed ones remain."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.publish_with_newsletter.return_value = {"id": "post-1", "status": "published"}
        mock_client.upload_image.side_effect = [
            "https://cdn.ghost.io/images/good.png",
            None,  # second upload fails
        ]

        config = _configured_ghost()
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        img_dir = tmp_path / "intake" / "images"
        img_dir.mkdir(parents=True)
        (img_dir / "good.png").write_bytes(b"fake")
        (img_dir / "bad.png").write_bytes(b"fake")

        prose = "![a](images/good.png)\n![b](images/bad.png)"
        pub.format_daily(_ctx(), prose)

        call_args = mock_client.create_post.call_args
        sent_prose = call_args[0][1]
        # First image replaced with CDN URL
        assert "https://cdn.ghost.io/images/good.png" in sent_prose
        # Second image remains as local path
        assert "images/bad.png" in sent_prose

        # feature_image is the successful first one
        call_kwargs = mock_client.create_post.call_args[1]
        assert call_kwargs["feature_image"] == "https://cdn.ghost.io/images/good.png"

    def test_feature_image_with_auto_publish(self, tmp_path):
        """feature_image is passed to create_post in auto_publish (no newsletter) mode."""
        mock_client = MagicMock()
        mock_client.create_post.return_value = {"id": "post-1"}
        mock_client.upload_image.return_value = "https://cdn.ghost.io/images/hero.png"

        config = GhostConfig(
            url="https://ghost.example.com",
            admin_api_key="abc123:deadbeef",
            newsletter_slug="",
            auto_publish=True,
        )
        pub = GhostIntakePublisher(ghost_config=config, output_dir=tmp_path)
        pub._api = mock_client

        img_dir = tmp_path / "intake" / "images"
        img_dir.mkdir(parents=True)
        (img_dir / "hero.png").write_bytes(b"fake")

        prose = "![hero](images/hero.png)\nContent."
        pub.format_daily(_ctx(), prose)

        call_kwargs = mock_client.create_post.call_args[1]
        assert call_kwargs["feature_image"] == "https://cdn.ghost.io/images/hero.png"
        assert call_kwargs["status"] == "published"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_meta(content: str) -> dict:
    """Extract the ghost-meta JSON from formatted content."""
    meta_str = content.split("<!-- ghost-meta:")[1].split("-->")[0].strip()
    return json.loads(meta_str)
