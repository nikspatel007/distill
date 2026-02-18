"""High-level query interface for the knowledge graph.

Provides structured queries for both the web dashboard and Claude
context injection, backed by ``GraphStore`` and ``ContextScorer``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from distill.graph.context import ContextScorer
from distill.graph.models import EdgeType, GraphNode, NodeType
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

        summary = node.properties.get("summary", node.name) if node.properties else node.name
        focus = {"name": node.name, "type": node.node_type.value, "summary": summary}

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
            summary = s.properties.get("summary", s.name) if s.properties else s.name
            result.append(
                {
                    "name": s.name,
                    "summary": summary,
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

        # Collect non-human session keys to exclude from scoring
        machine_keys: set[str] = set()
        for node in self._store.find_nodes(node_type=NodeType.SESSION):
            if node.properties and node.properties.get("session_type") in (
                "machine",
                "agent",
            ):
                machine_keys.add(node.node_key)

        scores = scorer.score_all(focus_key=focus_key, top_k=top_k, exclude_keys=machine_keys)

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

            # Use summary for sessions, name for everything else
            display_name = node.name
            if nt == NodeType.SESSION and node.properties:
                display_name = node.properties.get("summary", node.name)
            grouped[nt].append((display_name, cs.score))

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

    def gather_context_data(
        self,
        project: str | None = None,
        max_sessions: int = 10,
        max_hours: float = 72.0,
    ) -> dict[str, Any]:
        """Gather structured context data for LLM synthesis.

        Instead of scoring every node (slow at scale), this does targeted
        traversal: find recent human sessions, follow their edges to get
        files, problems, entities, and goals.

        Parameters
        ----------
        project:
            If provided, only include sessions for this project.
        max_sessions:
            Maximum number of recent sessions to include.
        max_hours:
            Only include sessions from the last N hours.

        Returns
        -------
        dict
            Structured data ready for prompt formatting.
        """
        now = self._now
        cutoff = now.timestamp() - (max_hours * 3600)

        # Find recent human sessions, sorted newest first
        all_sessions = self._store.find_nodes(node_type=NodeType.SESSION)
        recent: list[tuple[GraphNode, float]] = []
        for s in all_sessions:
            session_type = (
                s.properties.get("session_type", "unknown") if s.properties else "unknown"
            )
            if session_type != "human":
                continue
            if project and s.properties and s.properties.get("project") != project:
                continue
            ts = s.last_seen.timestamp() if s.last_seen else 0
            if ts < cutoff:
                continue
            hours_ago = (now.timestamp() - ts) / 3600
            recent.append((s, hours_ago))

        recent.sort(key=lambda x: x[1])  # nearest first
        recent = recent[:max_sessions]

        # For each session, follow edges to get related nodes
        session_data: list[dict[str, Any]] = []
        all_entity_counts: dict[str, int] = {}
        all_file_edits: dict[str, float] = {}  # path -> most recent hours_ago

        for sess_node, hours_ago in recent:
            skey = sess_node.node_key
            summary = sess_node.name
            if sess_node.properties:
                summary = str(sess_node.properties.get("summary", sess_node.name))

            # Files modified/read
            files_modified: list[str] = []
            files_read: list[str] = []
            for edge in self._store.find_edges(source_key=skey, edge_type=EdgeType.MODIFIES):
                fname = edge.target_key.removeprefix("file:")
                files_modified.append(fname)
                if fname not in all_file_edits or hours_ago < all_file_edits[fname]:
                    all_file_edits[fname] = hours_ago
            for edge in self._store.find_edges(source_key=skey, edge_type=EdgeType.READS):
                files_read.append(edge.target_key.removeprefix("file:"))

            # Problems
            problems: list[dict[str, Any]] = []
            for edge in self._store.find_edges(source_key=skey, edge_type=EdgeType.BLOCKED_BY):
                pnode = self._store.get_node(edge.target_key)
                if pnode and pnode.properties:
                    problems.append(
                        {
                            "error": str(pnode.properties.get("error_snippet", "")),
                            "command": str(pnode.properties.get("command", "")),
                            "resolved": bool(pnode.properties.get("resolved", False)),
                        }
                    )

            # Goal
            goal = ""
            for edge in self._store.find_edges(source_key=skey, edge_type=EdgeType.MOTIVATED_BY):
                gnode = self._store.get_node(edge.target_key)
                if gnode:
                    goal = gnode.name

            # Entities
            entities: list[str] = []
            for edge in self._store.find_edges(source_key=skey, edge_type=EdgeType.USES):
                ename = edge.target_key.removeprefix("entity:")
                entities.append(ename)
                all_entity_counts[ename] = all_entity_counts.get(ename, 0) + 1

            sess_proj = ""
            if sess_node.properties:
                sess_proj = str(sess_node.properties.get("project", ""))

            session_data.append(
                {
                    "id": sess_node.name,
                    "summary": summary,
                    "hours_ago": round(hours_ago, 1),
                    "project": sess_proj,
                    "goal": goal,
                    "files_modified": files_modified,
                    "files_read": files_read,
                    "problems": problems,
                    "entities": entities,
                }
            )

        # Other projects with recent activity (if not filtering by project)
        other_projects: list[dict[str, Any]] = []
        if project:
            for s in all_sessions:
                if not s.properties:
                    continue
                sp = str(s.properties.get("project", ""))
                st = s.properties.get("session_type", "")
                if sp == project or st != "human" or not sp:
                    continue
                ts = s.last_seen.timestamp() if s.last_seen else 0
                if ts < cutoff:
                    continue
                hours_ago = (now.timestamp() - ts) / 3600
                summary = str(s.properties.get("summary", s.name))
                other_projects.append(
                    {
                        "project": sp,
                        "summary": summary,
                        "hours_ago": round(hours_ago, 1),
                    }
                )
            other_projects.sort(key=lambda x: x["hours_ago"])
            other_projects = other_projects[:5]

        # Top entities by frequency
        top_entities = sorted(all_entity_counts.items(), key=lambda x: -x[1])[:10]

        # Active files (recently modified, sorted by recency)
        active_files = sorted(all_file_edits.items(), key=lambda x: x[1])[:15]

        return {
            "project": project or "(all)",
            "time_window_hours": max_hours,
            "sessions": session_data,
            "top_entities": [{"name": n, "count": c} for n, c in top_entities],
            "active_files": [{"path": p, "hours_ago": round(h, 1)} for p, h in active_files],
            "other_projects": other_projects,
        }

    # -- Helpers -------------------------------------------------------------

    def _find_node_by_name(self, name: str) -> GraphNode | None:
        """Try each NodeType prefix, then fallback to name_contains search."""
        for node_type in NodeType:
            node = self._store.get_node(f"{node_type}:{name}")
            if node:
                return node
        matches = self._store.find_nodes(name_contains=name)
        return matches[0] if matches else None
