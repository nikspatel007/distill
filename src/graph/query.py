"""High-level query interface for the knowledge graph.

Provides structured queries for both the web dashboard and Claude
context injection, backed by ``GraphStore`` and ``ContextScorer``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from distill.graph.context import ContextScorer
from distill.graph.models import GraphNode, NodeType
from distill.graph.store import GraphStore

# Ordered list of node types for render_context sections.
_TYPE_ORDER: list[NodeType] = [
    NodeType.THREAD,
    NodeType.GOAL,
    NodeType.DECISION,
    NodeType.INSIGHT,
    NodeType.PROBLEM,
    NodeType.SESSION,
    NodeType.FILE,
    NodeType.ENTITY,
    NodeType.PROJECT,
    NodeType.ARTIFACT,
]

# Display names for section headers (Title Case of enum value).
_TYPE_DISPLAY: dict[NodeType, str] = {
    NodeType.THREAD: "Threads",
    NodeType.GOAL: "Goals",
    NodeType.DECISION: "Decisions",
    NodeType.INSIGHT: "Insights",
    NodeType.PROBLEM: "Problems",
    NodeType.SESSION: "Sessions",
    NodeType.FILE: "Files",
    NodeType.ENTITY: "Entities",
    NodeType.PROJECT: "Projects",
    NodeType.ARTIFACT: "Artifacts",
}


class GraphQuery:
    """High-level query interface for the knowledge graph.

    Wraps ``GraphStore`` and ``ContextScorer`` to provide structured
    result dicts suitable for dashboard APIs and LLM context injection.
    """

    def __init__(self, store: GraphStore, *, now: datetime | None = None) -> None:
        self._store = store
        self._now = now or datetime.now(UTC)

    # -- Public API ----------------------------------------------------------

    def about(self, name: str, max_hops: int = 2) -> dict[str, Any]:
        """Return focus node, scored neighbors, and connecting edges.

        Parameters
        ----------
        name:
            Human-friendly name to look up (tries type prefixes, then
            substring match).
        max_hops:
            BFS depth for neighbor discovery.

        Returns
        -------
        dict
            ``{"focus": {...} | None, "neighbors": [...], "edges": [...]}``
        """
        node = self._find_node_by_name(name)
        if node is None:
            return {"focus": None, "neighbors": [], "edges": []}

        focus = {"name": node.name, "type": node.node_type.value}

        # Get neighbors within max_hops
        neighbor_nodes = self._store.neighbors(node.node_key, max_hops=max_hops)

        # Score neighbors with ContextScorer
        scorer = ContextScorer(self._store, now=self._now)
        scored: list[dict[str, Any]] = []
        for nb in neighbor_nodes:
            score = scorer.temporal_score(nb.node_key, now=self._now)
            structural = scorer.structural_score(nb.node_key, node.node_key)
            combined = 0.3 * score + 0.5 * structural + 0.2 * 0.0  # semantic placeholder
            scored.append(
                {
                    "name": nb.name,
                    "type": nb.node_type.value,
                    "relevance": round(combined, 4),
                    "last_seen": nb.last_seen.isoformat(),
                }
            )

        # Sort by relevance descending
        scored.sort(key=lambda x: x["relevance"], reverse=True)

        # Collect edges involving the focus node and its neighbors
        neighbor_keys = {nb.node_key for nb in neighbor_nodes}
        all_keys = neighbor_keys | {node.node_key}
        edges: list[dict[str, Any]] = []

        for edge in self._store.find_edges():
            if edge.source_key in all_keys and edge.target_key in all_keys:
                edges.append(
                    {
                        "type": edge.edge_type.value,
                        "source": edge.source_key,
                        "target": edge.target_key,
                        "weight": edge.weight,
                    }
                )

        return {"focus": focus, "neighbors": scored, "edges": edges}

    def stats(self) -> dict[str, Any]:
        """Return summary statistics about the graph.

        Delegates directly to ``GraphStore.stats()``.
        """
        return self._store.stats()

    def timeline(self, project: str | None = None) -> list[dict[str, Any]]:
        """Return session nodes as a chronological timeline.

        Parameters
        ----------
        project:
            If provided, only include sessions for this project.

        Returns
        -------
        list[dict]
            ``[{"name", "timestamp", "project", "branch"}, ...]``
            sorted by ``first_seen`` ascending.
        """
        sessions = self._store.find_nodes(node_type=NodeType.SESSION)

        if project is not None:
            sessions = [s for s in sessions if s.properties.get("project") == project]

        # Sort by first_seen ascending
        sessions.sort(key=lambda s: s.first_seen)

        result: list[dict[str, Any]] = []
        for s in sessions:
            result.append(
                {
                    "name": s.name,
                    "timestamp": s.first_seen.isoformat(),
                    "project": s.properties.get("project", ""),
                    "branch": s.properties.get("branch", ""),
                }
            )
        return result

    def render_context(self, focus: str | None = None, top_k: int = 15) -> str:
        """Render scored graph nodes as markdown for LLM context injection.

        Parameters
        ----------
        focus:
            If provided, score relative to this node name.
            Otherwise use global (temporal-only) scoring.
        top_k:
            Maximum total nodes to consider before grouping.

        Returns
        -------
        str
            Markdown text with sections per node type, or
            ``"No relevant context found."`` if no scores.
        """
        scorer = ContextScorer(self._store, now=self._now)

        # Resolve focus to a node key
        focus_key: str | None = None
        if focus is not None:
            focus_node = self._find_node_by_name(focus)
            if focus_node is not None:
                focus_key = focus_node.node_key

        scores = scorer.score_all(focus_key=focus_key, top_k=top_k)

        if not scores:
            return "No relevant context found."

        # Group by node type
        grouped: dict[NodeType, list[tuple[str, float]]] = {}
        for cs in scores:
            node = self._store.get_node(cs.node_key)
            if node is None:
                continue
            nt = node.node_type
            if nt not in grouped:
                grouped[nt] = []
            grouped[nt].append((node.name, cs.score))

        if not grouped:
            return "No relevant context found."

        # Render markdown
        lines: list[str] = ["# Active Context", ""]

        for node_type in _TYPE_ORDER:
            if node_type not in grouped:
                continue
            items = grouped[node_type]
            # Top 5 items per type
            items = items[:5]
            display_name = _TYPE_DISPLAY.get(node_type, node_type.value.title() + "s")
            lines.append(f"## {display_name}")
            for name, score in items:
                lines.append(f"- {name} (relevance: {score:.2f})")
            lines.append("")

        return "\n".join(lines)

    # -- Helpers -------------------------------------------------------------

    def _find_node_by_name(self, name: str) -> GraphNode | None:
        """Try each NodeType prefix, then fallback to name_contains search."""
        for node_type in NodeType:
            node = self._store.get_node(f"{node_type}:{name}")
            if node:
                return node
        matches = self._store.find_nodes(name_contains=name)
        return matches[0] if matches else None
