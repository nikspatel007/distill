"""In-memory graph store with JSON persistence.

Provides node and edge storage, BFS traversal, and save/load to a
JSON file following the same pattern as ``distill.store.JsonStore``.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from pathlib import Path

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType

logger = logging.getLogger(__name__)

GRAPH_STORE_FILENAME = ".distill-graph.json"


class GraphStore:
    """In-memory knowledge graph with optional JSON persistence.

    Internal indices:
    - ``_nodes``: node_key -> GraphNode
    - ``_edges``: edge_key -> GraphEdge
    - ``_outgoing``: node_key -> list[edge_key] (edges leaving the node)
    - ``_incoming``: node_key -> list[edge_key] (edges arriving at the node)
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._outgoing: dict[str, list[str]] = defaultdict(list)
        self._incoming: dict[str, list[str]] = defaultdict(list)

        if path is not None:
            self._load()

    # -- Node operations -----------------------------------------------------

    def upsert_node(self, node: GraphNode) -> GraphNode:
        """Insert or update a node.

        On update:
        - Keep the earliest ``first_seen``.
        - Use the latest ``last_seen``.
        - Merge ``properties`` (new keys overwrite).
        - Update ``embedding`` only if the incoming one is non-empty.

        Deduplication is by ``node_key``.
        """
        key = node.node_key
        existing = self._nodes.get(key)

        if existing is None:
            self._nodes[key] = node
            return node

        # Merge timestamps
        first_seen = min(existing.first_seen, node.first_seen)
        last_seen = max(existing.last_seen, node.last_seen)

        # Merge properties (existing + new, new wins on conflict)
        merged_props = {**existing.properties, **node.properties}

        # Embedding: use new if non-empty, else keep existing
        embedding = node.embedding if node.embedding else existing.embedding

        updated = existing.model_copy(
            update={
                "first_seen": first_seen,
                "last_seen": last_seen,
                "properties": merged_props,
                "embedding": embedding,
            }
        )
        self._nodes[key] = updated
        return updated

    def get_node(self, node_key: str) -> GraphNode | None:
        """Return a node by its canonical key, or ``None``."""
        return self._nodes.get(node_key)

    def find_nodes(
        self,
        node_type: NodeType | None = None,
        name_contains: str | None = None,
    ) -> list[GraphNode]:
        """Filter nodes by type and/or substring match on name."""
        results: list[GraphNode] = []
        for node in self._nodes.values():
            if node_type is not None and node.node_type != node_type:
                continue
            if name_contains is not None and name_contains not in node.name:
                continue
            results.append(node)
        return results

    def node_count(self) -> int:
        """Return the number of nodes in the store."""
        return len(self._nodes)

    # -- Edge operations -----------------------------------------------------

    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        """Insert or update an edge.

        On update: replace ``weight``, merge ``properties``.
        Deduplication is by ``edge_key``.
        """
        key = edge.edge_key
        existing = self._edges.get(key)

        if existing is None:
            self._edges[key] = edge
            self._outgoing[edge.source_key].append(key)
            self._incoming[edge.target_key].append(key)
            return edge

        merged_props = {**existing.properties, **edge.properties}
        updated = existing.model_copy(
            update={
                "weight": edge.weight,
                "properties": merged_props,
            }
        )
        self._edges[key] = updated
        return updated

    def find_edges(
        self,
        source_key: str | None = None,
        target_key: str | None = None,
        edge_type: EdgeType | None = None,
    ) -> list[GraphEdge]:
        """Filter edges by source, target, and/or type."""
        results: list[GraphEdge] = []
        for edge in self._edges.values():
            if source_key is not None and edge.source_key != source_key:
                continue
            if target_key is not None and edge.target_key != target_key:
                continue
            if edge_type is not None and edge.edge_type != edge_type:
                continue
            results.append(edge)
        return results

    def edge_count(self) -> int:
        """Return the number of edges in the store."""
        return len(self._edges)

    # -- Traversal -----------------------------------------------------------

    def neighbors(
        self,
        node_key: str,
        max_hops: int = 1,
        edge_types: list[EdgeType] | None = None,
    ) -> list[GraphNode]:
        """BFS traversal from *node_key* in both directions.

        Returns unique neighbor nodes (excluding the start node) reachable
        within *max_hops*.  Optionally filter by edge types.
        """
        if node_key not in self._nodes:
            return []

        edge_type_set = set(edge_types) if edge_types else None
        visited: set[str] = {node_key}
        queue: deque[tuple[str, int]] = deque([(node_key, 0)])
        result: list[GraphNode] = []

        while queue:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue

            # Outgoing edges
            for ekey in self._outgoing.get(current, []):
                edge = self._edges[ekey]
                if edge_type_set and edge.edge_type not in edge_type_set:
                    continue
                neighbor = edge.target_key
                if neighbor not in visited:
                    visited.add(neighbor)
                    node = self._nodes.get(neighbor)
                    if node is not None:
                        result.append(node)
                    queue.append((neighbor, depth + 1))

            # Incoming edges
            for ekey in self._incoming.get(current, []):
                edge = self._edges[ekey]
                if edge_type_set and edge.edge_type not in edge_type_set:
                    continue
                neighbor = edge.source_key
                if neighbor not in visited:
                    visited.add(neighbor)
                    node = self._nodes.get(neighbor)
                    if node is not None:
                        result.append(node)
                    queue.append((neighbor, depth + 1))

        return result

    # -- Stats ---------------------------------------------------------------

    def stats(self) -> dict[str, object]:
        """Return summary statistics about the graph.

        Returns a dict with keys:
        ``total_nodes``, ``total_edges``, ``nodes_by_type``, ``edges_by_type``.
        """
        nodes_by_type: dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            nodes_by_type[node.node_type.value] += 1

        edges_by_type: dict[str, int] = defaultdict(int)
        for edge in self._edges.values():
            edges_by_type[edge.edge_type.value] += 1

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": dict(nodes_by_type),
            "edges_by_type": dict(edges_by_type),
        }

    # -- Persistence ---------------------------------------------------------

    def save(self) -> None:
        """Serialize nodes and edges to JSON at ``path / GRAPH_STORE_FILENAME``."""
        if self._path is None:
            return

        filepath = self._path / GRAPH_STORE_FILENAME
        filepath.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "nodes": [n.model_dump(mode="json") for n in self._nodes.values()],
            "edges": [e.model_dump(mode="json") for e in self._edges.values()],
        }
        filepath.write_text(json.dumps(data, default=str), encoding="utf-8")

    def _load(self) -> None:
        """Deserialize from JSON and rebuild index structures."""
        if self._path is None:
            return

        filepath = self._path / GRAPH_STORE_FILENAME
        if not filepath.exists():
            return

        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            logger.warning("Corrupt graph store at %s, starting fresh", filepath)
            return

        for node_data in data.get("nodes", []):
            node = GraphNode.model_validate(node_data)
            self._nodes[node.node_key] = node

        for edge_data in data.get("edges", []):
            edge = GraphEdge.model_validate(edge_data)
            self._edges[edge.edge_key] = edge
            self._outgoing[edge.source_key].append(edge.edge_key)
            self._incoming[edge.target_key].append(edge.edge_key)
