"""Tests for journal context compression (deterministic, no LLM)."""

from datetime import date, datetime, timezone

from session_insights.journal.config import JournalConfig
from session_insights.journal.context import (
    DailyContext,
    SessionSummaryForLLM,
    prepare_daily_context,
)
from session_insights.parsers.models import (
    BaseSession,
    ConversationTurn,
    CycleInfo,
    SessionOutcome,
    ToolUsageSummary,
)


def _make_session(
    hour: int = 10,
    project: str = "test-project",
    day: int = 5,
    **kwargs,
) -> BaseSession:
    """Create a test session with sensible defaults."""
    start = datetime(2026, 2, day, hour, 0, tzinfo=timezone.utc)
    end = datetime(2026, 2, day, hour, 30, tzinfo=timezone.utc)
    defaults = dict(
        session_id=f"session-{hour}",
        start_time=start,
        end_time=end,
        source="claude",
        project=project,
        summary=f"Worked on {project} feature",
        narrative=f"A session working on {project}",
        tools_used=[
            ToolUsageSummary(name="Read", count=10),
            ToolUsageSummary(name="Edit", count=5),
            ToolUsageSummary(name="Bash", count=3),
            ToolUsageSummary(name="Grep", count=1),
        ],
        outcomes=[
            SessionOutcome(description="Implemented feature X"),
            SessionOutcome(description="Fixed bug Y", success=False),
        ],
        tags=["python", "refactoring"],
        turns=[
            ConversationTurn(role="user", content="How do I fix the auth bug?"),
            ConversationTurn(role="assistant", content="Let me look at the code..."),
        ],
    )
    defaults.update(kwargs)
    return BaseSession(**defaults)


class TestPrepareContext:
    """Tests for prepare_daily_context."""

    def test_basic_context(self):
        sessions = [_make_session(hour=10), _make_session(hour=14)]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.date == date(2026, 2, 5)
        assert ctx.total_sessions == 2
        assert ctx.total_duration_minutes == 60.0  # 30 min each
        assert ctx.projects_worked == ["test-project"]
        assert len(ctx.session_summaries) == 2

    def test_filters_to_target_date(self):
        sessions = [
            _make_session(hour=10, day=5),
            _make_session(hour=14, day=6),  # Different day
        ]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.total_sessions == 1

    def test_sorts_by_time(self):
        sessions = [_make_session(hour=14), _make_session(hour=9)]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.session_summaries[0].time == "09:00"
        assert ctx.session_summaries[1].time == "14:00"

    def test_limits_sessions(self):
        sessions = [_make_session(hour=h) for h in range(8, 18)]
        config = JournalConfig(max_sessions_per_entry=3)
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.total_sessions == 3

    def test_deduplicates_projects(self):
        sessions = [
            _make_session(hour=10, project="alpha"),
            _make_session(hour=11, project="alpha"),
            _make_session(hour=12, project="beta"),
        ]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.projects_worked == ["alpha", "beta"]

    def test_excludes_unknown_projects(self):
        sessions = [
            _make_session(hour=10, project="real"),
            _make_session(hour=11, project="(unknown)"),
            _make_session(hour=12, project="(unassigned)"),
        ]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.projects_worked == ["real"]

    def test_aggregates_outcomes(self):
        sessions = [
            _make_session(
                hour=10,
                outcomes=[SessionOutcome(description="Done A")],
            ),
            _make_session(
                hour=11,
                outcomes=[SessionOutcome(description="Done B")],
            ),
        ]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert "Done A" in ctx.key_outcomes
        assert "Done B" in ctx.key_outcomes

    def test_deduplicates_outcomes(self):
        sessions = [
            _make_session(hour=10, outcomes=[SessionOutcome(description="Same")]),
            _make_session(hour=11, outcomes=[SessionOutcome(description="Same")]),
        ]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert ctx.key_outcomes.count("Same") == 1

    def test_aggregates_tags(self):
        sessions = [
            _make_session(hour=10, tags=["python", "api"]),
            _make_session(hour=11, tags=["python", "tests"]),
        ]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        assert "python" in ctx.tags
        assert "api" in ctx.tags
        assert "tests" in ctx.tags
        assert ctx.tags.count("python") == 1  # Deduplicated

    def test_empty_sessions(self):
        config = JournalConfig()
        ctx = prepare_daily_context([], date(2026, 2, 5), config)

        assert ctx.total_sessions == 0
        assert ctx.total_duration_minutes == 0.0
        assert ctx.session_summaries == []


class TestSessionSummaryExtraction:
    """Tests for individual session summary extraction."""

    def test_extracts_top_tools(self):
        sessions = [_make_session()]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        summary = ctx.session_summaries[0]
        assert summary.top_tools == ["Read", "Edit", "Bash"]  # Top 3 by count

    def test_extracts_user_questions(self):
        sessions = [_make_session()]
        config = JournalConfig()
        ctx = prepare_daily_context(sessions, date(2026, 2, 5), config)

        summary = ctx.session_summaries[0]
        assert len(summary.user_questions) == 1
        assert "auth bug" in summary.user_questions[0]

    def test_extracts_cycle_outcome(self):
        session = _make_session(
            cycle_info=CycleInfo(
                mission_id="m1",
                cycle=1,
                outcome="done",
            )
        )
        config = JournalConfig()
        ctx = prepare_daily_context([session], date(2026, 2, 5), config)

        assert ctx.session_summaries[0].cycle_outcome == "done"

    def test_truncates_long_content(self):
        long_summary = "x" * 500
        session = _make_session(summary=long_summary)
        config = JournalConfig()
        ctx = prepare_daily_context([session], date(2026, 2, 5), config)

        assert len(ctx.session_summaries[0].summary) == 300


class TestRenderText:
    """Tests for DailyContext.render_text()."""

    def test_renders_header(self):
        ctx = DailyContext(
            date=date(2026, 2, 5),
            total_sessions=2,
            total_duration_minutes=60.0,
        )
        text = ctx.render_text()

        assert "2026-02-05" in text
        assert "Sessions: 2" in text
        assert "60 minutes" in text

    def test_renders_session_details(self):
        ctx = DailyContext(
            date=date(2026, 2, 5),
            total_sessions=1,
            total_duration_minutes=30.0,
            session_summaries=[
                SessionSummaryForLLM(
                    time="10:00",
                    source="claude",
                    project="myproject",
                    summary="Did some work",
                    top_tools=["Read", "Edit"],
                ),
            ],
        )
        text = ctx.render_text()

        assert "Session 1" in text
        assert "10:00" in text
        assert "myproject" in text
        assert "Did some work" in text
        assert "Read, Edit" in text

    def test_renders_key_outcomes(self):
        ctx = DailyContext(
            date=date(2026, 2, 5),
            total_sessions=1,
            total_duration_minutes=30.0,
            key_outcomes=["Shipped feature", "Fixed regression"],
        )
        text = ctx.render_text()

        assert "Key Outcomes" in text
        assert "Shipped feature" in text
        assert "Fixed regression" in text
