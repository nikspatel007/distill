"""Tests for blog memory model and persistence."""

from datetime import date
from pathlib import Path

from distill.blog.blog_memory import (
    BlogMemory,
    BlogPostSummary,
    load_blog_memory,
    save_blog_memory,
)


def _make_summary(**kwargs) -> BlogPostSummary:
    defaults = {
        "slug": "weekly-2026-W06",
        "title": "Week 6: Building Multi-Agent Systems",
        "post_type": "weekly",
        "date": date(2026, 2, 8),
        "key_points": ["Point A", "Point B", "Point C"],
        "themes_covered": ["multi-agent", "coordination"],
        "platforms_published": ["obsidian"],
    }
    defaults.update(kwargs)
    return BlogPostSummary(**defaults)


class TestBlogMemoryRender:
    def test_empty_memory_renders_empty(self):
        memory = BlogMemory()
        assert memory.render_for_prompt() == ""

    def test_renders_post_summaries(self):
        memory = BlogMemory(posts=[_make_summary()])
        result = memory.render_for_prompt()
        assert "Previous Blog Posts" in result
        assert "Week 6: Building Multi-Agent Systems" in result
        assert "Point A" in result

    def test_renders_multiple_posts_newest_first(self):
        memory = BlogMemory(posts=[
            _make_summary(slug="a", title="First", date=date(2026, 2, 1)),
            _make_summary(slug="b", title="Second", date=date(2026, 2, 8)),
        ])
        result = memory.render_for_prompt()
        # Second should appear before First (newest first)
        assert result.index("Second") < result.index("First")


class TestBlogMemoryAddPost:
    def test_add_post(self):
        memory = BlogMemory()
        memory.add_post(_make_summary())
        assert len(memory.posts) == 1

    def test_add_post_replaces_by_slug(self):
        memory = BlogMemory()
        memory.add_post(_make_summary(title="V1"))
        memory.add_post(_make_summary(title="V2"))
        assert len(memory.posts) == 1
        assert memory.posts[0].title == "V2"


class TestBlogMemoryPublishing:
    def test_is_published_to(self):
        memory = BlogMemory(posts=[_make_summary(platforms_published=["obsidian"])])
        assert memory.is_published_to("weekly-2026-W06", "obsidian") is True
        assert memory.is_published_to("weekly-2026-W06", "twitter") is False

    def test_is_published_to_unknown_slug(self):
        memory = BlogMemory(posts=[_make_summary()])
        assert memory.is_published_to("nonexistent", "obsidian") is False

    def test_mark_published(self):
        memory = BlogMemory(posts=[_make_summary(platforms_published=["obsidian"])])
        memory.mark_published("weekly-2026-W06", "twitter")
        assert "twitter" in memory.posts[0].platforms_published

    def test_mark_published_no_duplicate(self):
        memory = BlogMemory(posts=[_make_summary(platforms_published=["obsidian"])])
        memory.mark_published("weekly-2026-W06", "obsidian")
        assert memory.posts[0].platforms_published.count("obsidian") == 1


class TestBlogMemoryPersistence:
    def test_round_trip(self, tmp_path: Path):
        memory = BlogMemory(posts=[_make_summary()])
        save_blog_memory(memory, tmp_path)
        loaded = load_blog_memory(tmp_path)
        assert len(loaded.posts) == 1
        assert loaded.posts[0].slug == "weekly-2026-W06"
        assert loaded.posts[0].title == "Week 6: Building Multi-Agent Systems"

    def test_load_missing_file(self, tmp_path: Path):
        loaded = load_blog_memory(tmp_path)
        assert len(loaded.posts) == 0

    def test_load_corrupt_file(self, tmp_path: Path):
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / ".blog-memory.json").write_text("not json", encoding="utf-8")
        loaded = load_blog_memory(tmp_path)
        assert len(loaded.posts) == 0
