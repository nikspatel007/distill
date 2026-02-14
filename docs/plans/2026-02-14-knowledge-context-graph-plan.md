# Knowledge Graph + Context Graph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a two-layer graph system (Knowledge Graph + Context Graph) that transforms raw Claude Code session logs into queryable entities, relationships, and dynamic context.

**Architecture:** New `src/graph/` module with Pydantic models, PostgreSQL graph tables (extending the existing `store.py` pattern), tiered extraction pipeline (heuristic + LLM), context scoring, and a query API. Integrates into the existing pipeline as a parallel step alongside journal/blog generation.

**Tech Stack:** Python 3.11+, Pydantic v2, SQLAlchemy + pgvector (optional dep pattern), Typer CLI, Claude Haiku for LLM extraction.

**Design doc:** `docs/plans/2026-02-14-knowledge-context-graph-design.md`

---

### Task 1: Graph Models (Pydantic)

**Files:**
- Create: `src/graph/__init__.py`
- Create: `src/graph/models.py`
- Test: `tests/graph/test_models.py`

**Step 1: Write the failing tests**

```python
# tests/graph/__init__.py
# (empty)

# tests/graph/test_models.py
"""Tests for graph data models."""

from datetime import datetime, timezone

from distill.graph.models import (
    ContextScore,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)


class TestNodeType:
    def test_all_node_types_exist(self):
        expected = {
            "session", "project", "file", "entity",
            "thread", "artifact", "goal", "problem",
            "decision", "insight",
        }
        assert {t.value for t in NodeType} == expected

    def test_is_str_enum(self):
        assert NodeType.SESSION == "session"
        assert isinstance(NodeType.SESSION, str)


class TestEdgeType:
    def test_work_edges(self):
        for name in ("modifies", "reads", "executes_in", "uses", "produces"):
            assert EdgeType(name).value == name

    def test_causal_edges(self):
        for name in (
            "leads_to", "motivated_by", "blocked_by",
            "solved_by", "informed_by", "implements",
        ):
            assert EdgeType(name).value == name

    def test_semantic_edges(self):
        for name in (
            "co_occurs", "part_of", "related_to",
            "references", "depends_on", "pivoted_from",
            "evolved_into",
        ):
            assert EdgeType(name).value == name


class TestGraphNode:
    def test_create_session_node(self):
        now = datetime.now(timezone.utc)
        node = GraphNode(
            node_type=NodeType.SESSION,
            name="Added RSS parser",
            first_seen=now,
            last_seen=now,
            source_id="abc-123",
        )
        assert node.node_type == NodeType.SESSION
        assert node.name == "Added RSS parser"
        assert node.properties == {}
        assert node.id  # auto-generated UUID

    def test_create_entity_node_with_properties(self):
        now = datetime.now(timezone.utc)
        node = GraphNode(
            node_type=NodeType.ENTITY,
            name="pgvector",
            first_seen=now,
            last_seen=now,
            properties={"entity_subtype": "technology", "description": "Vector extension"},
        )
        assert node.properties["entity_subtype"] == "technology"

    def test_node_key_uniqueness(self):
        """node_key combines type + name for dedup."""
        now = datetime.now(timezone.utc)
        node = GraphNode(
            node_type=NodeType.ENTITY,
            name="pgvector",
            first_seen=now,
            last_seen=now,
        )
        assert node.node_key == "entity:pgvector"


class TestGraphEdge:
    def test_create_modifies_edge(self):
        edge = GraphEdge(
            source_key="session:abc",
            target_key="file:src/store.py",
            edge_type=EdgeType.MODIFIES,
            weight=3.0,
            properties={"lines_added": 45},
        )
        assert edge.edge_type == EdgeType.MODIFIES
        assert edge.weight == 3.0

    def test_default_weight_is_one(self):
        edge = GraphEdge(
            source_key="session:abc",
            target_key="file:foo.py",
            edge_type=EdgeType.READS,
        )
        assert edge.weight == 1.0

    def test_edge_identity(self):
        """edge_key combines source + target + type for dedup."""
        edge = GraphEdge(
            source_key="session:abc",
            target_key="file:foo.py",
            edge_type=EdgeType.READS,
        )
        assert edge.edge_key == "session:abc->file:foo.py:reads"


class TestContextScore:
    def test_create_score(self):
        score = ContextScore(
            node_key="entity:pgvector",
            score=0.85,
            components={"temporal": 0.9, "structural": 0.8, "semantic": 0.7},
        )
        assert score.score == 0.85
        assert score.components["temporal"] == 0.9

    def test_score_without_focus(self):
        score = ContextScore(node_key="entity:pgvector", score=0.5)
        assert score.focus_key is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.graph'`

**Step 3: Write minimal implementation**

```python
# src/graph/__init__.py
"""Knowledge Graph + Context Graph for distill."""

# src/graph/models.py
"""Graph data models — nodes, edges, and context scores."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    """Graph node types."""

    SESSION = "session"
    PROJECT = "project"
    FILE = "file"
    ENTITY = "entity"
    THREAD = "thread"
    ARTIFACT = "artifact"
    GOAL = "goal"
    PROBLEM = "problem"
    DECISION = "decision"
    INSIGHT = "insight"


class EdgeType(StrEnum):
    """Graph edge types."""

    # Work edges
    MODIFIES = "modifies"
    READS = "reads"
    EXECUTES_IN = "executes_in"
    USES = "uses"
    PRODUCES = "produces"

    # Causal edges
    LEADS_TO = "leads_to"
    MOTIVATED_BY = "motivated_by"
    BLOCKED_BY = "blocked_by"
    SOLVED_BY = "solved_by"
    INFORMED_BY = "informed_by"
    IMPLEMENTS = "implements"

    # Semantic edges
    CO_OCCURS = "co_occurs"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    PIVOTED_FROM = "pivoted_from"
    EVOLVED_INTO = "evolved_into"


class GraphNode(BaseModel):
    """A node in the knowledge graph."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType
    name: str
    properties: dict[str, object] = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    first_seen: datetime
    last_seen: datetime
    source_id: str = ""

    @property
    def node_key(self) -> str:
        """Unique key for deduplication: type:name."""
        return f"{self.node_type}:{self.name}"


class GraphEdge(BaseModel):
    """A typed, weighted edge between two nodes."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_key: str  # node_key of source node
    target_key: str  # node_key of target node
    edge_type: EdgeType
    weight: float = 1.0
    properties: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def edge_key(self) -> str:
        """Unique key for deduplication: source->target:type."""
        return f"{self.source_key}->{self.target_key}:{self.edge_type}"


class ContextScore(BaseModel):
    """Dynamic relevance score for a node relative to a focus."""

    node_key: str
    focus_key: str | None = None  # None = global context
    score: float
    components: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=datetime.now)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_models.py -v`
Expected: PASS (all tests green)

**Step 5: Commit**

```bash
git add src/graph/__init__.py src/graph/models.py tests/graph/__init__.py tests/graph/test_models.py
git commit -m "feat(graph): add graph data models — nodes, edges, context scores"
```

---

### Task 2: Graph Store (PostgreSQL tables)

**Files:**
- Create: `src/graph/store.py`
- Test: `tests/graph/test_store.py`

**Step 1: Write the failing tests**

```python
# tests/graph/test_store.py
"""Tests for in-memory graph store."""

from datetime import datetime, timezone

import pytest

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore


@pytest.fixture
def store():
    return GraphStore()


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


class TestGraphStoreNodes:
    def test_upsert_node_creates(self, store, now):
        node = GraphNode(
            node_type=NodeType.SESSION,
            name="test session",
            first_seen=now,
            last_seen=now,
        )
        store.upsert_node(node)
        assert store.get_node("session:test session") is not None

    def test_upsert_node_updates_last_seen(self, store, now):
        node = GraphNode(
            node_type=NodeType.ENTITY,
            name="python",
            first_seen=now,
            last_seen=now,
        )
        store.upsert_node(node)

        later = datetime(2026, 3, 1, tzinfo=timezone.utc)
        node2 = GraphNode(
            node_type=NodeType.ENTITY,
            name="python",
            first_seen=later,
            last_seen=later,
        )
        store.upsert_node(node2)
        stored = store.get_node("entity:python")
        assert stored is not None
        assert stored.last_seen == later
        # first_seen should NOT update
        assert stored.first_seen == now

    def test_get_node_missing(self, store):
        assert store.get_node("entity:nonexistent") is None

    def test_find_nodes_by_type(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.ENTITY, name="python", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.ENTITY, name="rust", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.PROJECT, name="distill", first_seen=now, last_seen=now,
        ))
        entities = store.find_nodes(node_type=NodeType.ENTITY)
        assert len(entities) == 2

    def test_node_count(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.ENTITY, name="python", first_seen=now, last_seen=now,
        ))
        assert store.node_count() == 1


class TestGraphStoreEdges:
    def test_add_edge(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="foo.py", first_seen=now, last_seen=now,
        ))
        edge = GraphEdge(
            source_key="session:s1",
            target_key="file:foo.py",
            edge_type=EdgeType.MODIFIES,
        )
        store.upsert_edge(edge)
        assert store.edge_count() == 1

    def test_upsert_edge_updates_weight(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="foo.py", first_seen=now, last_seen=now,
        ))
        edge1 = GraphEdge(
            source_key="session:s1", target_key="file:foo.py",
            edge_type=EdgeType.MODIFIES, weight=1.0,
        )
        store.upsert_edge(edge1)
        edge2 = GraphEdge(
            source_key="session:s1", target_key="file:foo.py",
            edge_type=EdgeType.MODIFIES, weight=3.0,
        )
        store.upsert_edge(edge2)
        edges = store.find_edges(source_key="session:s1")
        assert len(edges) == 1
        assert edges[0].weight == 3.0

    def test_find_edges_from_node(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="a.py", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="b.py", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:a.py", edge_type=EdgeType.MODIFIES,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:b.py", edge_type=EdgeType.READS,
        ))
        edges = store.find_edges(source_key="session:s1")
        assert len(edges) == 2

    def test_find_edges_by_type(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="a.py", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:a.py", edge_type=EdgeType.MODIFIES,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:a.py", edge_type=EdgeType.READS,
        ))
        modifies = store.find_edges(source_key="session:s1", edge_type=EdgeType.MODIFIES)
        assert len(modifies) == 1


class TestGraphStoreNeighbors:
    def test_neighbors_outgoing(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="a.py", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.PROJECT, name="distill", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:a.py", edge_type=EdgeType.MODIFIES,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="project:distill", edge_type=EdgeType.EXECUTES_IN,
        ))
        neighbors = store.neighbors("session:s1")
        assert len(neighbors) == 2

    def test_neighbors_incoming(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="a.py", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:a.py", edge_type=EdgeType.MODIFIES,
        ))
        neighbors = store.neighbors("file:a.py")
        assert len(neighbors) == 1
        assert neighbors[0].node_key == "session:s1"

    def test_neighbors_within_hops(self, store, now):
        """2-hop traversal."""
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.FILE, name="a.py", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.ENTITY, name="python", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="file:a.py", edge_type=EdgeType.MODIFIES,
        ))
        store.upsert_edge(GraphEdge(
            source_key="file:a.py", target_key="entity:python", edge_type=EdgeType.USES,
        ))
        # 1 hop from s1 = a.py only
        one_hop = store.neighbors("session:s1", max_hops=1)
        assert len(one_hop) == 1
        # 2 hops from s1 = a.py + python
        two_hop = store.neighbors("session:s1", max_hops=2)
        assert len(two_hop) == 2


class TestGraphStoreStats:
    def test_stats(self, store, now):
        store.upsert_node(GraphNode(
            node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
        ))
        store.upsert_node(GraphNode(
            node_type=NodeType.ENTITY, name="python", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="session:s1", target_key="entity:python", edge_type=EdgeType.USES,
        ))
        stats = store.stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["nodes_by_type"]["session"] == 1
        assert stats["nodes_by_type"]["entity"] == 1
        assert stats["edges_by_type"]["uses"] == 1


class TestGraphStorePersistence:
    def test_save_and_load(self, tmp_path, now):
        store = GraphStore(path=tmp_path)
        store.upsert_node(GraphNode(
            node_type=NodeType.ENTITY, name="python", first_seen=now, last_seen=now,
        ))
        store.upsert_edge(GraphEdge(
            source_key="entity:python", target_key="entity:python",
            edge_type=EdgeType.RELATED_TO,
        ))
        store.save()

        store2 = GraphStore(path=tmp_path)
        assert store2.node_count() == 1
        assert store2.edge_count() == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.graph.store'`

**Step 3: Write minimal implementation**

```python
# src/graph/store.py
"""Graph store — in-memory with JSON persistence.

Provides node/edge storage, neighbor traversal, and save/load.
PostgreSQL backend can be added later using the same interface.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType

logger = logging.getLogger(__name__)

GRAPH_STORE_FILENAME = ".distill-graph.json"


class GraphStore:
    """In-memory graph store with JSON persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self._nodes: dict[str, GraphNode] = {}  # node_key -> node
        self._edges: dict[str, GraphEdge] = {}  # edge_key -> edge
        self._outgoing: dict[str, list[str]] = {}  # node_key -> [edge_keys]
        self._incoming: dict[str, list[str]] = {}  # node_key -> [edge_keys]
        self._path = (path / GRAPH_STORE_FILENAME) if path else None
        if self._path:
            self._load()

    # --- Nodes ---

    def upsert_node(self, node: GraphNode) -> GraphNode:
        """Insert or update a node. On update, merges last_seen and properties."""
        key = node.node_key
        if key in self._nodes:
            existing = self._nodes[key]
            if node.last_seen > existing.last_seen:
                existing.last_seen = node.last_seen
            existing.properties.update(node.properties)
            if node.embedding:
                existing.embedding = node.embedding
            return existing
        self._nodes[key] = node
        return node

    def get_node(self, node_key: str) -> GraphNode | None:
        """Get a node by its key (type:name)."""
        return self._nodes.get(node_key)

    def find_nodes(
        self,
        node_type: NodeType | None = None,
        name_contains: str | None = None,
    ) -> list[GraphNode]:
        """Find nodes matching filters."""
        results: list[GraphNode] = []
        for node in self._nodes.values():
            if node_type and node.node_type != node_type:
                continue
            if name_contains and name_contains.lower() not in node.name.lower():
                continue
            results.append(node)
        return results

    def node_count(self) -> int:
        return len(self._nodes)

    # --- Edges ---

    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        """Insert or update an edge. On update, replaces weight and merges properties."""
        key = edge.edge_key
        if key in self._edges:
            existing = self._edges[key]
            existing.weight = edge.weight
            existing.properties.update(edge.properties)
            return existing
        self._edges[key] = edge
        self._outgoing.setdefault(edge.source_key, []).append(key)
        self._incoming.setdefault(edge.target_key, []).append(key)
        return edge

    def find_edges(
        self,
        source_key: str | None = None,
        target_key: str | None = None,
        edge_type: EdgeType | None = None,
    ) -> list[GraphEdge]:
        """Find edges matching filters."""
        if source_key:
            candidates = [
                self._edges[ek]
                for ek in self._outgoing.get(source_key, [])
                if ek in self._edges
            ]
        elif target_key:
            candidates = [
                self._edges[ek]
                for ek in self._incoming.get(target_key, [])
                if ek in self._edges
            ]
        else:
            candidates = list(self._edges.values())

        if edge_type:
            candidates = [e for e in candidates if e.edge_type == edge_type]
        if target_key and source_key:
            candidates = [e for e in candidates if e.target_key == target_key]
        return candidates

    def edge_count(self) -> int:
        return len(self._edges)

    # --- Traversal ---

    def neighbors(
        self,
        node_key: str,
        max_hops: int = 1,
        edge_types: list[EdgeType] | None = None,
    ) -> list[GraphNode]:
        """Find neighbor nodes within max_hops. Traverses both directions."""
        visited: set[str] = {node_key}
        frontier: set[str] = {node_key}

        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for key in frontier:
                # Outgoing
                for ek in self._outgoing.get(key, []):
                    edge = self._edges.get(ek)
                    if not edge:
                        continue
                    if edge_types and edge.edge_type not in edge_types:
                        continue
                    if edge.target_key not in visited:
                        next_frontier.add(edge.target_key)
                # Incoming
                for ek in self._incoming.get(key, []):
                    edge = self._edges.get(ek)
                    if not edge:
                        continue
                    if edge_types and edge.edge_type not in edge_types:
                        continue
                    if edge.source_key not in visited:
                        next_frontier.add(edge.source_key)
            visited.update(next_frontier)
            frontier = next_frontier

        visited.discard(node_key)
        return [self._nodes[k] for k in visited if k in self._nodes]

    # --- Stats ---

    def stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        node_types: Counter[str] = Counter(n.node_type.value for n in self._nodes.values())
        edge_types: Counter[str] = Counter(e.edge_type.value for e in self._edges.values())
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": dict(node_types),
            "edges_by_type": dict(edge_types),
        }

    # --- Persistence ---

    def save(self) -> None:
        """Save graph to JSON file."""
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": [n.model_dump(mode="json") for n in self._nodes.values()],
            "edges": [e.model_dump(mode="json") for e in self._edges.values()],
        }
        self._path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def _load(self) -> None:
        """Load graph from JSON file."""
        if not self._path or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for nd in data.get("nodes", []):
                node = GraphNode.model_validate(nd)
                self._nodes[node.node_key] = node
            for ed in data.get("edges", []):
                edge = GraphEdge.model_validate(ed)
                self._edges[edge.edge_key] = edge
                self._outgoing.setdefault(edge.source_key, []).append(edge.edge_key)
                self._incoming.setdefault(edge.target_key, []).append(edge.edge_key)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Corrupt graph store at %s, starting fresh", self._path)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/graph/store.py tests/graph/test_store.py
git commit -m "feat(graph): add in-memory graph store with JSON persistence"
```

---

### Task 3: Tier 1 Heuristic Extractor

**Files:**
- Create: `src/graph/extractor.py`
- Test: `tests/graph/test_extractor.py`

This is the core engine that walks JSONL entries and produces graph nodes/edges without any LLM calls.

**Step 1: Write the failing tests**

```python
# tests/graph/test_extractor.py
"""Tests for Tier 1 heuristic graph extraction."""

from datetime import datetime, timezone

import pytest

from distill.graph.extractor import SessionGraphExtractor
from distill.graph.models import EdgeType, NodeType
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession, Message, SessionOutcome, ToolCall


@pytest.fixture
def store():
    return GraphStore()


@pytest.fixture
def extractor(store):
    return SessionGraphExtractor(store)


def _make_session(
    session_id: str = "sess-1",
    summary: str = "Added RSS parser",
    project: str = "distill",
    cwd: str = "/Users/nik/distill",
    git_branch: str = "main",
    messages: list | None = None,
    tool_calls: list | None = None,
    outcomes: list | None = None,
    timestamp: datetime | None = None,
) -> BaseSession:
    ts = timestamp or datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)
    return BaseSession(
        session_id=session_id,
        timestamp=ts,
        start_time=ts,
        summary=summary,
        project=project,
        messages=messages or [
            Message(role="user", content="Add an RSS parser", timestamp=ts),
            Message(role="assistant", content="I'll create the parser.", timestamp=ts),
        ],
        tool_calls=tool_calls or [],
        outcomes=outcomes or [],
        metadata={"cwd": cwd, "git_branch": git_branch},
    )


class TestSessionNode:
    def test_creates_session_node(self, extractor, store):
        session = _make_session()
        extractor.extract(session)
        node = store.get_node("session:sess-1")
        assert node is not None
        assert node.node_type == NodeType.SESSION
        assert "RSS" in node.name

    def test_creates_project_node(self, extractor, store):
        session = _make_session(project="distill")
        extractor.extract(session)
        node = store.get_node("project:distill")
        assert node is not None

    def test_creates_executes_in_edge(self, extractor, store):
        session = _make_session()
        extractor.extract(session)
        edges = store.find_edges(source_key="session:sess-1", edge_type=EdgeType.EXECUTES_IN)
        assert len(edges) == 1
        assert edges[0].target_key == "project:distill"


class TestGoalExtraction:
    def test_extracts_goal_from_first_user_message(self, extractor, store):
        session = _make_session()
        extractor.extract(session)
        node = store.get_node("goal:Add an RSS parser")
        assert node is not None
        assert node.node_type == NodeType.GOAL

    def test_motivated_by_edge(self, extractor, store):
        session = _make_session()
        extractor.extract(session)
        edges = store.find_edges(source_key="session:sess-1", edge_type=EdgeType.MOTIVATED_BY)
        assert len(edges) == 1


class TestFileExtraction:
    def test_extracts_modified_files(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/Users/nik/distill/src/parsers/rss.py"},
                ),
                ToolCall(
                    tool_name="Edit",
                    arguments={"file_path": "/Users/nik/distill/src/parsers/rss.py"},
                ),
            ],
        )
        extractor.extract(session)
        node = store.get_node("file:src/parsers/rss.py")
        assert node is not None
        edges = store.find_edges(source_key="session:sess-1", edge_type=EdgeType.MODIFIES)
        assert len(edges) == 1
        assert edges[0].weight == 2.0  # edited twice

    def test_extracts_read_files(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    arguments={"file_path": "/Users/nik/distill/src/store.py"},
                ),
            ],
        )
        extractor.extract(session)
        edges = store.find_edges(source_key="session:sess-1", edge_type=EdgeType.READS)
        assert len(edges) == 1

    def test_normalizes_file_paths_to_relative(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    arguments={"file_path": "/Users/nik/distill/src/graph/models.py"},
                ),
            ],
        )
        extractor.extract(session)
        node = store.get_node("file:src/graph/models.py")
        assert node is not None


class TestProblemExtraction:
    def test_extracts_problem_from_failed_bash(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "uv run pytest tests/"},
                    result="FAILED tests/test_foo.py::test_bar - AssertionError",
                ),
            ],
        )
        extractor.extract(session)
        problems = store.find_nodes(node_type=NodeType.PROBLEM)
        assert len(problems) >= 1

    def test_blocked_by_edge_for_problem(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "pytest"},
                    result="ERROR: SyntaxError in foo.py",
                ),
            ],
        )
        extractor.extract(session)
        edges = store.find_edges(source_key="session:sess-1", edge_type=EdgeType.BLOCKED_BY)
        assert len(edges) >= 1


class TestSessionChaining:
    def test_leads_to_for_consecutive_sessions(self, extractor, store):
        ts1 = datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 2, 14, 11, 0, tzinfo=timezone.utc)
        s1 = _make_session(session_id="s1", project="distill", timestamp=ts1)
        s2 = _make_session(session_id="s2", project="distill", timestamp=ts2)
        extractor.extract(s1)
        extractor.extract(s2)
        edges = store.find_edges(source_key="session:s1", edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 1
        assert edges[0].target_key == "session:s2"

    def test_no_leads_to_for_large_gap(self, extractor, store):
        ts1 = datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)
        s1 = _make_session(session_id="s1", project="distill", timestamp=ts1)
        s2 = _make_session(session_id="s2", project="distill", timestamp=ts2)
        extractor.extract(s1)
        extractor.extract(s2)
        edges = store.find_edges(source_key="session:s1", edge_type=EdgeType.LEADS_TO)
        assert len(edges) == 0


class TestEntityHints:
    def test_extracts_known_tech_from_tool_args(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "uv run pytest tests/"},
                ),
            ],
        )
        extractor.extract(session)
        pytest_node = store.get_node("entity:pytest")
        assert pytest_node is not None

    def test_uses_edge_for_entity(self, extractor, store):
        session = _make_session(
            tool_calls=[
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "uv run pytest tests/"},
                ),
            ],
        )
        extractor.extract(session)
        edges = store.find_edges(source_key="session:sess-1", edge_type=EdgeType.USES)
        assert any(e.target_key == "entity:pytest" for e in edges)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.graph.extractor'`

**Step 3: Write minimal implementation**

```python
# src/graph/extractor.py
"""Tier 1-2 heuristic graph extraction from sessions.

Walks session data and produces graph nodes/edges without LLM calls.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession

logger = logging.getLogger(__name__)

# Max gap between sessions to create a leads_to edge
_SESSION_GAP_HOURS = 4

# Tools that indicate file modification
_MODIFY_TOOLS = {"Edit", "Write", "NotebookEdit"}
_READ_TOOLS = {"Read", "Glob", "Grep"}

# Known technology names for Tier 2 entity hints
_KNOWN_TECH = {
    "pytest", "mypy", "ruff", "docker", "git", "npm", "bun", "node",
    "python", "typescript", "javascript", "rust", "go", "java",
    "react", "vue", "svelte", "fastapi", "flask", "django",
    "postgresql", "pgvector", "redis", "sqlite", "mongodb",
    "tailwind", "vite", "webpack", "esbuild",
    "pydantic", "sqlalchemy", "typer", "click",
    "claude", "openai", "anthropic",
}

# Patterns indicating a failed command
_FAILURE_PATTERNS = re.compile(
    r"(FAIL|ERROR|error:|Exception|Traceback|SyntaxError|ImportError|"
    r"ModuleNotFoundError|AssertionError|TypeError|ValueError|KeyError|"
    r"AttributeError|FileNotFoundError|PermissionError)",
    re.IGNORECASE,
)


class SessionGraphExtractor:
    """Extracts graph nodes and edges from a parsed session."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store
        self._last_session_by_project: dict[str, str] = {}
        self._last_timestamp_by_project: dict[str, datetime] = {}

    def extract(self, session: BaseSession) -> None:
        """Extract all Tier 1-2 nodes and edges from a session."""
        ts = session.start_time or session.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # 1. Session node
        session_key = f"session:{session.session_id}"
        self._store.upsert_node(GraphNode(
            node_type=NodeType.SESSION,
            name=session.summary or session.session_id,
            first_seen=ts,
            last_seen=ts,
            source_id=session.session_id,
            properties={
                "project": session.project,
                "branch": session.metadata.get("git_branch", ""),
                "tool_count": len(session.tool_calls),
            },
        ))

        # 2. Project node + executes_in edge
        if session.project:
            self._store.upsert_node(GraphNode(
                node_type=NodeType.PROJECT,
                name=session.project,
                first_seen=ts,
                last_seen=ts,
            ))
            self._store.upsert_edge(GraphEdge(
                source_key=session_key,
                target_key=f"project:{session.project}",
                edge_type=EdgeType.EXECUTES_IN,
            ))

        # 3. Goal from first user message
        self._extract_goal(session, session_key, ts)

        # 4. File nodes from tool calls
        self._extract_files(session, session_key, ts)

        # 5. Problems from failed commands
        self._extract_problems(session, session_key, ts)

        # 6. Entity hints from tool arguments
        self._extract_entity_hints(session, session_key, ts)

        # 7. Session chaining (leads_to)
        self._chain_sessions(session, session_key, ts)

    def _extract_goal(
        self, session: BaseSession, session_key: str, ts: datetime,
    ) -> None:
        """Extract goal node from first user message."""
        for msg in session.messages:
            if msg.role == "user" and msg.content.strip():
                goal_text = msg.content.strip()
                # Truncate long goals
                if len(goal_text) > 200:
                    goal_text = goal_text[:200]
                self._store.upsert_node(GraphNode(
                    node_type=NodeType.GOAL,
                    name=goal_text,
                    first_seen=ts,
                    last_seen=ts,
                ))
                self._store.upsert_edge(GraphEdge(
                    source_key=session_key,
                    target_key=f"goal:{goal_text}",
                    edge_type=EdgeType.MOTIVATED_BY,
                ))
                break

    def _extract_files(
        self, session: BaseSession, session_key: str, ts: datetime,
    ) -> None:
        """Extract file nodes from tool calls."""
        cwd = session.metadata.get("cwd", "") or ""
        modify_counts: Counter[str] = Counter()
        read_counts: Counter[str] = Counter()

        for tc in session.tool_calls:
            file_path = tc.arguments.get("file_path", "") or tc.arguments.get("path", "")
            if not file_path:
                continue

            # Normalize to relative path
            rel_path = self._normalize_path(file_path, cwd)
            if not rel_path:
                continue

            if tc.tool_name in _MODIFY_TOOLS:
                modify_counts[rel_path] += 1
            elif tc.tool_name in _READ_TOOLS:
                read_counts[rel_path] += 1

        for path, count in modify_counts.items():
            self._store.upsert_node(GraphNode(
                node_type=NodeType.FILE,
                name=path,
                first_seen=ts,
                last_seen=ts,
            ))
            self._store.upsert_edge(GraphEdge(
                source_key=session_key,
                target_key=f"file:{path}",
                edge_type=EdgeType.MODIFIES,
                weight=float(count),
            ))

        for path, count in read_counts.items():
            if path not in modify_counts:  # don't double-count
                self._store.upsert_node(GraphNode(
                    node_type=NodeType.FILE,
                    name=path,
                    first_seen=ts,
                    last_seen=ts,
                ))
            self._store.upsert_edge(GraphEdge(
                source_key=session_key,
                target_key=f"file:{path}",
                edge_type=EdgeType.READS,
                weight=float(count),
            ))

    def _extract_problems(
        self, session: BaseSession, session_key: str, ts: datetime,
    ) -> None:
        """Extract problem nodes from failed tool calls."""
        for tc in session.tool_calls:
            if tc.tool_name != "Bash" or not tc.result:
                continue
            if _FAILURE_PATTERNS.search(tc.result):
                # Extract a concise problem description
                first_line = tc.result.strip().split("\n")[0][:200]
                problem_name = f"{session.session_id}:{first_line}"
                self._store.upsert_node(GraphNode(
                    node_type=NodeType.PROBLEM,
                    name=problem_name,
                    first_seen=ts,
                    last_seen=ts,
                    properties={
                        "command": tc.arguments.get("command", ""),
                        "error_snippet": tc.result[:500] if tc.result else "",
                    },
                ))
                self._store.upsert_edge(GraphEdge(
                    source_key=session_key,
                    target_key=f"problem:{problem_name}",
                    edge_type=EdgeType.BLOCKED_BY,
                ))

    def _extract_entity_hints(
        self, session: BaseSession, session_key: str, ts: datetime,
    ) -> None:
        """Tier 2: extract known technology names from tool arguments."""
        found: set[str] = set()
        for tc in session.tool_calls:
            text = str(tc.arguments).lower()
            for tech in _KNOWN_TECH:
                if tech in text:
                    found.add(tech)

        for tech in found:
            self._store.upsert_node(GraphNode(
                node_type=NodeType.ENTITY,
                name=tech,
                first_seen=ts,
                last_seen=ts,
                properties={"entity_subtype": "technology"},
            ))
            self._store.upsert_edge(GraphEdge(
                source_key=session_key,
                target_key=f"entity:{tech}",
                edge_type=EdgeType.USES,
            ))

    def _chain_sessions(
        self, session: BaseSession, session_key: str, ts: datetime,
    ) -> None:
        """Create leads_to edges between consecutive sessions in the same project."""
        project = session.project
        if not project:
            return

        prev_key = self._last_session_by_project.get(project)
        prev_ts = self._last_timestamp_by_project.get(project)

        if prev_key and prev_ts:
            gap = ts - prev_ts
            if gap <= timedelta(hours=_SESSION_GAP_HOURS) and gap > timedelta(0):
                self._store.upsert_edge(GraphEdge(
                    source_key=prev_key,
                    target_key=session_key,
                    edge_type=EdgeType.LEADS_TO,
                    properties={"gap_hours": gap.total_seconds() / 3600},
                ))

        self._last_session_by_project[project] = session_key
        self._last_timestamp_by_project[project] = ts

    @staticmethod
    def _normalize_path(file_path: str, cwd: str) -> str:
        """Convert absolute path to project-relative path."""
        if not file_path:
            return ""
        if cwd and file_path.startswith(cwd):
            rel = file_path[len(cwd):]
            return rel.lstrip("/")
        # If no cwd match, try to extract from common patterns
        parts = file_path.split("/")
        # Find 'src/' or 'tests/' as anchor
        for i, part in enumerate(parts):
            if part in ("src", "tests", "web", "docs"):
                return "/".join(parts[i:])
        # Last resort: just the filename
        return parts[-1] if parts else ""
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_extractor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/graph/extractor.py tests/graph/test_extractor.py
git commit -m "feat(graph): add Tier 1-2 heuristic extractor for sessions"
```

---

### Task 4: Context Scoring

**Files:**
- Create: `src/graph/context.py`
- Test: `tests/graph/test_context.py`

**Step 1: Write the failing tests**

```python
# tests/graph/test_context.py
"""Tests for context graph scoring."""

from datetime import datetime, timedelta, timezone

import pytest

from distill.graph.context import ContextScorer
from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore


@pytest.fixture
def now():
    return datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(now):
    s = GraphStore()
    # Build a small test graph
    s.upsert_node(GraphNode(
        node_type=NodeType.PROJECT, name="distill", first_seen=now, last_seen=now,
    ))
    s.upsert_node(GraphNode(
        node_type=NodeType.SESSION, name="s1", first_seen=now, last_seen=now,
    ))
    s.upsert_node(GraphNode(
        node_type=NodeType.FILE, name="src/store.py",
        first_seen=now - timedelta(days=7), last_seen=now,
    ))
    s.upsert_node(GraphNode(
        node_type=NodeType.ENTITY, name="pgvector",
        first_seen=now - timedelta(days=30), last_seen=now - timedelta(days=20),
    ))
    s.upsert_edge(GraphEdge(
        source_key="session:s1", target_key="project:distill", edge_type=EdgeType.EXECUTES_IN,
    ))
    s.upsert_edge(GraphEdge(
        source_key="session:s1", target_key="file:src/store.py", edge_type=EdgeType.MODIFIES,
    ))
    return s


@pytest.fixture
def scorer(store, now):
    return ContextScorer(store, now=now)


class TestTemporalScore:
    def test_recent_node_scores_high(self, scorer, now):
        score = scorer.temporal_score("session:s1", now)
        assert score > 0.9

    def test_old_node_scores_low(self, scorer, now):
        score = scorer.temporal_score("entity:pgvector", now)
        assert score < 0.5

    def test_missing_node_returns_zero(self, scorer, now):
        score = scorer.temporal_score("entity:nonexistent", now)
        assert score == 0.0


class TestStructuralScore:
    def test_direct_neighbor_scores_high(self, scorer):
        # file:src/store.py is 1 hop from session:s1
        score = scorer.structural_score("file:src/store.py", focus_key="session:s1")
        assert score > 0.4

    def test_distant_node_scores_lower(self, scorer):
        # entity:pgvector has no edge to session:s1
        score = scorer.structural_score("entity:pgvector", focus_key="session:s1")
        assert score < 0.2

    def test_self_scores_one(self, scorer):
        score = scorer.structural_score("session:s1", focus_key="session:s1")
        assert score == 1.0


class TestCombinedScore:
    def test_scores_all_nodes(self, scorer, store):
        scores = scorer.score_all(focus_key="session:s1")
        assert len(scores) > 0
        # Session s1's neighbor (src/store.py) should rank high
        file_score = next(
            (s for s in scores if s.node_key == "file:src/store.py"), None,
        )
        assert file_score is not None
        assert file_score.score > 0.3

    def test_top_k_limits_results(self, scorer):
        scores = scorer.score_all(focus_key="session:s1", top_k=2)
        assert len(scores) <= 2

    def test_global_context_no_focus(self, scorer):
        """Without focus, only temporal scoring applies."""
        scores = scorer.score_all()
        assert len(scores) > 0
        assert all(s.focus_key is None for s in scores)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.graph.context'`

**Step 3: Write minimal implementation**

```python
# src/graph/context.py
"""Context Graph — dynamic relevance scoring.

Scores nodes by temporal recency, structural distance, and
semantic similarity relative to a focus point.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from distill.graph.models import ContextScore, GraphNode
from distill.graph.store import GraphStore


# Default decay rate (lambda) for temporal scoring
_DECAY_LAMBDA = 0.1  # ~50% relevance after 7 days

# Default weights for combined scoring
_W_TEMPORAL = 0.3
_W_STRUCTURAL = 0.5
_W_SEMANTIC = 0.2


class ContextScorer:
    """Scores graph nodes by relevance to a focus point."""

    def __init__(
        self,
        store: GraphStore,
        *,
        now: datetime | None = None,
        decay_lambda: float = _DECAY_LAMBDA,
        w_temporal: float = _W_TEMPORAL,
        w_structural: float = _W_STRUCTURAL,
        w_semantic: float = _W_SEMANTIC,
    ) -> None:
        self._store = store
        self._now = now or datetime.now(timezone.utc)
        self._decay = decay_lambda
        self._w_t = w_temporal
        self._w_s = w_structural
        self._w_e = w_semantic

    def temporal_score(self, node_key: str, now: datetime | None = None) -> float:
        """Score based on recency: e^(-lambda * days_since_last_seen)."""
        node = self._store.get_node(node_key)
        if not node:
            return 0.0
        ref = now or self._now
        last_seen = node.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        days = max(0.0, (ref - last_seen).total_seconds() / 86400)
        return math.exp(-self._decay * days)

    def structural_score(
        self, node_key: str, focus_key: str, max_depth: int = 3,
    ) -> float:
        """Score based on shortest path: 1 / (1 + distance).

        Uses BFS. Returns 1.0 for self, 0.5 for direct neighbor, etc.
        Returns 0.0 if unreachable within max_depth.
        """
        if node_key == focus_key:
            return 1.0

        # BFS from focus
        visited: set[str] = {focus_key}
        frontier: set[str] = {focus_key}

        for depth in range(1, max_depth + 1):
            next_frontier: set[str] = set()
            for key in frontier:
                for neighbor in self._store.neighbors(key, max_hops=1):
                    nk = neighbor.node_key
                    if nk not in visited:
                        if nk == node_key:
                            return 1.0 / (1.0 + depth)
                        next_frontier.add(nk)
                        visited.add(nk)
            frontier = next_frontier
            if not frontier:
                break

        return 0.0  # unreachable

    def score_all(
        self,
        focus_key: str | None = None,
        top_k: int | None = None,
        min_score: float = 0.0,
    ) -> list[ContextScore]:
        """Score all nodes relative to focus. Returns sorted by score descending."""
        all_nodes = self._store.find_nodes()
        scores: list[ContextScore] = []

        for node in all_nodes:
            nk = node.node_key
            if nk == focus_key:
                continue  # skip the focus node itself

            t_score = self.temporal_score(nk)

            if focus_key:
                s_score = self.structural_score(nk, focus_key)
                # Semantic scoring requires embeddings — placeholder for now
                e_score = 0.0
                combined = (
                    self._w_t * t_score
                    + self._w_s * s_score
                    + self._w_e * e_score
                )
            else:
                # Global context: temporal only
                s_score = 0.0
                e_score = 0.0
                combined = t_score

            if combined < min_score:
                continue

            scores.append(ContextScore(
                node_key=nk,
                focus_key=focus_key,
                score=combined,
                components={
                    "temporal": round(t_score, 4),
                    "structural": round(s_score, 4),
                    "semantic": round(e_score, 4),
                },
            ))

        scores.sort(key=lambda s: s.score, reverse=True)
        if top_k:
            scores = scores[:top_k]
        return scores
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/graph/context.py tests/graph/test_context.py
git commit -m "feat(graph): add context scoring with temporal + structural relevance"
```

---

### Task 5: Query API

**Files:**
- Create: `src/graph/query.py`
- Test: `tests/graph/test_query.py`

High-level query interface for both dashboard and Claude context injection.

**Step 1: Write the failing tests**

```python
# tests/graph/test_query.py
"""Tests for graph query API."""

from datetime import datetime, timezone

import pytest

from distill.graph.extractor import SessionGraphExtractor
from distill.graph.models import NodeType
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession, Message, ToolCall


@pytest.fixture
def now():
    return datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def populated_store(now):
    """Build a small graph with 2 sessions."""
    store = GraphStore()
    ext = SessionGraphExtractor(store)

    s1 = BaseSession(
        session_id="s1", timestamp=now, start_time=now,
        summary="Build RSS parser", project="distill",
        messages=[Message(role="user", content="Build RSS parser", timestamp=now)],
        tool_calls=[
            ToolCall(tool_name="Edit", arguments={"file_path": "/p/distill/src/parsers/rss.py"}),
            ToolCall(tool_name="Bash", arguments={"command": "uv run pytest tests/"}),
        ],
        metadata={"cwd": "/p/distill", "git_branch": "feat/rss"},
    )
    s2 = BaseSession(
        session_id="s2", timestamp=now, start_time=now,
        summary="Fix RSS parser bug", project="distill",
        messages=[Message(role="user", content="Fix the RSS parser bug", timestamp=now)],
        tool_calls=[
            ToolCall(tool_name="Edit", arguments={"file_path": "/p/distill/src/parsers/rss.py"}),
            ToolCall(
                tool_name="Bash",
                arguments={"command": "pytest tests/"},
                result="FAILED test_rss.py - AssertionError",
            ),
        ],
        metadata={"cwd": "/p/distill", "git_branch": "feat/rss"},
    )
    ext.extract(s1)
    ext.extract(s2)
    return store


@pytest.fixture
def query(populated_store, now):
    return GraphQuery(populated_store, now=now)


class TestGraphQuery:
    def test_about_returns_relevant_subgraph(self, query):
        result = query.about("distill")
        assert result["focus"]["name"] == "distill"
        assert len(result["neighbors"]) > 0

    def test_about_unknown_entity(self, query):
        result = query.about("nonexistent-thing")
        assert result["focus"] is None

    def test_stats(self, query):
        stats = query.stats()
        assert stats["total_nodes"] > 0
        assert stats["total_edges"] > 0

    def test_render_context_for_prompt(self, query):
        text = query.render_context(focus="distill")
        assert "distill" in text
        assert isinstance(text, str)
        assert len(text) > 0

    def test_render_context_global(self, query):
        text = query.render_context()
        assert isinstance(text, str)

    def test_timeline_returns_sessions_ordered(self, query):
        timeline = query.timeline(project="distill")
        assert len(timeline) >= 2
        # Should be ordered by timestamp
        assert timeline[0]["name"] != timeline[1]["name"]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_query.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/graph/query.py
"""High-level graph query API.

Provides human-readable and machine-consumable queries over the
knowledge graph + context graph.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from distill.graph.context import ContextScorer
from distill.graph.models import GraphNode, NodeType
from distill.graph.store import GraphStore


class GraphQuery:
    """Query interface for the knowledge/context graph."""

    def __init__(
        self,
        store: GraphStore,
        *,
        now: datetime | None = None,
    ) -> None:
        self._store = store
        self._now = now or datetime.now(timezone.utc)

    def about(self, name: str, max_hops: int = 2) -> dict[str, Any]:
        """Get everything related to a named entity/project/file."""
        # Try to find the node by name across all types
        node = self._find_node_by_name(name)
        if not node:
            return {"focus": None, "neighbors": [], "edges": []}

        neighbors = self._store.neighbors(node.node_key, max_hops=max_hops)

        # Score neighbors for relevance
        scorer = ContextScorer(self._store, now=self._now)
        scores = scorer.score_all(focus_key=node.node_key, top_k=20)
        score_map = {s.node_key: s.score for s in scores}

        neighbor_data = []
        for n in neighbors:
            neighbor_data.append({
                "name": n.name,
                "type": n.node_type.value,
                "relevance": score_map.get(n.node_key, 0.0),
                "last_seen": n.last_seen.isoformat(),
            })
        neighbor_data.sort(key=lambda x: x["relevance"], reverse=True)

        edges = self._store.find_edges(source_key=node.node_key)
        edges += self._store.find_edges(target_key=node.node_key)
        edge_data = [
            {
                "type": e.edge_type.value,
                "source": e.source_key,
                "target": e.target_key,
                "weight": e.weight,
            }
            for e in edges
        ]

        return {
            "focus": {"name": node.name, "type": node.node_type.value},
            "neighbors": neighbor_data,
            "edges": edge_data,
        }

    def stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        return self._store.stats()

    def timeline(self, project: str | None = None) -> list[dict[str, Any]]:
        """Get sessions as a timeline, optionally filtered by project."""
        sessions = self._store.find_nodes(node_type=NodeType.SESSION)
        if project:
            sessions = [
                s for s in sessions
                if s.properties.get("project") == project
            ]
        sessions.sort(key=lambda s: s.first_seen)
        return [
            {
                "name": s.name,
                "timestamp": s.first_seen.isoformat(),
                "project": s.properties.get("project", ""),
                "branch": s.properties.get("branch", ""),
            }
            for s in sessions
        ]

    def render_context(
        self,
        focus: str | None = None,
        top_k: int = 15,
    ) -> str:
        """Render context graph as text for Claude session injection."""
        scorer = ContextScorer(self._store, now=self._now)

        focus_key: str | None = None
        if focus:
            node = self._find_node_by_name(focus)
            focus_key = node.node_key if node else None

        scores = scorer.score_all(focus_key=focus_key, top_k=top_k, min_score=0.1)

        if not scores:
            return "No relevant context found."

        lines: list[str] = ["# Active Context", ""]

        # Group by node type
        by_type: dict[str, list[tuple[str, float]]] = {}
        for s in scores:
            node = self._store.get_node(s.node_key)
            if not node:
                continue
            type_name = node.node_type.value
            by_type.setdefault(type_name, []).append((node.name, s.score))

        type_order = [
            "thread", "goal", "decision", "insight",
            "problem", "session", "file", "entity",
            "project", "artifact",
        ]
        for t in type_order:
            items = by_type.get(t, [])
            if not items:
                continue
            lines.append(f"## {t.title()}s")
            for name, score in items[:5]:
                lines.append(f"- {name} (relevance: {score:.2f})")
            lines.append("")

        return "\n".join(lines)

    def _find_node_by_name(self, name: str) -> GraphNode | None:
        """Find a node by name, trying common type prefixes."""
        # Try exact key first
        for node_type in NodeType:
            node = self._store.get_node(f"{node_type}:{name}")
            if node:
                return node
        # Fallback: search by name substring
        matches = self._store.find_nodes(name_contains=name)
        return matches[0] if matches else None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_query.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/graph/query.py tests/graph/test_query.py
git commit -m "feat(graph): add query API with context rendering and timeline"
```

---

### Task 6: CLI Commands

**Files:**
- Modify: `src/cli.py` (add `graph` command)
- Test: `tests/test_cli_graph.py`

**Step 1: Write the failing tests**

```python
# tests/test_cli_graph.py
"""Tests for graph CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from distill.cli import app

runner = CliRunner()


class TestGraphBuild:
    def test_graph_build_creates_store_file(self, tmp_path):
        # Create a minimal JSONL session file
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)
        session_file = project_dir / "sess-1.jsonl"
        entry = {
            "type": "user",
            "sessionId": "sess-1",
            "timestamp": "2026-02-14T10:00:00Z",
            "cwd": str(tmp_path),
            "message": {"role": "user", "content": "hello"},
        }
        session_file.write_text(json.dumps(entry) + "\n")

        result = runner.invoke(app, [
            "graph", "build",
            "--claude-dir", str(tmp_path / ".claude"),
            "--output", str(tmp_path / "output"),
        ])
        assert result.exit_code == 0

    def test_graph_stats_shows_counts(self, tmp_path):
        result = runner.invoke(app, [
            "graph", "stats",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "nodes" in result.stdout.lower() or "0" in result.stdout

    def test_graph_query_returns_text(self, tmp_path):
        result = runner.invoke(app, [
            "graph", "query",
            "distill",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_graph.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `src/cli.py` — a `graph` command group with `build`, `stats`, and `query` subcommands. Reference existing CLI patterns (same `output` param, `console.print`, progress spinners).

The implementation should:
1. Create a Typer sub-app: `graph_app = typer.Typer(name="graph")`
2. `app.add_typer(graph_app, name="graph")`
3. `build` command: iterate JSONL files, parse with ClaudeParser, extract with SessionGraphExtractor, save GraphStore
4. `stats` command: load GraphStore, print stats
5. `query` command: load GraphStore, run GraphQuery.about() or render_context()

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_graph.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/cli.py tests/test_cli_graph.py
git commit -m "feat(graph): add CLI commands — graph build/stats/query"
```

---

### Task 7: Integration Test — End-to-End Pipeline

**Files:**
- Test: `tests/graph/test_integration.py`

**Step 1: Write the integration test**

```python
# tests/graph/test_integration.py
"""End-to-end integration test for graph pipeline."""

from datetime import datetime, timezone

from distill.graph.context import ContextScorer
from distill.graph.extractor import SessionGraphExtractor
from distill.graph.models import NodeType
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession, Message, ToolCall


def test_full_pipeline():
    """Extract -> Store -> Score -> Query, all in memory."""
    now = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)
    store = GraphStore()
    extractor = SessionGraphExtractor(store)

    # Simulate 3 sessions building a feature
    sessions = [
        BaseSession(
            session_id="s1", timestamp=now, start_time=now,
            summary="Research graph databases", project="distill",
            messages=[Message(role="user", content="Research graph database options", timestamp=now)],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/p/distill/src/store.py"}),
            ],
            metadata={"cwd": "/p/distill", "git_branch": "feat/graph"},
        ),
        BaseSession(
            session_id="s2", timestamp=now, start_time=now,
            summary="Create graph models", project="distill",
            messages=[Message(role="user", content="Create the graph data models", timestamp=now)],
            tool_calls=[
                ToolCall(tool_name="Write", arguments={"file_path": "/p/distill/src/graph/models.py"}),
                ToolCall(tool_name="Write", arguments={"file_path": "/p/distill/tests/graph/test_models.py"}),
                ToolCall(tool_name="Bash", arguments={"command": "uv run pytest tests/graph/"}),
            ],
            metadata={"cwd": "/p/distill", "git_branch": "feat/graph"},
        ),
        BaseSession(
            session_id="s3", timestamp=now, start_time=now,
            summary="Add graph store", project="distill",
            messages=[Message(role="user", content="Build the graph store with persistence", timestamp=now)],
            tool_calls=[
                ToolCall(tool_name="Read", arguments={"file_path": "/p/distill/src/store.py"}),
                ToolCall(tool_name="Write", arguments={"file_path": "/p/distill/src/graph/store.py"}),
                ToolCall(
                    tool_name="Bash",
                    arguments={"command": "uv run pytest tests/graph/"},
                    result="FAILED tests/graph/test_store.py - AssertionError",
                ),
            ],
            metadata={"cwd": "/p/distill", "git_branch": "feat/graph"},
        ),
    ]

    for s in sessions:
        extractor.extract(s)

    # Verify graph structure
    stats = store.stats()
    assert stats["total_nodes"] > 5
    assert stats["total_edges"] > 5
    assert stats["nodes_by_type"]["session"] == 3
    assert stats["nodes_by_type"]["project"] == 1
    assert "file" in stats["nodes_by_type"]
    assert "goal" in stats["nodes_by_type"]

    # Verify context scoring
    scorer = ContextScorer(store, now=now)
    scores = scorer.score_all(focus_key="project:distill", top_k=10)
    assert len(scores) > 0

    # Verify query API
    query = GraphQuery(store, now=now)
    result = query.about("distill")
    assert result["focus"] is not None
    assert len(result["neighbors"]) > 0

    # Verify context rendering
    context = query.render_context(focus="distill")
    assert "distill" in context.lower() or "session" in context.lower()

    # Verify persistence round-trip
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        store_path = Path(td)
        store._path = store_path / ".distill-graph.json"
        store.save()

        store2 = GraphStore(path=store_path)
        assert store2.node_count() == store.node_count()
        assert store2.edge_count() == store.edge_count()
```

**Step 2: Run the integration test**

Run: `uv run pytest tests/graph/test_integration.py -v`
Expected: PASS (all prior tasks must be complete)

**Step 3: Commit**

```bash
git add tests/graph/test_integration.py
git commit -m "test(graph): add end-to-end integration test"
```

---

### Task 8: Run Full Test Suite + Lint

**Step 1: Run all graph tests**

Run: `uv run pytest tests/graph/ -v`
Expected: All PASS

**Step 2: Run full project test suite**

Run: `uv run pytest tests/ -x -q --ignore=tests/test_verify_all_kpis.py`
Expected: All PASS (no regressions)

**Step 3: Type check**

Run: `uv run mypy src/graph/ --no-error-summary`
Expected: 0 errors

**Step 4: Lint**

Run: `uv run ruff check src/graph/ && uv run ruff format src/graph/`
Expected: Clean

**Step 5: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix(graph): address lint and type-check issues"
```
