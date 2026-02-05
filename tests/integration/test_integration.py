"""Integration tests for the session-insights CLI and pipeline."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from session_insights.core import (
    AnalysisResult,
    analyze,
    discover_sessions,
    parse_session_file,
)
from session_insights.formatters.obsidian import ObsidianFormatter
from session_insights.models import BaseSession, ToolUsage


@pytest.fixture
def sample_claude_history(tmp_path: Path) -> Path:
    """Create a sample .claude directory with history.jsonl."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Create sample history entries
    now = datetime.now()
    entries = [
        {
            "display": "Help me fix the authentication bug",
            "timestamp": int((now - timedelta(hours=2)).timestamp() * 1000),
            "project": "/home/user/project",
        },
        {
            "display": "Add unit tests for the login module",
            "timestamp": int((now - timedelta(hours=1)).timestamp() * 1000),
            "project": "/home/user/project",
        },
        {
            "display": "Refactor the database connection pool",
            "timestamp": int(now.timestamp() * 1000),
            "project": "/home/user/project2",
        },
    ]

    history_file = claude_dir / "history.jsonl"
    with history_file.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return tmp_path


@pytest.fixture
def sample_vermas_session(tmp_path: Path) -> Path:
    """Create a sample .vermas directory with session data."""
    vermas_dir = tmp_path / ".vermas" / "agents" / "dev"
    vermas_dir.mkdir(parents=True)

    session_data = {
        "id": "vermas-session-001",
        "timestamp": int(datetime.now().timestamp() * 1000),
        "summary": "Implemented feature X",
        "tools": ["Read", "Write", "Bash"],
    }

    session_file = vermas_dir / "session.json"
    session_file.write_text(json.dumps(session_data), encoding="utf-8")

    return tmp_path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create an output directory for notes."""
    output = tmp_path / "obsidian_notes"
    output.mkdir()
    return output


class TestDiscoverSessions:
    """Tests for session discovery."""

    def test_discover_claude_sessions(self, sample_claude_history: Path) -> None:
        """Test discovering Claude session files."""
        discovered = discover_sessions(sample_claude_history, sources=["claude"])

        assert "claude" in discovered
        assert len(discovered["claude"]) >= 1
        assert any("history.jsonl" in str(f) for f in discovered["claude"])

    def test_discover_vermas_sessions(self, sample_vermas_session: Path) -> None:
        """Test discovering VerMAS session files."""
        discovered = discover_sessions(sample_vermas_session, sources=["vermas"])

        assert "vermas" in discovered
        assert len(discovered["vermas"]) >= 1
        assert any("session.json" in str(f) for f in discovered["vermas"])

    def test_discover_all_sources(
        self, sample_claude_history: Path, sample_vermas_session: Path
    ) -> None:
        """Test discovering from all sources."""
        # Combine the sample directories
        discovered = discover_sessions(sample_claude_history, sources=None)

        # Should find at least claude
        assert len(discovered) >= 1

    def test_discover_nonexistent_source(self, tmp_path: Path) -> None:
        """Test discovering with nonexistent source."""
        discovered = discover_sessions(tmp_path, sources=["nonexistent"])

        assert discovered == {}

    def test_discover_empty_directory(self, tmp_path: Path) -> None:
        """Test discovering in empty directory."""
        discovered = discover_sessions(tmp_path)

        assert discovered == {}


class TestParseSessionFile:
    """Tests for parsing session files."""

    def test_parse_claude_history(self, sample_claude_history: Path) -> None:
        """Test parsing Claude history.jsonl."""
        history_file = sample_claude_history / ".claude" / "history.jsonl"
        sessions = parse_session_file(history_file, "claude")

        assert len(sessions) == 3
        assert all(isinstance(s, BaseSession) for s in sessions)
        assert all(s.source == "claude" for s in sessions)

    def test_parse_vermas_session(self, sample_vermas_session: Path) -> None:
        """Test parsing VerMAS session.json."""
        session_file = list(sample_vermas_session.glob("**/*.json"))[0]
        sessions = parse_session_file(session_file, "vermas")

        assert len(sessions) == 1
        assert sessions[0].source == "vermas"
        assert sessions[0].id == "vermas-session-001"

    def test_parse_invalid_file(self, tmp_path: Path) -> None:
        """Test parsing invalid JSON file."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json {{{", encoding="utf-8")

        sessions = parse_session_file(invalid_file, "unknown")
        assert sessions == []

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        """Test parsing nonexistent file."""
        sessions = parse_session_file(tmp_path / "nonexistent.json", "unknown")
        assert sessions == []


class TestAnalyze:
    """Tests for session analysis."""

    def test_analyze_empty_sessions(self) -> None:
        """Test analyzing empty session list."""
        result = analyze([])

        assert isinstance(result, AnalysisResult)
        assert result.sessions == []
        assert result.stats.total_sessions == 0

    def test_analyze_single_session(self) -> None:
        """Test analyzing a single session."""
        session = BaseSession(
            id="test-001",
            start_time=datetime(2024, 1, 15, 10, 0),
            end_time=datetime(2024, 1, 15, 11, 0),
            source="claude",
            summary="Test session",
        )
        result = analyze([session])

        assert len(result.sessions) == 1
        assert result.stats.total_sessions == 1
        assert result.stats.sources["claude"] == 1

    def test_analyze_multiple_sessions(self) -> None:
        """Test analyzing multiple sessions."""
        sessions = [
            BaseSession(
                id=f"test-{i:03d}",
                start_time=datetime(2024, 1, 15, 10 + i, 0),
                end_time=datetime(2024, 1, 15, 10 + i, 30),
                source="claude" if i % 2 == 0 else "vermas",
                summary=f"Session {i}",
                tools_used=[ToolUsage(name="Read", count=i + 1)],
            )
            for i in range(5)
        ]
        result = analyze(sessions)

        assert result.stats.total_sessions == 5
        assert len(result.stats.sources) == 2
        assert len(result.patterns) > 0

    def test_analyze_detects_patterns(self) -> None:
        """Test that analysis detects patterns."""
        sessions = [
            BaseSession(
                id=f"test-{i:03d}",
                start_time=datetime(2024, 1, 15, 14, 0),  # All at 2 PM
                source="claude",
                tools_used=[ToolUsage(name="Read", count=5)],
            )
            for i in range(10)
        ]
        result = analyze(sessions)

        # Should detect peak hour pattern
        peak_hour_pattern = next(
            (p for p in result.patterns if p.name == "peak_activity_hour"), None
        )
        assert peak_hour_pattern is not None
        assert peak_hour_pattern.metadata["hour"] == 14


class TestEndToEndPipeline:
    """End-to-end integration tests."""

    def test_full_pipeline(
        self, sample_claude_history: Path, output_dir: Path
    ) -> None:
        """Test the complete analysis pipeline."""
        # 1. Discover sessions
        discovered = discover_sessions(sample_claude_history, sources=["claude"])
        assert discovered

        # 2. Parse sessions
        all_sessions: list[BaseSession] = []
        for source, files in discovered.items():
            for file_path in files:
                sessions = parse_session_file(file_path, source)
                all_sessions.extend(sessions)

        assert len(all_sessions) > 0

        # 3. Analyze
        result = analyze(all_sessions)
        assert result.stats.total_sessions > 0

        # 4. Format and write
        formatter = ObsidianFormatter(include_conversation=False)
        sessions_dir = output_dir / "sessions"
        sessions_dir.mkdir()

        for session in result.sessions:
            note = formatter.format_session(session)
            note_path = sessions_dir / f"{session.note_name}.md"
            note_path.write_text(note, encoding="utf-8")

        # Verify output
        md_files = list(sessions_dir.glob("*.md"))
        assert len(md_files) == len(result.sessions)

    def test_pipeline_with_date_filter(
        self, sample_claude_history: Path
    ) -> None:
        """Test pipeline with date filtering."""
        discovered = discover_sessions(sample_claude_history, sources=["claude"])

        all_sessions: list[BaseSession] = []
        for source, files in discovered.items():
            for file_path in files:
                sessions = parse_session_file(file_path, source)
                all_sessions.extend(sessions)

        # Filter to future date (should get nothing)
        future_date = (datetime.now() + timedelta(days=1)).date()
        filtered = [s for s in all_sessions if s.start_time.date() >= future_date]

        assert len(filtered) == 0


class TestCLIExitCodes:
    """Tests for CLI exit codes and error handling."""

    @pytest.fixture
    def cli_path(self) -> Path:
        """Get path to CLI module."""
        return Path(__file__).parents[2] / "src" / "session_insights" / "cli.py"

    def test_cli_version(self, cli_path: Path) -> None:
        """Test CLI version flag."""
        result = subprocess.run(
            [sys.executable, "-m", "session_insights.cli", "--version"],
            capture_output=True,
            text=True,
            cwd=cli_path.parents[2],
            env={**os.environ, "PYTHONPATH": str(cli_path.parents[2] / "src")},
        )
        # Allow either 0 or 1 (typer raises Exit on version)
        assert result.returncode in (0, 1)
        # Should contain version info
        assert "session-insights" in result.stdout or "0.1.0" in result.stdout

    def test_cli_missing_output(self, cli_path: Path, tmp_path: Path) -> None:
        """Test CLI with missing required output option."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "session_insights.cli",
                "analyze",
                "--dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=cli_path.parents[2],
            env={**os.environ, "PYTHONPATH": str(cli_path.parents[2] / "src")},
        )
        # Should fail due to missing required --output
        assert result.returncode != 0

    def test_cli_invalid_date(
        self, cli_path: Path, tmp_path: Path, output_dir: Path
    ) -> None:
        """Test CLI with invalid date format."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "session_insights.cli",
                "analyze",
                "--dir",
                str(tmp_path),
                "--output",
                str(output_dir),
                "--since",
                "not-a-date",
            ],
            capture_output=True,
            text=True,
            cwd=cli_path.parents[2],
            env={**os.environ, "PYTHONPATH": str(cli_path.parents[2] / "src")},
        )
        assert result.returncode == 1
        assert "Invalid date" in result.stdout or "Invalid date" in result.stderr or "Error" in result.stdout
