"""Journal/blog post generation from session data.

Transforms daily session data into publishable narrative entries using
LLM-powered synthesis. Two-phase pipeline: deterministic context compression
(testable without LLM) followed by Claude CLI prose synthesis.
"""

from session_insights.journal.config import JournalConfig, JournalStyle
from session_insights.journal.context import DailyContext, prepare_daily_context
from session_insights.journal.memory import (
    DailyMemoryEntry,
    MemoryThread,
    WorkingMemory,
    load_memory,
    save_memory,
)

__all__ = [
    "DailyContext",
    "DailyMemoryEntry",
    "JournalConfig",
    "JournalStyle",
    "MemoryThread",
    "WorkingMemory",
    "load_memory",
    "prepare_daily_context",
    "save_memory",
]
