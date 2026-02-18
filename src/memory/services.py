"""Unified memory services — I/O and migration logic.

Handles loading, saving, and migrating unified memory from/to disk.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from distill.memory.models import (
    MEMORY_FILENAME,
    DailyEntry,
    MemoryThread,
    PublishedRecord,
    UnifiedMemory,
)

logger = logging.getLogger(__name__)


def load_unified_memory(output_dir: Path) -> UnifiedMemory:
    """Load unified memory from disk.

    On first run, migrates from existing memory files if found.
    """
    memory_path = output_dir / MEMORY_FILENAME
    if memory_path.exists():
        try:
            data = json.loads(memory_path.read_text(encoding="utf-8"))
            return UnifiedMemory.model_validate(data)
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Corrupt unified memory at %s, starting fresh", memory_path)

    # Attempt migration from existing memory files
    memory = UnifiedMemory()

    # Migrate from working memory (journal)
    journal_memory = output_dir / "journal" / ".working-memory.json"
    if journal_memory.exists():
        try:
            data = json.loads(journal_memory.read_text(encoding="utf-8"))
            for entry_data in data.get("entries", []):
                memory.add_entry(
                    DailyEntry(
                        date=date.fromisoformat(entry_data["date"]),
                        sessions=entry_data.get("key_insights", []),
                        themes=entry_data.get("themes", []),
                        insights=entry_data.get("key_insights", []),
                        decisions=entry_data.get("decisions_made", []),
                        open_questions=entry_data.get("open_questions", []),
                    )
                )
            for thread_data in data.get("threads", []):
                memory.threads.append(
                    MemoryThread(
                        name=thread_data["name"],
                        summary=thread_data.get("summary", ""),
                        first_seen=date.fromisoformat(thread_data["first_mentioned"]),
                        last_seen=date.fromisoformat(thread_data["last_mentioned"]),
                        status=thread_data.get("status", "active"),
                    )
                )
            logger.info("Migrated journal working memory")
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Could not migrate journal memory")

    # Migrate from intake memory
    intake_memory = output_dir / "intake" / ".intake-memory.json"
    if intake_memory.exists():
        try:
            data = json.loads(intake_memory.read_text(encoding="utf-8"))
            for entry_data in data.get("entries", []):
                entry_date = date.fromisoformat(entry_data["date"])
                # Find existing entry for this date or create new
                existing = next((e for e in memory.entries if e.date == entry_date), None)
                if existing:
                    existing.reads = entry_data.get("key_items", [])
                    existing.themes.extend(entry_data.get("themes", []))
                else:
                    memory.add_entry(
                        DailyEntry(
                            date=entry_date,
                            reads=entry_data.get("key_items", []),
                            themes=entry_data.get("themes", []),
                        )
                    )
            logger.info("Migrated intake memory")
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Could not migrate intake memory")

    # Migrate from blog memory
    blog_memory = output_dir / "blog" / ".blog-memory.json"
    if blog_memory.exists():
        try:
            data = json.loads(blog_memory.read_text(encoding="utf-8"))
            for post_data in data.get("posts", []):
                memory.add_published(
                    PublishedRecord(
                        slug=post_data["slug"],
                        title=post_data.get("title", ""),
                        post_type=post_data.get("post_type", ""),
                        date=date.fromisoformat(post_data["date"]),
                        platforms=post_data.get("platforms_published", []),
                    )
                )
            logger.info("Migrated blog memory")
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Could not migrate blog memory")

    return memory


def save_unified_memory(memory: UnifiedMemory, output_dir: Path) -> None:
    """Save unified memory to disk."""
    memory_path = output_dir / MEMORY_FILENAME
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
