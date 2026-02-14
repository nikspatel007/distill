"""Tier 1-2 heuristic extractor for building a knowledge graph from sessions.

Walks a ``BaseSession`` and produces graph nodes and edges WITHOUT any LLM calls.
Tier 1 covers structural facts (sessions, files, projects, problems).
Tier 2 adds entity hints from known tech names found in tool arguments.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore
from distill.parsers.models import BaseSession

# Tools that produce "modifies" edges
_WRITE_TOOLS = {"Edit", "Write", "NotebookEdit"}

# Tools that produce "reads" edges
_READ_TOOLS = {"Read", "Glob", "Grep"}

# Regex for detecting failures in Bash output (case insensitive)
_FAILURE_PATTERN = re.compile(
    r"(?:FAIL|ERROR|Exception|Traceback|SyntaxError|ImportError"
    r"|TypeError|ValueError|KeyError|AttributeError|RuntimeError"
    r"|ModuleNotFoundError|FileNotFoundError|NameError|IndentationError"
    r"|AssertionError|OSError|PermissionError|ConnectionError"
    r"|TimeoutError|NotImplementedError)",
    re.IGNORECASE,
)

# Known tech names for Tier 2 entity extraction
KNOWN_ENTITIES: frozenset[str] = frozenset(
    {
        "pytest",
        "mypy",
        "ruff",
        "docker",
        "git",
        "npm",
        "bun",
        "node",
        "python",
        "typescript",
        "javascript",
        "rust",
        "go",
        "java",
        "react",
        "vue",
        "svelte",
        "fastapi",
        "flask",
        "django",
        "postgresql",
        "pgvector",
        "redis",
        "sqlite",
        "mongodb",
        "tailwind",
        "vite",
        "webpack",
        "esbuild",
        "pydantic",
        "sqlalchemy",
        "typer",
        "click",
        "claude",
        "openai",
        "anthropic",
    }
)

# Known path anchors for fallback normalization
_PATH_ANCHORS = ("src/", "tests/", "web/", "docs/")


def _normalize_path(raw_path: str, cwd: str) -> str:
    """Normalize an absolute file path to project-relative.

    Strategy:
    1. If *raw_path* starts with *cwd*, strip the cwd prefix.
    2. Otherwise look for known anchors (``src/``, ``tests/``, etc.).
    3. Fall back to the raw path as-is.
    """
    if not raw_path:
        return raw_path

    # Strip cwd prefix
    if cwd and raw_path.startswith(cwd):
        rel = raw_path[len(cwd) :]
        return rel.lstrip("/")

    # Anchor fallback
    for anchor in _PATH_ANCHORS:
        idx = raw_path.find(anchor)
        if idx >= 0:
            return raw_path[idx:]

    return raw_path


def _ensure_tz(ts: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (default to UTC)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


class SessionGraphExtractor:
    """Extract Tier 1-2 graph nodes and edges from a ``BaseSession``.

    Walks the session structure and heuristically creates:
    - Session, Project, Goal, File, Problem, Entity **nodes**
    - executes_in, motivated_by, modifies, reads, blocked_by, uses, leads_to **edges**

    No LLM calls are made — everything is derived from structural data.
    """

    def __init__(self, store: GraphStore) -> None:
        self._store = store
        self._last_session_by_project: dict[str, str] = {}
        self._last_timestamp_by_project: dict[str, datetime] = {}

    # -- Public API ----------------------------------------------------------

    def extract(self, session: BaseSession) -> None:
        """Extract all Tier 1-2 nodes and edges from *session*."""
        session_key = self._extract_session_node(session)
        self._extract_project(session, session_key)
        self._extract_goal(session, session_key)
        self._extract_files(session, session_key)
        self._extract_problems(session, session_key)
        self._extract_entities(session, session_key)
        self._chain_sessions(session, session_key)

    # -- Step 1: Session node ------------------------------------------------

    def _extract_session_node(self, session: BaseSession) -> str:
        """Create a SESSION node and return its node_key."""
        name = session.summary or session.session_id
        node = GraphNode(
            node_type=NodeType.SESSION,
            name=session.session_id,
            source_id=session.session_id,
            properties={
                "project": session.project,
                "branch": session.metadata.get("branch", ""),
                "tool_count": len(session.tool_calls),
                "summary": name,
            },
        )
        result = self._store.upsert_node(node)
        return result.node_key

    # -- Step 2: Project node + edge -----------------------------------------

    def _extract_project(self, session: BaseSession, session_key: str) -> None:
        if not session.project:
            return

        proj_node = GraphNode(
            node_type=NodeType.PROJECT,
            name=session.project,
        )
        result = self._store.upsert_node(proj_node)

        self._store.upsert_edge(
            GraphEdge(
                source_key=session_key,
                target_key=result.node_key,
                edge_type=EdgeType.EXECUTES_IN,
            )
        )

    # -- Step 3: Goal node ---------------------------------------------------

    def _extract_goal(self, session: BaseSession, session_key: str) -> None:
        first_user_msg = next(
            (m for m in session.messages if m.role == "user"),
            None,
        )
        if first_user_msg is None:
            return

        goal_text = first_user_msg.content[:200]
        goal_node = GraphNode(
            node_type=NodeType.GOAL,
            name=goal_text,
            source_id=session.session_id,
        )
        result = self._store.upsert_node(goal_node)

        self._store.upsert_edge(
            GraphEdge(
                source_key=session_key,
                target_key=result.node_key,
                edge_type=EdgeType.MOTIVATED_BY,
            )
        )

    # -- Step 4: File nodes --------------------------------------------------

    def _extract_files(self, session: BaseSession, session_key: str) -> None:
        cwd = session.metadata.get("cwd", "")

        # Count edits and reads per normalized path
        modify_counts: Counter[str] = Counter()
        read_counts: Counter[str] = Counter()

        for tc in session.tool_calls:
            raw_path = tc.arguments.get("file_path", "") or tc.arguments.get("path", "")
            if not raw_path:
                continue

            rel_path = _normalize_path(raw_path, cwd)
            if not rel_path:
                continue

            if tc.tool_name in _WRITE_TOOLS:
                modify_counts[rel_path] += 1
            elif tc.tool_name in _READ_TOOLS:
                read_counts[rel_path] += 1

        # Create file nodes + modifies edges
        for path, count in modify_counts.items():
            file_node = GraphNode(node_type=NodeType.FILE, name=path)
            self._store.upsert_node(file_node)
            self._store.upsert_edge(
                GraphEdge(
                    source_key=session_key,
                    target_key=file_node.node_key,
                    edge_type=EdgeType.MODIFIES,
                    weight=float(count),
                )
            )

        # Create file nodes + reads edges (skip files already counted as modifies)
        for path, count in read_counts.items():
            if path in modify_counts:
                continue
            file_node = GraphNode(node_type=NodeType.FILE, name=path)
            self._store.upsert_node(file_node)
            self._store.upsert_edge(
                GraphEdge(
                    source_key=session_key,
                    target_key=file_node.node_key,
                    edge_type=EdgeType.READS,
                    weight=float(count),
                )
            )

    # -- Step 5: Problem nodes -----------------------------------------------

    def _extract_problems(self, session: BaseSession, session_key: str) -> None:
        for tc in session.tool_calls:
            if tc.tool_name != "Bash":
                continue
            if tc.result is None:
                continue
            if not _FAILURE_PATTERN.search(tc.result):
                continue

            first_line = tc.result.split("\n")[0][:200]
            problem_name = f"{session.session_id}:{first_line}"
            problem_node = GraphNode(
                node_type=NodeType.PROBLEM,
                name=problem_name,
                source_id=session.session_id,
                properties={
                    "command": tc.arguments.get("command", ""),
                    "error_snippet": first_line,
                },
            )
            self._store.upsert_node(problem_node)
            self._store.upsert_edge(
                GraphEdge(
                    source_key=session_key,
                    target_key=problem_node.node_key,
                    edge_type=EdgeType.BLOCKED_BY,
                )
            )

    # -- Step 6: Entity hints (Tier 2) ---------------------------------------

    def _extract_entities(self, session: BaseSession, session_key: str) -> None:
        found_entities: set[str] = set()

        for tc in session.tool_calls:
            # Scan all string argument values
            for value in tc.arguments.values():
                if not isinstance(value, str):
                    continue
                # Tokenize on word boundaries, lowercase
                tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", value)
                for token in tokens:
                    lower = token.lower()
                    if lower in KNOWN_ENTITIES:
                        found_entities.add(lower)

        for entity_name in found_entities:
            entity_node = GraphNode(
                node_type=NodeType.ENTITY,
                name=entity_name,
            )
            self._store.upsert_node(entity_node)
            self._store.upsert_edge(
                GraphEdge(
                    source_key=session_key,
                    target_key=entity_node.node_key,
                    edge_type=EdgeType.USES,
                )
            )

    # -- Step 7: Session chaining --------------------------------------------

    def _chain_sessions(self, session: BaseSession, session_key: str) -> None:
        project = session.project
        if not project:
            return

        ts = _ensure_tz(session.timestamp)

        prev_key = self._last_session_by_project.get(project)
        prev_ts = self._last_timestamp_by_project.get(project)

        if prev_key is not None and prev_ts is not None:
            gap = ts - prev_ts
            gap_hours = gap.total_seconds() / 3600
            if 0 < gap_hours <= 4:
                self._store.upsert_edge(
                    GraphEdge(
                        source_key=prev_key,
                        target_key=session_key,
                        edge_type=EdgeType.LEADS_TO,
                        properties={"gap_hours": gap_hours},
                    )
                )

        self._last_session_by_project[project] = session_key
        self._last_timestamp_by_project[project] = ts
