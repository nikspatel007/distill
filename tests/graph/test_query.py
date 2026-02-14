"""Tests for GraphQuery — high-level query interface for the knowledge graph."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from distill.graph.context import ContextScorer
from distill.graph.extractor import SessionGraphExtractor
from distill.graph.models import GraphNode, NodeType
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession, Message, ToolCall


@pytest.fixture()
def now() -> datetime:
    return datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC)


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


@pytest.fixture()
def populated_store(now: datetime) -> GraphStore:
    """Build a populated graph using SessionGraphExtractor."""
    store = GraphStore()
    ext = SessionGraphExtractor(store)

    t1 = now - timedelta(hours=2)
    t2 = now - timedelta(hours=1)

    s1 = _make_session(
        session_id="s1",
        project="distill",
        summary="Build RSS parser",
        timestamp=t1,
        messages=[
            Message(role="user", content="Build an RSS parser for the intake pipeline"),
            Message(role="assistant", content="Working on it..."),
        ],
        tool_calls=[
            ToolCall(
                tool_name="Edit",
                arguments={"file_path": "/proj/src/intake/parsers/rss.py"},
            ),
            ToolCall(
                tool_name="Read",
                arguments={"file_path": "/proj/src/intake/models.py"},
            ),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/ -x"},
                result="All 10 tests passed",
            ),
        ],
        metadata={"cwd": "/proj", "branch": "feat/rss"},
    )

    s2 = _make_session(
        session_id="s2",
        project="distill",
        summary="Fix RSS parser bug",
        timestamp=t2,
        messages=[
            Message(role="user", content="Fix the RSS parser date parsing bug"),
            Message(role="assistant", content="Looking into it..."),
        ],
        tool_calls=[
            ToolCall(
                tool_name="Edit",
                arguments={"file_path": "/proj/src/intake/parsers/rss.py"},
            ),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/intake/ -x"},
                result="FAILED tests/intake/test_rss.py - ValueError",
            ),
            ToolCall(
                tool_name="Edit",
                arguments={"file_path": "/proj/src/intake/parsers/rss.py"},
            ),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/intake/ -x"},
                result="All 15 tests passed",
            ),
        ],
        metadata={"cwd": "/proj", "branch": "feat/rss-fix"},
    )

    ext.extract(s1)
    ext.extract(s2)
    return store


# -- about() -----------------------------------------------------------------


class TestAbout:
    def test_returns_focus_and_neighbors_for_existing_entity(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.about("distill")

        assert result["focus"] is not None
        assert result["focus"]["name"] == "distill"
        assert result["focus"]["type"] == "project"
        assert isinstance(result["neighbors"], list)
        assert len(result["neighbors"]) > 0
        assert isinstance(result["edges"], list)

    def test_returns_none_focus_for_unknown_name(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.about("nonexistent_thing_xyz")

        assert result["focus"] is None
        assert result["neighbors"] == []
        assert result["edges"] == []

    def test_neighbors_sorted_by_relevance_desc(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.about("distill")

        neighbors = result["neighbors"]
        if len(neighbors) > 1:
            relevance_scores = [n["relevance"] for n in neighbors]
            assert relevance_scores == sorted(relevance_scores, reverse=True)

    def test_neighbor_dict_has_required_keys(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.about("distill")

        for neighbor in result["neighbors"]:
            assert "name" in neighbor
            assert "type" in neighbor
            assert "relevance" in neighbor
            assert "last_seen" in neighbor

    def test_edge_dict_has_required_keys(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.about("distill")

        for edge in result["edges"]:
            assert "type" in edge
            assert "source" in edge
            assert "target" in edge
            assert "weight" in edge

    def test_about_session_by_name(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.about("s1")

        assert result["focus"] is not None
        assert result["focus"]["name"] == "s1"
        assert result["focus"]["type"] == "session"

    def test_about_with_max_hops(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result_1hop = query.about("distill", max_hops=1)
        result_2hop = query.about("distill", max_hops=2)

        # 2 hops should find at least as many neighbors as 1 hop
        assert len(result_2hop["neighbors"]) >= len(result_1hop["neighbors"])


# -- stats() -----------------------------------------------------------------


class TestStats:
    def test_returns_correct_counts(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.stats()

        assert "total_nodes" in result
        assert "total_edges" in result
        assert "nodes_by_type" in result
        assert "edges_by_type" in result

        # We should have session, project, goal, file, problem, entity nodes
        assert result["total_nodes"] > 0
        assert result["total_edges"] > 0

    def test_stats_delegates_to_store(self, now: datetime):
        store = GraphStore()
        query = GraphQuery(store, now=now)
        result = query.stats()

        assert result["total_nodes"] == 0
        assert result["total_edges"] == 0


# -- timeline() --------------------------------------------------------------


class TestTimeline:
    def test_returns_sessions_ordered_by_timestamp(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.timeline()

        assert len(result) == 2
        # Should be ordered by first_seen ascending
        assert result[0]["name"] == "s1"
        assert result[1]["name"] == "s2"

    def test_timeline_entries_have_required_keys(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.timeline()

        for entry in result:
            assert "name" in entry
            assert "timestamp" in entry
            assert "project" in entry
            assert "branch" in entry

    def test_timeline_filters_by_project(
        self, populated_store: GraphStore, now: datetime
    ):
        # Add a session from a different project
        ext = SessionGraphExtractor(populated_store)
        s3 = _make_session(
            session_id="s3",
            project="vermas",
            summary="Different project session",
            timestamp=now,
        )
        ext.extract(s3)

        query = GraphQuery(populated_store, now=now)

        # Filter to distill only
        distill_sessions = query.timeline(project="distill")
        assert all(e["project"] == "distill" for e in distill_sessions)
        assert len(distill_sessions) == 2

        # Filter to vermas only
        vermas_sessions = query.timeline(project="vermas")
        assert len(vermas_sessions) == 1
        assert vermas_sessions[0]["project"] == "vermas"

        # No filter returns all
        all_sessions = query.timeline()
        assert len(all_sessions) == 3

    def test_timeline_empty_store(self, now: datetime):
        store = GraphStore()
        query = GraphQuery(store, now=now)
        result = query.timeline()
        assert result == []

    def test_timeline_timestamp_is_isoformat(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.timeline()

        for entry in result:
            # Should be a valid ISO format string
            ts = entry["timestamp"]
            assert isinstance(ts, str)
            # Should parse back without error
            datetime.fromisoformat(ts)


# -- render_context() --------------------------------------------------------


class TestRenderContext:
    def test_with_focus_returns_markdown_with_sections(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.render_context(focus="distill")

        assert isinstance(result, str)
        assert "# Active Context" in result
        # Should have at least one section header
        assert "## " in result
        # Should have relevance scores
        assert "relevance:" in result

    def test_without_focus_returns_global_context(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.render_context()

        assert isinstance(result, str)
        assert "# Active Context" in result

    def test_empty_graph_returns_no_context_message(self, now: datetime):
        store = GraphStore()
        query = GraphQuery(store, now=now)
        result = query.render_context()

        assert result == "No relevant context found."

    def test_render_context_with_top_k(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.render_context(top_k=3)

        assert isinstance(result, str)
        # Should still produce valid output
        assert len(result) > 0

    def test_render_context_groups_by_type(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        result = query.render_context()

        # Should group by node type with section headers
        # At minimum we should see some type sections
        lines = result.split("\n")
        section_headers = [l for l in lines if l.startswith("## ")]
        assert len(section_headers) > 0


# -- _find_node_by_name() ---------------------------------------------------


class TestFindNodeByName:
    def test_finds_by_type_prefix(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        node = query._find_node_by_name("distill")

        assert node is not None
        # Should find via one of the type prefixes (project:distill exists)
        assert node.name == "distill"

    def test_falls_back_to_name_contains(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        # "rss.py" should match file nodes via name_contains
        node = query._find_node_by_name("rss.py")

        assert node is not None
        assert "rss.py" in node.name

    def test_returns_none_for_unknown(
        self, populated_store: GraphStore, now: datetime
    ):
        query = GraphQuery(populated_store, now=now)
        node = query._find_node_by_name("completely_unknown_xyz_123")

        assert node is None

    def test_prefers_type_prefix_over_name_contains(self, now: datetime):
        """If a node matches by type prefix, that should be preferred."""
        store = GraphStore()
        # Create a project node named "test"
        store.upsert_node(
            GraphNode(
                node_type=NodeType.PROJECT,
                name="test",
                first_seen=now,
                last_seen=now,
            )
        )
        # Create a file node that contains "test" in its name
        store.upsert_node(
            GraphNode(
                node_type=NodeType.FILE,
                name="src/test_utils.py",
                first_seen=now,
                last_seen=now,
            )
        )

        query = GraphQuery(store, now=now)
        # The type prefix search should find "session:test" first (which doesn't exist),
        # then "project:test" (which does exist), and return it
        node = query._find_node_by_name("test")
        assert node is not None
        assert node.node_type == NodeType.PROJECT
        assert node.name == "test"
