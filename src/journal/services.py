"""Business logic and I/O services for journal generation.

Contains all functions and classes that perform I/O (disk, subprocess),
orchestration, and non-trivial computation. Imports models from
``distill.journal.models``.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from distill.journal.models import (
    CacheEntry,
    DailyContext,
    DailyMemoryEntry,
    JournalConfig,
    JournalStyle,
    MemoryThread,
    SessionSummaryForLLM,
    WorkingMemory,
)
from distill.journal.prompts import get_system_prompt
from distill.parsers.models import BaseSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_FILENAME = ".working-memory.json"


# ---------------------------------------------------------------------------
# Context preparation (deterministic, no LLM)
# ---------------------------------------------------------------------------


def _extract_session_summary(session: BaseSession) -> SessionSummaryForLLM:
    """Extract a compact summary from a single session."""
    # Top 3 tools by usage count
    top_tools = sorted(session.tools_used, key=lambda t: t.count, reverse=True)[:3]

    # User questions from conversation turns
    user_questions = [
        turn.content[:200] for turn in session.turns if turn.role == "user" and turn.content.strip()
    ][:5]

    # Outcomes as strings
    outcomes = [o.description for o in session.outcomes if o.description]

    # Cycle outcome (workflow sessions)
    cycle_outcome = None
    if session.cycle_info:
        cycle_outcome = session.cycle_info.outcome

    return SessionSummaryForLLM(
        time=session.start_time.strftime("%H:%M"),
        duration_minutes=session.duration_minutes,
        source=session.source,
        project=session.project,
        summary=session.summary[:300] if session.summary else "",
        narrative=session.narrative[:300] if session.narrative else "",
        outcomes=outcomes[:5],
        top_tools=[t.name for t in top_tools],
        tags=session.tags[:10],
        user_questions=user_questions,
        cycle_outcome=cycle_outcome,
    )


def prepare_daily_context(
    sessions: list[BaseSession],
    target_date: date,
    config: JournalConfig,
) -> DailyContext:
    """Compress a day's sessions into LLM-ready context.

    Args:
        sessions: All sessions (will be filtered to target_date).
        target_date: The date to generate context for.
        config: Journal configuration.

    Returns:
        DailyContext with compressed session data.
    """
    # Filter to target date
    day_sessions = [s for s in sessions if s.start_time.date() == target_date]

    # Sort by start time
    day_sessions.sort(key=lambda s: s.start_time)

    # Limit sessions
    day_sessions = day_sessions[: config.max_sessions_per_entry]

    # Aggregate data
    total_duration = sum(s.duration_minutes or 0 for s in day_sessions)

    projects = list(
        dict.fromkeys(
            s.project
            for s in day_sessions
            if s.project and s.project not in ("(unknown)", "(unassigned)")
        )
    )

    all_outcomes: list[str] = []
    all_tags: list[str] = []
    summaries: list[SessionSummaryForLLM] = []

    for session in day_sessions:
        summaries.append(_extract_session_summary(session))
        for outcome in session.outcomes:
            if outcome.description and outcome.description not in all_outcomes:
                all_outcomes.append(outcome.description)
        for tag in session.tags:
            if tag not in all_tags:
                all_tags.append(tag)

    return DailyContext(
        date=target_date,
        total_sessions=len(day_sessions),
        total_duration_minutes=total_duration,
        projects_worked=projects,
        session_summaries=summaries,
        key_outcomes=all_outcomes[:15],
        tags=all_tags[:20],
    )


# ---------------------------------------------------------------------------
# Memory I/O
# ---------------------------------------------------------------------------


def load_memory(output_dir: Path) -> WorkingMemory:
    """Load working memory from disk.

    Returns empty WorkingMemory if file doesn't exist or is corrupt.
    """
    memory_path = output_dir / "journal" / MEMORY_FILENAME
    if not memory_path.exists():
        return WorkingMemory()
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
        return WorkingMemory.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt memory file at %s, starting fresh", memory_path)
        return WorkingMemory()


def save_memory(memory: WorkingMemory, output_dir: Path) -> None:
    """Save working memory to disk."""
    memory_path = output_dir / "journal" / MEMORY_FILENAME
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        memory.model_dump_json(indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Synthesizer (LLM integration)
# ---------------------------------------------------------------------------


class SynthesisError(Exception):
    """Raised when LLM synthesis fails."""


class JournalSynthesizer:
    """Synthesizes journal entries via Claude CLI."""

    def __init__(self, config: JournalConfig) -> None:
        self._config = config

    def synthesize(self, context: DailyContext) -> str:
        """Transform daily context into narrative prose.

        Args:
            context: Compressed daily session context.

        Returns:
            Raw prose string from Claude.

        Raises:
            SynthesisError: If the CLI call fails.
        """
        from distill.llm import LLMError, call_claude

        system_prompt = get_system_prompt(self._config.style, self._config.target_word_count)
        user_prompt = context.render_text()

        try:
            return call_claude(
                system_prompt,
                user_prompt,
                model=self._config.model,
                timeout=self._config.claude_timeout,
                label=f"journal {context.date}",
            )
        except LLMError as exc:
            raise SynthesisError(str(exc)) from exc

    def extract_memory(
        self, prose: str, target_date: date
    ) -> tuple[DailyMemoryEntry, list[MemoryThread]]:
        """Extract structured memory from generated prose.

        Makes a second LLM call to pull out themes, insights, decisions,
        open questions, and ongoing threads from the journal prose.

        Args:
            prose: The generated journal prose.
            target_date: The date the prose covers.

        Returns:
            Tuple of (daily entry, list of threads).

        Raises:
            SynthesisError: If the CLI call fails.
        """
        from distill.llm import LLMError, call_claude, strip_json_fences

        system_prompt = f"""\
Extract structured memory from this journal entry dated {target_date.isoformat()}.

Return ONLY valid JSON with this exact structure (no markdown fences, no commentary):
{{
  "themes": ["3-5 high-level themes from today"],
  "key_insights": ["what was learned or discovered"],
  "decisions_made": ["what was decided"],
  "open_questions": ["unresolved things"],
  "tomorrow_intentions": ["what was planned or implied for next steps"],
  "threads": [
    {{
      "name": "short-kebab-case-name",
      "summary": "current state of this ongoing thread",
      "status": "open or resolved"
    }}
  ]
}}

Threads are ongoing narratives that span multiple days: problems being debugged,
features being built, patterns being established. Only include threads if the prose
describes something clearly ongoing or recently resolved."""

        try:
            raw = call_claude(
                system_prompt,
                prose,
                model=self._config.model,
                timeout=self._config.claude_timeout,
                label=f"memory {target_date}",
            )
        except LLMError as exc:
            raise SynthesisError(str(exc)) from exc

        raw = strip_json_fences(raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SynthesisError(f"Memory extraction returned invalid JSON: {e}") from e

        entry = DailyMemoryEntry(
            date=target_date,
            themes=data.get("themes", []),
            key_insights=data.get("key_insights", []),
            decisions_made=data.get("decisions_made", []),
            open_questions=data.get("open_questions", []),
            tomorrow_intentions=data.get("tomorrow_intentions", []),
        )

        threads: list[MemoryThread] = []
        for t in data.get("threads", []):
            threads.append(
                MemoryThread(
                    name=t.get("name", "unnamed"),
                    summary=t.get("summary", ""),
                    first_mentioned=target_date,
                    last_mentioned=target_date,
                    status=t.get("status", "open"),
                )
            )

        return entry, threads


# ---------------------------------------------------------------------------
# Formatter (Obsidian-compatible markdown)
# ---------------------------------------------------------------------------


class JournalFormatter:
    """Formats synthesized prose into Obsidian-compatible markdown."""

    def __init__(self, config: JournalConfig) -> None:
        self._config = config

    def format_entry(self, context: DailyContext, prose: str) -> str:
        """Wrap prose in YAML frontmatter and Obsidian links.

        Args:
            context: The daily context used for metadata.
            prose: Synthesized prose from the LLM.

        Returns:
            Complete Obsidian markdown note.
        """
        frontmatter = self._build_frontmatter(context)
        body = self._build_body(context, prose)
        return frontmatter + body

    def output_path(self, output_dir: Path, context: DailyContext) -> Path:
        """Compute the output file path for a journal entry."""
        journal_dir = output_dir / "journal"
        filename = f"journal-{context.date.isoformat()}-{self._config.style.value}.md"
        return journal_dir / filename

    def _build_frontmatter(self, context: DailyContext) -> str:
        lines: list[str] = ["---"]
        lines.append(f"date: {context.date.isoformat()}")
        lines.append("type: journal")
        lines.append(f"style: {self._config.style.value}")
        lines.append(f"sessions_count: {context.total_sessions}")
        lines.append(f"duration_minutes: {context.total_duration_minutes:.0f}")

        if context.tags:
            lines.append("tags:")
            lines.append("  - journal")
            for tag in context.tags[:10]:
                lines.append(f"  - {tag}")
        else:
            lines.append("tags:")
            lines.append("  - journal")

        if context.projects_worked:
            lines.append("projects:")
            for project in context.projects_worked:
                lines.append(f"  - {project}")

        lines.append(f"created: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def _build_body(self, context: DailyContext, prose: str) -> str:
        lines: list[str] = []

        # Title
        date_str = context.date.strftime("%B %d, %Y")
        style_label = _style_display_name(self._config.style)
        lines.append(f"# {style_label}: {date_str}")
        lines.append("")

        # Prose body
        lines.append(prose)
        lines.append("")

        # Metrics footer (optional)
        if self._config.include_metrics:
            lines.append("---")
            lines.append("")
            lines.append(
                f"*{context.total_sessions} sessions | {context.total_duration_minutes:.0f} minutes"
            )
            if context.projects_worked:
                lines.append(f"| Projects: {', '.join(context.projects_worked)}")
            lines.append("*")
            lines.append("")

        # Related notes links
        lines.append("## Related")
        lines.append("")
        daily_link = f"[[daily/daily-{context.date.isoformat()}|Daily Summary]]"
        lines.append(f"- {daily_link}")
        lines.append("")

        return "\n".join(lines)


def _style_display_name(style: JournalStyle) -> str:
    """Human-readable display name for a journal style."""
    return {
        JournalStyle.DEV_JOURNAL: "Dev Journal",
        JournalStyle.TECH_BLOG: "Tech Blog",
        JournalStyle.TEAM_UPDATE: "Team Update",
        JournalStyle.BUILDING_IN_PUBLIC: "Building in Public",
    }[style]


# ---------------------------------------------------------------------------
# Cache (incremental generation tracking)
# ---------------------------------------------------------------------------


class JournalCache:
    """Tracks which journal entries have been generated.

    Cache file lives at ``{output_dir}/journal/.journal-cache.json``
    and maps ``"date:style"`` keys to CacheEntry values.
    """

    def __init__(self, output_dir: Path) -> None:
        self._cache_path = output_dir / "journal" / ".journal-cache.json"
        self._data: dict[str, CacheEntry] = self._load()

    def _load(self) -> dict[str, CacheEntry]:
        if not self._cache_path.exists():
            return {}
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return {k: CacheEntry.model_validate(v) for k, v in raw.items()}
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to load journal cache: %s", e)
            return {}

    def _save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        raw = {k: v.model_dump() for k, v in self._data.items()}
        self._cache_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    @staticmethod
    def _key(target_date: date, style: JournalStyle) -> str:
        return f"{target_date.isoformat()}:{style.value}"

    def is_generated(self, target_date: date, style: JournalStyle, session_count: int) -> bool:
        """Check if an entry is already cached with the same session count."""
        key = self._key(target_date, style)
        entry = self._data.get(key)
        if entry is None:
            return False
        return entry.session_count == session_count

    def mark_generated(self, target_date: date, style: JournalStyle, session_count: int) -> None:
        """Record that a journal entry has been generated."""
        key = self._key(target_date, style)
        self._data[key] = CacheEntry(
            session_count=session_count,
            generated_at=datetime.now().isoformat(),
        )
        self._save()
