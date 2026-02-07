"""Intake working memory — cross-session context for synthesis."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MEMORY_FILENAME = ".intake-memory.json"


class IntakeThread(BaseModel):
    """A recurring topic across intake sessions."""

    name: str
    summary: str
    first_seen: date
    last_seen: date
    mention_count: int = 1
    status: str = "active"


class DailyIntakeEntry(BaseModel):
    """Extracted memory from a single day's intake."""

    date: date
    themes: list[str] = Field(default_factory=list)
    key_items: list[str] = Field(default_factory=list)
    emerging_interests: list[str] = Field(default_factory=list)
    item_count: int = 0


class IntakeMemory(BaseModel):
    """Rolling memory across intake sessions."""

    entries: list[DailyIntakeEntry] = Field(default_factory=list)
    threads: list[IntakeThread] = Field(default_factory=list)

    def render_for_prompt(self) -> str:
        """Render memory as text for LLM context injection."""
        if not self.entries and not self.threads:
            return ""

        lines: list[str] = ["# Recent Reading Context", ""]

        recent = sorted(self.entries, key=lambda e: e.date, reverse=True)[:7]
        for entry in recent:
            lines.append(f"## {entry.date.isoformat()} ({entry.item_count} items)")
            if entry.themes:
                lines.append(f"Themes: {', '.join(entry.themes)}")
            if entry.key_items:
                for item in entry.key_items[:5]:
                    lines.append(f"- {item}")
            lines.append("")

        active_threads = [t for t in self.threads if t.status == "active"]
        if active_threads:
            lines.append("## Ongoing Interests")
            for thread in active_threads:
                lines.append(
                    f"- **{thread.name}** ({thread.mention_count}x since "
                    f"{thread.first_seen.isoformat()}): {thread.summary}"
                )
            lines.append("")

        return "\n".join(lines)

    def add_entry(self, entry: DailyIntakeEntry) -> None:
        """Add a daily entry, replacing any existing entry for the same date."""
        self.entries = [e for e in self.entries if e.date != entry.date]
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.date)

    def prune(self, keep_days: int = 30) -> None:
        """Remove entries older than ``keep_days``."""
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=keep_days)
        self.entries = [e for e in self.entries if e.date >= cutoff]


def load_intake_memory(output_dir: Path) -> IntakeMemory:
    """Load intake memory from disk."""
    memory_path = output_dir / "intake" / MEMORY_FILENAME
    if not memory_path.exists():
        return IntakeMemory()
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
        return IntakeMemory.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt intake memory at %s, starting fresh", memory_path)
        return IntakeMemory()


def save_intake_memory(memory: IntakeMemory, output_dir: Path) -> None:
    """Save intake memory to disk."""
    memory_path = output_dir / "intake" / MEMORY_FILENAME
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
