"""Smoke tests for the CLI."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from session_insights.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_claude_session(temp_output_dir: Path):
    """Create a temporary directory with a mock Claude session."""
    # Create .claude/projects directory structure
    claude_dir = temp_output_dir / ".claude" / "projects"
    claude_dir.mkdir(parents=True)

    # Create a minimal session file
    session_data = [
        {
            "type": "user",
            "message": {"content": "Hello, help me with a task"},
            "timestamp": datetime.now().isoformat(),
        },
        {
            "type": "assistant",
            "message": {"content": "I'll help you with that task."},
            "timestamp": datetime.now().isoformat(),
        },
    ]

    session_file = claude_dir / "test-session.jsonl"
    with open(session_file, "w") as f:
        for entry in session_data:
            f.write(json.dumps(entry) + "\n")

    return temp_output_dir


class TestCLI:
    """Tests for the CLI entry point."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Test that --help works on the main command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "session-insights" in result.output.lower() or "analyze" in result.output.lower()

    def test_main_version(self, runner: CliRunner) -> None:
        """Test that --version works."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "session-insights" in result.output

    def test_analyze_help(self, runner: CliRunner) -> None:
        """Test that analyze --help works."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "output" in result.output.lower()

    def test_analyze_default_output(self, runner: CliRunner) -> None:
        """Test that analyze uses default output directory when --output is not specified."""
        result = runner.invoke(app, ["analyze", "--dir", "/tmp"])
        # Should succeed (exit 0) even without --output, using default ./insights/
        assert result.exit_code == 0
        assert "Output will be written to:" in result.output


class TestAnalyzeFormatOption:
    """Tests for the --format option."""

    def test_analyze_help_shows_format_option(self, runner: CliRunner) -> None:
        """Test that --format option is documented in help."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output

    def test_analyze_default_format_is_obsidian(self, runner: CliRunner) -> None:
        """Test that default format is obsidian."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        # Help should mention obsidian as the format
        assert "obsidian" in result.output.lower()

    def test_analyze_unsupported_format_fails(self, runner: CliRunner) -> None:
        """Test that unsupported format produces an error."""
        result = runner.invoke(app, ["analyze", "--dir", "/tmp", "--format", "json"])
        assert result.exit_code == 1
        assert "unsupported format" in result.output.lower()

    def test_analyze_obsidian_format_succeeds(self, runner: CliRunner) -> None:
        """Test that obsidian format is accepted."""
        result = runner.invoke(app, ["analyze", "--dir", "/tmp", "--format", "obsidian"])
        assert result.exit_code == 0


class TestAnalyzeIndexGeneration:
    """Tests for index.md generation."""

    def test_analyze_no_sessions_does_not_create_index(
        self, runner: CliRunner, temp_output_dir: Path
    ) -> None:
        """Test that analyze with no sessions doesn't create index (exits early)."""
        output_dir = temp_output_dir / "output"
        result = runner.invoke(
            app, ["analyze", "--dir", "/tmp", "--output", str(output_dir)]
        )
        # Should succeed but exit early with no sessions
        assert result.exit_code == 0
        assert "No session files found" in result.output

        # Index should NOT be created when no sessions found
        index_path = output_dir / "index.md"
        assert not index_path.exists(), "index.md should not be created when no sessions"


class TestGenerateIndexFunction:
    """Tests for the _generate_index helper function."""

    def test_generate_index_creates_valid_markdown(self) -> None:
        """Test that _generate_index creates valid markdown."""
        from datetime import datetime
        from session_insights.cli import _generate_index
        from session_insights.core import AnalysisResult, SessionStats
        from session_insights.parsers.models import BaseSession

        # Create minimal test data with correct field names
        session = BaseSession(
            session_id="test-session-123",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            source="claude",
            summary="Test session",
        )

        result = AnalysisResult(
            sessions=[session],
            patterns=[],
            stats=SessionStats(
                total_sessions=1,
                total_duration_minutes=0.0,
                date_range=None,
            ),
        )

        daily_sessions = {session.start_time.date(): [session]}
        index_content = _generate_index([session], daily_sessions, result)

        # Verify frontmatter
        assert index_content.startswith("---"), "Should start with frontmatter"
        assert "type: index" in index_content
        assert "total_sessions: 1" in index_content

        # Verify content
        assert "# Session Insights Index" in index_content
        assert "Total Sessions" in index_content
        assert "Sessions by Date" in index_content

    def test_generate_index_includes_session_links(self) -> None:
        """Test that index contains links to sessions."""
        from datetime import datetime
        from session_insights.cli import _generate_index
        from session_insights.core import AnalysisResult, SessionStats
        from session_insights.parsers.models import BaseSession

        session = BaseSession(
            session_id="test-session-abc",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            source="claude",
            summary="Test session for linking",
        )

        result = AnalysisResult(
            sessions=[session],
            patterns=[],
            stats=SessionStats(
                total_sessions=1,
                total_duration_minutes=0.0,
                date_range=None,
            ),
        )

        daily_sessions = {session.start_time.date(): [session]}
        index_content = _generate_index([session], daily_sessions, result)

        # Should contain wiki-style links
        assert "[[" in index_content
        assert "sessions/" in index_content
