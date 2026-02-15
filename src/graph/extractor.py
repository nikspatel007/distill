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

# Regex for detecting failures in Bash output.
# Requires a word-boundary or line-start anchor to avoid matching filenames.
_FAILURE_PATTERN = re.compile(
    r"(?:^|\s|:)(?:FAIL(?:ED)?|ERROR|Exception|Traceback|SyntaxError|ImportError"
    r"|TypeError|ValueError|KeyError|AttributeError|RuntimeError"
    r"|ModuleNotFoundError|FileNotFoundError|NameError|IndentationError"
    r"|AssertionError|OSError|PermissionError|ConnectionError"
    r"|TimeoutError|NotImplementedError)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Patterns that indicate overall success — override failure detection
_SUCCESS_OVERRIDE = re.compile(
    r"(?:0 errors?\b|no errors?\b|all \d+ tests? passed"
    r"|\d+ passed(?:,\s*0 failed)?"
    r"|all checks? passed|Success:)",
    re.IGNORECASE,
)

# Max length for first user message to be considered a human goal
_MAX_GOAL_LENGTH = 500

# Patterns that indicate agent/automated session prompts in first user message.
_AGENT_PROMPT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^You are [\w-]+ \(\w+\)"),  # "You are name (role)"
    re.compile(r"^You are [\w]+-[\w-]+\."),  # Hyphenated agent name: "You are corp-planner-x."
    re.compile(r"^You are \w+ (?:supervisor|lead)\b", re.IGNORECASE),  # factory/squad lead
    re.compile(r"^You are (?:a |the |an )?\w+ agent\b", re.IGNORECASE),  # "You are X agent"
    re.compile(r"^You are (?:a |the |an )?[\w ]{1,40}\.[\s\n]", re.IGNORECASE),  # Role + instruction
    re.compile(r"^You are joining ", re.IGNORECASE),  # Meeting summon
    re.compile(r"^## (?:TASK|ROLE|MISSION)\b"),  # Structured agent task headers
]

# XML tag pattern for summary sanitization
_XML_TAG_RE = re.compile(r"</?[a-zA-Z][\w-]*(?:\s[^>]*)?>")

# Patterns that indicate low-quality summaries (raw prompts, commands, paths)
_LOW_QUALITY_SUMMARY_PATTERNS = [
    re.compile(r"<\w[\w-]*>"),  # XML-style tags
    re.compile(
        r"^(analyze|init|help|run|build|test|start|stop|deploy|status)\s*\w*$",
        re.IGNORECASE,
    ),
    re.compile(r"^/\w+"),  # slash commands
]

# Project aliases — map old/alternate names to canonical name.
# This lets the graph treat renamed projects as one entity.
PROJECT_ALIASES: dict[str, str] = {
    "session-insights": "distill",
}

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

# Short tokens that are too ambiguous when found in file paths.
# Only match these in Bash commands, not in file/path args.
_AMBIGUOUS_ENTITIES: frozenset[str] = frozenset(
    {"go", "node", "click", "java", "rust", "bun"}
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

    def __init__(
        self,
        store: GraphStore,
        extra_agent_patterns: list[str] | None = None,
    ) -> None:
        self._store = store
        self._last_session_by_project: dict[str, str] = {}
        self._last_timestamp_by_project: dict[str, datetime] = {}
        # Merge defaults with user-supplied patterns
        self._agent_patterns: list[re.Pattern[str]] = list(_AGENT_PROMPT_PATTERNS)
        for raw in extra_agent_patterns or []:
            try:
                self._agent_patterns.append(re.compile(raw, re.IGNORECASE))
            except re.error:
                pass

    # -- Public API ----------------------------------------------------------

    def extract(self, session: BaseSession) -> None:
        """Extract all Tier 1-2 nodes and edges from *session*.

        Idempotent: re-processing the same session upserts (merges) all
        nodes and edges without creating duplicates or inflating weights.
        """
        session_type = self._classify_session(session)

        # Check if this session was already processed (node exists in store)
        candidate_key = f"{NodeType.SESSION}:{session.session_id}"
        already_processed = self._store.get_node(candidate_key) is not None

        session_key = self._extract_session_node(session, session_type)
        self._extract_project(session, session_key)
        if session_type == "human":
            self._extract_goal(session, session_key)
        self._extract_files(session, session_key)
        self._extract_problems(session, session_key)
        self._extract_entities(session, session_key)
        # Only accumulate co-occurrence weights on first processing
        if not already_processed:
            self._extract_co_occurrences(session, session_key)
        self._chain_sessions(session, session_key)

    # -- Session classification ----------------------------------------------

    def _classify_session(self, session: BaseSession) -> str:
        """Classify a session as ``"human"``, ``"machine"``, or ``"agent"``.

        Heuristics (no hardcoded prompt matching):
        - **agent**: has ``cycle_info`` or ``signals`` (workflow-managed session),
          or first message matches an agent prompt pattern
        - **machine**: ≤1 user message AND (no tool calls OR first message
          is very long — structured prompts like blog synthesis or entity
          extraction use tools but aren't interactive)
        - **human**: multiple user turns (interactive conversation),
          or single turn with tool calls and a short first message
        """
        # Agent detection: workflow metadata or agent signals present
        if session.cycle_info is not None or len(session.signals) > 0:
            return "agent"

        user_msgs = [m for m in session.messages if m.role == "user"]
        has_tool_calls = len(session.tool_calls) > 0
        multi_turn = len(user_msgs) > 1

        # Single turn (or no messages)
        first_msg_len = len(user_msgs[0].content) if user_msgs else 0

        # Long first message = structured prompt (even with tool calls)
        if first_msg_len > _MAX_GOAL_LENGTH:
            return "machine"

        # Check if first message matches agent prompt patterns
        # (applied after length check so LLM prompts stay "machine")
        if user_msgs:
            first_content = user_msgs[0].content.strip()
            for pattern in self._agent_patterns:
                if pattern.search(first_content):
                    return "agent"

        # Multi-turn is always interactive
        if multi_turn:
            return "human"

        # No tool calls and short/no message = machine
        if not has_tool_calls:
            return "machine"

        return "human"

    # -- Summary cleaning -----------------------------------------------------

    @staticmethod
    def _clean_summary(summary: str, session_id: str) -> str:
        """Validate and clean a session summary.

        Returns the cleaned summary, or *session_id* as fallback for
        low-quality summaries (XML tags, slash commands, file paths, etc.).
        """
        if not summary or not summary.strip():
            return session_id

        text = summary.strip()

        # Strip XML tags
        cleaned = _XML_TAG_RE.sub("", text).strip()
        if not cleaned:
            return session_id

        # Too short (< 5 words)
        if len(cleaned.split()) < 5:
            # Check for raw command patterns
            for pattern in _LOW_QUALITY_SUMMARY_PATTERNS:
                if pattern.match(cleaned):
                    return session_id
            # Check if it's just a file path
            if re.match(r"^[\w./\\-]+\.\w{1,5}$", cleaned):
                return session_id
            # Very short but not a pattern match — still too short
            if len(cleaned.split()) < 3:
                return session_id

        return cleaned

    # -- Step 1: Session node ------------------------------------------------

    def _extract_session_node(
        self, session: BaseSession, session_type: str = "human"
    ) -> str:
        """Create a SESSION node and return its node_key."""
        name = self._clean_summary(session.summary, session.session_id)
        canonical_project = self._resolve_project(session.project) if session.project else ""
        ts = _ensure_tz(session.timestamp)
        node = GraphNode(
            node_type=NodeType.SESSION,
            name=session.session_id,
            source_id=session.session_id,
            first_seen=ts,
            last_seen=ts,
            properties={
                "project": canonical_project,
                "branch": session.metadata.get("branch", ""),
                "tool_count": len(session.tool_calls),
                "summary": name,
                "session_type": session_type,
            },
        )
        result = self._store.upsert_node(node)
        return result.node_key

    # -- Step 2: Project node + edge -----------------------------------------

    @staticmethod
    def _resolve_project(raw_name: str) -> str:
        """Apply project aliases to merge renamed projects."""
        return PROJECT_ALIASES.get(raw_name, raw_name)

    def _extract_project(self, session: BaseSession, session_key: str) -> None:
        if not session.project:
            return

        canonical = self._resolve_project(session.project)
        proj_node = GraphNode(
            node_type=NodeType.PROJECT,
            name=canonical,
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

        # Skip structured prompts (very long first messages are likely LLM prompts)
        if len(first_user_msg.content) > _MAX_GOAL_LENGTH:
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
        # First pass: find all bash failures and track which are resolved
        failures: list[tuple[int, str, str]] = []  # (index, command, first_line)

        for i, tc in enumerate(session.tool_calls):
            if tc.tool_name != "Bash" or tc.result is None:
                continue
            if not _FAILURE_PATTERN.search(tc.result):
                continue
            # Check for success-override patterns (e.g., "0 errors", "all passed")
            if _SUCCESS_OVERRIDE.search(tc.result):
                continue
            first_line = tc.result.split("\n")[0][:200]
            failures.append((i, tc.arguments.get("command", ""), first_line))

        # Second pass: check resolution — if a failure is followed by edits
        # then a successful bash, mark it resolved
        for idx, command, first_line in failures:
            resolved = self._is_resolved(session, idx)
            problem_name = f"{session.session_id}:{first_line}"
            problem_node = GraphNode(
                node_type=NodeType.PROBLEM,
                name=problem_name,
                source_id=session.session_id,
                properties={
                    "command": command,
                    "error_snippet": first_line,
                    "resolved": resolved,
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

    @staticmethod
    def _is_resolved(session: BaseSession, failure_idx: int) -> bool:
        """Check if a bash failure at *failure_idx* was resolved later.

        Looks for the pattern: failure → edit(s) → bash success.
        """
        saw_edit = False
        for tc in session.tool_calls[failure_idx + 1 :]:
            if tc.tool_name in _WRITE_TOOLS:
                saw_edit = True
            elif tc.tool_name == "Bash" and saw_edit:
                if tc.result is not None and not _FAILURE_PATTERN.search(tc.result):
                    return True
                if tc.result is not None and _SUCCESS_OVERRIDE.search(tc.result):
                    return True
        return False

    # -- Step 6: Entity hints (Tier 2) ---------------------------------------

    def _extract_entities(self, session: BaseSession, session_key: str) -> None:
        found_entities: set[str] = set()

        for tc in session.tool_calls:
            is_bash = tc.tool_name == "Bash"
            for arg_name, value in tc.arguments.items():
                if not isinstance(value, str):
                    continue
                is_path_arg = arg_name in ("file_path", "path", "notebook_path")
                tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", value)
                for token in tokens:
                    lower = token.lower()
                    if lower not in KNOWN_ENTITIES:
                        continue
                    # Ambiguous short tokens (go, node, click, etc.)
                    # only count from Bash commands, not file paths
                    if lower in _AMBIGUOUS_ENTITIES and (is_path_arg or not is_bash):
                        continue
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

    # -- Step 6b: Entity co-occurrence edges ---------------------------------

    def _extract_co_occurrences(
        self, session: BaseSession, session_key: str
    ) -> None:
        """Create CO_OCCURS edges between entities found in the same session.

        Weight accumulates across sessions: if entities A and B co-occur
        in 3 sessions, the edge weight becomes 3.0.
        """
        # Find which entities this session uses
        uses_edges = self._store.find_edges(
            source_key=session_key, edge_type=EdgeType.USES
        )
        entity_keys = sorted(e.target_key for e in uses_edges)

        # Create pairwise co-occurrence edges (sorted to ensure stable ordering)
        for i, key_a in enumerate(entity_keys):
            for key_b in entity_keys[i + 1 :]:
                edge = GraphEdge(
                    source_key=key_a,
                    target_key=key_b,
                    edge_type=EdgeType.CO_OCCURS,
                )
                # Read existing weight and accumulate
                existing = self._store._edges.get(edge.edge_key)
                if existing is not None:
                    edge = edge.model_copy(
                        update={"weight": existing.weight + 1.0}
                    )
                self._store.upsert_edge(edge)

    # -- Step 7: Session chaining --------------------------------------------

    def _chain_sessions(self, session: BaseSession, session_key: str) -> None:
        project = self._resolve_project(session.project) if session.project else ""
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
