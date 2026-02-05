"""Smoke tests for the CLI."""

import pytest
from click.testing import CliRunner

from session_insights.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


class TestCLI:
    """Tests for the CLI entry point."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Test that --help works on the main command."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Session Insights" in result.output
        assert "analyze" in result.output

    def test_main_version(self, runner: CliRunner) -> None:
        """Test that --version works."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "session-insights" in result.output
        assert "0.1.0" in result.output

    def test_analyze_help(self, runner: CliRunner) -> None:
        """Test that analyze --help works."""
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "SESSION_PATH" in result.output
        assert "--output" in result.output
        assert "--format" in result.output

    def test_analyze_missing_path(self, runner: CliRunner) -> None:
        """Test that analyze requires a session path."""
        result = runner.invoke(main, ["analyze"])
        assert result.exit_code != 0
        assert "SESSION_PATH" in result.output or "Missing argument" in result.output
