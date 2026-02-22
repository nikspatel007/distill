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
        projects_worked=["distill", "session-insights"],
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

        assert "  - distill" in result
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


class TestExtractBrief:
    """Tests for _extract_brief helper."""

    def test_extract_brief_parses_bullets(self):
        from distill.journal.services import _extract_brief

        text = (
            "BRIEF:\n"
            "- Shipped TLS support\n"
            "- Fixed mobile nav\n"
            "- Added PWA manifest\n"
            "\n"
            "Today was productive..."
        )
        brief, prose = _extract_brief(text)
        assert brief == ["Shipped TLS support", "Fixed mobile nav", "Added PWA manifest"]
        assert prose.startswith("Today was productive")

    def test_extract_brief_no_block(self):
        from distill.journal.services import _extract_brief

        text = "Today I worked on several things..."
        brief, prose = _extract_brief(text)
        assert brief == []
        assert prose == text

    def test_extract_brief_with_leading_whitespace(self):
        from distill.journal.services import _extract_brief

        text = "\n  BRIEF:\n- Item one\n- Item two\n\nProse here."
        brief, prose = _extract_brief(text)
        assert brief == ["Item one", "Item two"]
        assert prose == "Prose here."

    def test_extract_brief_five_bullets(self):
        from distill.journal.services import _extract_brief

        text = (
            "BRIEF:\n"
            "- One\n"
            "- Two\n"
            "- Three\n"
            "- Four\n"
            "- Five\n"
            "\n"
            "The rest."
        )
        brief, prose = _extract_brief(text)
        assert len(brief) == 5
        assert brief[4] == "Five"


class TestBriefInFrontmatter:
    """Tests for brief: field in frontmatter."""

    def test_frontmatter_includes_brief(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        prose = "BRIEF:\n- Built feature A\n- Fixed bug B\n\nToday I worked..."
        result = formatter.format_entry(_make_context(), prose)

        assert "brief:" in result
        assert '  - "Built feature A"' in result
        assert '  - "Fixed bug B"' in result
        # Prose should NOT contain the BRIEF block
        body_after_frontmatter = result.split("---", 2)[2]
        assert "BRIEF:" not in body_after_frontmatter

    def test_frontmatter_no_brief_when_empty(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        result = formatter.format_entry(_make_context(), "Just prose, no brief.")
        # brief: should not appear in frontmatter
        frontmatter = result.split("---")[1]
        assert "brief:" not in frontmatter

    def test_brief_appears_before_created(self):
        config = JournalConfig()
        formatter = JournalFormatter(config)
        prose = "BRIEF:\n- Did something\n\nProse."
        result = formatter.format_entry(_make_context(), prose)
        frontmatter = result.split("---")[1]
        brief_pos = frontmatter.index("brief:")
        created_pos = frontmatter.index("created:")
        assert brief_pos < created_pos
