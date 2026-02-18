"""Tests for graph structural insight extraction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from distill.graph.insights import (
    CouplingCluster,
    DailyInsights,
    ErrorHotspot,
    GraphInsights,
    RecurringProblem,
    ScopeWarning,
    format_insights_for_prompt,
)
from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 2, 14, 12, 0, tzinfo=UTC)


@pytest.fixture
def store() -> GraphStore:
    return GraphStore()


def _make_session(
    store: GraphStore,
    name: str,
    *,
    project: str = "distill",
    session_type: str = "human",
    last_seen: datetime | None = None,
) -> GraphNode:
    ts = last_seen or datetime.now(UTC)
    node = GraphNode(
        node_type=NodeType.SESSION,
        name=name,
        properties={"project": project, "session_type": session_type, "summary": name},
        first_seen=ts,
        last_seen=ts,
    )
    store.upsert_node(node)
    return node


def _make_file(store: GraphStore, name: str) -> GraphNode:
    node = GraphNode(
        node_type=NodeType.FILE,
        name=name,
        properties={"name": name},
    )
    store.upsert_node(node)
    return node


def _make_problem(store: GraphStore, name: str) -> GraphNode:
    node = GraphNode(
        node_type=NodeType.PROBLEM,
        name=name,
        properties={"error_snippet": name},
    )
    store.upsert_node(node)
    return node


def _link(store: GraphStore, source: GraphNode, target: GraphNode, edge_type: EdgeType) -> None:
    store.upsert_edge(
        GraphEdge(
            source_key=source.node_key,
            target_key=target.node_key,
            edge_type=edge_type,
        )
    )


class TestCoModificationClusters:
    def test_detects_co_modified_pair(self, store: GraphStore, now: datetime) -> None:
        """Two files modified together in 3 sessions should be detected."""
        f1 = _make_file(store, "core.py")
        f2 = _make_file(store, "cli.py")
        for i in range(3):
            s = _make_session(store, f"session-{i}", last_seen=now)
            _link(store, s, f1, EdgeType.MODIFIES)
            _link(store, s, f2, EdgeType.MODIFIES)

        gi = GraphInsights(store, now=now)
        clusters = gi.co_modification_clusters(min_count=3)

        assert len(clusters) == 1
        assert set(clusters[0].files) == {"core.py", "cli.py"}
        assert clusters[0].co_modification_count == 3

    def test_ignores_below_threshold(self, store: GraphStore, now: datetime) -> None:
        """Pairs co-modified less than min_count are not returned."""
        f1 = _make_file(store, "a.py")
        f2 = _make_file(store, "b.py")
        for i in range(2):
            s = _make_session(store, f"s-{i}", last_seen=now)
            _link(store, s, f1, EdgeType.MODIFIES)
            _link(store, s, f2, EdgeType.MODIFIES)

        gi = GraphInsights(store, now=now)
        clusters = gi.co_modification_clusters(min_count=3)
        assert clusters == []

    def test_empty_graph(self, store: GraphStore, now: datetime) -> None:
        gi = GraphInsights(store, now=now)
        assert gi.co_modification_clusters() == []


class TestErrorHotspots:
    def test_detects_error_prone_file(self, store: GraphStore, now: datetime) -> None:
        """File modified in sessions with problems should be flagged."""
        f = _make_file(store, "worker.py")
        for i in range(3):
            s = _make_session(store, f"s-{i}", last_seen=now)
            p = _make_problem(store, f"Error {i}")
            _link(store, s, f, EdgeType.MODIFIES)
            _link(store, s, p, EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        hotspots = gi.error_hotspots()

        assert len(hotspots) >= 1
        assert hotspots[0].file == "worker.py"
        assert hotspots[0].problem_count == 3

    def test_ranks_by_problem_count(self, store: GraphStore, now: datetime) -> None:
        """Files with more problems should rank higher."""
        f1 = _make_file(store, "stable.py")
        f2 = _make_file(store, "fragile.py")

        # stable.py: 1 problem
        s1 = _make_session(store, "s-stable", last_seen=now)
        _link(store, s1, f1, EdgeType.MODIFIES)
        _link(store, s1, _make_problem(store, "err1"), EdgeType.BLOCKED_BY)

        # fragile.py: 3 problems
        for i in range(3):
            s = _make_session(store, f"s-fragile-{i}", last_seen=now)
            _link(store, s, f2, EdgeType.MODIFIES)
            _link(store, s, _make_problem(store, f"err-f-{i}"), EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        hotspots = gi.error_hotspots()

        assert hotspots[0].file == "fragile.py"
        assert hotspots[0].problem_count > hotspots[-1].problem_count

    def test_empty_graph(self, store: GraphStore, now: datetime) -> None:
        gi = GraphInsights(store, now=now)
        assert gi.error_hotspots() == []


class TestScopeWarnings:
    def test_flags_over_threshold(self, store: GraphStore, now: datetime) -> None:
        """Sessions modifying more than 5 files should be flagged."""
        s = _make_session(store, "big-session", last_seen=now)
        for i in range(7):
            f = _make_file(store, f"file{i}.py")
            _link(store, s, f, EdgeType.MODIFIES)

        gi = GraphInsights(store, now=now)
        warnings = gi.scope_warnings(lookback_hours=48.0)

        assert len(warnings) == 1
        assert warnings[0].files_modified == 7
        assert warnings[0].session_name == "big-session"

    def test_ignores_under_threshold(self, store: GraphStore, now: datetime) -> None:
        """Sessions with 5 or fewer files should not be flagged."""
        s = _make_session(store, "small-session", last_seen=now)
        for i in range(3):
            f = _make_file(store, f"small-file{i}.py")
            _link(store, s, f, EdgeType.MODIFIES)

        gi = GraphInsights(store, now=now)
        warnings = gi.scope_warnings(lookback_hours=48.0)
        assert warnings == []

    def test_ignores_old_sessions(self, store: GraphStore, now: datetime) -> None:
        """Sessions older than lookback_hours should not be flagged."""
        old_time = now - timedelta(hours=100)
        s = _make_session(store, "old-session", last_seen=old_time)
        for i in range(10):
            f = _make_file(store, f"old-file{i}.py")
            _link(store, s, f, EdgeType.MODIFIES)

        gi = GraphInsights(store, now=now)
        warnings = gi.scope_warnings(lookback_hours=48.0)
        assert warnings == []

    def test_includes_problem_count(self, store: GraphStore, now: datetime) -> None:
        """Scope warnings should include the number of problems hit."""
        s = _make_session(store, "problem-session", last_seen=now)
        for i in range(6):
            _link(store, s, _make_file(store, f"pf{i}.py"), EdgeType.MODIFIES)
        for i in range(3):
            _link(store, s, _make_problem(store, f"prob{i}"), EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        warnings = gi.scope_warnings(lookback_hours=48.0)
        assert warnings[0].problems_hit == 3


class TestRecurringProblems:
    def test_detects_recurring_pattern(self, store: GraphStore, now: datetime) -> None:
        """Same error appearing in multiple sessions should be flagged."""
        # Base message must be >60 chars so truncation makes them identical
        base = "ImportError: cannot import module 'foo' from 'bar.baz.qux.long'"
        assert len(base) > 60, "base must exceed 60 chars for truncation grouping"
        for i in range(3):
            s = _make_session(store, f"s-{i}", last_seen=now)
            p = _make_problem(store, f"{base} -- instance {i}")
            _link(store, s, p, EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        # All have the same first 60 chars
        recurring = gi.recurring_problems(min_occurrences=2)
        assert len(recurring) >= 1
        assert recurring[0].occurrence_count >= 2

    def test_ignores_unique_problems(self, store: GraphStore, now: datetime) -> None:
        """Problems appearing only once should not be flagged."""
        s = _make_session(store, "s-unique", last_seen=now)
        p = _make_problem(store, "UniqueError: never seen before xyz123")
        _link(store, s, p, EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        recurring = gi.recurring_problems(min_occurrences=2)
        assert recurring == []

    def test_empty_graph(self, store: GraphStore, now: datetime) -> None:
        gi = GraphInsights(store, now=now)
        assert gi.recurring_problems() == []


class TestDailySessionStats:
    def test_computes_stats(self, store: GraphStore, now: datetime) -> None:
        for i in range(4):
            s = _make_session(store, f"stat-s-{i}", last_seen=now)
            for j in range(3):
                _link(store, s, _make_file(store, f"stat-f{i}-{j}.py"), EdgeType.MODIFIES)
            _link(store, s, _make_problem(store, f"stat-err-{i}"), EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        stats = gi.daily_session_stats(lookback_hours=48.0)

        assert stats["session_count"] == 4
        assert stats["avg_files_per_session"] == 3.0
        assert stats["total_problems"] == 4

    def test_excludes_old_sessions(self, store: GraphStore, now: datetime) -> None:
        old = now - timedelta(hours=100)
        _make_session(store, "old-stat", last_seen=old)

        gi = GraphInsights(store, now=now)
        stats = gi.daily_session_stats(lookback_hours=48.0)
        assert stats["session_count"] == 0


class TestGenerateDailyInsights:
    def test_returns_daily_insights_object(self, store: GraphStore, now: datetime) -> None:
        s = _make_session(store, "insight-session", last_seen=now)
        for i in range(7):
            _link(store, s, _make_file(store, f"ins-f{i}.py"), EdgeType.MODIFIES)
        _link(store, s, _make_problem(store, "insight-err"), EdgeType.BLOCKED_BY)

        gi = GraphInsights(store, now=now)
        daily = gi.generate_daily_insights(lookback_hours=48.0)

        assert isinstance(daily, DailyInsights)
        assert daily.date == "2026-02-14"
        assert daily.session_count == 1
        assert len(daily.scope_warnings) == 1

    def test_empty_graph_returns_empty_insights(self, store: GraphStore, now: datetime) -> None:
        gi = GraphInsights(store, now=now)
        daily = gi.generate_daily_insights()
        assert daily.session_count == 0
        assert daily.coupling_clusters == []
        assert daily.error_hotspots == []


class TestFormatInsightsForPrompt:
    def test_formats_complete_insights(self) -> None:
        insights = DailyInsights(
            date="2026-02-14",
            session_count=5,
            avg_files_per_session=3.2,
            total_problems=8,
            coupling_clusters=[
                CouplingCluster(files=["core.py", "cli.py"], co_modification_count=15)
            ],
            error_hotspots=[
                ErrorHotspot(file="worker.py", problem_count=42)
            ],
            scope_warnings=[
                ScopeWarning(
                    session_name="big refactor",
                    files_modified=12,
                    project="vermas",
                    problems_hit=5,
                )
            ],
            recurring_problems=[
                RecurringProblem(pattern="Exit code 1", occurrence_count=7)
            ],
        )
        result = format_insights_for_prompt(insights)

        assert "## Retrospective Insights" in result
        assert "5 sessions" in result
        assert "3.2 files/session" in result
        assert "core.py + cli.py" in result
        assert "worker.py" in result
        assert "big refactor" in result
        assert "12 files modified" in result
        assert "Exit code 1" in result

    def test_empty_insights_returns_empty(self) -> None:
        insights = DailyInsights(date="2026-02-14")
        result = format_insights_for_prompt(insights)
        assert result == ""

    def test_partial_insights(self) -> None:
        """Only sections with data should appear."""
        insights = DailyInsights(
            date="2026-02-14",
            session_count=3,
            avg_files_per_session=2.0,
            total_problems=1,
            scope_warnings=[
                ScopeWarning(session_name="overscoped", files_modified=8, problems_hit=2)
            ],
        )
        result = format_insights_for_prompt(insights)

        assert "Scope Warnings" in result
        assert "overscoped" in result
        # No coupling or recurring problems sections
        assert "Architectural Coupling" not in result
        assert "Recurring Problems" not in result


class TestPersistInsights:
    def test_creates_coupling_insight_nodes(self, store: GraphStore, now: datetime) -> None:
        """Coupling clusters should be persisted as INSIGHT nodes."""
        # Create file nodes so REFERENCES edges can link to them
        _make_file(store, "core.py")
        _make_file(store, "cli.py")

        insights = DailyInsights(
            date="2026-02-14",
            coupling_clusters=[
                CouplingCluster(
                    files=["core.py", "cli.py"],
                    co_modification_count=10,
                    description="core.py and cli.py are co-modified in 10 sessions",
                )
            ],
        )

        gi = GraphInsights(store, now=now)
        count = gi.persist_insights(insights)

        assert count == 1
        # Verify insight node exists
        insight_nodes = store.find_nodes(node_type=NodeType.INSIGHT)
        coupling_nodes = [
            n for n in insight_nodes
            if n.properties and n.properties.get("insight_type") == "coupling_cluster"
        ]
        assert len(coupling_nodes) == 1
        assert coupling_nodes[0].properties["co_modification_count"] == 10

    def test_creates_related_to_edges_between_files(self, store: GraphStore, now: datetime) -> None:
        """Coupling should create RELATED_TO edges between the file nodes."""
        _make_file(store, "core.py")
        _make_file(store, "cli.py")

        insights = DailyInsights(
            date="2026-02-14",
            coupling_clusters=[
                CouplingCluster(files=["core.py", "cli.py"], co_modification_count=5)
            ],
        )

        gi = GraphInsights(store, now=now)
        gi.persist_insights(insights)

        related_edges = store.find_edges(edge_type=EdgeType.RELATED_TO)
        assert len(related_edges) >= 1
        edge = related_edges[0]
        assert edge.properties and edge.properties.get("relationship") == "co_modified"

    def test_creates_error_hotspot_nodes(self, store: GraphStore, now: datetime) -> None:
        """Error hotspots should be persisted as INSIGHT nodes."""
        _make_file(store, "worker.py")

        insights = DailyInsights(
            date="2026-02-14",
            error_hotspots=[
                ErrorHotspot(file="worker.py", problem_count=42, recent_problems=["err1"])
            ],
        )

        gi = GraphInsights(store, now=now)
        count = gi.persist_insights(insights)

        assert count == 1
        insight_nodes = store.find_nodes(node_type=NodeType.INSIGHT)
        hotspot_nodes = [
            n for n in insight_nodes
            if n.properties and n.properties.get("insight_type") == "error_hotspot"
        ]
        assert len(hotspot_nodes) == 1
        assert hotspot_nodes[0].properties["problem_count"] == 42

    def test_creates_recurring_problem_threads(self, store: GraphStore, now: datetime) -> None:
        """Recurring problems should be persisted as THREAD nodes."""
        insights = DailyInsights(
            date="2026-02-14",
            recurring_problems=[
                RecurringProblem(
                    pattern="ImportError: cannot import module 'foo'",
                    occurrence_count=5,
                    sessions=["s1", "s2"],
                )
            ],
        )

        gi = GraphInsights(store, now=now)
        count = gi.persist_insights(insights)

        assert count == 1
        thread_nodes = store.find_nodes(node_type=NodeType.THREAD)
        recurring_threads = [
            n for n in thread_nodes
            if n.properties and n.properties.get("thread_type") == "recurring_problem"
        ]
        assert len(recurring_threads) == 1
        assert recurring_threads[0].properties["total_occurrences"] == 5

    def test_creates_scope_warning_nodes(self, store: GraphStore, now: datetime) -> None:
        """Scope warnings should be persisted as INSIGHT nodes."""
        insights = DailyInsights(
            date="2026-02-14",
            scope_warnings=[
                ScopeWarning(
                    session_name="big refactor", files_modified=12, problems_hit=5, project="distill"
                )
            ],
        )

        gi = GraphInsights(store, now=now)
        count = gi.persist_insights(insights)

        assert count == 1
        insight_nodes = store.find_nodes(node_type=NodeType.INSIGHT)
        scope_nodes = [
            n for n in insight_nodes
            if n.properties and n.properties.get("insight_type") == "scope_warning"
        ]
        assert len(scope_nodes) == 1
        assert scope_nodes[0].properties["files_modified"] == 12

    def test_idempotent_persist(self, store: GraphStore, now: datetime) -> None:
        """Persisting the same insights twice should upsert, not duplicate."""
        insights = DailyInsights(
            date="2026-02-14",
            error_hotspots=[
                ErrorHotspot(file="fragile.py", problem_count=10)
            ],
        )

        gi = GraphInsights(store, now=now)
        gi.persist_insights(insights)
        gi.persist_insights(insights)

        insight_nodes = store.find_nodes(node_type=NodeType.INSIGHT)
        hotspot_nodes = [
            n for n in insight_nodes
            if n.properties and n.properties.get("insight_type") == "error_hotspot"
        ]
        assert len(hotspot_nodes) == 1  # upserted, not duplicated

    def test_thread_accumulates_occurrences(self, store: GraphStore, now: datetime) -> None:
        """Re-persisting recurring problem should keep the higher count."""
        pattern = "ImportError: cannot import module 'foo'"
        insights1 = DailyInsights(
            date="2026-02-14",
            recurring_problems=[
                RecurringProblem(pattern=pattern, occurrence_count=3, sessions=["s1"])
            ],
        )
        insights2 = DailyInsights(
            date="2026-02-15",
            recurring_problems=[
                RecurringProblem(pattern=pattern, occurrence_count=5, sessions=["s2", "s3"])
            ],
        )

        gi = GraphInsights(store, now=now)
        gi.persist_insights(insights1)
        gi.persist_insights(insights2)

        thread_nodes = store.find_nodes(node_type=NodeType.THREAD)
        recurring = [
            n for n in thread_nodes
            if n.properties and n.properties.get("thread_type") == "recurring_problem"
        ]
        assert len(recurring) == 1
        assert recurring[0].properties["total_occurrences"] == 5  # max(3, 5)

    def test_returns_total_count(self, store: GraphStore, now: datetime) -> None:
        """persist_insights should return total nodes created/updated."""
        insights = DailyInsights(
            date="2026-02-14",
            coupling_clusters=[
                CouplingCluster(files=["a.py", "b.py"], co_modification_count=5)
            ],
            error_hotspots=[
                ErrorHotspot(file="c.py", problem_count=3)
            ],
            scope_warnings=[
                ScopeWarning(session_name="big", files_modified=8, problems_hit=2)
            ],
            recurring_problems=[
                RecurringProblem(pattern="TypeError in handler", occurrence_count=4)
            ],
        )

        gi = GraphInsights(store, now=now)
        count = gi.persist_insights(insights)

        assert count == 4  # 1 coupling + 1 hotspot + 1 scope + 1 recurring

    def test_empty_insights_persists_nothing(self, store: GraphStore, now: datetime) -> None:
        """Empty insights should create no nodes."""
        insights = DailyInsights(date="2026-02-14")

        gi = GraphInsights(store, now=now)
        count = gi.persist_insights(insights)

        assert count == 0
        assert store.find_nodes(node_type=NodeType.INSIGHT) == []
        assert store.find_nodes(node_type=NodeType.THREAD) == []
