"""Core analysis pipeline for session insights."""

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from session_insights.models import BaseSession, ToolUsage


class SessionStats(BaseModel):
    """Statistics about analyzed sessions."""

    total_sessions: int = 0
    total_duration_minutes: float = 0.0
    sources: dict[str, int] = Field(default_factory=dict)
    tools_used: dict[str, int] = Field(default_factory=dict)
    date_range: tuple[datetime, datetime] | None = None


class SessionPattern(BaseModel):
    """Detected patterns in sessions."""

    name: str
    description: str
    occurrences: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Result of analyzing a collection of sessions."""

    sessions: list[BaseSession] = Field(default_factory=list)
    stats: SessionStats = Field(default_factory=SessionStats)
    patterns: list[SessionPattern] = Field(default_factory=list)


# Known session file patterns by source
SESSION_PATTERNS: dict[str, list[str]] = {
    "claude": ["history.jsonl", "sessions/*.jsonl", "projects/**/history.jsonl"],
    "codex": ["history.jsonl", "sessions/*.json"],
    "vermas": [".vermas/**/session.json", ".vermas/**/history.jsonl"],
}


def discover_sessions(
    directory: Path,
    sources: list[str] | None = None,
) -> dict[str, list[Path]]:
    """Discover session files in a directory.

    Args:
        directory: Root directory to scan.
        sources: Filter to specific sources. If None, discover all.

    Returns:
        Dictionary mapping source name to list of session file paths.
    """
    if sources is None:
        sources = list(SESSION_PATTERNS.keys())

    discovered: dict[str, list[Path]] = {}

    for source in sources:
        if source not in SESSION_PATTERNS:
            continue

        patterns = SESSION_PATTERNS[source]
        found_files: list[Path] = []

        for pattern in patterns:
            # Check for .claude directory
            claude_dir = directory / ".claude"
            if claude_dir.exists():
                for match in claude_dir.glob(pattern):
                    if match.is_file() and match not in found_files:
                        found_files.append(match)

            # Also check the directory itself for vermas patterns
            if source == "vermas":
                for match in directory.glob(pattern):
                    if match.is_file() and match not in found_files:
                        found_files.append(match)

        if found_files:
            discovered[source] = sorted(found_files, key=lambda p: p.stat().st_mtime, reverse=True)

    return discovered


def parse_session_file(path: Path, source: str) -> list[BaseSession]:
    """Parse a session file into BaseSession objects.

    Args:
        path: Path to the session file.
        source: The source type (claude, codex, vermas).

    Returns:
        List of parsed sessions.
    """
    import json

    sessions: list[BaseSession] = []

    try:
        if path.suffix == ".jsonl":
            # JSONL format - one JSON object per line
            with path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        session = _parse_session_entry(data, source, f"{path.stem}-{line_num}")
                        if session:
                            sessions.append(session)
                    except json.JSONDecodeError:
                        continue
        else:
            # JSON format - single object or array
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for i, entry in enumerate(data):
                    session = _parse_session_entry(entry, source, f"{path.stem}-{i}")
                    if session:
                        sessions.append(session)
            else:
                session = _parse_session_entry(data, source, path.stem)
                if session:
                    sessions.append(session)

    except (OSError, json.JSONDecodeError):
        pass

    return sessions


def _parse_session_entry(
    data: dict[str, Any],
    source: str,
    fallback_id: str,
) -> BaseSession | None:
    """Parse a single session entry from raw data.

    Args:
        data: Raw session data dictionary.
        source: The source type.
        fallback_id: ID to use if none found in data.

    Returns:
        Parsed BaseSession or None if invalid.
    """
    # Extract timestamp
    timestamp = data.get("timestamp")
    if timestamp is None:
        return None

    # Convert timestamp (milliseconds or ISO string)
    if isinstance(timestamp, (int, float)):
        start_time = datetime.fromtimestamp(timestamp / 1000)
    elif isinstance(timestamp, str):
        try:
            start_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    # Extract ID
    session_id = data.get("id") or data.get("session_id") or fallback_id

    # Extract summary/display content
    summary = data.get("display", "") or data.get("summary", "") or data.get("content", "")
    if isinstance(summary, str) and len(summary) > 200:
        summary = summary[:200] + "..."

    # Extract project info as metadata
    metadata: dict[str, Any] = {}
    if "project" in data:
        metadata["project"] = data["project"]

    return BaseSession(
        id=str(session_id),
        start_time=start_time,
        end_time=None,  # Most history entries don't have end time
        source=source,
        summary=summary,
        metadata=metadata,
    )


def analyze(sessions: list[BaseSession]) -> AnalysisResult:
    """Analyze a collection of sessions.

    Args:
        sessions: List of sessions to analyze.

    Returns:
        Analysis result with statistics and patterns.
    """
    if not sessions:
        return AnalysisResult()

    # Calculate statistics
    stats = _calculate_stats(sessions)

    # Detect patterns
    patterns = _detect_patterns(sessions)

    return AnalysisResult(
        sessions=sessions,
        stats=stats,
        patterns=patterns,
    )


def _calculate_stats(sessions: list[BaseSession]) -> SessionStats:
    """Calculate statistics from sessions."""
    total_duration = sum(s.duration_minutes or 0 for s in sessions)

    # Count by source
    sources: Counter[str] = Counter(s.source for s in sessions)

    # Count tools
    tools: Counter[str] = Counter()
    for session in sessions:
        for tool in session.tools_used:
            tools[tool.name] += tool.count

    # Date range
    times = [s.start_time for s in sessions]
    date_range = (min(times), max(times)) if times else None

    return SessionStats(
        total_sessions=len(sessions),
        total_duration_minutes=total_duration,
        sources=dict(sources),
        tools_used=dict(tools),
        date_range=date_range,
    )


def _detect_patterns(sessions: list[BaseSession]) -> list[SessionPattern]:
    """Detect patterns in sessions."""
    patterns: list[SessionPattern] = []

    if len(sessions) < 2:
        return patterns

    # Pattern: Peak hours
    hours: Counter[int] = Counter(s.start_time.hour for s in sessions)
    if hours:
        peak_hour = hours.most_common(1)[0]
        patterns.append(
            SessionPattern(
                name="peak_activity_hour",
                description=f"Most sessions occur at {peak_hour[0]}:00",
                occurrences=peak_hour[1],
                metadata={"hour": peak_hour[0]},
            )
        )

    # Pattern: Common tools
    tools: Counter[str] = Counter()
    for session in sessions:
        for tool in session.tools_used:
            tools[tool.name] += tool.count

    if tools:
        top_tools = tools.most_common(3)
        patterns.append(
            SessionPattern(
                name="frequent_tools",
                description=f"Most used tools: {', '.join(t[0] for t in top_tools)}",
                occurrences=sum(t[1] for t in top_tools),
                metadata={"tools": dict(top_tools)},
            )
        )

    # Pattern: Session frequency by day of week
    days: Counter[int] = Counter(s.start_time.weekday() for s in sessions)
    if days:
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        peak_day = days.most_common(1)[0]
        patterns.append(
            SessionPattern(
                name="peak_activity_day",
                description=f"Most active day: {day_names[peak_day[0]]}",
                occurrences=peak_day[1],
                metadata={"day": peak_day[0], "day_name": day_names[peak_day[0]]},
            )
        )

    return patterns
