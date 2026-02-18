"""Business logic and I/O services for blog generation.

Contains all functions and classes that perform I/O (disk, subprocess),
orchestration, and non-trivial computation. Imports models from
``distill.blog.models``.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from distill.blog.models import (
    BlogConfig,
    BlogMemory,
    BlogPostSummary,
    BlogPostType,
    BlogState,
    IntakeDigestEntry,
    JournalEntry,
    ReadingListContext,
    ThematicBlogContext,
    ThemeDefinition,
    WeeklyBlogContext,
)
from distill.blog.prompts import MEMORY_EXTRACTION_PROMPT, get_blog_prompt, get_social_prompt
from distill.journal.models import MemoryThread, WorkingMemory

if TYPE_CHECKING:
    from distill.memory import UnifiedMemory
    from distill.store import JsonStore, PgvectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILENAME = ".blog-state.json"
MEMORY_FILENAME = ".blog-memory.json"


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------


def load_blog_state(output_dir: Path) -> BlogState:
    """Load blog state from disk.

    Returns empty BlogState if file doesn't exist or is corrupt.
    """
    state_path = output_dir / "blog" / STATE_FILENAME
    if not state_path.exists():
        return BlogState()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return BlogState.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt blog state at %s, starting fresh", state_path)
        return BlogState()


def save_blog_state(state: BlogState, output_dir: Path) -> None:
    """Save blog state to disk."""
    state_path = output_dir / "blog" / STATE_FILENAME
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Blog memory I/O
# ---------------------------------------------------------------------------


def load_blog_memory(output_dir: Path) -> BlogMemory:
    """Load blog memory from disk.

    Returns empty BlogMemory if file doesn't exist or is corrupt.
    """
    memory_path = output_dir / "blog" / MEMORY_FILENAME
    if not memory_path.exists():
        return BlogMemory()
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
        return BlogMemory.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt blog memory at %s, starting fresh", memory_path)
        return BlogMemory()


def save_blog_memory(memory: BlogMemory, output_dir: Path) -> None:
    """Save blog memory to disk."""
    memory_path = output_dir / "blog" / MEMORY_FILENAME
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        memory.model_dump_json(indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Journal / intake reader
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Extract YAML frontmatter from markdown text.

    Simple key-value parser -- handles scalar values and YAML lists
    without requiring a heavy YAML dependency.
    """
    if not text.startswith("---"):
        return {}

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    raw = parts[1].strip()
    result: dict[str, str | list[str]] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in raw.splitlines():
        # List item under a key
        if line.startswith("  - ") and current_key is not None:
            if current_list is None:
                current_list = []
            current_list.append(line.strip().removeprefix("- "))
            continue

        # Flush previous list
        if current_list is not None and current_key is not None:
            result[current_key] = current_list
            current_list = None
            current_key = None

        # Key-value pair
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                result[key] = value
            else:
                # Might be a list header
                current_key = key
                current_list = None
        # Bare key with no value -- start a list
        elif current_key is None and line.strip():
            current_key = line.strip().rstrip(":")

    # Flush trailing list
    if current_list is not None and current_key is not None:
        result[current_key] = current_list

    return result


def _extract_prose(text: str) -> str:
    """Extract the narrative body, stripping frontmatter, title, and metrics footer."""
    # Remove frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else ""
    else:
        body = text

    lines = body.strip().splitlines()

    # Strip leading title line (# ...)
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    # Strip trailing Related section
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "## Related":
            lines = lines[:i]
            break

    # Strip trailing metrics footer (starts with ---)
    while lines and lines[-1].strip() == "":
        lines.pop()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "---":
            lines = lines[:i]
            break

    # Strip trailing/leading blank lines
    text_body = "\n".join(lines).strip()
    return text_body


class JournalReader:
    """Discovers and reads journal entries from the output directory."""

    def read_intake_digests(self, intake_dir: Path) -> list[IntakeDigestEntry]:
        """Read intake digest markdown files.

        Args:
            intake_dir: Directory containing intake digest files.

        Returns:
            List of parsed intake digest entries.
        """
        if not intake_dir.exists():
            return []

        entries: list[IntakeDigestEntry] = []
        for md_file in sorted(intake_dir.glob("intake-*.md")):
            entry = self._parse_intake_file(md_file)
            if entry is not None:
                entries.append(entry)

        return sorted(entries, key=lambda e: e.date)

    def _parse_intake_file(self, path: Path) -> IntakeDigestEntry | None:
        """Parse a single intake digest markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Could not read intake file: %s", path)
            return None

        fm = _parse_frontmatter(text)
        prose = _extract_prose(text)

        # Parse date from frontmatter or filename
        entry_date: date | None = None
        if "date" in fm and isinstance(fm["date"], str):
            with contextlib.suppress(ValueError):
                entry_date = date.fromisoformat(fm["date"])

        if entry_date is None:
            match = re.search(r"intake-(\d{4}-\d{2}-\d{2})", path.name)
            if match:
                with contextlib.suppress(ValueError):
                    entry_date = date.fromisoformat(match.group(1))

        if entry_date is None:
            logger.warning("Could not determine date for intake %s", path)
            return None

        # Parse themes/tags
        themes = fm.get("themes", fm.get("tags", []))
        if isinstance(themes, str):
            themes = [themes]

        return IntakeDigestEntry(
            date=entry_date,
            themes=list(themes),
            prose=prose,
            file_path=path,
        )

    def read_all(self, journal_dir: Path) -> list[JournalEntry]:
        """Read all journal entries from the journal directory."""
        if not journal_dir.exists():
            return []

        entries: list[JournalEntry] = []
        for md_file in sorted(journal_dir.glob("journal-*.md")):
            entry = self._parse_file(md_file)
            if entry is not None:
                entries.append(entry)

        return sorted(entries, key=lambda e: e.date)

    def read_week(self, journal_dir: Path, year: int, week: int) -> list[JournalEntry]:
        """Read journal entries for a specific ISO week."""
        all_entries = self.read_all(journal_dir)
        return [
            e
            for e in all_entries
            if e.date.isocalendar().year == year and e.date.isocalendar().week == week
        ]

    def read_date_range(self, journal_dir: Path, start: date, end: date) -> list[JournalEntry]:
        """Read journal entries within a date range (inclusive)."""
        all_entries = self.read_all(journal_dir)
        return [e for e in all_entries if start <= e.date <= end]

    def _parse_file(self, path: Path) -> JournalEntry | None:
        """Parse a single journal markdown file into a JournalEntry."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Could not read journal file: %s", path)
            return None

        fm = _parse_frontmatter(text)
        prose = _extract_prose(text)

        # Parse date from frontmatter or filename
        entry_date: date | None = None
        if "date" in fm and isinstance(fm["date"], str):
            with contextlib.suppress(ValueError):
                entry_date = date.fromisoformat(fm["date"])

        if entry_date is None:
            # Try filename: journal-YYYY-MM-DD-style.md
            match = re.search(r"journal-(\d{4}-\d{2}-\d{2})", path.name)
            if match:
                with contextlib.suppress(ValueError):
                    entry_date = date.fromisoformat(match.group(1))

        if entry_date is None:
            logger.warning("Could not determine date for %s", path)
            return None

        # Parse numeric fields
        sessions_count = 0
        if "sessions_count" in fm and isinstance(fm["sessions_count"], str):
            with contextlib.suppress(ValueError):
                sessions_count = int(fm["sessions_count"])

        duration = 0.0
        if "duration_minutes" in fm and isinstance(fm["duration_minutes"], str):
            with contextlib.suppress(ValueError):
                duration = float(fm["duration_minutes"])

        # Parse list fields
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        projects = fm.get("projects", [])
        if isinstance(projects, str):
            projects = [projects]

        style = ""
        raw_style = fm.get("style")
        if isinstance(raw_style, str):
            style = raw_style

        return JournalEntry(
            date=entry_date,
            style=style,
            sessions_count=sessions_count,
            duration_minutes=duration,
            tags=list(tags),
            projects=list(projects),
            prose=prose,
            file_path=path,
        )


# ---------------------------------------------------------------------------
# Context preparation
# ---------------------------------------------------------------------------


def prepare_weekly_context(
    entries: list[JournalEntry],
    year: int,
    week: int,
    memory: WorkingMemory | None = None,
    intake_digests: list[IntakeDigestEntry] | None = None,
) -> WeeklyBlogContext:
    """Assemble context for a weekly synthesis post.

    Args:
        entries: Journal entries for the target week.
        year: ISO year.
        week: ISO week number.
        memory: Optional working memory for narrative continuity.
        intake_digests: Optional intake digests for the same week.

    Returns:
        Fully assembled weekly blog context.
    """
    # Compute week start/end (Monday to Sunday)
    week_start = date.fromisocalendar(year, week, 1)
    week_end = week_start + timedelta(days=6)

    # Aggregate stats
    total_sessions = sum(e.sessions_count for e in entries)
    total_duration = sum(e.duration_minutes for e in entries)

    # Collect unique projects and tags
    projects: list[str] = []
    tags: list[str] = []
    seen_projects: set[str] = set()
    seen_tags: set[str] = set()

    for entry in entries:
        for p in entry.projects:
            if p not in seen_projects:
                projects.append(p)
                seen_projects.add(p)
        for t in entry.tags:
            if t not in seen_tags:
                tags.append(t)
                seen_tags.add(t)

    # Combine prose from all entries
    prose_parts: list[str] = []
    for entry in sorted(entries, key=lambda e: e.date):
        day_label = entry.date.strftime("%A, %B %d")
        prose_parts.append(f"## {day_label}\n\n{entry.prose}")
    combined_prose = "\n\n".join(prose_parts)

    # Render working memory if available
    working_memory_text = ""
    if memory is not None:
        working_memory_text = memory.render_for_prompt()

    # Build intake context from digests for the same week
    intake_text = ""
    reading_themes: list[str] = []
    if intake_digests:
        week_digests = [d for d in intake_digests if week_start <= d.date <= week_end]
        if week_digests:
            parts: list[str] = ["## What You Read This Week\n"]
            for digest in sorted(week_digests, key=lambda d: d.date):
                day_label = digest.date.strftime("%A, %B %d")
                excerpt = digest.prose[:800] if digest.prose else "(no digest)"
                parts.append(f"### {day_label}\n\n{excerpt}")
                reading_themes.extend(digest.themes)
            intake_text = "\n\n".join(parts)
            # Deduplicate themes
            seen: set[str] = set()
            deduped: list[str] = []
            for t in reading_themes:
                if t not in seen:
                    deduped.append(t)
                    seen.add(t)
            reading_themes = deduped

    return WeeklyBlogContext(
        year=year,
        week=week,
        week_start=week_start,
        week_end=week_end,
        entries=entries,
        total_sessions=total_sessions,
        total_duration_minutes=total_duration,
        projects=projects,
        all_tags=tags,
        working_memory=working_memory_text,
        combined_prose=combined_prose,
        intake_context=intake_text,
        reading_themes=reading_themes,
    )


def prepare_thematic_context(
    theme: ThemeDefinition,
    evidence: list[JournalEntry],
    memory: WorkingMemory | None = None,
    intake_digests: list[IntakeDigestEntry] | None = None,
    seed_angle: str = "",
) -> ThematicBlogContext:
    """Assemble context for a thematic deep-dive post.

    Args:
        theme: The theme to write about.
        evidence: Journal entries containing evidence for the theme.
        memory: Optional working memory for thread matching.
        intake_digests: Optional intake digests for date range.
        seed_angle: Optional seed angle text.

    Returns:
        Fully assembled thematic blog context.
    """
    if not evidence:
        return ThematicBlogContext(theme=theme)

    # Date range
    dates = sorted(e.date for e in evidence)
    date_range = (dates[0], dates[-1])

    # Find relevant threads from working memory
    relevant_threads: list[MemoryThread] = []
    if memory is not None:
        for thread in memory.threads:
            thread_name_lower = thread.name.lower()
            for pattern in theme.thread_patterns:
                if pattern.lower() in thread_name_lower:
                    relevant_threads.append(thread)
                    break

    # Combine evidence prose
    evidence_parts: list[str] = []
    for entry in sorted(evidence, key=lambda e: e.date):
        day_label = entry.date.strftime("%B %d, %Y")
        evidence_parts.append(f"### {day_label}\n\n{entry.prose}")
    combined_evidence = "\n\n".join(evidence_parts)

    # Build intake context for relevant digests
    intake_text = ""
    if intake_digests and evidence:
        relevant_digests = [d for d in intake_digests if dates[0] <= d.date <= dates[-1]]
        if relevant_digests:
            parts: list[str] = ["## Related Reading\n"]
            for digest in sorted(relevant_digests, key=lambda d: d.date):
                excerpt = digest.prose[:500] if digest.prose else ""
                if excerpt:
                    parts.append(f"### {digest.date.isoformat()}\n\n{excerpt}")
            if len(parts) > 1:
                intake_text = "\n\n".join(parts)

    return ThematicBlogContext(
        theme=theme,
        evidence_entries=evidence,
        date_range=date_range,
        evidence_count=len(evidence),
        relevant_threads=relevant_threads,
        combined_evidence=combined_evidence,
        intake_context=intake_text,
        seed_angle=seed_angle,
    )


# ---------------------------------------------------------------------------
# Theme detection and evidence gathering
# ---------------------------------------------------------------------------

THEMES: list[ThemeDefinition] = [
    # Achievement / what-works themes
    ThemeDefinition(
        slug="healthy-friction-works",
        title="How Healthy Friction Between Agents Catches Real Bugs",
        description=(
            "QA-dev friction as a quality multiplier"
            " — when structured disagreement produces better code."
        ),
        keywords=["healthy friction", "caught", "revision", "coverage gap", "real bug"],
        thread_patterns=["healthy-friction", "qa-dev", "friction"],
    ),
    ThemeDefinition(
        slug="pipeline-that-compounds",
        title="Building a Content Pipeline That Compounds",
        description=(
            "How a system that ingests sessions, reads, and thoughts"
            " produces richer output over time."
        ),
        keywords=["pipeline", "compound", "memory", "continuity", "narrative"],
        thread_patterns=["pipeline", "compound", "memory"],
    ),
    ThemeDefinition(
        slug="mission-cycles-that-chain",
        title="When Mission Cycles Start Chaining Autonomously",
        description="The moment multi-agent workflows go from orchestrated to self-sustaining.",
        keywords=["chaining", "autonomous", "mission cycle", "self-sustaining", "pipeline"],
        thread_patterns=["mission-cycle", "chaining", "autonomous"],
    ),
    ThemeDefinition(
        slug="self-referential-loop",
        title="The Self-Referential AI Tooling Loop",
        description=(
            "Building tools where the AI watches itself work, then learns from what it sees."
        ),
        keywords=["self-referential", "meta-learning", "knowledge extraction", "self-improving"],
        thread_patterns=["self-referential", "self-improvement", "knowledge-extraction"],
    ),
    # Challenge / learning themes
    ThemeDefinition(
        slug="coordination-overhead",
        title="When Coordination Overhead Exceeds Task Value",
        description="Explores the costs of multi-agent coordination relative to task complexity.",
        keywords=["ceremony", "overhead", "coordination", "granularity"],
        thread_patterns=["coordination", "ceremony", "overhead"],
    ),
    ThemeDefinition(
        slug="quality-gates-that-work",
        title="Quality Gates That Actually Work",
        description="Examines which QA patterns catch real bugs vs create busywork.",
        keywords=["QA", "revision", "caught", "quality gate"],
        thread_patterns=["qa", "quality", "review"],
    ),
    ThemeDefinition(
        slug="infrastructure-vs-shipping",
        title="Infrastructure Building vs Shipping Features",
        description="The tension between building tooling and delivering user-visible results.",
        keywords=["validation theater", "infrastructure", "shipping", "user-visible"],
        thread_patterns=["validation", "infrastructure", "shipping"],
    ),
    ThemeDefinition(
        slug="branch-merge-failures",
        title="Why Branch Merges Keep Failing",
        description="Root causes of merge failures in multi-agent branch workflows.",
        keywords=["merge", "branch", "direct-to-main", "worktree"],
        thread_patterns=["merge", "branch", "worktree"],
    ),
    ThemeDefinition(
        slug="meta-work-recursion",
        title="When Introspection Systems Become Obstacles",
        description="How tools built to analyze work can themselves become the work.",
        keywords=["meta-work", "recursion", "introspection", "analyzing"],
        thread_patterns=["meta-work", "recursion", "reflection"],
    ),
    ThemeDefinition(
        slug="visibility-gap",
        title="What Your Coordination System Can't See",
        description="Blind spots in agent orchestration and repository state tracking.",
        keywords=["visibility", "blind", "git status", "repository state"],
        thread_patterns=["visibility", "blind"],
    ),
]


def gather_evidence(theme: ThemeDefinition, entries: list[JournalEntry]) -> list[JournalEntry]:
    """Find journal entries that contain evidence for a theme.

    Searches both prose content (via keywords) and tags (via thread patterns).
    """
    matching: list[JournalEntry] = []
    for entry in entries:
        if _entry_matches_theme(entry, theme):
            matching.append(entry)
    return matching


def get_ready_themes(
    entries: list[JournalEntry], state: BlogState
) -> list[tuple[ThemeDefinition, list[JournalEntry]]]:
    """Find themes with enough evidence that haven't been blogged yet.

    Returns tuples of (theme, evidence_entries) for themes that meet the
    minimum evidence threshold and haven't already been generated.
    """
    ready: list[tuple[ThemeDefinition, list[JournalEntry]]] = []
    for theme in THEMES:
        if state.is_generated(theme.slug):
            continue
        evidence = gather_evidence(theme, entries)
        unique_dates = {e.date for e in evidence}
        if len(unique_dates) >= theme.min_evidence_days:
            ready.append((theme, evidence))
    return ready


def themes_from_seeds(seeds: list[object]) -> list[ThemeDefinition]:
    """Convert unused seed ideas into dynamic blog themes.

    Each seed becomes a theme. The seed text is the title, and keywords
    are derived from the seed's tags plus key words from the text.

    Args:
        seeds: List of SeedIdea objects (has .id, .text, .tags attributes).

    Returns:
        List of ThemeDefinition objects ready for evidence gathering.
    """
    themes: list[ThemeDefinition] = []
    for seed in seeds:
        # Build keywords from tags + significant words in the text
        text = seed.text  # type: ignore[union-attr]
        tags = list(seed.tags) if hasattr(seed, "tags") else []  # type: ignore[union-attr]

        # Extract meaningful words (>4 chars, not stopwords) as keywords
        stopwords = {
            "about",
            "after",
            "before",
            "being",
            "between",
            "could",
            "every",
            "from",
            "have",
            "into",
            "more",
            "most",
            "much",
            "only",
            "over",
            "should",
            "some",
            "such",
            "than",
            "that",
            "their",
            "them",
            "then",
            "there",
            "these",
            "they",
            "this",
            "through",
            "under",
            "very",
            "what",
            "when",
            "where",
            "which",
            "while",
            "with",
            "would",
            "your",
        }
        words = [
            w.strip(".,;:!?\"'()—-")
            for w in text.lower().split()
            if len(w.strip(".,;:!?\"'()—-")) > 4 and w.strip(".,;:!?\"'()—-") not in stopwords
        ]
        keywords = tags + words[:8]

        # Slug from seed ID
        slug = f"seed-{seed.id}"  # type: ignore[union-attr]

        themes.append(
            ThemeDefinition(
                slug=slug,
                title=text,
                description=f"Blog post exploring: {text}",
                keywords=keywords,
                thread_patterns=tags if tags else words[:3],
                min_evidence_days=3,  # Seeds still need real evidence from journal entries
            )
        )
    return themes


def detect_series_candidates(
    entries: list[JournalEntry],
    memory: object,
    state: object,
) -> list[ThemeDefinition]:
    """Find series-worthy topics from memory threads and entities.

    Looks for threads with high mention counts and entities with high
    frequency that haven't been blogged yet.

    Filters out generic single-word names (tool names, language names,
    common programming terms) that produce meaningless blog posts.

    Args:
        entries: Journal entries.
        memory: UnifiedMemory instance.
        state: BlogState instance.

    Returns:
        List of ThemeDefinition objects for series candidates.
    """
    from distill.memory import UnifiedMemory

    if not isinstance(memory, UnifiedMemory) or not isinstance(state, BlogState):
        return []

    candidates: list[ThemeDefinition] = []

    # Series from threads with mention_count >= 5 and multi-word names
    for thread in memory.threads:
        if thread.status != "active":
            continue
        if thread.mention_count < 5:
            continue
        if _is_generic_name(thread.name):
            continue
        slug = f"series-{thread.name.lower().replace(' ', '-')}"
        if state.is_generated(slug):
            continue
        candidates.append(
            ThemeDefinition(
                slug=slug,
                title=f"Series: {thread.name}",
                description=thread.summary,
                keywords=[thread.name.lower()],
                thread_patterns=[thread.name.lower()],
                min_evidence_days=3,
            )
        )

    # Series from entities with mention_count >= 10 and multi-word names
    for _key, entity in memory.entities.items():
        if entity.mention_count < 10:
            continue
        if _is_generic_name(entity.name):
            continue
        slug = f"series-{entity.name.lower().replace(' ', '-')}"
        if state.is_generated(slug):
            continue
        candidates.append(
            ThemeDefinition(
                slug=slug,
                title=f"Deep Dive: {entity.name}",
                description=f"Extended exploration of {entity.name} ({entity.entity_type})",
                keywords=[entity.name.lower()],
                thread_patterns=[entity.name.lower()],
                min_evidence_days=3,
            )
        )

    return candidates


# Generic names that are too vague for a standalone blog post
_GENERIC_NAMES: set[str] = {
    "ai",
    "api",
    "bash",
    "blog",
    "blog post",
    "bot",
    "bug",
    "cache",
    "cli",
    "code",
    "code review",
    "config",
    "css",
    "data",
    "debug",
    "debugging",
    "deploy",
    "distill",
    "docker",
    "docs",
    "edit",
    "error",
    "feature",
    "file",
    "file modification",
    "fix",
    "glob",
    "grep",
    "git",
    "html",
    "http",
    "issue",
    "javascript",
    "journal",
    "journal entry",
    "json",
    "lint",
    "linkedin",
    "llm",
    "log",
    "markdown",
    "mcp",
    "meeting",
    "message",
    "messaging",
    "model",
    "node",
    "npm",
    "pivot",
    "pr",
    "prompt",
    "python",
    "react",
    "read",
    "reddit",
    "redis",
    "registration",
    "review",
    "rss",
    "schema",
    "script",
    "seed",
    "server",
    "session",
    "session data",
    "shell",
    "shell commands",
    "slack",
    "sql",
    "ssh",
    "task",
    "test",
    "testing",
    "themes",
    "thread",
    "token",
    "tool",
    "troopx",
    "twitter",
    "type",
    "typescript",
    "ui",
    "url",
    "ux",
    "validation",
    "verification",
    "vermas",
    "webhook",
    "workflow",
    "write",
    "x",
    "yaml",
}


def _is_generic_name(name: str) -> bool:
    """Check if a name is too generic for a blog series."""
    lower = name.lower().strip()
    # Exact match against blocklist
    if lower in _GENERIC_NAMES:
        return True
    # Single-word names are almost always too generic
    return " " not in lower and "-" not in lower


def _entry_matches_theme(entry: JournalEntry, theme: ThemeDefinition) -> bool:
    """Check if a journal entry matches a theme via keywords or patterns."""
    prose_lower = entry.prose.lower()

    # Check keywords in prose
    for keyword in theme.keywords:
        if keyword.lower() in prose_lower:
            return True

    # Check thread patterns against tags
    tags_lower = [t.lower() for t in entry.tags]
    for pattern in theme.thread_patterns:
        pattern_lower = pattern.lower()
        for tag in tags_lower:
            if pattern_lower in tag:
                return True

    return False


# ---------------------------------------------------------------------------
# Diagrams (Mermaid)
# ---------------------------------------------------------------------------

VALID_DIAGRAM_TYPES = frozenset(
    {
        "graph",
        "flowchart",
        "sequencediagram",
        "classdiagram",
        "statediagram",
        "statediagram-v2",
        "erdiagram",
        "gantt",
        "pie",
        "timeline",
        "gitgraph",
        "mindmap",
    }
)


def extract_mermaid_blocks(prose: str) -> list[str]:
    """Extract ```mermaid ... ``` blocks from prose.

    Returns the content of each block (without the fence markers).
    """
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
    return [m.group(1).strip() for m in pattern.finditer(prose)]


def validate_mermaid(block: str) -> bool:
    """Basic syntax validation for a Mermaid block.

    Checks that the block starts with a recognized diagram type keyword.
    """
    if not block.strip():
        return False

    first_line = block.strip().splitlines()[0].strip().lower()

    # Check for diagram type at start of first line
    for dtype in VALID_DIAGRAM_TYPES:
        if first_line.startswith(dtype):
            return True

    # Some diagram types use a hyphenated form
    return bool(first_line.startswith("state diagram"))


def clean_diagrams(prose: str) -> str:
    """Remove invalid Mermaid blocks from prose, keeping valid ones.

    Invalid blocks are replaced with empty string (removing the entire
    fenced block). Valid blocks are left in place.
    """

    def _replace(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        if validate_mermaid(content):
            return match.group(0)  # Keep valid blocks as-is
        return ""

    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
    result = pattern.sub(_replace, prose)

    # Clean up any double blank lines left by removed blocks
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result


# ---------------------------------------------------------------------------
# Reading list
# ---------------------------------------------------------------------------


def prepare_reading_list_context(
    output_dir: Path,
    year: int,
    week: int,
    unified_memory: UnifiedMemory,
    store: JsonStore | PgvectorStore,
    *,
    max_items: int = 10,
) -> ReadingListContext | None:
    """Build context for a reading list post from stored intake items.

    Queries the content store for intake items published during the
    given week, sorts by relevance classification, and picks the top items.

    Args:
        output_dir: Root output directory.
        year: ISO year.
        week: ISO week number.
        unified_memory: Memory for theme context.
        store: Content store to query.
        max_items: Maximum items to include.

    Returns:
        ReadingListContext if enough items found, else None.
    """
    # Calculate week date range
    week_start = date.fromisocalendar(year, week, 1)
    week_end = week_start + timedelta(days=6)

    try:
        items = store.find_by_date_range(week_start, week_end)
    except Exception:
        logger.warning("Failed to query store for reading list", exc_info=True)
        return None

    if not items:
        return None

    # Sort by relevance score from classification metadata
    scored_items: list[tuple[float, object]] = []
    for item in items:
        classification = item.metadata.get("classification", {})
        relevance = 0.5  # default
        if isinstance(classification, dict):
            relevance = classification.get("relevance", 0.5)
            if isinstance(relevance, str):
                try:
                    relevance = float(relevance)
                except ValueError:
                    relevance = 0.5
        scored_items.append((relevance, item))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    top_items = scored_items[:max_items]

    # Build item dicts for the context
    context_items = []
    for score, item in top_items:
        context_items.append(
            {
                "title": item.title,
                "url": item.url,
                "author": item.author,
                "site": item.site_name,
                "excerpt": item.excerpt[:200] if item.excerpt else "",
                "tags": item.tags[:5],
                "relevance": score,
            }
        )

    # Collect themes from memory for the week
    themes: list[str] = []
    for entry in unified_memory.entries:
        if week_start <= entry.date <= week_end:
            themes.extend(entry.themes)
    themes = list(dict.fromkeys(themes))[:10]  # deduplicate, preserve order

    if not context_items:
        return None

    return ReadingListContext(
        week_start=week_start,
        week_end=week_end,
        items=context_items,
        total_items_read=len(items),
        themes=themes,
    )


def render_reading_list_prompt(context: ReadingListContext) -> str:
    """Render the reading list context as prompt text for the LLM."""
    lines = [
        f"# Reading List: Week {context.year}-W{context.week:02d}",
        f"({context.week_start.isoformat()} to {context.week_end.isoformat()})",
        "",
        f"Total articles read: {context.total_items_read}",
        f"Top {len(context.items)} curated below:",
        "",
    ]

    for i, item in enumerate(context.items, 1):
        title = item.get("title", "Untitled")
        author = item.get("author", "")
        site = item.get("site", "")
        excerpt = item.get("excerpt", "")
        tags: list[str] = item.get("tags", [])  # type: ignore[assignment]
        attribution = f" by {author}" if author else (f" ({site})" if site else "")

        lines.append(f"## {i}. {title}{attribution}")
        if excerpt:
            lines.append(f"> {excerpt}")
        if tags:
            lines.append(f"Tags: {', '.join(tags)}")
        lines.append("")

    if context.themes:
        lines.append(f"Weekly themes: {', '.join(context.themes)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Synthesizer (LLM integration)
# ---------------------------------------------------------------------------


class BlogSynthesisError(Exception):
    """Raised when blog LLM synthesis fails."""


class BlogSynthesizer:
    """Synthesizes blog posts via Claude CLI."""

    def __init__(self, config: BlogConfig) -> None:
        self._config = config

    def synthesize_weekly(self, context: WeeklyBlogContext, blog_memory: str = "") -> str:
        """Transform weekly context into blog prose.

        Args:
            context: Assembled weekly blog context.
            blog_memory: Optional rendered blog memory for cross-referencing.

        Returns:
            Raw prose string from Claude including Mermaid blocks.

        Raises:
            BlogSynthesisError: If the CLI call fails.
        """
        system_prompt = get_blog_prompt(
            BlogPostType.WEEKLY,
            self._config.target_word_count,
            blog_memory=blog_memory,
        )
        user_prompt = _render_weekly_prompt(context)
        raw = self._call_claude(system_prompt, user_prompt, f"weekly W{context.week}")
        return _strip_preamble(raw)

    def synthesize_thematic(self, context: ThematicBlogContext, blog_memory: str = "") -> str:
        """Transform thematic context into blog prose.

        Args:
            context: Assembled thematic blog context.
            blog_memory: Optional rendered blog memory for cross-referencing.

        Returns:
            Raw prose string from Claude including Mermaid blocks.

        Raises:
            BlogSynthesisError: If the CLI call fails.
        """
        system_prompt = get_blog_prompt(
            BlogPostType.THEMATIC,
            self._config.target_word_count,
            theme_title=context.theme.title,
            blog_memory=blog_memory,
            intake_context=context.intake_context,
            seed_angle=context.seed_angle,
        )
        user_prompt = _render_thematic_prompt(context)
        raw = self._call_claude(system_prompt, user_prompt, context.theme.slug)
        return _strip_preamble(raw)

    def synthesize_raw(self, system_prompt: str, user_prompt: str) -> str:
        """Synthesize content from raw system and user prompts."""
        return self._call_claude(system_prompt, user_prompt, "raw-synthesis")

    def adapt_for_platform(
        self,
        prose: str,
        platform: str,
        slug: str,
        editorial_hint: str = "",
        hashtags: str = "",
    ) -> str:
        """Adapt blog prose for a specific platform.

        Args:
            prose: Canonical blog post prose.
            platform: Target platform key (e.g., "twitter", "linkedin", "reddit").
            slug: Post slug for logging.
            editorial_hint: Optional editorial direction to prepend.
            hashtags: Space-separated hashtags for the closing line.

        Returns:
            Platform-adapted text.

        Raises:
            BlogSynthesisError: If the CLI call fails.
            KeyError: If platform is not a known social prompt key.
        """
        # Map Postiz provider names to prompt keys (e.g. "x" -> "twitter")
        prompt_key = {"x": "twitter"}.get(platform, platform)
        system_prompt = get_social_prompt(prompt_key, hashtags=hashtags)
        input_text = prose
        if editorial_hint:
            input_text = f"EDITORIAL DIRECTION: {editorial_hint}\n\n{prose}"
        return self._call_claude(system_prompt, input_text, f"adapt-{platform}-{slug}")

    def extract_blog_memory(
        self, prose: str, slug: str, title: str, post_type: str
    ) -> BlogPostSummary:
        """Extract structured memory from blog prose.

        Args:
            prose: Blog post prose to extract from.
            slug: Post slug.
            title: Post title.
            post_type: Post type ("weekly" or "thematic").

        Returns:
            BlogPostSummary with extracted key_points and themes_covered.
        """
        try:
            raw = self._call_claude(MEMORY_EXTRACTION_PROMPT, prose, f"memory-{slug}")
            data = json.loads(_strip_json_fences(raw))
            key_points = data.get("key_points", [])
            themes_covered = data.get("themes_covered", [])
            examples_used = data.get("examples_used", [])
        except (BlogSynthesisError, json.JSONDecodeError, ValueError):
            logger.warning("Failed to extract blog memory for %s", slug)
            key_points = []
            themes_covered = []
            examples_used = []

        return BlogPostSummary(
            slug=slug,
            title=title,
            post_type=post_type,
            date=date.today(),
            key_points=key_points,
            themes_covered=themes_covered,
            examples_used=examples_used,
            platforms_published=[],
        )

    def _call_claude(self, system_prompt: str, user_prompt: str, label: str) -> str:
        """Call Claude CLI with combined prompt."""
        from distill.llm import LLMError, call_claude

        try:
            return call_claude(
                system_prompt,
                user_prompt,
                model=self._config.model,
                timeout=self._config.claude_timeout,
                label=label,
            )
        except LLMError as exc:
            raise BlogSynthesisError(str(exc)) from exc


def _strip_preamble(text: str) -> str:
    """Strip LLM thinking/preamble before the first markdown heading.

    Claude sometimes outputs reasoning text before the actual blog post
    despite prompt instructions. This strips everything before the first
    line starting with '# ' (H1 heading).
    """
    match = re.search(r"^# ", text, re.MULTILINE)
    if match:
        stripped = text[match.start() :]
        if stripped != text:
            logger.info("Stripped %d chars of LLM preamble", match.start())
        return stripped
    return text


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences and preamble from LLM JSON output."""
    from distill.llm import strip_json_fences

    return strip_json_fences(text)


def _render_weekly_prompt(context: WeeklyBlogContext) -> str:
    """Render the user prompt for weekly synthesis."""
    lines: list[str] = []
    lines.append(f"# Week {context.year}-W{context.week:02d}")
    lines.append(f"({context.week_start.isoformat()} to {context.week_end.isoformat()})")
    lines.append(f"Total sessions: {context.total_sessions}")
    lines.append(f"Total duration: {context.total_duration_minutes:.0f} minutes")

    if context.projects:
        lines.append(f"Projects: {', '.join(context.projects)}")
    lines.append("")

    if context.working_memory:
        lines.append(context.working_memory)
        lines.append("")

    if context.project_context:
        lines.append(context.project_context)
        lines.append("")

    if context.editorial_notes:
        lines.append(context.editorial_notes)
        lines.append("")

    lines.append("# Daily Journal Entries")
    lines.append("")
    lines.append(context.combined_prose)

    return "\n".join(lines)


def _render_thematic_prompt(context: ThematicBlogContext) -> str:
    """Render the user prompt for thematic synthesis."""
    lines: list[str] = []
    lines.append(f"# Theme: {context.theme.title}")
    lines.append(f"Description: {context.theme.description}")
    lines.append(
        f"Evidence from {context.evidence_count} journal entries "
        f"({context.date_range[0].isoformat()} to {context.date_range[1].isoformat()})"
    )
    lines.append("")

    if context.relevant_threads:
        lines.append("## Relevant Ongoing Threads")
        for thread in context.relevant_threads:
            lines.append(f"- {thread.name} ({thread.status}): {thread.summary}")
        lines.append("")

    if context.project_context:
        lines.append(context.project_context)
        lines.append("")

    if context.editorial_notes:
        lines.append(context.editorial_notes)
        lines.append("")

    lines.append("# Evidence from Journal Entries")
    lines.append("")
    lines.append(context.combined_evidence)

    return "\n".join(lines)
