"""End-to-end integration test for the knowledge graph pipeline.

Exercises the full flow: Extract sessions -> Store -> Score -> Query -> Persist round-trip.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from distill.graph.context import ContextScorer
from distill.graph.extractor import SessionGraphExtractor
from distill.graph.models import NodeType
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession, Message, ToolCall


def test_full_pipeline():
    """Extract -> Store -> Score -> Query, all in memory."""

    # -- 1. Create 3 sessions simulating building a feature ------------------

    base_time = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)

    session1 = BaseSession(
        session_id="sess-research",
        timestamp=base_time,
        project="distill",
        summary="Research graph databases",
        messages=[
            Message(role="user", content="Research graph databases"),
            Message(role="assistant", content="I'll look at the store module."),
        ],
        tool_calls=[
            ToolCall(
                tool_name="Read",
                arguments={"file_path": "/p/distill/src/store.py"},
            ),
        ],
        metadata={"cwd": "/p/distill", "branch": "feat/graph"},
    )

    session2 = BaseSession(
        session_id="sess-models",
        timestamp=base_time + timedelta(hours=1),
        project="distill",
        summary="Create graph models",
        messages=[
            Message(role="user", content="Create graph models"),
            Message(role="assistant", content="I'll create the models and tests."),
        ],
        tool_calls=[
            ToolCall(
                tool_name="Write",
                arguments={"file_path": "/p/distill/src/graph/models.py"},
            ),
            ToolCall(
                tool_name="Write",
                arguments={"file_path": "/p/distill/tests/graph/test_models.py"},
            ),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "uv run pytest tests/graph/test_models.py"},
                result="4 passed in 0.5s",
            ),
        ],
        metadata={"cwd": "/p/distill", "branch": "feat/graph"},
    )

    session3 = BaseSession(
        session_id="sess-store",
        timestamp=base_time + timedelta(hours=2),
        project="distill",
        summary="Add graph store",
        messages=[
            Message(role="user", content="Add graph store"),
            Message(role="assistant", content="I'll build the store implementation."),
        ],
        tool_calls=[
            ToolCall(
                tool_name="Read",
                arguments={"file_path": "/p/distill/src/store.py"},
            ),
            ToolCall(
                tool_name="Write",
                arguments={"file_path": "/p/distill/src/graph/store.py"},
            ),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "uv run pytest tests/graph/"},
                result="FAILED tests/graph/test_store.py::test_save - AssertionError",
            ),
        ],
        metadata={"cwd": "/p/distill", "branch": "feat/graph"},
    )

    # -- 2. Extract all 3 sessions ------------------------------------------

    store = GraphStore()
    extractor = SessionGraphExtractor(store)

    extractor.extract(session1)
    extractor.extract(session2)
    extractor.extract(session3)

    # -- 3. Verify graph structure -------------------------------------------

    stats = store.stats()
    assert stats["total_nodes"] >= 5, f"Expected >=5 nodes, got {stats['total_nodes']}"
    assert stats["total_edges"] >= 5, f"Expected >=5 edges, got {stats['total_edges']}"

    # 3 session nodes
    session_nodes = store.find_nodes(node_type=NodeType.SESSION)
    assert len(session_nodes) == 3

    # 1 project node ("distill")
    project_nodes = store.find_nodes(node_type=NodeType.PROJECT)
    assert len(project_nodes) == 1
    assert project_nodes[0].name == "distill"

    # File nodes exist
    file_nodes = store.find_nodes(node_type=NodeType.FILE)
    assert len(file_nodes) >= 1

    # Goal nodes exist
    goal_nodes = store.find_nodes(node_type=NodeType.GOAL)
    assert len(goal_nodes) >= 1

    # -- 4. Verify context scoring -------------------------------------------

    scorer = ContextScorer(store, now=base_time + timedelta(hours=3))
    results = scorer.score_all(focus_key="project:distill", top_k=10)
    assert len(results) > 0, "score_all should return results"
    assert all(r.score > 0 for r in results), "All scores should be non-zero"

    # -- 5. Verify query API -------------------------------------------------

    query = GraphQuery(store, now=base_time + timedelta(hours=3))

    about_result = query.about("distill")
    assert about_result["focus"] is not None, "about('distill') should find focus node"
    assert len(about_result["neighbors"]) > 0, "about('distill') should have neighbors"

    context_text = query.render_context(focus="distill")
    assert len(context_text) > 0, "render_context should return non-empty string"
    assert context_text != "No relevant context found."

    # -- 6. Verify persistence round-trip ------------------------------------

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Save original graph
        store._path = tmp_path
        store.save()

        original_node_count = store.node_count()
        original_edge_count = store.edge_count()

        # Load into a new GraphStore
        loaded_store = GraphStore(path=tmp_path)

        assert loaded_store.node_count() == original_node_count, (
            f"Node count mismatch: {loaded_store.node_count()} != {original_node_count}"
        )
        assert loaded_store.edge_count() == original_edge_count, (
            f"Edge count mismatch: {loaded_store.edge_count()} != {original_edge_count}"
        )
