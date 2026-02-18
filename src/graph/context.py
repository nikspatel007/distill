"""Context scoring for knowledge-graph nodes.

Scores each node's relevance based on temporal recency, structural
proximity to a focus node, and (placeholder) semantic similarity.
"""

from __future__ import annotations

import math
from collections import deque
from datetime import UTC, datetime

from distill.graph.models import ContextScore
from distill.graph.store import GraphStore

# Module-level defaults -------------------------------------------------------

_DECAY_LAMBDA: float = 0.1  # ~50% relevance after 7 days
_W_TEMPORAL: float = 0.3
_W_STRUCTURAL: float = 0.5
_W_SEMANTIC: float = 0.2


class ContextScorer:
    """Score graph nodes by relevance to a focus context.

    The combined score is::

        w_temporal * temporal + w_structural * structural + w_semantic * semantic

    where *semantic* is currently always 0.0 (placeholder for future
    embedding-based similarity).
    """

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
        self._now = now
        self._decay_lambda = decay_lambda
        self._w_temporal = w_temporal
        self._w_structural = w_structural
        self._w_semantic = w_semantic

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Attach UTC if *dt* is timezone-naive."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    def _resolve_now(self, now: datetime | None) -> datetime:
        """Return *now* (parameter) > constructor *now* > ``utcnow``."""
        ts = now or self._now or datetime.now(tz=UTC)
        return self._ensure_utc(ts)

    # -- public API -----------------------------------------------------------

    def temporal_score(self, node_key: str, now: datetime | None = None) -> float:
        """Exponential decay based on ``node.last_seen``.

        Formula: ``e^(-lambda * days_since_last_seen)``

        Returns 0.0 if the node is not found.
        """
        node = self._store.get_node(node_key)
        if node is None:
            return 0.0

        reference = self._resolve_now(now)
        last_seen = self._ensure_utc(node.last_seen)
        delta = reference - last_seen
        days = max(delta.total_seconds() / 86400.0, 0.0)
        return math.exp(-self._decay_lambda * days)

    def structural_score(
        self,
        node_key: str,
        focus_key: str,
        max_depth: int = 3,
    ) -> float:
        """Shortest-path proximity: ``1 / (1 + distance)``.

        Uses BFS from *focus_key*, traversing both outgoing and incoming
        edges at each level.  Returns 1.0 for self, 0.0 if unreachable
        within *max_depth*.
        """
        if node_key == focus_key:
            return 1.0

        # If either node is absent from the store, unreachable.
        if self._store.get_node(focus_key) is None:
            return 0.0
        if self._store.get_node(node_key) is None:
            return 0.0

        # BFS using store internal indices for efficiency.
        visited: set[str] = {focus_key}
        queue: deque[tuple[str, int]] = deque([(focus_key, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # Collect neighbor keys via outgoing + incoming edges.
            neighbor_keys: list[str] = []

            for ekey in self._store._outgoing.get(current, []):
                edge = self._store._edges[ekey]
                neighbor_keys.append(edge.target_key)

            for ekey in self._store._incoming.get(current, []):
                edge = self._store._edges[ekey]
                neighbor_keys.append(edge.source_key)

            for nkey in neighbor_keys:
                if nkey in visited:
                    continue
                visited.add(nkey)
                next_depth = depth + 1
                if nkey == node_key:
                    return 1.0 / (1.0 + next_depth)
                queue.append((nkey, next_depth))

        return 0.0

    def score_all(
        self,
        focus_key: str | None = None,
        top_k: int | None = None,
        min_score: float = 0.0,
        exclude_keys: set[str] | None = None,
    ) -> list[ContextScore]:
        """Score every node and return sorted results.

        Parameters
        ----------
        focus_key:
            If provided, combine temporal + structural scores.
            If ``None``, use temporal scoring only (global context).
        top_k:
            Maximum number of results to return.
        min_score:
            Exclude nodes below this combined score.
        exclude_keys:
            Node keys to skip entirely (e.g., machine sessions).

        Returns
        -------
        list[ContextScore]
            Sorted descending by score.
        """
        now = self._resolve_now(None)
        all_nodes = self._store.find_nodes()
        results: list[ContextScore] = []
        skip = exclude_keys or set()

        for node in all_nodes:
            key = node.node_key

            # Skip the focus node itself.
            if key == focus_key:
                continue

            # Skip excluded keys
            if key in skip:
                continue

            temporal = self.temporal_score(key, now=now)
            semantic = 0.0  # placeholder

            if focus_key is not None:
                structural = self.structural_score(key, focus_key)
                combined = (
                    self._w_temporal * temporal
                    + self._w_structural * structural
                    + self._w_semantic * semantic
                )
                components = {
                    "temporal": temporal,
                    "structural": structural,
                    "semantic": semantic,
                }
            else:
                combined = temporal
                components = {
                    "temporal": temporal,
                    "semantic": semantic,
                }

            if combined < min_score:
                continue

            results.append(
                ContextScore(
                    node_key=key,
                    focus_key=focus_key,
                    score=combined,
                    components=components,
                    computed_at=now,
                )
            )

        # Sort descending by score.
        results.sort(key=lambda cs: cs.score, reverse=True)

        if top_k is not None:
            results = results[:top_k]

        return results
