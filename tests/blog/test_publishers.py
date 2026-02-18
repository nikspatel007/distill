"""Tests for blog publishers."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.blog.config import GhostConfig, Platform
from distill.blog.context import ThematicBlogContext, WeeklyBlogContext
from distill.blog.publishers import create_publisher
from distill.blog.publishers.base import BlogPublisher
from distill.blog.publishers.ghost import GhostAPIClient, GhostPublisher
from distill.blog.publishers.markdown import MarkdownPublisher
from distill.blog.publishers.obsidian import ObsidianPublisher
from distill.blog.reader import JournalEntry
from distill.blog.state import BlogPostRecord, BlogState
from distill.blog.themes import ThemeDefinition


def _make_weekly_context(**kwargs) -> WeeklyBlogContext:
    defaults = {
        "year": 2026,
        "week": 6,
        "week_start": date(2026, 2, 2),
        "week_end": date(2026, 2, 8),
        "entries": [
            JournalEntry(
                date=date(2026, 2, 3),
                prose="Monday.",
                file_path=Path("journal/journal-2026-02-03-dev-journal.md"),
            ),
            JournalEntry(
                date=date(2026, 2, 5),
                prose="Wednesday.",
                file_path=Path("journal/journal-2026-02-05-dev-journal.md"),
            ),
        ],
        "total_sessions": 10,
        "total_duration_minutes": 200,
        "projects": ["distill", "session-insights"],
        "all_tags": ["python", "multi-agent"],
        "combined_prose": "All the prose.",
    }
    defaults.update(kwargs)
    return WeeklyBlogContext(**defaults)


def _make_thematic_context(**kwargs) -> ThematicBlogContext:
    defaults = {
        "theme": ThemeDefinition(
            slug="coordination-overhead",
            title="When Coordination Overhead Exceeds Task Value",
            keywords=["overhead"],
            thread_patterns=[],
        ),
        "evidence_entries": [
            JournalEntry(
                date=date(2026, 2, 3),
                prose="Evidence A.",
                file_path=Path("journal/journal-2026-02-03-dev-journal.md"),
            ),
        ],
        "date_range": (date(2026, 2, 3), date(2026, 2, 5)),
        "evidence_count": 1,
        "combined_evidence": "All the evidence.",
    }
    defaults.update(kwargs)
    return ThematicBlogContext(**defaults)


class TestMarkdownPublisher:
    def test_weekly_has_frontmatter(self):
        pub = MarkdownPublisher()
        result = pub.format_weekly(_make_weekly_context(), "Blog prose.")
        assert result.startswith("---\n")
        assert "title:" in result
        assert "date: 2026-02-02" in result
        assert "  - blog" in result

    def test_weekly_uses_relative_links(self):
        pub = MarkdownPublisher()
        result = pub.format_weekly(_make_weekly_context(), "Prose.")
        assert "](../journal/" in result
        assert "[[" not in result  # No wiki links

    def test_weekly_output_path(self):
        pub = MarkdownPublisher()
        path = pub.weekly_output_path(Path("/output"), 2026, 6)
        assert path == Path("/output/blog/markdown/weekly/weekly-2026-W06.md")

    def test_thematic_has_frontmatter(self):
        pub = MarkdownPublisher()
        result = pub.format_thematic(_make_thematic_context(), "Prose.")
        assert "title:" in result
        assert "  - thematic" in result

    def test_thematic_output_path(self):
        pub = MarkdownPublisher()
        path = pub.thematic_output_path(Path("/output"), "coordination-overhead")
        assert path == Path("/output/blog/markdown/themes/coordination-overhead.md")

    def test_index_path(self):
        pub = MarkdownPublisher()
        assert pub.index_path(Path("/output")) == Path("/output/blog/markdown/README.md")

    def test_contains_prose(self):
        pub = MarkdownPublisher()
        result = pub.format_weekly(_make_weekly_context(), "The week was productive.")
        assert "The week was productive." in result


class TestGhostPublisher:
    def test_weekly_has_ghost_meta(self):
        pub = GhostPublisher()
        result = pub.format_weekly(_make_weekly_context(), "Blog prose.")
        assert "<!-- ghost-meta:" in result
        assert '"status": "draft"' in result

    def test_weekly_no_yaml_frontmatter(self):
        pub = GhostPublisher()
        result = pub.format_weekly(_make_weekly_context(), "Prose.")
        assert not result.startswith("---\n")

    def test_weekly_contains_prose(self):
        pub = GhostPublisher()
        result = pub.format_weekly(_make_weekly_context(), "Great week.")
        assert "Great week." in result

    def test_weekly_output_path(self):
        pub = GhostPublisher()
        path = pub.weekly_output_path(Path("/output"), 2026, 6)
        assert path == Path("/output/blog/ghost/weekly/weekly-2026-W06.md")

    def test_thematic_has_ghost_meta(self):
        pub = GhostPublisher()
        result = pub.format_thematic(_make_thematic_context(), "Deep dive.")
        assert "<!-- ghost-meta:" in result
        meta_section = result.split("ghost-meta:")[1].split("-->")[0]
        assert "coordination" in meta_section
        assert "overhead" in meta_section

    def test_thematic_output_path(self):
        pub = GhostPublisher()
        path = pub.thematic_output_path(Path("/output"), "coordination-overhead")
        assert path == Path("/output/blog/ghost/themes/coordination-overhead.md")

    def test_index_path(self):
        pub = GhostPublisher()
        assert pub.index_path(Path("/output")) == Path("/output/blog/ghost/index.md")




def _make_blog_state() -> BlogState:
    state = BlogState()
    state.mark_generated(
        BlogPostRecord(
            slug="weekly-2026-W06",
            post_type="weekly",
            generated_at=datetime(2026, 2, 8, 12, 0, 0),
            source_dates=[date(2026, 2, 3), date(2026, 2, 5)],
        )
    )
    state.mark_generated(
        BlogPostRecord(
            slug="coordination-overhead",
            post_type="thematic",
            generated_at=datetime(2026, 2, 7, 10, 0, 0),
            source_dates=[date(2026, 2, 3)],
        )
    )
    return state


class TestObsidianPublisher:
    def test_format_index_with_posts(self):
        pub = ObsidianPublisher()
        result = pub.format_index(Path("/output"), _make_blog_state())
        assert "# Blog Index" in result
        assert "## Weekly Synthesis" in result
        assert "## Thematic Deep-Dives" in result
        assert "[[blog/weekly/weekly-2026-W06" in result
        assert "[[blog/themes/coordination-overhead" in result

    def test_format_index_empty(self):
        pub = ObsidianPublisher()
        result = pub.format_index(Path("/output"), BlogState())
        assert "# Blog Index" in result
        assert "## Weekly" not in result

    def test_index_path(self):
        pub = ObsidianPublisher()
        assert pub.index_path(Path("/output")) == Path("/output/blog/index.md")

    def test_weekly_output_path(self):
        pub = ObsidianPublisher()
        path = pub.weekly_output_path(Path("/output"), 2026, 6)
        assert path == Path("/output/blog/weekly/weekly-2026-W06.md")

    def test_thematic_output_path(self):
        pub = ObsidianPublisher()
        path = pub.thematic_output_path(Path("/output"), "coordination-overhead")
        assert path == Path("/output/blog/themes/coordination-overhead.md")

    def test_requires_llm_is_false(self):
        assert ObsidianPublisher.requires_llm is False

    def test_is_blog_publisher(self):
        assert issubclass(ObsidianPublisher, BlogPublisher)


class TestGhostFormatIndex:
    def test_format_index_with_posts(self):
        pub = GhostPublisher()
        result = pub.format_index(Path("/output"), _make_blog_state())
        assert "# Blog Posts" in result
        assert "## Weekly" in result
        assert "## Thematic" in result
        assert "weekly-2026-W06" in result
        assert "coordination-overhead" in result

    def test_format_index_empty(self):
        pub = GhostPublisher()
        result = pub.format_index(Path("/output"), BlogState())
        assert "# Blog Posts" in result
        assert "## Weekly" not in result


class TestMarkdownFormatIndex:
    def test_format_index_with_posts(self):
        pub = MarkdownPublisher()
        result = pub.format_index(Path("/output"), _make_blog_state())
        assert "# Blog" in result
        assert "## Weekly Synthesis" in result
        assert "## Thematic Deep-Dives" in result
        assert "weekly-2026-W06" in result
        assert "coordination-overhead" in result

    def test_format_index_empty(self):
        pub = MarkdownPublisher()
        result = pub.format_index(Path("/output"), BlogState())
        assert "# Blog" in result
        assert "## Weekly" not in result


class TestCreatePublisherFactory:
    def test_creates_file_publishers(self):
        for platform in [Platform.OBSIDIAN, Platform.GHOST, Platform.MARKDOWN]:
            pub = create_publisher(platform)
            assert pub.requires_llm is False

    def test_creates_postiz_publisher(self):
        synth = MagicMock()
        pub = create_publisher(Platform.POSTIZ, synthesizer=synth)
        assert pub.requires_llm is True

    def test_creates_from_string(self):
        pub = create_publisher("obsidian")
        assert isinstance(pub, ObsidianPublisher)

    def test_unknown_platform_string_raises(self):
        with pytest.raises(ValueError):
            create_publisher("nonexistent")


def _make_ghost_api_client() -> GhostAPIClient:
    """Create a GhostAPIClient with dummy config for testing."""
    config = GhostConfig(
        url="https://example.ghost.io",
        admin_api_key="aabbccdd:00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
    )
    return GhostAPIClient(config)


class TestGhostAPIClientUploadImage:
    def test_upload_image_returns_url_on_success(self):
        client = _make_ghost_api_client()
        mock_response = {
            "images": [{"url": "https://example.ghost.io/content/images/hero.png"}]
        }
        with patch.object(client, "_request_multipart", return_value=mock_response):
            result = client.upload_image(Path("/tmp/hero.png"))
        assert result == "https://example.ghost.io/content/images/hero.png"

    def test_upload_image_returns_none_on_error(self):
        client = _make_ghost_api_client()
        with patch.object(client, "_request_multipart", side_effect=Exception("network")):
            result = client.upload_image(Path("/tmp/hero.png"))
        assert result is None

    def test_create_post_with_feature_image(self):
        client = _make_ghost_api_client()
        mock_post = {"id": "post-1", "title": "Test", "feature_image": "https://img.url/hero.png"}
        mock_response = {"posts": [mock_post]}
        with patch.object(client, "_request", return_value=mock_response) as mock_req:
            result = client.create_post(
                title="Test",
                markdown="Hello world",
                feature_image="https://img.url/hero.png",
            )
        assert result["feature_image"] == "https://img.url/hero.png"
        # Verify feature_image was included in the post data sent to _request
        call_args = mock_req.call_args
        post_data = call_args[0][2]  # third positional arg is the data dict
        assert post_data["posts"][0]["feature_image"] == "https://img.url/hero.png"

    def test_create_post_without_feature_image(self):
        client = _make_ghost_api_client()
        mock_post = {"id": "post-1", "title": "Test"}
        mock_response = {"posts": [mock_post]}
        with patch.object(client, "_request", return_value=mock_response) as mock_req:
            result = client.create_post(title="Test", markdown="Hello world")
        call_args = mock_req.call_args
        post_data = call_args[0][2]
        assert "feature_image" not in post_data["posts"][0]
