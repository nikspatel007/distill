"""Tests for blog formatter (frontmatter + body)."""

from datetime import date
from pathlib import Path

from session_insights.blog.context import ThematicBlogContext, WeeklyBlogContext
from session_insights.blog.formatter import BlogFormatter
from session_insights.blog.reader import JournalEntry
from session_insights.blog.themes import ThemeDefinition


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
        "projects": ["vermas", "session-insights"],
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
            JournalEntry(
                date=date(2026, 2, 5),
                prose="Evidence B.",
                file_path=Path("journal/journal-2026-02-05-dev-journal.md"),
            ),
        ],
        "date_range": (date(2026, 2, 3), date(2026, 2, 5)),
        "evidence_count": 2,
        "combined_evidence": "All the evidence.",
    }
    defaults.update(kwargs)
    return ThematicBlogContext(**defaults)


class TestBlogFormatterWeekly:
    def test_has_frontmatter(self):
        formatter = BlogFormatter()
        result = formatter.format_weekly(_make_weekly_context(), "Blog prose.")
        assert result.startswith("---\n")
        assert "\n---\n" in result

    def test_frontmatter_metadata(self):
        formatter = BlogFormatter()
        result = formatter.format_weekly(_make_weekly_context(), "Prose.")
        assert "date: 2026-02-02" in result
        assert "type: blog" in result
        assert "blog_type: weekly" in result
        assert "week: 2026-W06" in result
        assert "sessions_count: 10" in result
        assert "duration_minutes: 200" in result

    def test_frontmatter_projects(self):
        formatter = BlogFormatter()
        result = formatter.format_weekly(_make_weekly_context(), "Prose.")
        assert "  - vermas" in result
        assert "  - session-insights" in result

    def test_frontmatter_tags(self):
        formatter = BlogFormatter()
        result = formatter.format_weekly(_make_weekly_context(), "Prose.")
        assert "  - blog" in result
        assert "  - weekly" in result
        assert "  - python" in result

    def test_contains_prose(self):
        formatter = BlogFormatter()
        result = formatter.format_weekly(
            _make_weekly_context(), "The week was productive."
        )
        assert "The week was productive." in result

    def test_sources_section(self):
        formatter = BlogFormatter()
        result = formatter.format_weekly(_make_weekly_context(), "Prose.")
        assert "## Sources" in result
        assert "[[journal/journal-2026-02-03-dev-journal|Feb 03 Journal]]" in result
        assert "[[journal/journal-2026-02-05-dev-journal|Feb 05 Journal]]" in result

    def test_output_path(self):
        formatter = BlogFormatter()
        path = formatter.weekly_output_path(Path("/output"), 2026, 6)
        assert path == Path("/output/blog/weekly/weekly-2026-W06.md")


class TestBlogFormatterThematic:
    def test_has_frontmatter(self):
        formatter = BlogFormatter()
        result = formatter.format_thematic(_make_thematic_context(), "Prose.")
        assert result.startswith("---\n")
        assert "type: blog" in result
        assert "blog_type: thematic" in result

    def test_frontmatter_theme(self):
        formatter = BlogFormatter()
        result = formatter.format_thematic(_make_thematic_context(), "Prose.")
        assert "theme: coordination-overhead" in result
        assert "evidence_days: 2" in result

    def test_frontmatter_tags(self):
        formatter = BlogFormatter()
        result = formatter.format_thematic(_make_thematic_context(), "Prose.")
        assert "  - blog" in result
        assert "  - thematic" in result

    def test_contains_prose(self):
        formatter = BlogFormatter()
        result = formatter.format_thematic(
            _make_thematic_context(), "Deep analysis."
        )
        assert "Deep analysis." in result

    def test_sources_section(self):
        formatter = BlogFormatter()
        result = formatter.format_thematic(_make_thematic_context(), "Prose.")
        assert "## Sources" in result
        assert "[[journal/journal-2026-02-03-dev-journal|Feb 03 Journal]]" in result

    def test_output_path(self):
        formatter = BlogFormatter()
        path = formatter.thematic_output_path(Path("/output"), "coordination-overhead")
        assert path == Path("/output/blog/themes/coordination-overhead.md")
