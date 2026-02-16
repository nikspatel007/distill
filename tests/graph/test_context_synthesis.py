"""Tests for context data gathering and synthesis prompt generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from distill.graph.extractor import SessionGraphExtractor
from distill.graph.prompts import get_context_prompt
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore
from distill.graph.synthesizer import (
    ContextSynthesisError,
    inject_context,
    synthesize_context,
)
from distill.parsers.models import BaseSession, Message, ToolCall


def _make_session(
    session_id: str,
    project: str,
    summary: str,
    timestamp: datetime,
    messages: list[Message] | None = None,
    tool_calls: list[ToolCall] | None = None,
    metadata: dict | None = None,
) -> BaseSession:
    return BaseSession(
        session_id=session_id,
        timestamp=timestamp,
        project=project,
        summary=summary,
        messages=messages or [],
        tool_calls=tool_calls or [],
        metadata=metadata or {},
    )


@pytest.fixture()
def now() -> datetime:
    return datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def populated_store(now: datetime) -> GraphStore:
    """Build a graph with several sessions for testing gather_context_data."""
    store = GraphStore()
    ext = SessionGraphExtractor(store)

    # Recent human session (2h ago)
    s1 = _make_session(
        session_id="s1",
        project="distill",
        summary="Build knowledge graph extractor",
        timestamp=now - timedelta(hours=2),
        messages=[
            Message(role="user", content="Build the graph extractor"),
            Message(role="assistant", content="Working on it"),
        ],
        tool_calls=[
            ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/graph/extractor.py"}),
            ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/graph/models.py"}),
            ToolCall(tool_name="Bash", arguments={"command": "pytest tests/"}, result="20 passed"),
        ],
        metadata={"cwd": "/proj"},
    )

    # Recent human session (30min ago)
    s2 = _make_session(
        session_id="s2",
        project="distill",
        summary="Add context scoring",
        timestamp=now - timedelta(minutes=30),
        messages=[
            Message(role="user", content="Add context scoring to the graph"),
            Message(role="assistant", content="On it"),
        ],
        tool_calls=[
            ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/graph/context.py"}),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/graph/"},
                result="FAILED - AssertionError",
            ),
            ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/graph/context.py"}),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/graph/"},
                result="All 30 tests passed",
            ),
        ],
        metadata={"cwd": "/proj"},
    )

    # Machine session (should be excluded)
    s3 = _make_session(
        session_id="s3",
        project="distill",
        summary="Extract entities from text",
        timestamp=now - timedelta(hours=1),
        messages=[
            Message(role="user", content="Extract entities from this JSON blob"),
            Message(role="assistant", content='{"result": "ok"}'),
        ],
        tool_calls=[],
        metadata={},
    )

    # Different project session
    s4 = _make_session(
        session_id="s4",
        project="vermas",
        summary="Fix agent spawning",
        timestamp=now - timedelta(hours=3),
        messages=[
            Message(role="user", content="Fix the agent spawning timeout"),
            Message(role="assistant", content="Looking into it"),
        ],
        tool_calls=[
            ToolCall(tool_name="Edit", arguments={"file_path": "/vermas/src/spawn.py"}),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/"},
                result="All 10 tests passed",
            ),
        ],
        metadata={"cwd": "/vermas"},
    )

    # Old session (outside 72h window)
    s5 = _make_session(
        session_id="s5",
        project="distill",
        summary="Old session",
        timestamp=now - timedelta(hours=100),
        messages=[
            Message(role="user", content="Do something old"),
            Message(role="assistant", content="Done"),
        ],
        tool_calls=[
            ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/old.py"}),
        ],
        metadata={"cwd": "/proj"},
    )

    for s in [s1, s2, s3, s4, s5]:
        ext.extract(s)

    return store


# -- gather_context_data() ---------------------------------------------------


class TestGatherContextData:
    def test_returns_recent_human_sessions_only(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        # Should have s1 and s2, not s3 (machine) or s5 (old)
        session_ids = [s["id"] for s in data["sessions"]]
        assert "s1" in session_ids
        assert "s2" in session_ids
        assert "s3" not in session_ids  # machine
        assert "s5" not in session_ids  # old

    def test_sessions_ordered_by_recency(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        hours = [s["hours_ago"] for s in data["sessions"]]
        assert hours == sorted(hours)  # nearest first

    def test_includes_files_modified(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        s1_data = next(s for s in data["sessions"] if s["id"] == "s1")
        assert "src/graph/extractor.py" in s1_data["files_modified"]
        assert "src/graph/models.py" in s1_data["files_modified"]

    def test_includes_problems_with_resolution(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        s2_data = next(s for s in data["sessions"] if s["id"] == "s2")
        assert len(s2_data["problems"]) == 1
        assert s2_data["problems"][0]["resolved"] is True

    def test_includes_entities(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        s1_data = next(s for s in data["sessions"] if s["id"] == "s1")
        assert "pytest" in s1_data["entities"]

    def test_includes_other_projects(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        assert len(data["other_projects"]) >= 1
        projects = [op["project"] for op in data["other_projects"]]
        assert "vermas" in projects

    def test_no_other_projects_without_filter(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data()  # no project filter

        # other_projects is only populated when filtering by project
        assert data["other_projects"] == []

    def test_respects_max_sessions(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(max_sessions=1)

        assert len(data["sessions"]) <= 1

    def test_respects_max_hours(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(max_hours=1.0)

        # Only s2 (30min ago) should be within 1 hour
        session_ids = [s["id"] for s in data["sessions"]]
        assert "s2" in session_ids
        assert "s1" not in session_ids  # 2h ago

    def test_active_files_sorted_by_recency(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")

        active_files = data["active_files"]
        hours = [f["hours_ago"] for f in active_files]
        assert hours == sorted(hours)  # most recent first

    def test_empty_graph_returns_empty(self, now: datetime):
        store = GraphStore()
        query = GraphQuery(store, now=now)
        data = query.gather_context_data()

        assert data["sessions"] == []
        assert data["top_entities"] == []
        assert data["active_files"] == []


# -- Prompt formatting -------------------------------------------------------


class TestContextPrompt:
    def test_prompt_contains_session_data(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")
        prompt = get_context_prompt(data)

        assert "Build knowledge graph extractor" in prompt
        assert "Add context scoring" in prompt
        assert "src/graph/extractor.py" in prompt

    def test_prompt_contains_system_instructions(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")
        prompt = get_context_prompt(data)

        assert "context synthesizer" in prompt
        assert "second person" in prompt

    def test_prompt_shows_problem_resolution(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")
        prompt = get_context_prompt(data)

        assert "RESOLVED" in prompt

    def test_prompt_shows_other_projects(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        data = query.gather_context_data(project="distill")
        prompt = get_context_prompt(data)

        assert "vermas" in prompt


# -- Synthesizer (mocked) ---------------------------------------------------


class TestSynthesizer:
    def test_synthesize_calls_claude_cli(self):
        data = {"project": "test", "sessions": [{"id": "s1", "summary": "Test"}]}

        with patch("distill.graph.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "# Context\nYou were working on tests."
            mock_run.return_value.stderr = ""

            result = synthesize_context(data)

        assert result == "# Context\nYou were working on tests."
        mock_run.assert_called_once()

        # Verify claude -p was called
        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"

    def test_synthesize_passes_model_option(self):
        data = {"project": "test", "sessions": []}

        with patch("distill.graph.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "context"
            mock_run.return_value.stderr = ""

            synthesize_context(data, model="claude-sonnet-4-5-20250929")

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-sonnet-4-5-20250929" in cmd

    def test_synthesize_raises_on_cli_error(self):
        data = {"project": "test", "sessions": []}

        with patch("distill.graph.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "API error"

            with pytest.raises(ContextSynthesisError, match="exited 1"):
                synthesize_context(data)

    def test_synthesize_raises_on_timeout(self):
        data = {"project": "test", "sessions": []}

        with patch("distill.graph.synthesizer.subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("claude", 60)

            with pytest.raises(ContextSynthesisError, match="timed out"):
                synthesize_context(data)

    def test_synthesize_raises_on_missing_cli(self):
        data = {"project": "test", "sessions": []}

        with patch("distill.graph.synthesizer.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("claude")

            with pytest.raises(ContextSynthesisError, match="not found"):
                synthesize_context(data)

    def test_synthesize_clears_claudecode_env(self):
        data = {"project": "test", "sessions": []}

        with patch("distill.graph.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "context"
            mock_run.return_value.stderr = ""

            with patch.dict("os.environ", {"CLAUDECODE": "1"}):
                synthesize_context(data)

            env = mock_run.call_args.kwargs.get("env", {})
            assert "CLAUDECODE" not in env


# -- inject_context ---------------------------------------------------------


class TestInjectContext:
    def test_creates_new_file(self, tmp_path: Path):
        target = tmp_path / "CLAUDE.md"
        inject_context("## Context\nYou were working on tests.", target)

        content = target.read_text()
        assert "<!-- DISTILL-CONTEXT-START -->" in content
        assert "<!-- DISTILL-CONTEXT-END -->" in content
        assert "You were working on tests." in content

    def test_appends_to_existing_file(self, tmp_path: Path):
        target = tmp_path / "CLAUDE.md"
        target.write_text("# My Project\n\nHand-written content.\n")

        inject_context("## Context\nNew context.", target)

        content = target.read_text()
        assert content.startswith("# My Project\n")
        assert "Hand-written content." in content
        assert "New context." in content
        assert "<!-- DISTILL-CONTEXT-START -->" in content

    def test_replaces_existing_block(self, tmp_path: Path):
        target = tmp_path / "CLAUDE.md"
        target.write_text(
            "# Project\n\n"
            "<!-- DISTILL-CONTEXT-START -->\nOld context.\n<!-- DISTILL-CONTEXT-END -->\n\n"
            "# Other section\n"
        )

        inject_context("Updated context.", target)

        content = target.read_text()
        assert "Old context." not in content
        assert "Updated context." in content
        assert "# Project" in content
        assert "# Other section" in content
        # Should have exactly one start/end marker pair
        assert content.count("DISTILL-CONTEXT-START") == 1
        assert content.count("DISTILL-CONTEXT-END") == 1

    def test_preserves_surrounding_content(self, tmp_path: Path):
        target = tmp_path / "CLAUDE.md"
        original = (
            "# Header\n\nBefore.\n\n"
            "<!-- DISTILL-CONTEXT-START -->\nOld.\n<!-- DISTILL-CONTEXT-END -->\n\n"
            "After.\n"
        )
        target.write_text(original)

        inject_context("New.", target)

        content = target.read_text()
        assert "Before." in content
        assert "After." in content
        assert "New." in content
        assert "Old." not in content
