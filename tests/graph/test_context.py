"""Tests for ContextScorer — relevance scoring of graph nodes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from distill.graph.context import _W_STRUCTURAL, _W_TEMPORAL, ContextScorer
from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore


@pytest.fixture()
def now() -> datetime:
    return datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def graph(now: datetime) -> GraphStore:
    """Build a small test graph:

    - project:distill (last_seen=now)
    - session:s1 (last_seen=now), edge: s1 -> distill (executes_in)
    - file:src/store.py (last_seen=now), edge: s1 -> file (modifies)
    - entity:pgvector (last_seen=now-20days), no edges to s1
    """
    store = GraphStore()
    twenty_days_ago = now - timedelta(days=20)

    store.upsert_node(
        GraphNode(
            node_type=NodeType.PROJECT,
            name="distill",
            first_seen=now,
            last_seen=now,
        )
    )
    store.upsert_node(
        GraphNode(
            node_type=NodeType.SESSION,
            name="s1",
            first_seen=now,
            last_seen=now,
        )
    )
    store.upsert_node(
        GraphNode(
            node_type=NodeType.FILE,
            name="src/store.py",
            first_seen=now,
            last_seen=now,
        )
    )
    store.upsert_node(
        GraphNode(
            node_type=NodeType.ENTITY,
            name="pgvector",
            first_seen=twenty_days_ago,
            last_seen=twenty_days_ago,
        )
    )

    # s1 -> distill (executes_in)
    store.upsert_edge(
        GraphEdge(
            source_key="session:s1",
            target_key="project:distill",
            edge_type=EdgeType.EXECUTES_IN,
        )
    )
    # s1 -> file:src/store.py (modifies)
    store.upsert_edge(
        GraphEdge(
            source_key="session:s1",
            target_key="file:src/store.py",
            edge_type=EdgeType.MODIFIES,
        )
    )

    return store


# -- temporal_score ----------------------------------------------------------


class TestTemporalScore:
    def test_recent_node_scores_high(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        score = scorer.temporal_score("project:distill", now=now)
        assert score > 0.9

    def test_old_node_scores_low(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        score = scorer.temporal_score("entity:pgvector", now=now)
        assert score < 0.5

    def test_missing_node_returns_zero(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        score = scorer.temporal_score("entity:nonexistent", now=now)
        assert score == 0.0

    def test_timezone_naive_datetime_handled(self, graph: GraphStore):
        """Timezone-naive datetimes should be treated as UTC without error."""
        naive_now = datetime(2026, 2, 14, 12, 0, 0)
        scorer = ContextScorer(graph, now=naive_now)
        score = scorer.temporal_score("project:distill", now=naive_now)
        # Should produce a valid score, not crash
        assert 0.0 <= score <= 1.0

    def test_exact_zero_days_is_one(self, graph: GraphStore, now: datetime):
        """Node last seen right now should score exactly 1.0."""
        scorer = ContextScorer(graph, now=now)
        score = scorer.temporal_score("project:distill", now=now)
        assert score == pytest.approx(1.0, abs=1e-9)


# -- structural_score --------------------------------------------------------


class TestStructuralScore:
    def test_self_scores_one(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("session:s1", "session:s1")
        assert score == 1.0

    def test_direct_neighbor_scores_half(self, graph: GraphStore, now: datetime):
        """Distance 1 -> 1/(1+1) = 0.5."""
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("project:distill", "session:s1")
        assert score == pytest.approx(0.5)

    def test_unreachable_node_scores_zero(self, graph: GraphStore, now: datetime):
        """entity:pgvector has no edges to s1 -> unreachable."""
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("entity:pgvector", "session:s1")
        assert score == 0.0

    def test_two_hop_neighbor(self, graph: GraphStore, now: datetime):
        """project:distill is 2 hops from file:src/store.py (via session:s1).
        Distance 2 -> 1/(1+2) = 1/3.
        """
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("project:distill", "file:src/store.py")
        assert score == pytest.approx(1.0 / 3.0)

    def test_max_depth_limits_search(self, graph: GraphStore, now: datetime):
        """With max_depth=1, two-hop paths should not be found."""
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("project:distill", "file:src/store.py", max_depth=1)
        assert score == 0.0

    def test_missing_focus_key_returns_zero(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("project:distill", "entity:nonexistent")
        assert score == 0.0

    def test_missing_node_key_returns_zero(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        score = scorer.structural_score("entity:nonexistent", "session:s1")
        assert score == 0.0


# -- score_all ---------------------------------------------------------------


class TestScoreAll:
    def test_returns_sorted_descending(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits_results(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1", top_k=2)
        assert len(results) <= 2

    def test_global_context_uses_temporal_only(self, graph: GraphStore, now: datetime):
        """No focus_key => only temporal scoring."""
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key=None)
        # All nodes should appear (4 nodes, no focus to skip)
        assert len(results) == 4
        # Recent nodes should score higher than old ones
        keys_scores = {r.node_key: r.score for r in results}
        assert keys_scores["project:distill"] > keys_scores["entity:pgvector"]
        # Components should only have temporal
        for r in results:
            assert "temporal" in r.components
            assert r.components.get("structural", 0.0) == 0.0

    def test_min_score_filters_low_scores(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1", min_score=0.5)
        for r in results:
            assert r.score >= 0.5

    def test_skips_focus_node(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1")
        result_keys = {r.node_key for r in results}
        assert "session:s1" not in result_keys

    def test_context_score_has_components(self, graph: GraphStore, now: datetime):
        """Each ContextScore should have component breakdown."""
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1")
        for r in results:
            assert "temporal" in r.components
            assert "structural" in r.components

    def test_focus_key_set_on_results(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1")
        for r in results:
            assert r.focus_key == "session:s1"

    def test_global_context_focus_key_is_none(self, graph: GraphStore, now: datetime):
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key=None)
        for r in results:
            assert r.focus_key is None

    def test_combined_score_weights(self, graph: GraphStore, now: datetime):
        """Verify the combined score uses the correct weights."""
        scorer = ContextScorer(graph, now=now)
        results = scorer.score_all(focus_key="session:s1")
        for r in results:
            expected = (
                _W_TEMPORAL * r.components["temporal"]
                + _W_STRUCTURAL * r.components["structural"]
                + 0.2 * r.components.get("semantic", 0.0)
            )
            assert r.score == pytest.approx(expected, abs=1e-9)
