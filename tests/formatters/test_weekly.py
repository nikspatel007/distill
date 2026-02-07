"""Tests for weekly digest formatter."""

from datetime import date, datetime, timedelta, timezone

import pytest

from distill.formatters.weekly import (
    WeeklyDigestFormatter,
    group_sessions_by_week,
    week_start_date,
)
from distill.parsers.models import (
    BaseSession,
    SessionOutcome,
    ToolUsageSummary,
)


def _make_session(
    session_id: str,
    day_offset: int = 0,
    project: str = "",
    summary: str = "test session",
    tags: list[str] | None = None,
    narrative: str = "",
) -> BaseSession:
    """Helper to create test sessions on specific days."""
    # 2024-06-10 is a Monday (week 24)
    start = datetime(2024, 6, 10, 10, 0, 0, tzinfo=timezone.utc) + timedelta(
        days=day_offset
    )
    return BaseSession(
        session_id=session_id,
        start_time=start,
        end_time=start + timedelta(minutes=45),
        source="claude-code",
        summary=summary,
        project=project,
        tags=tags or ["feature"],
        narrative=narrative,
        tools_used=[ToolUsageSummary(name="Edit", count=5)],
        outcomes=[
            SessionOutcome(description="Did stuff", success=True),
        ],
    )


class TestWeekStartDate:
    """Tests for week_start_date helper."""

    def test_returns_monday(self) -> None:
        d = week_start_date(2024, 24)
        assert d.weekday() == 0  # Monday

    def test_correct_date(self) -> None:
        # 2024-W24 starts on June 10
        d = week_start_date(2024, 24)
        assert d == date(2024, 6, 10)

    def test_week_1(self) -> None:
        d = week_start_date(2024, 1)
        assert d.weekday() == 0


class TestGroupSessionsByWeek:
    """Tests for group_sessions_by_week function."""

    def test_groups_by_iso_week(self) -> None:
        sessions = [
            _make_session("mon", day_offset=0),   # week 24
            _make_session("wed", day_offset=2),   # week 24
            _make_session("next_mon", day_offset=7),  # week 25
        ]
        groups = group_sessions_by_week(sessions)
        assert len(groups) == 2
        assert len(groups[(2024, 24)]) == 2
        assert len(groups[(2024, 25)]) == 1

    def test_empty_input(self) -> None:
        groups = group_sessions_by_week([])
        assert groups == {}

    def test_sorted_within_week(self) -> None:
        sessions = [
            _make_session("fri", day_offset=4),
            _make_session("mon", day_offset=0),
        ]
        groups = group_sessions_by_week(sessions)
        week = groups[(2024, 24)]
        assert week[0].session_id == "mon"
        assert week[1].session_id == "fri"


class TestWeeklyDigestFormatter:
    """Tests for WeeklyDigestFormatter class."""

    @pytest.fixture
    def formatter(self) -> WeeklyDigestFormatter:
        return WeeklyDigestFormatter()

    @pytest.fixture
    def week_sessions(self) -> list[BaseSession]:
        return [
            _make_session(
                "s1",
                day_offset=0,
                project="proj-a",
                summary="Auth work",
                tags=["feature"],
                narrative="Implemented auth.",
            ),
            _make_session(
                "s2",
                day_offset=1,
                project="proj-b",
                summary="Bug fix",
                tags=["debugging"],
                narrative="Fixed login bug.",
            ),
            _make_session(
                "s3",
                day_offset=3,
                project="proj-a",
                summary="Tests",
                tags=["testing"],
                narrative="Added test coverage.",
            ),
        ]

    def test_note_name(self) -> None:
        assert WeeklyDigestFormatter.note_name(2024, 24) == "weekly-2024-W24"
        assert WeeklyDigestFormatter.note_name(2024, 1) == "weekly-2024-W01"

    def test_format_has_frontmatter(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert digest.startswith("---")
        assert "type: weekly-digest" in digest
        assert "week: 2024-W24" in digest
        assert "total_sessions: 3" in digest

    def test_format_has_title(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "# Weekly Digest: 2024-W24" in digest

    def test_format_has_overview(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "## Overview" in digest
        assert "**Sessions:** 3" in digest
        assert "**Projects:** 2" in digest

    def test_format_has_accomplishments(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "## Accomplishments" in digest
        assert "Implemented auth." in digest
        assert "Fixed login bug." in digest
        assert "Added test coverage." in digest

    def test_format_has_projects_breakdown(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "## Projects" in digest
        assert "proj-a" in digest
        assert "proj-b" in digest

    def test_format_has_daily_breakdown(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "## Daily Breakdown" in digest

    def test_format_has_tool_usage(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "## Tool Usage" in digest
        assert "Edit" in digest

    def test_format_has_activity_tags(
        self, formatter: WeeklyDigestFormatter, week_sessions: list[BaseSession]
    ) -> None:
        digest = formatter.format_weekly_digest(2024, 24, week_sessions)
        assert "## Activity Tags" in digest
        assert "#feature" in digest
        assert "#debugging" in digest

    def test_format_no_accomplishments_without_narratives(
        self, formatter: WeeklyDigestFormatter
    ) -> None:
        sessions = [_make_session("s1", narrative="")]
        digest = formatter.format_weekly_digest(2024, 24, sessions)
        assert "## Accomplishments" not in digest
