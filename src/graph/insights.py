"""Structural insight extraction from the knowledge graph.

Computes actionable retrospective insights — coupling clusters, error
hotspots, scope warnings, recurring problems — and formats them for
injection into daily journal prompts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import re

from distill.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from distill.graph.store import GraphStore

# Patterns for noise problem names (UUIDs, raw paths, timestamps)
_NOISE_PATTERNS = [
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-"),  # UUID prefix
    re.compile(r"^/"),  # absolute paths
    re.compile(r"^\s*$"),  # blank
    re.compile(r"^Exit code \d+$"),  # bare exit codes (not actionable)
]


def _short_path(path: str) -> str:
    """Shorten a file path to parent/filename for readability.

    Generic names like ``__init__.py`` get an extra parent level.
    """
    parts = path.replace("\\", "/").split("/")
    basename = parts[-1] if parts else path
    # For generic names, include parent dir
    generic = {"__init__.py", "index.ts", "index.js", "README.md", "models.py", "config.py"}
    if basename in generic and len(parts) >= 2:
        return "/".join(parts[-2:])
    if len(parts) >= 2 and basename.startswith("test_"):
        return "/".join(parts[-2:])
    return basename


def _is_noise_problem(msg: str) -> bool:
    """Return True if the problem name looks like noise rather than a real error."""
    return any(p.search(msg) for p in _NOISE_PATTERNS)


# File patterns to exclude from hotspot analysis (templates, generated, non-code)
_HOTSPOT_EXCLUDE = {
    "_feature.md", "_epic.md", "_bug.md", "_task.md", "_story.md",
    "DONE.md", "TASK.md", "status.yaml", "events.log",
}


@dataclass
class CouplingCluster:
    """A group of files that are frequently co-modified."""

    files: list[str]
    co_modification_count: int
    description: str = ""


@dataclass
class ErrorHotspot:
    """A file with high problem association."""

    file: str
    problem_count: int
    recent_problems: list[str] = field(default_factory=list)


@dataclass
class ScopeWarning:
    """A session that exceeded the safe file-modification threshold."""

    session_name: str
    files_modified: int
    project: str = ""
    problems_hit: int = 0


@dataclass
class RecurringProblem:
    """A problem pattern that appeared in multiple sessions."""

    pattern: str
    occurrence_count: int
    sessions: list[str] = field(default_factory=list)


@dataclass
class DailyInsights:
    """All structural insights for a given day."""

    date: str
    coupling_clusters: list[CouplingCluster] = field(default_factory=list)
    error_hotspots: list[ErrorHotspot] = field(default_factory=list)
    scope_warnings: list[ScopeWarning] = field(default_factory=list)
    recurring_problems: list[RecurringProblem] = field(default_factory=list)
    session_count: int = 0
    avg_files_per_session: float = 0.0
    total_problems: int = 0


class GraphInsights:
    """Structural insight extraction from a knowledge graph.

    Computes actionable patterns from the graph's structure rather than
    just listing raw session data.  Designed for daily retrospective
    injection into journal prompts.
    """

    # Sessions modifying more than this many files are flagged.
    SCOPE_THRESHOLD = 5

    def __init__(self, store: GraphStore, *, now: datetime | None = None) -> None:
        self._store = store
        self._now = now or datetime.now(UTC)

    def co_modification_clusters(
        self, *, min_count: int = 3, max_pairs: int = 10
    ) -> list[CouplingCluster]:
        """Find file pairs that are frequently modified in the same session.

        Returns pairs sorted by co-modification count descending.
        """
        sessions = self._store.find_nodes(node_type=NodeType.SESSION)
        co_mod: Counter[tuple[str, str]] = Counter()

        for s in sessions:
            modified = [
                e.target_key.removeprefix("file:")
                for e in self._store.find_edges(
                    source_key=s.node_key, edge_type=EdgeType.MODIFIES
                )
            ]
            short = [_short_path(f) for f in modified]
            unique = sorted(set(short))
            for i, f1 in enumerate(unique):
                for f2 in unique[i + 1 :]:
                    co_mod[(f1, f2)] += 1

        clusters: list[CouplingCluster] = []
        for (f1, f2), count in co_mod.most_common(max_pairs):
            if count < min_count:
                break
            clusters.append(
                CouplingCluster(
                    files=[f1, f2],
                    co_modification_count=count,
                    description=f"{f1} and {f2} are modified together in {count} sessions",
                )
            )
        return clusters

    def error_hotspots(self, *, top_n: int = 10) -> list[ErrorHotspot]:
        """Find files most associated with problems.

        A file is associated with a problem when it was modified in a
        session that also had BLOCKED_BY edges to problem nodes.
        """
        file_problems: Counter[str] = Counter()
        file_recent: defaultdict[str, list[str]] = defaultdict(list)

        sessions = self._store.find_nodes(node_type=NodeType.SESSION)
        for s in sessions:
            skey = s.node_key
            # Find problems in this session
            problems = self._store.find_edges(
                source_key=skey, edge_type=EdgeType.BLOCKED_BY
            )
            if not problems:
                continue

            problem_snippets: list[str] = []
            for pe in problems:
                pnode = self._store.get_node(pe.target_key)
                if pnode and pnode.properties:
                    snippet = str(pnode.properties.get("error_snippet", ""))[:80]
                    if snippet:
                        problem_snippets.append(snippet)

            # Find files modified in this session
            modified = self._store.find_edges(
                source_key=skey, edge_type=EdgeType.MODIFIES
            )
            for me in modified:
                fname = me.target_key.removeprefix("file:")
                short = _short_path(fname)
                file_problems[short] += len(problems)
                file_recent[short].extend(problem_snippets[:2])

        hotspots: list[ErrorHotspot] = []
        for fname, count in file_problems.most_common(top_n + len(_HOTSPOT_EXCLUDE)):
            basename = fname.rsplit("/", 1)[-1] if "/" in fname else fname
            if basename in _HOTSPOT_EXCLUDE:
                continue
            recent = file_recent[fname][:3]
            hotspots.append(ErrorHotspot(file=fname, problem_count=count, recent_problems=recent))
            if len(hotspots) >= top_n:
                break
        return hotspots

    def scope_warnings(
        self, *, lookback_hours: float = 48.0
    ) -> list[ScopeWarning]:
        """Find recent sessions that exceeded the safe file-modification threshold."""
        cutoff = self._now - timedelta(hours=lookback_hours)
        sessions = self._store.find_nodes(node_type=NodeType.SESSION)
        warnings: list[ScopeWarning] = []

        for s in sessions:
            if s.last_seen.tzinfo is None:
                ts = s.last_seen.replace(tzinfo=UTC)
            else:
                ts = s.last_seen
            if ts < cutoff:
                continue

            modified = self._store.find_edges(
                source_key=s.node_key, edge_type=EdgeType.MODIFIES
            )
            n_files = len(modified)
            if n_files <= self.SCOPE_THRESHOLD:
                continue

            problems = self._store.find_edges(
                source_key=s.node_key, edge_type=EdgeType.BLOCKED_BY
            )
            project = ""
            if s.properties:
                project = str(s.properties.get("project", ""))

            summary = s.name
            if s.properties:
                summary = str(s.properties.get("summary", s.name))

            warnings.append(
                ScopeWarning(
                    session_name=summary[:100],
                    files_modified=n_files,
                    project=project,
                    problems_hit=len(problems),
                )
            )

        warnings.sort(key=lambda w: -w.files_modified)
        return warnings

    def recurring_problems(
        self, *, min_occurrences: int = 2, top_n: int = 10
    ) -> list[RecurringProblem]:
        """Find problem patterns that appear in multiple sessions."""
        problems = self._store.find_nodes(node_type=NodeType.PROBLEM)
        pattern_sessions: defaultdict[str, list[str]] = defaultdict(list)

        for p in problems:
            # Normalize: take first 60 chars as a pattern key
            msg = p.name[:60].strip() if p.name else ""
            if not msg or len(msg) < 5:
                continue
            if _is_noise_problem(msg):
                continue

            # Find session(s) connected to this problem
            edges = self._store.find_edges(
                target_key=p.node_key, edge_type=EdgeType.BLOCKED_BY
            )
            for e in edges:
                snode = self._store.get_node(e.source_key)
                if snode:
                    sname = str(snode.properties.get("summary", snode.name))[:60] if snode.properties else snode.name[:60]
                    pattern_sessions[msg].append(sname)

        recurring: list[RecurringProblem] = []
        for pattern, sessions in sorted(
            pattern_sessions.items(), key=lambda x: -len(x[1])
        ):
            if len(sessions) < min_occurrences:
                continue
            recurring.append(
                RecurringProblem(
                    pattern=pattern,
                    occurrence_count=len(sessions),
                    sessions=sessions[:5],
                )
            )
            if len(recurring) >= top_n:
                break
        return recurring

    def daily_session_stats(
        self, *, lookback_hours: float = 48.0
    ) -> dict[str, Any]:
        """Compute session statistics for recent sessions."""
        cutoff = self._now - timedelta(hours=lookback_hours)
        sessions = self._store.find_nodes(node_type=NodeType.SESSION)

        count = 0
        total_files = 0
        total_problems = 0

        for s in sessions:
            if s.last_seen.tzinfo is None:
                ts = s.last_seen.replace(tzinfo=UTC)
            else:
                ts = s.last_seen
            if ts < cutoff:
                continue
            count += 1
            n_files = len(
                self._store.find_edges(
                    source_key=s.node_key, edge_type=EdgeType.MODIFIES
                )
            )
            total_files += n_files
            total_problems += len(
                self._store.find_edges(
                    source_key=s.node_key, edge_type=EdgeType.BLOCKED_BY
                )
            )

        return {
            "session_count": count,
            "avg_files_per_session": round(total_files / count, 1) if count else 0,
            "total_problems": total_problems,
        }

    def generate_daily_insights(
        self, *, lookback_hours: float = 48.0
    ) -> DailyInsights:
        """Generate all structural insights for the current period.

        Runs all analysis methods and returns a ``DailyInsights`` object.
        """
        stats = self.daily_session_stats(lookback_hours=lookback_hours)
        return DailyInsights(
            date=self._now.strftime("%Y-%m-%d"),
            coupling_clusters=self.co_modification_clusters(min_count=3, max_pairs=5),
            error_hotspots=self.error_hotspots(top_n=5),
            scope_warnings=self.scope_warnings(lookback_hours=lookback_hours),
            recurring_problems=self.recurring_problems(min_occurrences=2, top_n=5),
            session_count=stats["session_count"],
            avg_files_per_session=stats["avg_files_per_session"],
            total_problems=stats["total_problems"],
        )


    def persist_insights(self, insights: DailyInsights) -> int:
        """Write insights back into the graph as INSIGHT, THREAD, and RELATED_TO structures.

        Creates:
        - INSIGHT nodes for coupling clusters, error hotspots, and scope warnings
        - THREAD nodes for recurring problems (tracked over time)
        - RELATED_TO edges between coupled file pairs
        - REFERENCES edges from insights to the files they concern

        Returns the number of nodes created/updated.

        Idempotent: uses date-based keys so re-running for the same day
        upserts rather than duplicates.
        """
        ts = self._now
        count = 0

        # 1. Coupling clusters → INSIGHT nodes + RELATED_TO edges between files
        for i, cluster in enumerate(insights.coupling_clusters):
            insight_name = f"coupling:{insights.date}:{cluster.files[0]}+{cluster.files[1]}"
            node = GraphNode(
                node_type=NodeType.INSIGHT,
                name=insight_name,
                first_seen=ts,
                last_seen=ts,
                properties={
                    "insight_type": "coupling_cluster",
                    "date": insights.date,
                    "files": cluster.files,
                    "co_modification_count": cluster.co_modification_count,
                    "description": (
                        f"{cluster.files[0]} and {cluster.files[1]} are "
                        f"co-modified in {cluster.co_modification_count} sessions"
                    ),
                },
            )
            self._store.upsert_node(node)
            count += 1

            # RELATED_TO edge between the two files (if they exist as nodes)
            for f in cluster.files:
                file_nodes = self._store.find_nodes(
                    node_type=NodeType.FILE, name_contains=f
                )
                for fn in file_nodes[:1]:  # link to first match
                    self._store.upsert_edge(
                        GraphEdge(
                            source_key=node.node_key,
                            target_key=fn.node_key,
                            edge_type=EdgeType.REFERENCES,
                            weight=float(cluster.co_modification_count),
                            properties={"insight_type": "coupling"},
                        )
                    )

            # RELATED_TO edge between the two files themselves
            if len(cluster.files) == 2:
                f1_nodes = self._store.find_nodes(
                    node_type=NodeType.FILE, name_contains=cluster.files[0]
                )
                f2_nodes = self._store.find_nodes(
                    node_type=NodeType.FILE, name_contains=cluster.files[1]
                )
                if f1_nodes and f2_nodes:
                    self._store.upsert_edge(
                        GraphEdge(
                            source_key=f1_nodes[0].node_key,
                            target_key=f2_nodes[0].node_key,
                            edge_type=EdgeType.RELATED_TO,
                            weight=float(cluster.co_modification_count),
                            properties={
                                "relationship": "co_modified",
                                "strength": cluster.co_modification_count,
                            },
                        )
                    )

        # 2. Error hotspots → INSIGHT nodes linked to files
        for hotspot in insights.error_hotspots:
            insight_name = f"hotspot:{insights.date}:{hotspot.file}"
            node = GraphNode(
                node_type=NodeType.INSIGHT,
                name=insight_name,
                first_seen=ts,
                last_seen=ts,
                properties={
                    "insight_type": "error_hotspot",
                    "date": insights.date,
                    "file": hotspot.file,
                    "problem_count": hotspot.problem_count,
                    "description": (
                        f"{hotspot.file} has {hotspot.problem_count} "
                        f"problem-associations across all sessions"
                    ),
                },
            )
            self._store.upsert_node(node)
            count += 1

            # Link to the actual file node
            file_nodes = self._store.find_nodes(
                node_type=NodeType.FILE, name_contains=hotspot.file
            )
            for fn in file_nodes[:1]:
                self._store.upsert_edge(
                    GraphEdge(
                        source_key=node.node_key,
                        target_key=fn.node_key,
                        edge_type=EdgeType.REFERENCES,
                        weight=float(hotspot.problem_count),
                        properties={"insight_type": "error_hotspot"},
                    )
                )

        # 3. Recurring problems → THREAD nodes (tracked over time)
        for rp in insights.recurring_problems:
            thread_name = f"recurring:{rp.pattern[:50]}"
            existing = self._store.get_node(f"{NodeType.THREAD}:{thread_name}")
            mention_count = rp.occurrence_count
            if existing and existing.properties:
                # Accumulate: track how many times we've seen this pattern
                prev = int(existing.properties.get("total_occurrences", 0))
                mention_count = max(mention_count, prev)

            node = GraphNode(
                node_type=NodeType.THREAD,
                name=thread_name,
                first_seen=ts if not existing else existing.first_seen,
                last_seen=ts,
                properties={
                    "thread_type": "recurring_problem",
                    "pattern": rp.pattern,
                    "total_occurrences": mention_count,
                    "last_date": insights.date,
                    "status": "active",
                    "description": (
                        f"Recurring: \"{rp.pattern}\" — "
                        f"seen {mention_count} times"
                    ),
                },
            )
            self._store.upsert_node(node)
            count += 1

        # 4. Scope warnings → INSIGHT nodes linked to sessions
        for sw in insights.scope_warnings[:5]:
            insight_name = f"scope:{insights.date}:{sw.session_name[:40]}"
            node = GraphNode(
                node_type=NodeType.INSIGHT,
                name=insight_name,
                first_seen=ts,
                last_seen=ts,
                properties={
                    "insight_type": "scope_warning",
                    "date": insights.date,
                    "session_name": sw.session_name,
                    "files_modified": sw.files_modified,
                    "problems_hit": sw.problems_hit,
                    "project": sw.project,
                    "description": (
                        f"Session '{sw.session_name[:50]}' touched "
                        f"{sw.files_modified} files with {sw.problems_hit} problems"
                    ),
                },
            )
            self._store.upsert_node(node)
            count += 1

        return count


def format_insights_for_prompt(insights: DailyInsights) -> str:
    """Render ``DailyInsights`` as markdown for LLM prompt injection.

    The output is appended to the journal context so the synthesizer
    can incorporate structural observations into the daily narrative.
    """
    lines: list[str] = ["## Retrospective Insights (from knowledge graph)"]
    lines.append("")

    # Session stats
    if insights.session_count > 0:
        lines.append(
            f"Today: {insights.session_count} sessions, "
            f"avg {insights.avg_files_per_session} files/session, "
            f"{insights.total_problems} total problems."
        )
        lines.append("")

    # Scope warnings
    if insights.scope_warnings:
        lines.append("### Scope Warnings")
        lines.append(
            "Sessions touching >5 files have a 78% error rate historically. "
            "These recent sessions exceeded that threshold:"
        )
        for w in insights.scope_warnings[:3]:
            proj = f" [{w.project}]" if w.project else ""
            lines.append(
                f"- {w.session_name}{proj}: {w.files_modified} files modified, "
                f"{w.problems_hit} problems"
            )
        lines.append("")

    # Error hotspots
    if insights.error_hotspots:
        lines.append("### Error Hotspots")
        lines.append("Files most associated with problems across all sessions:")
        for h in insights.error_hotspots[:5]:
            lines.append(f"- **{h.file}**: {h.problem_count} problem-associations")
        lines.append("")

    # Coupling clusters
    if insights.coupling_clusters:
        lines.append("### Architectural Coupling")
        lines.append("File pairs that always change together (hidden dependencies):")
        for c in insights.coupling_clusters[:5]:
            lines.append(
                f"- {c.files[0]} + {c.files[1]}: "
                f"co-modified in {c.co_modification_count} sessions"
            )
        lines.append("")

    # Recurring problems
    if insights.recurring_problems:
        lines.append("### Recurring Problems")
        for rp in insights.recurring_problems[:3]:
            lines.append(
                f"- \"{rp.pattern}\" — appeared {rp.occurrence_count} times"
            )
        lines.append("")

    # Only return content if there's something meaningful
    if len(lines) <= 2:
        return ""
    return "\n".join(lines)
