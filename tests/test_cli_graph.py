"""Tests for the graph CLI commands (build, stats, query)."""

import json
import re
from pathlib import Path

import pytest
from distill.cli import app
from typer.testing import CliRunner

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner(env={"NO_COLOR": "1", "FORCE_COLOR": None})


def _create_session_jsonl(tmp_path: Path) -> Path:
    """Create a minimal .claude directory with a valid JSONL session file.

    Returns the parent directory containing .claude/ (i.e., the --claude-dir target).
    """
    project_dir = tmp_path / ".claude" / "projects" / "test-project"
    project_dir.mkdir(parents=True)

    user_entry = {
        "type": "user",
        "sessionId": "test-sess",
        "timestamp": "2026-02-14T10:00:00Z",
        "cwd": str(tmp_path),
        "message": {"role": "user", "content": "Build something"},
    }
    assistant_entry = {
        "type": "assistant",
        "sessionId": "test-sess",
        "timestamp": "2026-02-14T10:01:00Z",
        "cwd": str(tmp_path),
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "I'll build it."}],
        },
    }

    session_file = project_dir / "test-session.jsonl"
    with open(session_file, "w") as f:
        f.write(json.dumps(user_entry) + "\n")
        f.write(json.dumps(assistant_entry) + "\n")

    return tmp_path / ".claude"


class TestGraphBuild:
    """Tests for the 'graph build' command."""

    def test_build_help(self, runner: CliRunner) -> None:
        """Test that graph build --help works."""
        result = runner.invoke(app, ["graph", "build", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "--claude-dir" in output
        assert "--output" in output

    def test_build_creates_graph_store(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that graph build creates a graph store JSON file."""
        claude_dir = _create_session_jsonl(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
                "--quiet",
            ],
        )
        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"

        # Verify graph store file was created
        store_file = output_dir / ".distill-graph.json"
        assert store_file.exists(), f"Graph store file not created. Output: {result.output}"

        # Verify it contains valid JSON with nodes
        data = json.loads(store_file.read_text())
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_build_with_claude_dir_fixture(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test graph build with --claude-dir pointing to fixture data."""
        claude_dir = _create_session_jsonl(tmp_path)
        output_dir = tmp_path / "graph-output"
        output_dir.mkdir()

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
                "--quiet",
            ],
        )
        assert result.exit_code == 0

        # The store should have at least a session node
        store_file = output_dir / ".distill-graph.json"
        data = json.loads(store_file.read_text())
        node_types = [n["node_type"] for n in data["nodes"]]
        assert "session" in node_types

    def test_build_prints_stats(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that graph build prints stats when not quiet."""
        claude_dir = _create_session_jsonl(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        # Should print some stats about what was built
        assert "node" in output.lower() or "session" in output.lower()

    def test_build_empty_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test graph build with an empty claude directory."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
                "--quiet",
            ],
        )
        # Should succeed even with no sessions (just no nodes)
        assert result.exit_code == 0


class TestGraphStats:
    """Tests for the 'graph stats' command."""

    def test_stats_help(self, runner: CliRunner) -> None:
        """Test that graph stats --help works."""
        result = runner.invoke(app, ["graph", "stats", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "--output" in output

    def test_stats_shows_counts(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that graph stats shows node and edge counts."""
        # First build a graph
        claude_dir = _create_session_jsonl(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
                "--quiet",
            ],
        )

        # Then check stats
        result = runner.invoke(
            app,
            ["graph", "stats", "--output", str(output_dir)],
        )
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "node" in output.lower()
        assert "edge" in output.lower()

    def test_stats_empty_graph(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that stats on an empty graph shows zeros."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(
            app,
            ["graph", "stats", "--output", str(output_dir)],
        )
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        # Should show 0 nodes and 0 edges
        assert "0" in output


class TestGraphQuery:
    """Tests for the 'graph query' command."""

    def test_query_help(self, runner: CliRunner) -> None:
        """Test that graph query --help works."""
        result = runner.invoke(app, ["graph", "query", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "--output" in output
        assert "--context" in output

    def test_query_known_entity(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test graph query returns focus + neighbors for a known entity."""
        # Build a graph first
        claude_dir = _create_session_jsonl(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
                "--quiet",
            ],
        )

        # Query for the session (should exist)
        result = runner.invoke(
            app,
            ["graph", "query", "test-sess", "--output", str(output_dir)],
        )
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        # Should show the focus entity
        assert "test-sess" in output

    def test_query_unknown_entity(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test graph query for an entity not in the graph."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(
            app,
            ["graph", "query", "nonexistent-thing", "--output", str(output_dir)],
        )
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        # Should indicate nothing was found
        assert "not found" in output.lower() or "no" in output.lower()

    def test_query_context_mode(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test graph query --context renders markdown text."""
        # Build a graph first
        claude_dir = _create_session_jsonl(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        runner.invoke(
            app,
            [
                "graph",
                "build",
                "--claude-dir",
                str(claude_dir),
                "--output",
                str(output_dir),
                "--quiet",
            ],
        )

        result = runner.invoke(
            app,
            [
                "graph",
                "query",
                "test-sess",
                "--output",
                str(output_dir),
                "--context",
            ],
        )
        assert result.exit_code == 0
        # Context mode should produce markdown-style output
        output = _strip_ansi(result.output)
        assert len(output.strip()) > 0
