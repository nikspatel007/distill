"""Tests for SessionGraphExtractor — Tier 1-2 heuristic extraction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from distill.graph.extractor import SessionGraphExtractor
from distill.graph.models import EdgeType, NodeType
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession, Message, ToolCall


def _make_session(
    session_id: str = "sess-001",
    project: str = "distill",
    summary: str = "Implement graph extractor",
    timestamp: datetime | None = None,
    messages: list[Message] | None = None,
    tool_calls: list[ToolCall] | None = None,
    metadata: dict | None = None,
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
        long_message = "A" * 300
        session = _make_session(
            messages=[Message(role="user", content=long_message)],
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
