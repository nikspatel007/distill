"""Tests for theme registry and evidence gathering."""

from datetime import date

from distill.blog.reader import JournalEntry
from distill.blog.state import BlogState
from distill.blog.themes import (
    ThemeDefinition,
    gather_evidence,
    get_ready_themes,
)


def _make_entry(
    day: int = 5,
    prose: str = "Some default prose about development.",
    tags: list[str] | None = None,
) -> JournalEntry:
    return JournalEntry(
        date=date(2026, 2, day),
        style="dev-journal",
        sessions_count=3,
        duration_minutes=60.0,
        tags=tags or [],
        projects=["vermas"],
        prose=prose,
    )


class TestGatherEvidence:
    def test_matches_keyword_in_prose(self):
        theme = ThemeDefinition(
            slug="test-theme",
            title="Test",
            keywords=["overhead", "ceremony"],
            thread_patterns=[],
        )
        entries = [
            _make_entry(day=3, prose="The coordination overhead was significant."),
            _make_entry(day=4, prose="A normal productive day."),
            _make_entry(day=5, prose="Too much ceremony around simple tasks."),
        ]
        evidence = gather_evidence(theme, entries)
        assert len(evidence) == 2
        assert evidence[0].date == date(2026, 2, 3)
        assert evidence[1].date == date(2026, 2, 5)

    def test_matches_thread_pattern_in_tags(self):
        theme = ThemeDefinition(
            slug="test-theme",
            title="Test",
            keywords=[],
            thread_patterns=["qa", "quality"],
        )
        entries = [
            _make_entry(day=3, tags=["qa-improvements"]),
            _make_entry(day=4, tags=["infrastructure"]),
            _make_entry(day=5, tags=["quality-gates"]),
        ]
        evidence = gather_evidence(theme, entries)
        assert len(evidence) == 2

    def test_keyword_case_insensitive(self):
        theme = ThemeDefinition(
            slug="test",
            title="Test",
            keywords=["QA"],
            thread_patterns=[],
        )
        entries = [_make_entry(prose="The qa process worked well.")]
        assert len(gather_evidence(theme, entries)) == 1

    def test_no_matches(self):
        theme = ThemeDefinition(
            slug="test",
            title="Test",
            keywords=["nonexistent-keyword"],
            thread_patterns=["nonexistent-pattern"],
        )
        entries = [_make_entry()]
        assert gather_evidence(theme, entries) == []


class TestGetReadyThemes:
    def test_returns_themes_meeting_threshold(self):
        theme = ThemeDefinition(
            slug="ready-theme",
            title="Ready",
            keywords=["merge"],
            thread_patterns=[],
            min_evidence_days=2,
        )
        entries = [
            _make_entry(day=3, prose="The merge failed again."),
            _make_entry(day=4, prose="Another merge conflict."),
            _make_entry(day=5, prose="Normal work."),
        ]
        # Monkey-patch THEMES for this test
        import distill.blog.themes as themes_mod
        original = themes_mod.THEMES
        themes_mod.THEMES = [theme]
        try:
            ready = get_ready_themes(entries, BlogState())
            assert len(ready) == 1
            assert ready[0][0].slug == "ready-theme"
            assert len(ready[0][1]) == 2
        finally:
            themes_mod.THEMES = original

    def test_skips_already_generated(self):
        theme = ThemeDefinition(
            slug="done-theme",
            title="Done",
            keywords=["merge"],
            thread_patterns=[],
            min_evidence_days=1,
        )
        entries = [_make_entry(prose="merge conflict")]

        from datetime import datetime

        from distill.blog.state import BlogPostRecord

        state = BlogState()
        state.mark_generated(
            BlogPostRecord(
                slug="done-theme",
                post_type="thematic",
                generated_at=datetime.now(),
            )
        )

        import distill.blog.themes as themes_mod
        original = themes_mod.THEMES
        themes_mod.THEMES = [theme]
        try:
            ready = get_ready_themes(entries, state)
            assert len(ready) == 0
        finally:
            themes_mod.THEMES = original

    def test_skips_themes_below_threshold(self):
        theme = ThemeDefinition(
            slug="not-ready",
            title="Not Ready",
            keywords=["special-keyword"],
            thread_patterns=[],
            min_evidence_days=5,
        )
        entries = [
            _make_entry(day=3, prose="special-keyword found"),
            _make_entry(day=4, prose="special-keyword again"),
        ]
        import distill.blog.themes as themes_mod
        original = themes_mod.THEMES
        themes_mod.THEMES = [theme]
        try:
            ready = get_ready_themes(entries, BlogState())
            assert len(ready) == 0
        finally:
            themes_mod.THEMES = original
