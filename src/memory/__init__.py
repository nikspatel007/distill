"""Unified memory — tracks themes across sessions, reads, and posts.

Consolidates journal working memory, intake memory, and blog memory
into a single coherent memory system.
"""

from distill.memory.models import (
    MEMORY_FILENAME,
    DailyEntry,
    EntityRecord,
    MemoryThread,
    PublishedRecord,
    UnifiedMemory,
)
from distill.memory.services import (
    load_unified_memory,
    save_unified_memory,
)

__all__ = [
    "MEMORY_FILENAME",
    "DailyEntry",
    "EntityRecord",
    "MemoryThread",
    "PublishedRecord",
    "UnifiedMemory",
    "load_unified_memory",
    "save_unified_memory",
]
