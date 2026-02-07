"""Tests for blog state persistence."""

from datetime import date, datetime
from pathlib import Path

from distill.blog.state import (
    BlogPostRecord,
    BlogState,
    load_blog_state,
    save_blog_state,
)


class TestBlogState:
    def test_initially_empty(self):
        state = BlogState()
        assert state.posts == []
        assert not state.is_generated("anything")

    def test_mark_and_check(self):
        state = BlogState()
        record = BlogPostRecord(
            slug="weekly-2026-W06",
            post_type="weekly",
            generated_at=datetime(2026, 2, 8, 12, 0),
            source_dates=[date(2026, 2, 3), date(2026, 2, 5)],
            file_path="/output/blog/weekly/weekly-2026-W06.md",
        )
        state.mark_generated(record)

        assert state.is_generated("weekly-2026-W06")
        assert not state.is_generated("weekly-2026-W07")

    def test_replaces_existing_slug(self):
        state = BlogState()
        old = BlogPostRecord(
            slug="test",
            post_type="weekly",
            generated_at=datetime(2026, 2, 1),
        )
        new = BlogPostRecord(
            slug="test",
            post_type="weekly",
            generated_at=datetime(2026, 2, 8),
        )
        state.mark_generated(old)
        state.mark_generated(new)

        assert len(state.posts) == 1
        assert state.posts[0].generated_at == datetime(2026, 2, 8)


class TestBlogStatePersistence:
    def test_round_trip(self, tmp_path: Path):
        state = BlogState()
        state.mark_generated(
            BlogPostRecord(
                slug="weekly-2026-W06",
                post_type="weekly",
                generated_at=datetime(2026, 2, 8, 12, 0),
                source_dates=[date(2026, 2, 3), date(2026, 2, 5)],
                file_path="/output/blog/weekly.md",
            )
        )
        state.mark_generated(
            BlogPostRecord(
                slug="coordination-overhead",
                post_type="thematic",
                generated_at=datetime(2026, 2, 8, 13, 0),
                source_dates=[date(2026, 2, 1)],
            )
        )

        save_blog_state(state, tmp_path)
        loaded = load_blog_state(tmp_path)

        assert loaded.is_generated("weekly-2026-W06")
        assert loaded.is_generated("coordination-overhead")
        assert len(loaded.posts) == 2

    def test_load_nonexistent(self, tmp_path: Path):
        state = load_blog_state(tmp_path)
        assert state.posts == []

    def test_load_corrupt(self, tmp_path: Path):
        state_path = tmp_path / "blog" / ".blog-state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text("not valid json {{{", encoding="utf-8")

        state = load_blog_state(tmp_path)
        assert state.posts == []
