"""Tests for Obsidian formatter."""

import re
from datetime import date, datetime, timedelta

import pytest
import yaml

from session_insights.formatters.obsidian import ObsidianFormatter, _format_timedelta
from session_insights.formatters.templates import (
    format_duration,
    format_obsidian_link,
    format_tag,
)
from session_insights.models import (
    BaseSession,
    ConversationTurn,
    SessionOutcome,
    ToolUsage,
)
from session_insights.parsers.models import ToolCall


@pytest.fixture
def sample_session() -> BaseSession:
    """Create a sample session for testing."""
    start = datetime(2024, 1, 15, 10, 30, 0)
    end = datetime(2024, 1, 15, 11, 45, 0)

    return BaseSession(
        id="test-session-12345678",
        start_time=start,
        end_time=end,
        source="claude-code",
        summary="Implemented user authentication feature",
        turns=[
            ConversationTurn(
                role="user",
                content="Help me add login functionality",
                timestamp=start,
            ),
            ConversationTurn(
                role="assistant",
                content="I'll help you implement login. Let me start by...",
                timestamp=start + timedelta(seconds=30),
                tools_called=["Read", "Edit"],
            ),
        ],
        tools_used=[
            ToolUsage(name="Read", count=5),
            ToolUsage(name="Edit", count=3),
            ToolUsage(name="Bash", count=2),
        ],
        outcomes=[
            SessionOutcome(
                description="Added login endpoint",
                files_modified=["src/auth.py", "src/routes.py"],
                success=True,
            ),
        ],
        tags=["auth", "feature"],
    )


@pytest.fixture
def minimal_session() -> BaseSession:
    """Create a minimal session for edge case testing."""
    return BaseSession(
        id="minimal-session-00000000",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        source="unknown",
    )


@pytest.fixture
def formatter() -> ObsidianFormatter:
    """Create a formatter instance."""
    return ObsidianFormatter()


class TestFrontmatterYAML:
    """Test that frontmatter is valid YAML."""

    def test_session_frontmatter_is_valid_yaml(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify session frontmatter parses as valid YAML."""
        output = formatter.format_session(sample_session)

        # Extract frontmatter between --- markers
        frontmatter_match = re.match(r"^---\n(.*?)\n---", output, re.DOTALL)
        assert frontmatter_match is not None, "Frontmatter markers not found"

        frontmatter_text = frontmatter_match.group(1)
        parsed = yaml.safe_load(frontmatter_text)

        assert parsed is not None
        assert isinstance(parsed, dict)

    def test_session_frontmatter_contains_required_fields(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify session frontmatter contains all required fields."""
        output = formatter.format_session(sample_session)

        frontmatter_match = re.match(r"^---\n(.*?)\n---", output, re.DOTALL)
        assert frontmatter_match is not None
        parsed = yaml.safe_load(frontmatter_match.group(1))

        required_fields = ["id", "date", "time", "source", "tags", "tools_used", "created"]
        for field in required_fields:
            assert field in parsed, f"Missing required field: {field}"

    def test_daily_summary_frontmatter_is_valid_yaml(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify daily summary frontmatter parses as valid YAML."""
        output = formatter.format_daily_summary([sample_session], date(2024, 1, 15))

        frontmatter_match = re.match(r"^---\n(.*?)\n---", output, re.DOTALL)
        assert frontmatter_match is not None

        parsed = yaml.safe_load(frontmatter_match.group(1))
        assert parsed is not None
        assert isinstance(parsed, dict)

    def test_daily_frontmatter_contains_required_fields(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify daily frontmatter contains all required fields."""
        output = formatter.format_daily_summary([sample_session], date(2024, 1, 15))

        frontmatter_match = re.match(r"^---\n(.*?)\n---", output, re.DOTALL)
        assert frontmatter_match is not None
        parsed = yaml.safe_load(frontmatter_match.group(1))

        required_fields = ["date", "type", "total_sessions", "tags", "created"]
        for field in required_fields:
            assert field in parsed, f"Missing required field: {field}"

    def test_frontmatter_tags_are_list(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify tags are formatted as a YAML list."""
        output = formatter.format_session(sample_session)

        frontmatter_match = re.match(r"^---\n(.*?)\n---", output, re.DOTALL)
        assert frontmatter_match is not None
        parsed = yaml.safe_load(frontmatter_match.group(1))

        assert isinstance(parsed["tags"], list)
        assert len(parsed["tags"]) > 0
        # Tags should start with #
        assert all(tag.startswith("#") for tag in parsed["tags"])


class TestObsidianLinks:
    """Test Obsidian wiki-style links."""

    def test_format_obsidian_link_simple(self) -> None:
        """Test basic wiki link format."""
        link = format_obsidian_link("my-note")
        assert link == "[[my-note]]"

    def test_format_obsidian_link_with_display_text(self) -> None:
        """Test wiki link with custom display text."""
        link = format_obsidian_link("my-note", "My Note Title")
        assert link == "[[my-note|My Note Title]]"

    def test_session_contains_daily_summary_link(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify session note links to daily summary."""
        output = formatter.format_session(sample_session)

        # Should contain a link to daily summary
        assert "[[daily-2024-01-15" in output

    def test_daily_summary_links_to_sessions(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify daily summary links to individual sessions."""
        output = formatter.format_daily_summary([sample_session], date(2024, 1, 15))

        # Should contain wiki-style link to session
        assert "[[session-" in output

    def test_links_have_no_broken_brackets(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify all wiki links have matching brackets."""
        output = formatter.format_session(sample_session)

        # Count opening and closing brackets
        open_double = output.count("[[")
        close_double = output.count("]]")
        assert open_double == close_double, "Mismatched wiki link brackets"


class TestMarkdownSyntax:
    """Test that generated markdown is syntactically correct."""

    def test_session_has_valid_headings(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify session output has proper heading structure."""
        output = formatter.format_session(sample_session)

        # Should have H1 for title
        assert re.search(r"^# .+$", output, re.MULTILINE)

        # Should have H2 sections
        assert "## Summary" in output
        assert "## Timeline" in output
        assert "## Tools Used" in output
        assert "## Outcomes" in output

    def test_daily_summary_has_valid_headings(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify daily summary has proper heading structure."""
        output = formatter.format_daily_summary([sample_session], date(2024, 1, 15))

        assert "# Daily Summary" in output
        assert "## Overview" in output
        assert "## Sessions" in output
        assert "## Statistics" in output

    def test_lists_are_properly_formatted(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify list items use correct markdown syntax."""
        output = formatter.format_session(sample_session)

        # Find bullet points - should start with "- "
        list_items = re.findall(r"^- .+$", output, re.MULTILINE)
        assert len(list_items) > 0, "No list items found"

        # Each list item should have content after "- "
        for item in list_items:
            assert len(item) > 2, f"Empty list item: {item}"

    def test_code_blocks_have_matching_backticks(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify inline code blocks have matching backticks."""
        output = formatter.format_session(sample_session)

        # Count backticks - should be even
        backtick_count = output.count("`")
        assert backtick_count % 2 == 0, "Mismatched backticks in code blocks"

    def test_tables_are_valid_markdown(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify any tables have proper header separator."""
        output = formatter.format_daily_summary([sample_session], date(2024, 1, 15))

        # If there's a table header, it should have separator
        table_lines = [
            line for line in output.split("\n") if line.startswith("|") and line.endswith("|")
        ]

        if len(table_lines) >= 2:
            # Second line should be separator (|---|---|)
            separator = table_lines[1]
            assert re.match(r"^\|[-| ]+\|$", separator), "Invalid table separator"

    def test_no_unescaped_special_characters(
        self, formatter: ObsidianFormatter, sample_session: BaseSession
    ) -> None:
        """Verify special characters don't break markdown."""
        output = formatter.format_session(sample_session)

        # Check there are no HTML-like unclosed tags that could break rendering
        # This is a basic check - actual markdown rendering is more complex
        assert "< >" not in output  # Broken empty tags


class TestEdgeCases:
    """Test edge cases and minimal inputs."""

    def test_minimal_session_formats_without_error(
        self, formatter: ObsidianFormatter, minimal_session: BaseSession
    ) -> None:
        """Verify minimal session can be formatted."""
        output = formatter.format_session(minimal_session)
        assert output is not None
        assert len(output) > 0

    def test_empty_sessions_list(self, formatter: ObsidianFormatter) -> None:
        """Verify empty session list formats correctly."""
        output = formatter.format_daily_summary([], date(2024, 1, 15))
        assert "No sessions recorded" in output or "0" in output

    def test_session_without_end_time(
        self, formatter: ObsidianFormatter, minimal_session: BaseSession
    ) -> None:
        """Verify session without end time shows as ongoing."""
        output = formatter.format_session(minimal_session)
        # Should indicate ongoing or unknown duration
        assert "Ongoing" in output or "Unknown" in output

    def test_long_summary_is_handled(self, formatter: ObsidianFormatter) -> None:
        """Verify long summaries don't break formatting."""
        long_session = BaseSession(
            id="long-session-00000000",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            summary="A" * 1000,  # Very long summary
            source="test",
        )
        output = formatter.format_session(long_session)
        assert output is not None

    def test_special_characters_in_summary(self, formatter: ObsidianFormatter) -> None:
        """Verify special characters in summary don't break formatting."""
        special_session = BaseSession(
            id="special-session-00000000",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            summary="Used `code` and **bold** and [links](http://example.com)",
            source="test",
        )
        output = formatter.format_session(special_session)
        # Just verify it doesn't crash
        assert output is not None


class TestTemplateHelpers:
    """Test template helper functions."""

    def test_format_tag(self) -> None:
        """Test tag formatting for YAML."""
        result = format_tag("ai-session")
        assert result == '  - "#ai-session"'

    def test_format_duration_seconds(self) -> None:
        """Test duration formatting for seconds."""
        result = format_duration(0.5)
        assert "30 seconds" in result

    def test_format_duration_minutes(self) -> None:
        """Test duration formatting for minutes."""
        result = format_duration(45)
        assert "45 minutes" in result

    def test_format_duration_hours(self) -> None:
        """Test duration formatting for hours."""
        result = format_duration(90)
        assert "1h 30m" in result or "1 hour" in result

    def test_format_duration_none(self) -> None:
        """Test duration formatting for None."""
        result = format_duration(None)
        assert result == "Unknown"


class TestFormatterOptions:
    """Test formatter configuration options."""

    def test_exclude_conversation(self, sample_session: BaseSession) -> None:
        """Test that conversation can be excluded."""
        formatter = ObsidianFormatter(include_conversation=False)
        output = formatter.format_session(sample_session)

        assert "Conversation not included" in output

    def test_include_conversation_by_default(self, sample_session: BaseSession) -> None:
        """Test that conversation is included by default."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(sample_session)

        # Should contain conversation content
        assert "user" in output.lower() or "assistant" in output.lower()


class TestVermasFormatting:
    """Test VerMAS-specific formatting sections."""

    @pytest.fixture
    def vermas_session(self) -> BaseSession:
        """Create a VerMAS-like session using duck typing fields."""
        from session_insights.parsers.models import (
            AgentLearning,
            AgentSignal,
            KnowledgeImprovement,
        )
        from session_insights.parsers.vermas import VermasSession

        start = datetime(2024, 6, 15, 14, 0, 0)
        end = datetime(2024, 6, 15, 14, 30, 0)

        return VermasSession(
            session_id="vermas-test-001",
            timestamp=start,
            start_time=start,
            end_time=end,
            source="vermas",
            summary="Implemented pattern analyzer",
            task_name="create-pattern-analyzer",
            task_description="Build the pattern detection system for session analysis.",
            mission_id="mission-abc123",
            cycle=3,
            outcome="completed",
            signals=[
                AgentSignal(
                    signal_id="sig-1",
                    agent_id="dev-agent-001",
                    role="dev",
                    signal="done",
                    message="Code and tests written",
                    timestamp=datetime(2024, 6, 15, 14, 20, 0),
                    workflow_id="wf-001",
                ),
                AgentSignal(
                    signal_id="sig-2",
                    agent_id="qa-agent-001",
                    role="qa",
                    signal="approved",
                    message="All tests pass, coverage met",
                    timestamp=datetime(2024, 6, 15, 14, 25, 0),
                    workflow_id="wf-001",
                ),
            ],
            learnings=[
                AgentLearning(
                    agent="dev",
                    learnings=["Incremental testing prevents regressions"],
                    best_practices=["Run tests after each change"],
                ),
            ],
            improvements=[
                KnowledgeImprovement(
                    id="imp-1",
                    type="process",
                    target="test-workflow",
                    change="Added pre-commit checks",
                    validated=True,
                    impact="Reduced failed commits by 50%",
                ),
            ],
        )

    def test_vermas_session_has_task_details(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify VerMAS notes show task details."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "## Task Details" in output
        assert "create-pattern-analyzer" in output
        assert "mission-abc123" in output
        assert "Cycle:** 3" in output
        assert "completed" in output

    def test_vermas_session_has_task_description(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify VerMAS notes show task description."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "### Description" in output
        assert "Build the pattern detection system" in output

    def test_vermas_session_has_signals_timeline(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify VerMAS notes show agent signals timeline."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "## Agent Signals" in output
        assert "done" in output
        assert "approved" in output
        assert "dev" in output
        assert "qa" in output

    def test_vermas_session_has_learnings(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify VerMAS notes show agent learnings."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "## Learnings" in output
        assert "Incremental testing prevents regressions" in output
        assert "Best Practices" in output
        assert "Run tests after each change" in output

    def test_vermas_session_has_improvements(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify VerMAS notes show improvements."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "### Improvements" in output
        assert "pre-commit checks" in output
        assert "validated" in output
        assert "Reduced failed commits" in output

    def test_non_vermas_session_has_no_vermas_sections(
        self, sample_session: BaseSession
    ) -> None:
        """Verify non-VerMAS sessions don't get VerMAS sections."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(sample_session)

        assert "## Task Details" not in output
        assert "## Agent Signals" not in output
        assert "## Learnings" not in output

    def test_vermas_signals_have_elapsed_time(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify signals timeline includes elapsed duration column."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "Elapsed" in output
        assert "Total workflow time" in output
        # First signal should show 0s elapsed
        assert "0s" in output
        # Second signal is 5 minutes later
        assert "5m" in output

    def test_vermas_signals_timestamps_formatted(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify signal timestamps are formatted as HH:MM:SS."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "14:20:00" in output
        assert "14:25:00" in output

    def test_vermas_quality_assessment_rendering(self) -> None:
        """Verify quality assessment section renders score, criteria, and notes."""
        from session_insights.parsers.models import (
            AgentSignal,
            QualityAssessment,
        )
        from session_insights.parsers.vermas import VermasSession

        start = datetime(2024, 6, 15, 14, 0, 0)
        session = VermasSession(
            session_id="qa-test-001",
            timestamp=start,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            source="vermas",
            summary="Test session with quality assessment",
            task_name="test-task",
            mission_id="mission-qa",
            cycle=1,
            outcome="completed",
            quality_assessment=QualityAssessment(
                score=0.92,
                criteria={
                    "code_quality": 0.90,
                    "test_coverage": 0.95,
                },
                notes="Excellent implementation with minor doc gaps",
            ),
            signals=[
                AgentSignal(
                    signal_id="sig-qa",
                    agent_id="dev-001",
                    role="dev",
                    signal="done",
                    message="Done",
                    timestamp=start + timedelta(minutes=20),
                    workflow_id="wf-qa",
                ),
            ],
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "## Quality Assessment" in output
        assert "92/100" in output
        assert "Code Quality" in output
        assert "90/100" in output
        assert "Test Coverage" in output
        assert "95/100" in output
        assert "Excellent implementation" in output

    def test_vermas_no_quality_section_when_absent(
        self, vermas_session: BaseSession
    ) -> None:
        """Verify quality section is omitted when no assessment exists."""
        formatter = ObsidianFormatter()
        output = formatter.format_session(vermas_session)

        assert "## Quality Assessment" not in output


class TestEnrichedConversation:
    """Test the enriched conversation section rendering."""

    def test_user_questions_extracted(self) -> None:
        """Verify user questions are listed in the conversation section."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        session = BaseSession(
            id="conv-test-001",
            start_time=start,
            source="claude-code",
            turns=[
                ConversationTurn(
                    role="user",
                    content="How do I implement authentication?",
                    timestamp=start,
                ),
                ConversationTurn(
                    role="assistant",
                    content="I'll help you implement authentication.",
                    timestamp=start + timedelta(seconds=10),
                ),
                ConversationTurn(
                    role="user",
                    content="Should we use JWT or session tokens?",
                    timestamp=start + timedelta(seconds=60),
                ),
            ],
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "### User Questions" in output
        assert "How do I implement authentication?" in output
        assert "Should we use JWT or session tokens?" in output

    def test_tool_usage_analysis_table(self) -> None:
        """Verify tool usage analysis renders with context."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        session = BaseSession(
            id="tool-test-001",
            start_time=start,
            source="claude-code",
            tools_used=[
                ToolUsage(name="Read", count=3),
                ToolUsage(name="Edit", count=2),
            ],
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "src/auth.py"},
                ),
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "src/models.py"},
                ),
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "src/auth.py"},
                ),
            ],
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "### Tool Usage" in output
        assert "| Read | 3 |" in output
        assert "| Edit | 2 |" in output
        assert "`src/auth.py`" in output
        assert "`src/models.py`" in output

    def test_key_decisions_extracted(self) -> None:
        """Verify key decisions are extracted from assistant messages."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        session = BaseSession(
            id="decision-test-001",
            start_time=start,
            source="claude-code",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Fix the login bug",
                    timestamp=start,
                ),
                ConversationTurn(
                    role="assistant",
                    content="I decided to refactor the auth module. I will add proper error handling.",
                    timestamp=start + timedelta(seconds=10),
                ),
            ],
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "### Key Decisions" in output
        assert "decided to refactor the auth module" in output

    def test_accomplishments_summary(self) -> None:
        """Verify accomplishments are rendered from session outcomes."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        session = BaseSession(
            id="accomplishment-test-001",
            start_time=start,
            source="claude-code",
            outcomes=[
                SessionOutcome(
                    description="Implemented login endpoint",
                    files_modified=["src/auth.py"],
                    success=True,
                ),
                SessionOutcome(
                    description="Added test coverage",
                    files_modified=["tests/test_auth.py"],
                    success=True,
                ),
            ],
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "### Accomplishments" in output
        assert "2/2" in output
        assert "Implemented login endpoint" in output
        assert "Added test coverage" in output
        assert "`src/auth.py`" in output

    def test_empty_session_shows_fallback(self) -> None:
        """Verify session with no conversation data shows fallback message."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        session = BaseSession(
            id="empty-conv-test-001",
            start_time=start,
            source="claude-code",
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "No conversation content available" in output

    def test_long_user_question_truncated(self) -> None:
        """Verify long user questions are truncated at 200 chars."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        long_content = "A" * 300
        session = BaseSession(
            id="truncate-test-001",
            start_time=start,
            source="claude-code",
            turns=[
                ConversationTurn(role="user", content=long_content, timestamp=start),
            ],
        )

        formatter = ObsidianFormatter()
        output = formatter.format_session(session)

        assert "..." in output
        # Should not have the full 300-char string
        assert long_content not in output

    def test_include_conversation_false_still_works(self) -> None:
        """Verify include_conversation=False suppresses conversation section."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        session = BaseSession(
            id="no-conv-test-001",
            start_time=start,
            source="claude-code",
            turns=[
                ConversationTurn(role="user", content="Hello", timestamp=start),
            ],
            outcomes=[
                SessionOutcome(description="Did something", success=True),
            ],
        )

        formatter = ObsidianFormatter(include_conversation=False)
        output = formatter.format_session(session)

        assert "Conversation not included" in output
        assert "### User Questions" not in output
        assert "### Accomplishments" not in output


class TestFormatTimedelta:
    """Test the _format_timedelta helper function."""

    def test_seconds(self) -> None:
        assert _format_timedelta(timedelta(seconds=30)) == "30s"

    def test_zero_seconds(self) -> None:
        assert _format_timedelta(timedelta(seconds=0)) == "0s"

    def test_minutes(self) -> None:
        assert _format_timedelta(timedelta(minutes=5)) == "5m"

    def test_minutes_and_seconds(self) -> None:
        assert _format_timedelta(timedelta(minutes=5, seconds=30)) == "5m 30s"

    def test_hours(self) -> None:
        assert _format_timedelta(timedelta(hours=2)) == "2h"

    def test_hours_and_minutes(self) -> None:
        assert _format_timedelta(timedelta(hours=1, minutes=30)) == "1h 30m"
