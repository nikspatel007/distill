"""Tests for SessionGraphExtractor — Tier 1-2 heuristic extraction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from distill.graph.extractor import PROJECT_ALIASES, SessionGraphExtractor
from distill.graph.models import EdgeType, NodeType
from distill.graph.store import GraphStore
from distill.parsers.models import (
    AgentSignal,
    BaseSession,
    CycleInfo,
    Message,
    ToolCall,
)


def _make_session(
    session_id: str = "sess-001",
    project: str = "distill",
    summary: str = "Implement graph extractor",
    timestamp: datetime | None = None,
    messages: list[Message] | None = None,
    tool_calls: list[ToolCall] | None = None,
    metadata: dict | None = None,
    cycle_info: CycleInfo | None = None,
    signals: list[AgentSignal] | None = None,
) -> BaseSession:
    """Helper to create a BaseSession with sensible defaults."""
    ts = timestamp or datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
    return BaseSession(
        session_id=session_id,
        timestamp=ts,
        project=project,
        summary=summary,
        messages=messages or [],
        tool_calls=tool_calls or [],
        metadata=metadata or {},
        cycle_info=cycle_info,
        signals=signals or [],
    )


# -- Session node -----------------------------------------------------------


class TestSessionNode:
    def test_creates_session_node(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session()
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        assert node.node_type == NodeType.SESSION
        assert node.name == "sess-001"
        assert node.source_id == "sess-001"

    def test_session_node_uses_summary_as_name_when_present(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="Fix the login bug")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        # name is session_id (for stable keys), summary in properties
        assert node.source_id == "sess-001"

    def test_session_node_properties(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
                ToolCall(tool_name="Edit", arguments={"file_path": "/b.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        assert node.properties["project"] == "distill"
        assert node.properties["tool_count"] == 2

    def test_session_node_with_empty_summary_uses_session_id(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        assert node.name == "sess-001"


# -- Project node + edge ---------------------------------------------------


class TestProjectNode:
    def test_creates_project_node_and_edge(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(project="distill")
        extractor.extract(session)

        proj = store.get_node("project:distill")
        assert proj is not None
        assert proj.node_type == NodeType.PROJECT

        edges = store.find_edges(
            source_key="session:sess-001",
            target_key="project:distill",
            edge_type=EdgeType.EXECUTES_IN,
        )
        assert len(edges) == 1

    def test_no_project_node_when_project_empty(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(project="")
        extractor.extract(session)

        projects = store.find_nodes(node_type=NodeType.PROJECT)
        assert len(projects) == 0


# -- Goal node + edge ------------------------------------------------------


class TestGoalNode:
    def test_extracts_goal_from_first_user_message(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Please fix the authentication bug"),
                Message(role="assistant", content="I'll look into it"),
                Message(role="user", content="Also update the docs"),
            ],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 1
        assert goals[0].name == "Please fix the authentication bug"

        edges = store.find_edges(
            source_key="session:sess-001",
            edge_type=EdgeType.MOTIVATED_BY,
        )
        assert len(edges) == 1

    def test_goal_truncated_to_200_chars(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        long_message = "A" * 300  # under 500 threshold, so goal created
        session = _make_session(
            messages=[Message(role="user", content=long_message)],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 1
        assert len(goals[0].name) == 200

    def test_no_goal_when_no_user_messages(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[Message(role="assistant", content="Hello")],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 0


# -- File nodes + edges -----------------------------------------------------


class TestFileNodes:
    def test_edit_creates_modifies_edge(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/home/user/project/src/main.py"},
                ),
            ],
            metadata={"cwd": "/home/user/project"},
        )
        extractor.extract(session)

        file_node = store.get_node("file:src/main.py")
        assert file_node is not None

        edges = store.find_edges(
            source_key="session:sess-001",
            edge_type=EdgeType.MODIFIES,
        )
        assert len(edges) == 1
        assert edges[0].weight == 1.0

    def test_write_creates_modifies_edge(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    arguments={"file_path": "/proj/src/utils.py"},
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        edges = store.find_edges(edge_type=EdgeType.MODIFIES)
        assert len(edges) == 1

    def test_notebook_edit_creates_modifies_edge(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="NotebookEdit",
                    arguments={"file_path": "/proj/notebook.ipynb"},
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        edges = store.find_edges(edge_type=EdgeType.MODIFIES)
        assert len(edges) == 1

    def test_multiple_edits_increment_weight(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/a.py"}),
                ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/a.py"}),
                ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/a.py"}),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        edges = store.find_edges(edge_type=EdgeType.MODIFIES)
        assert len(edges) == 1
        assert edges[0].weight == 3.0

    def test_read_creates_reads_edge(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/proj/src/config.py"},
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        edges = store.find_edges(edge_type=EdgeType.READS)
        assert len(edges) == 1

    def test_glob_creates_reads_edge_using_path_argument(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Glob",
                    arguments={"path": "/proj/src/utils"},
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        edges = store.find_edges(edge_type=EdgeType.READS)
        assert len(edges) == 1

    def test_grep_creates_reads_edge(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Grep",
                    arguments={"path": "/proj/src/"},
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        edges = store.find_edges(edge_type=EdgeType.READS)
        assert len(edges) == 1

    def test_no_reads_edge_for_modified_file(self):
        """If a file is both read and modified, only modifies edge should exist."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/proj/src/a.py"}),
                ToolCall(tool_name="Edit", arguments={"file_path": "/proj/src/a.py"}),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        mod_edges = store.find_edges(edge_type=EdgeType.MODIFIES)
        read_edges = store.find_edges(edge_type=EdgeType.READS)
        assert len(mod_edges) == 1
        assert len(read_edges) == 0

    def test_normalizes_absolute_paths_to_relative(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/home/user/myproject/src/graph/models.py"},
                ),
            ],
            metadata={"cwd": "/home/user/myproject"},
        )
        extractor.extract(session)

        node = store.get_node("file:src/graph/models.py")
        assert node is not None

    def test_normalizes_paths_with_anchor_fallback(self):
        """When cwd doesn't match, use known anchors like src/, tests/, etc."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/some/other/path/src/graph/models.py"},
                ),
            ],
            metadata={"cwd": "/different/path"},
        )
        extractor.extract(session)

        node = store.get_node("file:src/graph/models.py")
        assert node is not None

    def test_skips_tool_calls_without_file_path(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(tool_name="Bash", arguments={"command": "ls -la"}),
            ],
        )
        extractor.extract(session)

        files = store.find_nodes(node_type=NodeType.FILE)
        assert len(files) == 0


# -- Problem nodes ----------------------------------------------------------


class TestProblemNodes:
    def test_extracts_problem_from_failed_bash(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/"},
                    result="FAILED tests/test_foo.py::test_bar - AssertionError",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 1
        assert "command" in problems[0].properties
        assert "error_snippet" in problems[0].properties

        edges = store.find_edges(
            source_key="session:sess-001",
            edge_type=EdgeType.BLOCKED_BY,
        )
        assert len(edges) == 1

    def test_detects_various_failure_patterns(self):
        patterns = [
            "ERROR: something went wrong",
            "Traceback (most recent call last):",
            "SyntaxError: invalid syntax",
            "ImportError: No module named foo",
            "Exception: unexpected failure",
            "FAIL: test_something",
        ]
        for pattern_result in patterns:
            store = GraphStore()
            extractor = SessionGraphExtractor(store)
            session = _make_session(
                tool_calls=[
                    ToolCall(
                        tool_name="Bash",
                        arguments={"command": "run_something"},
                        result=pattern_result,
                    ),
                ],
            )
            extractor.extract(session)

            problems = store.find_nodes(node_type=NodeType.PROBLEM)
            assert len(problems) == 1, f"Failed to detect pattern: {pattern_result}"

    def test_no_problem_for_successful_bash(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "echo hello"},
                    result="hello",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 0

    def test_no_problem_when_result_is_none(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "echo hello"},
                    result=None,
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 0


# -- Entity hints (Tier 2) -------------------------------------------------


class TestEntityHints:
    def test_extracts_known_tech_entity_from_tool_args(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ -x"},
                ),
            ],
        )
        extractor.extract(session)

        entity = store.get_node("entity:pytest")
        assert entity is not None
        assert entity.node_type == NodeType.ENTITY

        edges = store.find_edges(
            source_key="session:sess-001",
            target_key="entity:pytest",
            edge_type=EdgeType.USES,
        )
        assert len(edges) == 1

    def test_extracts_multiple_entities(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "mypy src/ && ruff check src/"},
                ),
            ],
        )
        extractor.extract(session)

        mypy = store.get_node("entity:mypy")
        ruff = store.get_node("entity:ruff")
        assert mypy is not None
        assert ruff is not None

    def test_no_duplicate_entity_edges(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(tool_name="Bash", arguments={"command": "pytest tests/a.py"}),
                ToolCall(tool_name="Bash", arguments={"command": "pytest tests/b.py"}),
            ],
        )
        extractor.extract(session)

        edges = store.find_edges(
            source_key="session:sess-001",
            target_key="entity:pytest",
            edge_type=EdgeType.USES,
        )
        # Upsert deduplicates by edge_key
        assert len(edges) == 1


# -- Session chaining -------------------------------------------------------


class TestSessionChaining:
    def test_creates_leads_to_edge_for_consecutive_sessions(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        t2 = t1 + timedelta(hours=2)

        s1 = _make_session(session_id="s1", project="distill", timestamp=t1)
        s2 = _make_session(session_id="s2", project="distill", timestamp=t2)

        extractor.extract(s1)
        extractor.extract(s2)

        edges = store.find_edges(
            source_key="session:s1",
            target_key="session:s2",
            edge_type=EdgeType.LEADS_TO,
        )
        assert len(edges) == 1
        assert edges[0].properties["gap_hours"] == 2.0

    def test_no_leads_to_for_large_time_gap(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        t2 = t1 + timedelta(hours=5)  # > 4 hours

        s1 = _make_session(session_id="s1", project="distill", timestamp=t1)
        s2 = _make_session(session_id="s2", project="distill", timestamp=t2)

        extractor.extract(s1)
        extractor.extract(s2)

        edges = store.find_edges(edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 0

    def test_no_leads_to_across_different_projects(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        t2 = t1 + timedelta(hours=1)

        s1 = _make_session(session_id="s1", project="distill", timestamp=t1)
        s2 = _make_session(session_id="s2", project="vermas", timestamp=t2)

        extractor.extract(s1)
        extractor.extract(s2)

        edges = store.find_edges(edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 0

    def test_chaining_tracks_per_project(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        t2 = t1 + timedelta(hours=1)
        t3 = t1 + timedelta(hours=2)

        s1 = _make_session(session_id="s1", project="distill", timestamp=t1)
        s2 = _make_session(session_id="s2", project="vermas", timestamp=t2)
        s3 = _make_session(session_id="s3", project="distill", timestamp=t3)

        extractor.extract(s1)
        extractor.extract(s2)
        extractor.extract(s3)

        # s1 -> s3 for distill (2hr gap, same project)
        edges = store.find_edges(
            source_key="session:s1",
            target_key="session:s3",
            edge_type=EdgeType.LEADS_TO,
        )
        assert len(edges) == 1

    def test_no_chaining_when_no_project(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        t2 = t1 + timedelta(hours=1)

        s1 = _make_session(session_id="s1", project="", timestamp=t1)
        s2 = _make_session(session_id="s2", project="", timestamp=t2)

        extractor.extract(s1)
        extractor.extract(s2)

        edges = store.find_edges(edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 0


# -- Timezone awareness -----------------------------------------------------


class TestTimezoneAwareness:
    def test_handles_naive_timestamps(self):
        """Naive timestamps should be treated as UTC without crashing."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0)  # naive
        t2 = datetime(2026, 2, 14, 11, 0, 0)  # naive

        s1 = _make_session(session_id="s1", project="distill", timestamp=t1)
        s2 = _make_session(session_id="s2", project="distill", timestamp=t2)

        extractor.extract(s1)
        extractor.extract(s2)

        edges = store.find_edges(edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 1


# -- Integration: full session extraction -----------------------------------


class TestFullExtraction:
    def test_full_session_creates_expected_graph(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        session = _make_session(
            session_id="full-test",
            project="distill",
            summary="Add graph extractor",
            messages=[
                Message(role="user", content="Implement the graph extractor"),
                Message(role="assistant", content="Working on it..."),
            ],
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/proj/src/models.py"},
                ),
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/proj/src/extractor.py"},
                ),
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/proj/src/extractor.py"},
                ),
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ -x"},
                    result="FAILED tests/test_ex.py - AssertionError",
                ),
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/proj/src/extractor.py"},
                ),
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "ruff check src/"},
                    result="All checks passed",
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        # Session node
        assert store.get_node("session:full-test") is not None

        # Project node + edge
        assert store.get_node("project:distill") is not None
        assert len(store.find_edges(edge_type=EdgeType.EXECUTES_IN)) == 1

        # Goal node
        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 1
        assert goals[0].name == "Implement the graph extractor"

        # File nodes: models.py (read), extractor.py (modified x3)
        assert store.get_node("file:src/models.py") is not None
        assert store.get_node("file:src/extractor.py") is not None

        # modifies edge with weight 3 for extractor.py
        mod_edges = store.find_edges(
            target_key="file:src/extractor.py",
            edge_type=EdgeType.MODIFIES,
        )
        assert len(mod_edges) == 1
        assert mod_edges[0].weight == 3.0

        # reads edge for models.py only (not extractor.py since it's modified)
        read_edges = store.find_edges(edge_type=EdgeType.READS)
        assert len(read_edges) == 1
        assert read_edges[0].target_key == "file:src/models.py"

        # Problem node from failed pytest
        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 1

        # Entity nodes: pytest, ruff
        assert store.get_node("entity:pytest") is not None
        assert store.get_node("entity:ruff") is not None


# -- Session classification -------------------------------------------------


class TestSessionClassification:
    def test_human_session_has_tool_calls_and_messages(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Fix the bug"),
                Message(role="assistant", content="On it"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        assert node.properties["session_type"] == "human"

    def test_machine_session_no_tool_calls_single_turn(self):
        """Machine session: ≤1 user message AND 0 tool calls."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Extract named entities from this text..."),
                Message(role="assistant", content='{"entities": ["Python", "React"]}'),
            ],
            tool_calls=[],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        assert node.properties["session_type"] == "machine"

    def test_machine_session_no_messages(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(messages=[], tool_calls=[])
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node is not None
        assert node.properties["session_type"] == "machine"

    def test_human_session_multiple_user_turns(self):
        """Multiple user turns = interactive = human."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Do X"),
                Message(role="assistant", content="Done"),
                Message(role="user", content="Now do Y"),
                Message(role="assistant", content="Done"),
            ],
            tool_calls=[],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "human"

    def test_human_session_with_tool_calls_short_message(self):
        """Single turn + tool calls + short first message = human."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Read file"),
                Message(role="assistant", content="Here it is"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "human"

    def test_machine_session_long_message_with_tool_calls(self):
        """Single turn + tool calls + long first message = machine (structured prompt)."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        long_prompt = "You are writing an essay on X. " + "A" * 500
        session = _make_session(
            messages=[
                Message(role="user", content=long_prompt),
                Message(role="assistant", content="Here is the essay..."),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "machine"


# -- Goal filtering for machine sessions -----------------------------------


class TestGoalFiltering:
    def test_no_goal_for_machine_session(self):
        """Machine sessions should not create goal nodes."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Extract entities from this JSON blob"),
                Message(role="assistant", content='{"result": "ok"}'),
            ],
            tool_calls=[],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 0

    def test_no_goal_for_very_long_first_message(self):
        """First message >500 chars is likely a structured prompt, skip goal."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        long_prompt = "A" * 501
        session = _make_session(
            messages=[
                Message(role="user", content=long_prompt),
                Message(role="assistant", content="Done"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 0

    def test_goal_created_for_normal_human_session(self):
        """Normal human sessions with short first messages still get goals."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Fix the auth bug"),
                Message(role="assistant", content="Looking into it"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 1
        assert goals[0].name == "Fix the auth bug"

    def test_goal_at_boundary_500_chars(self):
        """Exactly 500 chars should still create a goal (boundary test)."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        boundary_msg = "A" * 500
        session = _make_session(
            messages=[
                Message(role="user", content=boundary_msg),
                Message(role="assistant", content="Done"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 1


# -- Problem detection improvements ----------------------------------------


class TestProblemFalsePositives:
    def test_no_problem_for_zero_errors(self):
        """'0 errors' in output should not be flagged as a problem."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "ruff check src/"},
                    result="Found 0 errors in 45 files",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 0

    def test_no_problem_for_no_errors(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "mypy src/"},
                    result="Success: no errors found",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 0

    def test_no_problem_for_all_tests_passed(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/"},
                    result="================== 50 passed in 3.2s ==================",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 0

    def test_real_error_still_detected(self):
        """Genuine errors should still be detected."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/"},
                    result="FAILED tests/test_foo.py::test_bar - AssertionError: 1 != 2",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 1

    def test_no_problem_for_error_in_filename(self):
        """'error' appearing in a filename should not trigger a problem."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "ls src/"},
                    result="error_handler.py\nerror_codes.py\nmain.py",
                ),
            ],
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 0

    def test_problem_resolution_tracking(self):
        """If a bash failure is followed by edits + bash success, mark resolved."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ -x"},
                    result="FAILED tests/test_foo.py - ValueError",
                ),
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/proj/src/foo.py"},
                ),
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ -x"},
                    result="All 10 tests passed",
                ),
            ],
            metadata={"cwd": "/proj"},
        )
        extractor.extract(session)

        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) == 1
        assert problems[0].properties.get("resolved") is True


# -- Entity co-occurrence ---------------------------------------------------


class TestEntityCoOccurrence:
    def test_creates_co_occurs_edges_between_entities(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ && mypy src/"},
                ),
            ],
        )
        extractor.extract(session)

        co_edges = store.find_edges(edge_type=EdgeType.CO_OCCURS)
        assert len(co_edges) >= 1

        # Check that pytest and mypy are connected
        edge_pairs = {(e.source_key, e.target_key) for e in co_edges}
        assert ("entity:mypy", "entity:pytest") in edge_pairs or (
            "entity:pytest",
            "entity:mypy",
        ) in edge_pairs

    def test_no_co_occurs_for_single_entity(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/"},
                ),
            ],
        )
        extractor.extract(session)

        co_edges = store.find_edges(edge_type=EdgeType.CO_OCCURS)
        assert len(co_edges) == 0

    def test_co_occurs_weight_increments(self):
        """Multiple sessions with same entity pair should accumulate weight."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        for sid in ("s1", "s2"):
            session = _make_session(
                session_id=sid,
                tool_calls=[
                    ToolCall(
                        tool_name="Bash",
                        arguments={"command": "pytest tests/ && ruff check src/"},
                    ),
                ],
            )
            extractor.extract(session)

        co_edges = store.find_edges(edge_type=EdgeType.CO_OCCURS)
        assert len(co_edges) >= 1
        # Weight should be 2.0 (accumulated across 2 sessions)
        for edge in co_edges:
            if "pytest" in edge.source_key and "ruff" in edge.target_key:
                assert edge.weight == 2.0
                break
            elif "ruff" in edge.source_key and "pytest" in edge.target_key:
                assert edge.weight == 2.0
                break


# -- Project aliases --------------------------------------------------------


class TestProjectAliases:
    def test_alias_merges_renamed_project(self):
        """session-insights should be mapped to distill."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        s1 = _make_session(session_id="old", project="session-insights")
        s2 = _make_session(session_id="new", project="distill")

        extractor.extract(s1)
        extractor.extract(s2)

        # Should have ONE project node (distill), not two
        projects = store.find_nodes(node_type=NodeType.PROJECT)
        assert len(projects) == 1
        assert projects[0].name == "distill"

        # Both sessions should link to the same project
        edges = store.find_edges(
            target_key="project:distill",
            edge_type=EdgeType.EXECUTES_IN,
        )
        assert len(edges) == 2

    def test_alias_in_session_properties(self):
        """Session properties should use canonical project name."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(session_id="s1", project="session-insights")
        extractor.extract(session)

        node = store.get_node("session:s1")
        assert node.properties["project"] == "distill"

    def test_alias_enables_cross_rename_chaining(self):
        """Sessions across rename should still chain if within time window."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        t1 = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        t2 = t1 + timedelta(hours=2)

        s1 = _make_session(
            session_id="s1", project="session-insights", timestamp=t1
        )
        s2 = _make_session(session_id="s2", project="distill", timestamp=t2)

        extractor.extract(s1)
        extractor.extract(s2)

        # Should chain because both resolve to "distill"
        edges = store.find_edges(edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 1

    def test_unknown_project_passes_through(self):
        """Projects not in alias map should pass through unchanged."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(project="vermas")
        extractor.extract(session)

        assert store.get_node("project:vermas") is not None

    def test_alias_map_has_session_insights(self):
        assert "session-insights" in PROJECT_ALIASES
        assert PROJECT_ALIASES["session-insights"] == "distill"


# -- Entity extraction quality ---------------------------------------------


class TestEntityExtractionQuality:
    def test_go_not_detected_from_file_path(self):
        """'go' in a file path like /usr/local/go/bin should NOT create entity."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/usr/local/go/bin/main.go"},
                ),
            ],
        )
        extractor.extract(session)

        assert store.get_node("entity:go") is None

    def test_go_detected_from_bash_command(self):
        """'go' in a bash command like 'go build' SHOULD create entity."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "go build ./..."},
                ),
            ],
        )
        extractor.extract(session)

        assert store.get_node("entity:go") is not None

    def test_click_not_detected_from_read_path(self):
        """'click' in a path like /site-packages/click/ should NOT create entity."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/lib/python/site-packages/click/core.py"},
                ),
            ],
        )
        extractor.extract(session)

        assert store.get_node("entity:click") is None

    def test_node_not_detected_from_glob_path(self):
        """'node' in a path like /node_modules/ should NOT create entity."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Glob",
                    arguments={"path": "/proj/node_modules/react/"},
                ),
            ],
        )
        extractor.extract(session)

        # node should not be detected (ambiguous in path context)
        assert store.get_node("entity:node") is None
        # react should still be detected (not ambiguous)
        assert store.get_node("entity:react") is not None

    def test_unambiguous_entities_still_detected_from_paths(self):
        """Unambiguous entities like 'pytest' should be detected everywhere."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/proj/.venv/lib/pytest/main.py"},
                ),
            ],
        )
        extractor.extract(session)

        assert store.get_node("entity:pytest") is not None


# -- Agent session detection ------------------------------------------------


class TestAgentSessionDetection:
    def test_agent_session_with_cycle_info(self):
        """Sessions with cycle_info should be classified as 'agent'."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Build the authentication module"),
                Message(role="assistant", content="Working on it"),
                Message(role="user", content="Now add tests"),
            ],
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/a.py"}),
            ],
            cycle_info=CycleInfo(
                workflow_id="wf-001",
                mission_id="mission-001",
                cycle=1,
                task_name="auth-module",
            ),
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_agent_session_with_signals(self):
        """Sessions with agent signals should be classified as 'agent'."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        ts = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
        session = _make_session(
            messages=[
                Message(role="user", content="Implement the feature"),
                Message(role="assistant", content="Done"),
            ],
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/a.py"}),
            ],
            signals=[
                AgentSignal(
                    signal_id="sig-1",
                    agent_id="agent-1",
                    role="dev",
                    signal="done",
                    message="Task complete",
                    timestamp=ts,
                    workflow_id="wf-001",
                ),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_agent_session_skips_goal(self):
        """Agent sessions should not create goal nodes."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Build the auth module"),
                Message(role="assistant", content="Working on it"),
            ],
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/a.py"}),
            ],
            cycle_info=CycleInfo(workflow_id="wf-001"),
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 0

    def test_regular_multi_turn_still_human(self):
        """Multi-turn session without agent markers stays 'human'."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="Fix the bug"),
                Message(role="assistant", content="Looking into it"),
                Message(role="user", content="Also check tests"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "human"

    def test_troopx_agent_prompt_detected(self):
        """TroopX 'You are name (role)' pattern classified as agent."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(
                    role="user",
                    content='You are tokyo-worker-rogers (worker) in workflow wf-123. Your task is to implement...',
                ),
                Message(role="assistant", content="Working on it"),
                Message(role="user", content="Continue"),
            ],
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_troopx_agent_prompt_no_goal(self):
        """Agent prompt sessions should not create goal nodes."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(
                    role="user",
                    content="You are dev-agent-42 (developer) assigned to task...",
                ),
                Message(role="assistant", content="On it"),
            ],
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        goals = store.find_nodes(node_type=NodeType.GOAL)
        assert len(goals) == 0

    def test_generic_agent_prompt_detected(self):
        """'You are a X agent' pattern classified as agent."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(
                    role="user",
                    content="You are a testing agent responsible for running all tests...",
                ),
                Message(role="assistant", content="Running tests"),
            ],
            tool_calls=[
                ToolCall(tool_name="Bash", arguments={"command": "pytest"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_structured_task_header_detected(self):
        """'## TASK' structured header classified as agent."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(
                    role="user",
                    content="## TASK\nImplement the auth module\n## CONTEXT\nThis is part of...",
                ),
                Message(role="assistant", content="Implementing"),
            ],
            tool_calls=[
                ToolCall(tool_name="Edit", arguments={"file_path": "/a.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_the_role_agent_pattern_detected(self):
        """'You are the CEO agent' pattern classified as agent."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(
                    role="user",
                    content='You are the CEO agent. Work order wo-fizzbuzz-001 has been assigned.',
                ),
                Message(role="assistant", content="Processing"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/task.md"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_hyphenated_agent_name_detected(self):
        """'You are corp-planner-littlefinger.' pattern classified as agent."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(
                    role="user",
                    content="You are corp-planner-littlefinger. Read .vermas/agents/ for your role.",
                ),
                Message(role="assistant", content="Reading config"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/config.md"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "agent"

    def test_normal_you_sentence_not_agent(self):
        """Normal messages starting with 'You' should not be flagged as agent."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            messages=[
                Message(role="user", content="You need to fix this bug in login.py"),
                Message(role="assistant", content="Looking at it"),
            ],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/login.py"}),
            ],
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["session_type"] == "human"


# -- Summary quality -------------------------------------------------------


class TestSummaryQuality:
    def test_xml_tags_stripped_from_summary(self):
        """Summaries with XML tags should be cleaned."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            summary="<system-reminder>This is a system message</system-reminder>"
        )
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert "<system-reminder>" not in node.properties["summary"]

    def test_very_short_summary_replaced(self):
        """Summaries that are too short get replaced with session_id."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="hi")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        # Should fall back to session_id
        assert node.properties["summary"] == "sess-001"

    def test_slash_command_summary_replaced(self):
        """Summaries that look like slash commands get replaced."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="/analyze")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["summary"] == "sess-001"

    def test_good_summary_preserved(self):
        """Normal summaries are kept as-is."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="Fix the authentication bug in login flow")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["summary"] == "Fix the authentication bug in login flow"

    def test_empty_summary_uses_session_id(self):
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["summary"] == "sess-001"

    def test_file_path_summary_replaced(self):
        """Summary that's just a file path gets replaced."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(summary="src/main.py")
        extractor.extract(session)

        node = store.get_node("session:sess-001")
        assert node.properties["summary"] == "sess-001"


# -- Co-occurrence weight accumulation -------------------------------------


class TestCoOccurrenceWeightAccumulation:
    def test_weight_accumulates_across_sessions(self):
        """Same entity pair across multiple sessions should have weight > 1."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)

        for sid in ("s1", "s2", "s3"):
            session = _make_session(
                session_id=sid,
                tool_calls=[
                    ToolCall(
                        tool_name="Bash",
                        arguments={"command": "pytest tests/ && ruff check src/"},
                    ),
                ],
            )
            extractor.extract(session)

        co_edges = store.find_edges(edge_type=EdgeType.CO_OCCURS)
        assert len(co_edges) >= 1

        # Find the pytest-ruff co-occurrence edge
        for edge in co_edges:
            if "pytest" in edge.source_key and "ruff" in edge.target_key:
                assert edge.weight == 3.0
                break
            elif "ruff" in edge.source_key and "pytest" in edge.target_key:
                assert edge.weight == 3.0
                break
        else:
            raise AssertionError("pytest-ruff co-occurrence edge not found")

    def test_single_session_co_occurrence_weight_is_one(self):
        """First co-occurrence should have weight 1.0."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ && mypy src/"},
                ),
            ],
        )
        extractor.extract(session)

        co_edges = store.find_edges(edge_type=EdgeType.CO_OCCURS)
        for edge in co_edges:
            assert edge.weight == 1.0

    def test_reprocessing_same_session_does_not_double_count(self):
        """Re-extracting the same session should not inflate co-occurrence weights."""
        store = GraphStore()
        extractor = SessionGraphExtractor(store)
        session = _make_session(
            session_id="idempotent-test",
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest tests/ && mypy src/"},
                ),
            ],
        )
        # Process the same session twice (simulates 2-day overlap)
        extractor.extract(session)
        extractor.extract(session)

        co_edges = store.find_edges(edge_type=EdgeType.CO_OCCURS)
        for edge in co_edges:
            assert edge.weight == 1.0, (
                f"Co-occurrence weight should be 1.0 after re-processing, "
                f"got {edge.weight} for {edge.edge_key}"
            )
