"""Tests for journal formatter (frontmatter + body)."""

from datetime import date
from pathlib import Path

from distill.journal.config import JournalConfig, JournalStyle
from distill.journal.context import DailyContext
from distill.journal.formatter import JournalFormatter


def _make_context(**kwargs) -> DailyContext:
    defaults = dict(
        date=date(2026, 2, 5),
        total_sessions=3,
        total_duration_minutes=90.0,
        projects_worked=["vermas", "session-insights"],
        key_outcomes=["Shipped feature"],
        tags=["python", "refactoring"],
    )
    defaults.update(kwargs)
    return DailyContext(**defaults)


class TestJournalFormatter:
    """Tests for JournalFormatter."""

    def test_has_frontmatter(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Some prose here.")

        assert result.startswith("---\n")
        assert "\n---\n" in result

    def test_frontmatter_contains_metadata(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "date: 2026-02-05" in result
        assert "type: journal" in result
        assert "style: dev-journal" in result
        assert "sessions_count: 3" in result
        assert "duration_minutes: 90" in result

    def test_frontmatter_tags(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "  - journal" in result
        assert "  - python" in result
        assert "  - refactoring" in result

    def test_frontmatter_projects(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "  - vermas" in result
        assert "  - session-insights" in result

    def test_body_has_title(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "# Dev Journal: February 05, 2026" in result

    def test_body_contains_prose(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        prose = "Today I worked on several exciting things."
        result = formatter.format_entry(_make_context(), prose)

        assert prose in result

    def test_body_has_metrics(self):
        config = JournalConfig(include_metrics=True)
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "3 sessions" in result
        assert "90 minutes" in result

    def test_no_metrics_when_disabled(self):
        config = JournalConfig(include_metrics=False)
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "3 sessions" not in result

    def test_related_section(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "## Related" in result
        assert "[[daily/daily-2026-02-05|Daily Summary]]" in result

    def test_tech_blog_title(self):
        config = JournalConfig(style=JournalStyle.TECH_BLOG)
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Prose.")

        assert "# Tech Blog: February 05, 2026" in result

    def test_output_path(self):
        config = JournalConfig(style=JournalStyle.DEV_JOURNAL)
        formatter = JournalFormatter(config)
        path = formatter.output_path(Path("/output"), _make_context())

        assert path == Path("/output/journal/journal-2026-02-05-dev-journal.md")

    def test_output_path_tech_blog(self):
        config = JournalConfig(style=JournalStyle.TECH_BLOG)
        formatter = JournalFormatter(config)
        path = formatter.output_path(Path("/output"), _make_context())

        assert path == Path("/output/journal/journal-2026-02-05-tech-blog.md")

    def test_empty_tags(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        ctx = _make_context(tags=[])
        result = formatter.format_entry(ctx, "Prose.")

        # Should still have the journal tag
        assert "  - journal" in result
