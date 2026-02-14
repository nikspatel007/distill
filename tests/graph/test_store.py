"""Tests for GraphStore — in-memory graph with JSON persistence."""

from __future__ import annotations

from datetime import datetime

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GRAPH_STORE_FILENAME, GraphStore

# -- Node operations ---------------------------------------------------------


class TestUpsertNode:
    def test_creates_new_node(self):
        store = GraphStore()
        node = GraphNode(node_type=NodeType.PROJECT, name="distill")
        result = store.upsert_node(node)
        assert result.node_key == "project:distill"
        assert store.node_count() == 1
        assert store.get_node("project:distill") is not None

    def test_updates_last_seen_keeps_earliest_first_seen(self):
        store = GraphStore()
        early = datetime(2026, 1, 1)
        mid = datetime(2026, 1, 15)
        late = datetime(2026, 2, 1)

        node1 = GraphNode(
            node_type=NodeType.ENTITY,
            name="Python",
            first_seen=mid,
            last_seen=mid,
        )
        store.upsert_node(node1)

        node2 = GraphNode(
            node_type=NodeType.ENTITY,
            name="Python",
            first_seen=early,
            last_seen=late,
        )
        result = store.upsert_node(node2)

        assert result.first_seen == early
        assert result.last_seen == late

    def test_merges_properties_on_update(self):
        store = GraphStore()
        node1 = GraphNode(
            node_type=NodeType.FILE,
            name="main.py",
            properties={"language": "python"},
        )
        store.upsert_node(node1)

        node2 = GraphNode(
            node_type=NodeType.FILE,
            name="main.py",
            properties={"lines": 42},
        )
        result = store.upsert_node(node2)

        assert result.properties["language"] == "python"
        assert result.properties["lines"] == 42

    def test_updates_embedding_when_non_empty(self):
        store = GraphStore()
        node1 = GraphNode(
            node_type=NodeType.ENTITY,
            name="Rust",
            embedding=[0.1, 0.2],
        )
        store.upsert_node(node1)

        # Update with new embedding
        node2 = GraphNode(
            node_type=NodeType.ENTITY,
            name="Rust",
            embedding=[0.3, 0.4],
        )
        result = store.upsert_node(node2)
        assert result.embedding == [0.3, 0.4]

    def test_keeps_embedding_when_update_is_empty(self):
        store = GraphStore()
        node1 = GraphNode(
            node_type=NodeType.ENTITY,
            name="Rust",
            embedding=[0.1, 0.2],
        )
        store.upsert_node(node1)

        # Update with empty embedding — should keep existing
        node2 = GraphNode(
            node_type=NodeType.ENTITY,
            name="Rust",
            embedding=[],
        )
        result = store.upsert_node(node2)
        assert result.embedding == [0.1, 0.2]


class TestGetNode:
    def test_returns_none_for_missing(self):
        store = GraphStore()
        assert store.get_node("entity:nonexistent") is None

    def test_returns_node_when_present(self):
        store = GraphStore()
        node = GraphNode(node_type=NodeType.GOAL, name="ship-v1")
        store.upsert_node(node)
        result = store.get_node("goal:ship-v1")
        assert result is not None
        assert result.name == "ship-v1"


class TestFindNodes:
    def test_find_by_type(self):
        store = GraphStore()
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="a.py"))
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="b.py"))
        store.upsert_node(GraphNode(node_type=NodeType.PROJECT, name="distill"))

        files = store.find_nodes(node_type=NodeType.FILE)
        assert len(files) == 2
        assert all(n.node_type == NodeType.FILE for n in files)

    def test_find_by_name_contains(self):
        store = GraphStore()
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="src/main.py"))
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="tests/test_main.py"))
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="README.md"))

        results = store.find_nodes(name_contains="main")
        assert len(results) == 2

    def test_find_all_returns_everything(self):
        store = GraphStore()
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="a.py"))
        store.upsert_node(GraphNode(node_type=NodeType.PROJECT, name="distill"))

        results = store.find_nodes()
        assert len(results) == 2


class TestNodeCount:
    def test_empty_store(self):
        store = GraphStore()
        assert store.node_count() == 0

    def test_after_inserts(self):
        store = GraphStore()
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="a.py"))
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="b.py"))
        assert store.node_count() == 2


# -- Edge operations ---------------------------------------------------------


class TestUpsertEdge:
    def test_creates_new_edge(self):
        store = GraphStore()
        edge = GraphEdge(
            source_key="session:s1",
            target_key="file:main.py",
            edge_type=EdgeType.MODIFIES,
        )
        result = store.upsert_edge(edge)
        assert result.edge_key == "session:s1->file:main.py:modifies"
        assert store.edge_count() == 1

    def test_updates_weight_on_duplicate(self):
        store = GraphStore()
        edge1 = GraphEdge(
            source_key="entity:A",
            target_key="entity:B",
            edge_type=EdgeType.RELATED_TO,
            weight=1.0,
        )
        store.upsert_edge(edge1)

        edge2 = GraphEdge(
            source_key="entity:A",
            target_key="entity:B",
            edge_type=EdgeType.RELATED_TO,
            weight=2.5,
        )
        result = store.upsert_edge(edge2)
        assert result.weight == 2.5
        assert store.edge_count() == 1

    def test_merges_properties_on_update(self):
        store = GraphStore()
        edge1 = GraphEdge(
            source_key="entity:A",
            target_key="entity:B",
            edge_type=EdgeType.USES,
            properties={"context": "import"},
        )
        store.upsert_edge(edge1)

        edge2 = GraphEdge(
            source_key="entity:A",
            target_key="entity:B",
            edge_type=EdgeType.USES,
            properties={"count": 5},
        )
        result = store.upsert_edge(edge2)
        assert result.properties["context"] == "import"
        assert result.properties["count"] == 5


class TestFindEdges:
    def _populate(self, store: GraphStore) -> None:
        store.upsert_edge(
            GraphEdge(
                source_key="session:s1",
                target_key="file:a.py",
                edge_type=EdgeType.MODIFIES,
            )
        )
        store.upsert_edge(
            GraphEdge(
                source_key="session:s1",
                target_key="file:b.py",
                edge_type=EdgeType.READS,
            )
        )
        store.upsert_edge(
            GraphEdge(
                source_key="session:s2",
                target_key="file:a.py",
                edge_type=EdgeType.MODIFIES,
            )
        )

    def test_find_by_source_key(self):
        store = GraphStore()
        self._populate(store)
        edges = store.find_edges(source_key="session:s1")
        assert len(edges) == 2

    def test_find_by_target_key(self):
        store = GraphStore()
        self._populate(store)
        edges = store.find_edges(target_key="file:a.py")
        assert len(edges) == 2

    def test_find_by_edge_type(self):
        store = GraphStore()
        self._populate(store)
        edges = store.find_edges(edge_type=EdgeType.MODIFIES)
        assert len(edges) == 2

    def test_find_with_combined_filters(self):
        store = GraphStore()
        self._populate(store)
        edges = store.find_edges(source_key="session:s1", edge_type=EdgeType.MODIFIES)
        assert len(edges) == 1
        assert edges[0].target_key == "file:a.py"

    def test_find_all_returns_everything(self):
        store = GraphStore()
        self._populate(store)
        assert len(store.find_edges()) == 3


class TestEdgeCount:
    def test_empty_store(self):
        store = GraphStore()
        assert store.edge_count() == 0

    def test_after_inserts(self):
        store = GraphStore()
        store.upsert_edge(
            GraphEdge(
                source_key="a:1",
                target_key="b:2",
                edge_type=EdgeType.USES,
            )
        )
        assert store.edge_count() == 1


# -- Traversal ---------------------------------------------------------------


class TestNeighbors:
    def _build_chain(self, store: GraphStore) -> None:
        """Build: A -> B -> C -> D."""
        for name in ("A", "B", "C", "D"):
            store.upsert_node(GraphNode(node_type=NodeType.ENTITY, name=name))
        store.upsert_edge(
            GraphEdge(source_key="entity:A", target_key="entity:B", edge_type=EdgeType.LEADS_TO)
        )
        store.upsert_edge(
            GraphEdge(source_key="entity:B", target_key="entity:C", edge_type=EdgeType.LEADS_TO)
        )
        store.upsert_edge(
            GraphEdge(source_key="entity:C", target_key="entity:D", edge_type=EdgeType.LEADS_TO)
        )

    def test_outgoing_one_hop(self):
        store = GraphStore()
        self._build_chain(store)
        result = store.neighbors("entity:A", max_hops=1)
        keys = {n.node_key for n in result}
        assert keys == {"entity:B"}

    def test_incoming_one_hop(self):
        store = GraphStore()
        self._build_chain(store)
        result = store.neighbors("entity:B", max_hops=1)
        keys = {n.node_key for n in result}
        # B has outgoing to C and incoming from A
        assert keys == {"entity:A", "entity:C"}

    def test_multi_hop(self):
        store = GraphStore()
        self._build_chain(store)
        result = store.neighbors("entity:A", max_hops=2)
        keys = {n.node_key for n in result}
        assert keys == {"entity:B", "entity:C"}

    def test_with_edge_type_filter(self):
        store = GraphStore()
        self._build_chain(store)
        # Add an edge of different type
        store.upsert_edge(
            GraphEdge(source_key="entity:A", target_key="entity:D", edge_type=EdgeType.RELATED_TO)
        )
        result = store.neighbors("entity:A", max_hops=1, edge_types=[EdgeType.LEADS_TO])
        keys = {n.node_key for n in result}
        assert keys == {"entity:B"}

    def test_no_neighbors(self):
        store = GraphStore()
        store.upsert_node(GraphNode(node_type=NodeType.ENTITY, name="lonely"))
        result = store.neighbors("entity:lonely", max_hops=1)
        assert result == []

    def test_missing_node(self):
        store = GraphStore()
        result = store.neighbors("entity:missing", max_hops=1)
        assert result == []


# -- Stats -------------------------------------------------------------------


class TestStats:
    def test_returns_correct_counts(self):
        store = GraphStore()
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="a.py"))
        store.upsert_node(GraphNode(node_type=NodeType.FILE, name="b.py"))
        store.upsert_node(GraphNode(node_type=NodeType.PROJECT, name="distill"))
        store.upsert_edge(
            GraphEdge(
                source_key="file:a.py",
                target_key="project:distill",
                edge_type=EdgeType.PART_OF,
            )
        )
        store.upsert_edge(
            GraphEdge(
                source_key="file:b.py",
                target_key="project:distill",
                edge_type=EdgeType.PART_OF,
            )
        )
        store.upsert_edge(
            GraphEdge(source_key="file:a.py", target_key="file:b.py", edge_type=EdgeType.DEPENDS_ON)
        )

        s = store.stats()
        assert s["total_nodes"] == 3
        assert s["total_edges"] == 3
        assert s["nodes_by_type"]["file"] == 2
        assert s["nodes_by_type"]["project"] == 1
        assert s["edges_by_type"]["part_of"] == 2
        assert s["edges_by_type"]["depends_on"] == 1


# -- Persistence -------------------------------------------------------------


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        # Create and populate a store
        store = GraphStore(path=tmp_path)
        store.upsert_node(GraphNode(node_type=NodeType.PROJECT, name="distill"))
        store.upsert_node(
            GraphNode(
                node_type=NodeType.FILE,
                name="main.py",
                properties={"lang": "python"},
                embedding=[0.1, 0.2, 0.3],
            )
        )
        store.upsert_edge(
            GraphEdge(
                source_key="file:main.py",
                target_key="project:distill",
                edge_type=EdgeType.PART_OF,
                weight=0.9,
                properties={"context": "import"},
            )
        )
        store.save()

        # Verify the JSON file exists
        json_file = tmp_path / GRAPH_STORE_FILENAME
        assert json_file.exists()

        # Load into a fresh store
        store2 = GraphStore(path=tmp_path)
        assert store2.node_count() == 2
        assert store2.edge_count() == 1

        # Check node data survived
        node = store2.get_node("project:distill")
        assert node is not None
        assert node.node_type == NodeType.PROJECT

        file_node = store2.get_node("file:main.py")
        assert file_node is not None
        assert file_node.properties["lang"] == "python"
        assert file_node.embedding == [0.1, 0.2, 0.3]

        # Check edge data survived
        edges = store2.find_edges(source_key="file:main.py")
        assert len(edges) == 1
        assert edges[0].weight == 0.9
        assert edges[0].properties["context"] == "import"

    def test_load_from_nonexistent_path(self, tmp_path):
        """No JSON file => empty store, no crash."""
        store = GraphStore(path=tmp_path)
        assert store.node_count() == 0
        assert store.edge_count() == 0

    def test_no_path_means_no_autoload(self):
        """GraphStore(path=None) works as pure in-memory."""
        store = GraphStore()
        assert store.node_count() == 0

    def test_indices_rebuilt_on_load(self, tmp_path):
        """After load, outgoing/incoming indices must work for traversal."""
        store = GraphStore(path=tmp_path)
        store.upsert_node(GraphNode(node_type=NodeType.ENTITY, name="A"))
        store.upsert_node(GraphNode(node_type=NodeType.ENTITY, name="B"))
        store.upsert_edge(
            GraphEdge(source_key="entity:A", target_key="entity:B", edge_type=EdgeType.LEADS_TO)
        )
        store.save()

        store2 = GraphStore(path=tmp_path)
        result = store2.neighbors("entity:A", max_hops=1)
        assert len(result) == 1
        assert result[0].node_key == "entity:B"
